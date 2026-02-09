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


def _parse_time(value: str | None, *, default_hour: int, default_minute: int) -> tuple[int, int]:
    raw = (value or "").strip()
    if not raw:
        return default_hour, default_minute
    parts = raw.split(":")
    if len(parts) != 2:
        return default_hour, default_minute
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return default_hour, default_minute
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return default_hour, default_minute
    return hour, minute


def _is_within_window(local_now: datetime, hour: int, minute: int, window_minutes: int) -> bool:
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta_seconds = abs((local_now - target).total_seconds())
    return delta_seconds <= window_minutes * 60


def _format_amount(amount) -> str:
    try:
        return f"{float(amount):.2f}"
    except (TypeError, ValueError):
        return str(amount) if amount is not None else "0.00"


def _build_message(row: dict, reminder_type: str) -> str:
    amount = _format_amount(row.get("amount"))
    currency = (row.get("currency") or "RUB").strip()
    description = (row.get("description") or "").strip()
    if reminder_type == "evening":
        lines = [
            "Напоминание: платеж за сегодня не оплачен.",
            f"Сумма: {amount} {currency}",
        ]
        if description:
            lines.append(f"Описание: {description}")
        lines.append("Пожалуйста, внесите оплату.")
        return "\n".join(lines)
    lines = [
        "Сегодня запланирован платеж.",
        f"Сумма: {amount} {currency}",
    ]
    if description:
        lines.append(f"Описание: {description}")
    lines.append("Пожалуйста, оплатите сегодня.")
    return "\n".join(lines)


def _send_telegram_message(chat_id: int, text: str) -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("Payment reminder skipped: TELEGRAM_BOT_TOKEN is missing")
        return False
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Failed to send payment reminder: %s %s", response.status_code, response.text)
            return False
    except Exception:
        logger.exception("Error while sending payment reminder")
        return False
    return True


def _register_notification(schema: str, payment_id: int, chat_id: int, reminder_type: str) -> int | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {schema}.crm_payment_notifications
                (payment_id, telegram_chat_id, reminder_type, sent_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (payment_id, telegram_chat_id, reminder_type) DO NOTHING
            RETURNING id
            """,
            [payment_id, chat_id, reminder_type],
        )
        res = cursor.fetchone()
        if not res:
            return None
        return res[0]


def _delete_notification(schema: str, notification_id: int) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {schema}.crm_payment_notifications WHERE id = %s",
            [notification_id],
        )


@shared_task
def send_payment_reminders() -> int:
    schema = _map_schema()
    window_minutes = int(os.getenv("PAYMENT_REMINDER_WINDOW_MINUTES", "2"))
    if window_minutes <= 0:
        return 0

    morning_hour, morning_minute = _parse_time(
        os.getenv("PAYMENT_REMINDER_MORNING_TIME"),
        default_hour=9,
        default_minute=0,
    )
    evening_hour, evening_minute = _parse_time(
        os.getenv("PAYMENT_REMINDER_EVENING_TIME"),
        default_hour=19,
        default_minute=5,
    )

    now_utc = timezone.now().astimezone(UTC_TZ)
    utc_date = now_utc.date()
    min_date = utc_date - timedelta(days=1)
    max_date = utc_date + timedelta(days=1)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                p.id AS payment_id,
                p.contact_id,
                p.amount,
                p.currency,
                p.status,
                p.description,
                p.planned_at,
                p.paid_at,
                b.telegram_chat_id,
                c.timezone AS client_timezone
            FROM {schema}.crm_payments p
            JOIN {schema}.user_tenant_binding b
              ON b.contact_id = p.contact_id
             AND b.is_active = true
            JOIN public.core_client c
              ON c.id = b.tenant_id
            WHERE p.planned_at IS NOT NULL
              AND (p.status IS NULL OR p.status != 'paid')
              AND p.paid_at IS NULL
              AND p.planned_at::date BETWEEN %s AND %s
            ORDER BY p.planned_at ASC
            """,
            [min_date, max_date],
        )
        rows = _fetch_all(cursor)

    total_sent = 0

    for row in rows:
        planned_at = row.get("planned_at")
        if not planned_at:
            continue

        tz = _resolve_timezone(row.get("client_timezone"))
        local_now = now_utc.astimezone(tz)

        planned_local = _to_tenant_local(planned_at, tz)

        if planned_local.date() != local_now.date():
            continue

        reminder_type = None
        if _is_within_window(local_now, morning_hour, morning_minute, window_minutes):
            reminder_type = "morning"
        elif _is_within_window(local_now, evening_hour, evening_minute, window_minutes):
            reminder_type = "evening"
        else:
            continue

        notification_id = _register_notification(
            schema,
            int(row["payment_id"]),
            int(row["telegram_chat_id"]),
            reminder_type,
        )
        if notification_id is None:
            continue

        text = _build_message(row, reminder_type)
        if _send_telegram_message(int(row["telegram_chat_id"]), text):
            total_sent += 1
            continue

        _delete_notification(schema, notification_id)

    logger.info(
        "Payment reminders: sent=%s window=%sm morning=%02d:%02d evening=%02d:%02d",
        total_sent,
        window_minutes,
        morning_hour,
        morning_minute,
        evening_hour,
        evening_minute,
    )

    return total_sent
