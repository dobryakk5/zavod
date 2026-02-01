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


def _to_utc(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


def _format_time_range(start: datetime, end: datetime, tz) -> str:
    start_local = _to_tenant_local(start, tz)
    end_local = _to_tenant_local(end, tz)
    if start_local.date() != end_local.date():
        return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%d.%m.%Y %H:%M')}"
    return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%H:%M')}"


def _format_reminder_label(reminder_minutes: int) -> str:
    if reminder_minutes == 60:
        return "1 час"
    if reminder_minutes == 1440:
        return "24 часа"
    if reminder_minutes % 60 == 0:
        return f"{reminder_minutes // 60} ч."
    return f"{reminder_minutes} мин."


def _build_reminder_text(row: dict, reminder_minutes: int) -> str:
    title = (row.get("title") or "Встреча").strip() or "Встреча"
    event_type = (row.get("event_type") or "").strip()
    location = (row.get("location") or "").strip()
    tz = _resolve_timezone(row.get("client_timezone"))
    time_range = _format_time_range(row["start_time"], row["end_time"], tz)
    reminder_label = _format_reminder_label(reminder_minutes)

    lines = [
        f"⏰ Напоминание: встреча через {reminder_label}.",
        f"📝 {title}",
        f"🗓 {time_range}",
    ]
    if event_type:
        lines.append(f"🏷 {event_type}")
    if location:
        lines.append(f"📍 {location}")
    return "\n".join(lines)


def _send_telegram_message(chat_id: int, text: str) -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("Meeting reminder skipped: TELEGRAM_BOT_TOKEN is missing")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Failed to send meeting reminder: %s %s", response.status_code, response.text)
            return False
    except Exception:
        logger.exception("Error while sending meeting reminder")
        return False
    return True


@shared_task
def send_meeting_reminders() -> int:
    schema = _map_schema()
    window_minutes = int(os.getenv("MEETING_REMINDER_WINDOW_MINUTES", "2"))
    reminder_minutes = int(os.getenv("MEETING_REMINDER_MINUTES", "60"))
    reminder_24h_minutes = int(os.getenv("MEETING_REMINDER_24H_MINUTES", "1440"))
    reminder_24h_min_lead_hours = int(os.getenv("MEETING_REMINDER_24H_MIN_LEAD_HOURS", "5"))

    reminder_configs = [
        {
            "minutes": reminder_minutes,
            "type": f"{reminder_minutes}m",
            "min_created_lead_hours": None,
        },
        {
            "minutes": reminder_24h_minutes,
            "type": f"{reminder_24h_minutes}m",
            "min_created_lead_hours": reminder_24h_min_lead_hours,
        },
    ]

    total_sent = 0

    for config in reminder_configs:
        minutes = int(config["minutes"])
        if minutes <= 0:
            continue

        reminder_type = config["type"]
        min_created_lead_hours = config.get("min_created_lead_hours")
        window_start_offset = minutes - window_minutes
        window_end_offset = minutes + window_minutes
        now_utc_naive = timezone.now().astimezone(UTC_TZ).replace(tzinfo=None)
        window_start = now_utc_naive + timedelta(minutes=window_start_offset)
        window_end = now_utc_naive + timedelta(minutes=window_end_offset)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    e.id AS event_id,
                    e.contact_id,
                    e.title,
                    e.start_time,
                    e.end_time,
                    e.location,
                    e.created_at,
                    et.name AS event_type,
                    b.telegram_chat_id,
                    c.timezone AS client_timezone
                FROM {schema}.crm_events e
                JOIN {schema}.user_tenant_binding b
                  ON b.contact_id = e.contact_id
                 AND b.is_active = true
                JOIN public.core_client c
                  ON c.id = b.tenant_id
                LEFT JOIN {schema}.crm_event_types et ON et.id = e.event_type_id
                WHERE e.status = 'scheduled'
                  AND e.start_time >= %s
                  AND e.start_time < %s
                ORDER BY e.start_time ASC
                """,
                [window_start, window_end],
            )
            rows = _fetch_all(cursor)

        sent = 0
        skipped = 0
        for row in rows:
            if min_created_lead_hours:
                created_at = row.get("created_at")
                start_time = row.get("start_time")
                if created_at and start_time:
                    created_utc = _to_utc(created_at)
                    start_utc = _to_utc(start_time)
                    reminder_time = start_utc - timedelta(minutes=minutes)
                    if created_utc > reminder_time - timedelta(hours=min_created_lead_hours):
                        skipped += 1
                        continue

            notification_id = None
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {schema}.crm_event_notifications
                        (event_id, telegram_chat_id, reminder_type, sent_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (event_id, telegram_chat_id, reminder_type) DO NOTHING
                    RETURNING id
                    """,
                    [row["event_id"], row["telegram_chat_id"], reminder_type],
                )
                res = cursor.fetchone()
                if not res:
                    skipped += 1
                    continue
                notification_id = res[0]

            text = _build_reminder_text(row, minutes)
            if _send_telegram_message(row["telegram_chat_id"], text):
                sent += 1
                continue

            if notification_id is not None:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {schema}.crm_event_notifications WHERE id = %s",
                        [notification_id],
                    )

        total_sent += sent
        logger.info(
            "Meeting reminders (%s): sent=%s skipped=%s window=%s..%s",
            reminder_type,
            sent,
            skipped,
            window_start,
            window_end,
        )

    return total_sent
