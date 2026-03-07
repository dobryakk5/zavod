import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from celery import shared_task
from django.conf import settings
from django.db import connection
from django.utils import timezone


logger = logging.getLogger(__name__)
UTC_TZ = ZoneInfo("UTC")


def _map_schema() -> str:
    schema = os.getenv("MAP_SCHEMA", "map").strip()
    if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        return "map"
    return schema


def _fetch_all(cursor) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _resolve_timezone(name: str | None):
    tz_name = (name or "").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def _to_tenant_local(dt: datetime, tz) -> datetime:
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(tz)


def _format_reminder_label(reminder_minutes: int) -> str:
    if reminder_minutes == 60:
        return "1 час"
    if reminder_minutes == 1440:
        return "24 часа"
    if reminder_minutes % 60 == 0:
        return f"{reminder_minutes // 60} ч."
    return f"{reminder_minutes} мин."


def _build_reminder_text(row: dict, reminder_minutes: int) -> str:
    title = (row.get("title") or "Задание").strip() or "Задание"
    description = (row.get("description") or "").strip()
    due_at = row.get("due_at")
    reminder_label = _format_reminder_label(reminder_minutes)

    lines = [
        f"⏰ Напоминание: дедлайн задания через {reminder_label}.",
        f"📌 {title}",
    ]

    if due_at:
        tz = _resolve_timezone(row.get("client_timezone"))
        due_local = _to_tenant_local(due_at, tz)
        lines.append(f"🗓 Дедлайн: {due_local.strftime('%d.%m.%Y %H:%M')}")

    if description:
        lines.append(f"📝 {description}")

    return "\n".join(lines)


def _send_telegram_message(chat_id: int, text: str) -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("Task deadline reminder skipped: TELEGRAM_BOT_TOKEN is missing")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Failed to send task deadline reminder: %s %s", response.status_code, response.text)
            return False
    except Exception:
        logger.exception("Error while sending task deadline reminder")
        return False
    return True


@shared_task
def send_task_deadline_reminders() -> int:
    schema = _map_schema()
    window_minutes = int(os.getenv("TASK_REMINDER_WINDOW_MINUTES", "2"))
    reminder_1h_minutes = int(os.getenv("TASK_REMINDER_1H_MINUTES", "60"))
    reminder_24h_minutes = int(os.getenv("TASK_REMINDER_24H_MINUTES", "1440"))

    logger.info(
        "Beat tick send_task_deadline_reminders: schema=%s window=%sm reminder_1h=%sm reminder_24h=%sm",
        schema,
        window_minutes,
        reminder_1h_minutes,
        reminder_24h_minutes,
    )

    reminder_configs = [
        {"minutes": reminder_24h_minutes, "type": f"{reminder_24h_minutes}m"},
        {"minutes": reminder_1h_minutes, "type": f"{reminder_1h_minutes}m"},
    ]

    now_utc = timezone.now().astimezone(UTC_TZ)
    total_sent = 0

    for config in reminder_configs:
        minutes = int(config["minutes"])
        if minutes <= 0:
            continue

        reminder_type = config["type"]
        window_start = now_utc + timedelta(minutes=minutes - window_minutes)
        window_end = now_utc + timedelta(minutes=minutes + window_minutes)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    t.id AS task_id,
                    t.contact_id,
                    t.title,
                    t.description,
                    t.status,
                    t.due_at,
                    b.telegram_chat_id,
                    c.timezone AS client_timezone
                FROM {schema}.crm_tasks t
                JOIN {schema}.user_tenant_binding b
                  ON b.contact_id = t.contact_id
                 AND b.is_active = true
                 AND b.provider = 'telegram'
                 AND b.telegram_chat_id IS NOT NULL
                JOIN public.core_client c
                  ON c.id = b.tenant_id
                WHERE t.contact_id IS NOT NULL
                  AND t.due_at IS NOT NULL
                  AND t.status NOT IN ('done', 'checked')
                  AND t.due_at >= %s
                  AND t.due_at < %s
                ORDER BY t.due_at ASC
                """,
                [window_start, window_end],
            )
            rows = _fetch_all(cursor)

        sent = 0
        skipped = 0

        for row in rows:
            notification_id = None
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {schema}.crm_task_notifications
                        (task_id, telegram_chat_id, reminder_type, due_at, sent_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (task_id, telegram_chat_id, reminder_type, due_at) DO NOTHING
                    RETURNING id
                    """,
                    [row["task_id"], row["telegram_chat_id"], reminder_type, row["due_at"]],
                )
                res = cursor.fetchone()
                if not res:
                    skipped += 1
                    continue
                notification_id = res[0]

            text = _build_reminder_text(row, minutes)
            if _send_telegram_message(int(row["telegram_chat_id"]), text):
                sent += 1
                continue

            if notification_id is not None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {schema}.crm_task_notifications WHERE id = %s",
                        [notification_id],
                    )

        total_sent += sent
        logger.info(
            "Task deadline reminders (%s): sent=%s skipped=%s window=%s..%s",
            reminder_type,
            sent,
            skipped,
            window_start,
            window_end,
        )

    logger.info("Beat tick send_task_deadline_reminders done: total_sent=%s", total_sent)
    return total_sent

