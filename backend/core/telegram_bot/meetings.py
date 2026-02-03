"""
Модуль для работы со встречами и календарём в Telegram боте
"""
import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from asgiref.sync import sync_to_async
from django.db import connection
from django.utils import timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.telegram_bot.dependencies import get_telegram_user_service


# Router для встреч
meetings_router = Router()

# Константы
SCHEDULE_LOOKAHEAD_DAYS = 60
CALLBACK_IGNORE = "ignore"
CALLBACK_MEETING_RESCHEDULE = "meeting_reschedule"
CALLBACK_MEETING_NEW = "meeting_new"
CALLBACK_CALENDAR_SELECT = "cal_select"
CALLBACK_CALENDAR_PREV = "cal_prev"
CALLBACK_CALENDAR_NEXT = "cal_next"
CALLBACK_TIME_SELECT = "time_select"
CALLBACK_CONFIRM = "meeting_confirm"
CALLBACK_CANCEL = "meeting_cancel"
CALLBACK_BACK_DATES = "meeting_back_dates"
CALLBACK_BACK_TIMES = "meeting_back_times"

MONTH_NAMES_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAY_SHORT_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
UTC_TZ = ZoneInfo("UTC")


# States
class MeetingFlowStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()


# Helper functions
def _map_schema() -> str:
    import os
    import re
    schema = os.getenv("MAP_SCHEMA", "map").strip()
    if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        return "map"
    return schema


def _fetch_all(cursor) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _resolve_timezone(name: str | None):
    from zoneinfo import ZoneInfoNotFoundError
    tz_name = (name or "").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Moscow")


def _to_tenant_local(dt: datetime, tenant_tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(tenant_tz)


def _to_utc(dt: datetime, tenant_tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tenant_tz)
    return dt.astimezone(UTC_TZ)


def _to_utc_naive(dt: datetime, tenant_tz: ZoneInfo | None = None) -> datetime:
    if dt.tzinfo is None:
        if tenant_tz is None:
            dt = dt.replace(tzinfo=UTC_TZ)
        else:
            dt = dt.replace(tzinfo=tenant_tz)
    dt = dt.astimezone(UTC_TZ)
    return dt.replace(tzinfo=None)


def _format_dt(dt: datetime, tenant_tz: ZoneInfo) -> str:
    local_dt = _to_tenant_local(dt, tenant_tz)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def _format_time_range(start: datetime, end: datetime, tenant_tz: ZoneInfo) -> str:
    start_local = _to_tenant_local(start, tenant_tz)
    end_local = _to_tenant_local(end, tenant_tz)
    if start_local.date() != end_local.date():
        return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%d.%m.%Y %H:%M')}"
    return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%H:%M')}"


def _meeting_actions_keyboard(event_id: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if event_id is not None:
        builder.button(
            text="Перенести",
            callback_data=f"{CALLBACK_MEETING_RESCHEDULE}:{event_id}",
        )
    builder.button(text="Добавить новую", callback_data=CALLBACK_MEETING_NEW)
    builder.adjust(1)
    return builder.as_markup()


def _calendar_nav_month(year: int, month: int, delta: int) -> tuple[int, int]:
    next_month = month + delta
    next_year = year
    while next_month < 1:
        next_month += 12
        next_year -= 1
    while next_month > 12:
        next_month -= 12
        next_year += 1
    return next_year, next_month


def _build_availability_calendar(
    available_dates: set[date],
    marked_dates: set[date],
    *,
    year: int,
    month: int,
    min_date: date | None = None,
    max_date: date | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    header = f"{MONTH_NAMES_RU[month - 1]} {year}"
    builder.row(InlineKeyboardButton(text=header, callback_data=CALLBACK_IGNORE))
    builder.row(
        *[
            InlineKeyboardButton(text=weekday, callback_data=CALLBACK_IGNORE)
            for weekday in WEEKDAY_SHORT_RU
        ]
    )

    first_weekday, month_days = calendar.monthrange(year, month)
    leading_empty = first_weekday
    row: list[InlineKeyboardButton] = []
    for _ in range(leading_empty):
        row.append(InlineKeyboardButton(text=" ", callback_data=CALLBACK_IGNORE))

    for day in range(1, month_days + 1):
        current_date = date(year, month, day)
        is_available = current_date in available_dates
        indicators = ""
        if current_date in marked_dates:
            indicators += "✅"
        if is_available:
            indicators += "🟩"
        label = f"{day}{indicators}" if indicators else str(day)
        callback = (
            f"{CALLBACK_CALENDAR_SELECT}:{current_date.isoformat()}"
            if is_available
            else CALLBACK_IGNORE
        )
        row.append(InlineKeyboardButton(text=label, callback_data=callback))
        if len(row) == 7:
            builder.row(*row)
            row = []

    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(text=" ", callback_data=CALLBACK_IGNORE))
        builder.row(*row)

    prev_year, prev_month = _calendar_nav_month(year, month, -1)
    next_year, next_month = _calendar_nav_month(year, month, 1)

    prev_allowed = True
    if min_date:
        prev_allowed = date(prev_year, prev_month, 1) >= date(min_date.year, min_date.month, 1)
    next_allowed = True
    if max_date:
        next_allowed = date(next_year, next_month, 1) <= date(max_date.year, max_date.month, 1)

    prev_button = InlineKeyboardButton(
        text="‹ Назад" if prev_allowed else " ",
        callback_data=f"{CALLBACK_CALENDAR_PREV}:{prev_year}:{prev_month}"
        if prev_allowed
        else CALLBACK_IGNORE,
    )
    next_button = InlineKeyboardButton(
        text="Вперёд ›" if next_allowed else " ",
        callback_data=f"{CALLBACK_CALENDAR_NEXT}:{next_year}:{next_month}"
        if next_allowed
        else CALLBACK_IGNORE,
    )
    builder.row(prev_button, InlineKeyboardButton(text=" ", callback_data=CALLBACK_IGNORE), next_button)
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CALLBACK_CANCEL))
    return builder.as_markup()


def _build_time_slots_keyboard(slots: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(
            text=slot["time"],
            callback_data=f"{CALLBACK_TIME_SELECT}:{slot['time']}",
        )
    if slots:
        builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=CALLBACK_BACK_DATES))
    builder.row(InlineKeyboardButton(text="❌ Отменить", callback_data=CALLBACK_CANCEL))
    return builder.as_markup()


def _build_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=CALLBACK_CONFIRM)
    builder.button(text="◀️ Назад", callback_data=CALLBACK_BACK_TIMES)
    builder.button(text="❌ Отменить", callback_data=CALLBACK_CANCEL)
    builder.adjust(1)
    return builder.as_markup()


def _binding_meeting_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да", callback_data=CALLBACK_MEETING_NEW)
    builder.adjust(1)
    return builder.as_markup()


# Database functions
def _get_tenant_contact_ids(tenant_id: int, fallback_contact_id: int | None) -> list[int]:
    schema = _map_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT DISTINCT contact_id
            FROM {schema}.user_tenant_binding
            WHERE tenant_id = %s AND contact_id IS NOT NULL
            """,
            [tenant_id],
        )
        ids = [row[0] for row in cursor.fetchall()]
    if fallback_contact_id is not None and fallback_contact_id not in ids:
        ids.append(fallback_contact_id)
    return ids


def _get_availability_events(tenant_id: int) -> list[dict]:
    schema = _map_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                start_time,
                duration_minutes,
                repeat_type
            FROM {schema}.events
            WHERE tenant_id = %s
            ORDER BY start_time ASC
            """,
            [tenant_id],
        )
        return _fetch_all(cursor)


def _get_busy_events(contact_ids: list[int], exclude_event_id: int | None) -> list[dict]:
    if not contact_ids:
        return []
    schema = _map_schema()
    now_utc_naive = timezone.now().astimezone(UTC_TZ).replace(tzinfo=None)
    params: list = [contact_ids, now_utc_naive]
    exclude_sql = ""
    if exclude_event_id is not None:
        exclude_sql = "AND id <> %s"
        params.append(exclude_event_id)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, start_time, end_time
            FROM {schema}.crm_events
            WHERE contact_id = ANY(%s)
              AND status = 'scheduled'
              AND end_time >= %s
              {exclude_sql}
            ORDER BY start_time ASC
            """,
            params,
        )
        return _fetch_all(cursor)


def _get_contact_busy_dates(
    contact_id: int,
    tenant_tz: ZoneInfo,
    exclude_event_id: int | None = None,
) -> set[date]:
    schema = _map_schema()
    now_utc_naive = timezone.now().astimezone(UTC_TZ).replace(tzinfo=None)
    params: list = [contact_id, now_utc_naive]
    exclude_sql = ""
    if exclude_event_id is not None:
        exclude_sql = "AND id <> %s"
        params.append(exclude_event_id)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT start_time, end_time
            FROM {schema}.crm_events
            WHERE contact_id = %s
              AND status = 'scheduled'
              AND end_time >= %s
              {exclude_sql}
            ORDER BY start_time ASC
            """,
            params,
        )
        rows = _fetch_all(cursor)

    dates: set[date] = set()
    for row in rows:
        start_dt = _to_tenant_local(row["start_time"], tenant_tz)
        end_dt = _to_tenant_local(row["end_time"], tenant_tz)
        current = start_dt.date()
        end_date = end_dt.date()
        while current <= end_date:
            dates.add(current)
            current += timedelta(days=1)
    return dates


def _availability_matches_date(item: dict, check_date: date, tenant_tz: ZoneInfo) -> bool:
    base_start = _to_tenant_local(item["start_time"], tenant_tz)
    base_date = base_start.date()
    if check_date < base_date:
        return False
    repeat_type = int(item.get("repeat_type") or 0)
    if repeat_type == 1:
        return True
    if repeat_type == 2:
        return check_date.weekday() == base_date.weekday()
    if repeat_type == 3:
        return check_date.day == base_date.day
    return check_date == base_date


def _build_slots_for_date(
    check_date: date,
    availability_events: list[dict],
    busy_events: list[dict],
    *,
    tenant_tz: ZoneInfo,
    required_duration_minutes: int | None = None,
) -> list[dict]:
    now_local = timezone.now().astimezone(UTC_TZ).astimezone(tenant_tz)
    slots: list[dict] = []
    for item in availability_events:
        if not _availability_matches_date(item, check_date, tenant_tz):
            continue
        duration_minutes = int(item.get("duration_minutes") or 0)
        if required_duration_minutes is not None and duration_minutes < required_duration_minutes:
            continue
        slot_duration = required_duration_minutes or duration_minutes or 60

        base_start = _to_tenant_local(item["start_time"], tenant_tz)
        start_dt = datetime.combine(check_date, base_start.timetz())
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tenant_tz)
        else:
            start_dt = start_dt.astimezone(tenant_tz)
        end_dt = start_dt + timedelta(minutes=slot_duration)

        if end_dt <= now_local:
            continue

        overlaps = False
        for busy in busy_events:
            busy_start = _to_tenant_local(busy["start_time"], tenant_tz)
            busy_end = _to_tenant_local(busy["end_time"], tenant_tz)
            if start_dt < busy_end and end_dt > busy_start:
                overlaps = True
                break
        if overlaps:
            continue

        slots.append(
            {
                "start_dt": start_dt,
                "end_dt": end_dt,
                "time": start_dt.strftime("%H:%M"),
                "duration": slot_duration,
            }
        )

    slots.sort(key=lambda s: s["start_dt"])
    return slots


def _get_available_dates(
    tenant_id: int,
    contact_id: int,
    *,
    tz_name: str | None,
    required_duration_minutes: int | None = None,
    exclude_event_id: int | None = None,
) -> list[date]:
    availability_events = _get_availability_events(tenant_id)
    if not availability_events:
        return []
    contact_ids = _get_tenant_contact_ids(tenant_id, contact_id)
    busy_events = _get_busy_events(contact_ids, exclude_event_id)

    tenant_tz = _resolve_timezone(tz_name)
    today = timezone.now().astimezone(UTC_TZ).astimezone(tenant_tz).date()
    available_dates: list[date] = []
    for offset in range(SCHEDULE_LOOKAHEAD_DAYS + 1):
        check_date = today + timedelta(days=offset)
        slots = _build_slots_for_date(
            check_date,
            availability_events,
            busy_events,
            tenant_tz=tenant_tz,
            required_duration_minutes=required_duration_minutes,
        )
        if slots:
            available_dates.append(check_date)
    return available_dates


def _get_slots_for_date(
    tenant_id: int,
    contact_id: int,
    check_date: date,
    *,
    tz_name: str | None,
    required_duration_minutes: int | None = None,
    exclude_event_id: int | None = None,
) -> list[dict]:
    availability_events = _get_availability_events(tenant_id)
    if not availability_events:
        return []
    contact_ids = _get_tenant_contact_ids(tenant_id, contact_id)
    busy_events = _get_busy_events(contact_ids, exclude_event_id)
    tenant_tz = _resolve_timezone(tz_name)
    return _build_slots_for_date(
        check_date,
        availability_events,
        busy_events,
        tenant_tz=tenant_tz,
        required_duration_minutes=required_duration_minutes,
    )


def _fetch_event_by_id(event_id: int, contact_id: int) -> dict | None:
    schema = _map_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                e.id,
                e.title,
                e.start_time,
                e.end_time,
                e.location,
                e.status,
                et.name AS event_type
            FROM {schema}.crm_events e
            LEFT JOIN {schema}.crm_event_types et ON et.id = e.event_type_id
            WHERE e.id = %s AND e.contact_id = %s AND e.status = 'scheduled'
            """,
            [event_id, contact_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))


def _update_event_time(event_id: int, contact_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    schema = _map_schema()
    start_local = _to_utc_naive(start_dt)
    end_local = _to_utc_naive(end_dt)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {schema}.crm_events
            SET start_time = %s, end_time = %s, updated_at = NOW()
            WHERE id = %s AND contact_id = %s
            """,
            [start_local, end_local, event_id, contact_id],
        )
        return cursor.rowcount > 0


def _create_event(
    *,
    contact_id: int,
    title: str,
    start_dt: datetime,
    end_dt: datetime,
    event_type_id: int | None,
) -> int | None:
    schema = _map_schema()
    start_local = _to_utc_naive(start_dt)
    end_local = _to_utc_naive(end_dt)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {schema}.crm_events
            (contact_id, event_type_id, title, description, start_time, end_time, location, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'scheduled', %s)
            RETURNING id
            """,
            [
                contact_id,
                event_type_id,
                title,
                "",
                start_local,
                end_local,
                "",
                "",
            ],
        )
        row = cursor.fetchone()
        if not row:
            return None
        return int(row[0])


async def _safe_edit_message(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception as exc:
        if "message is not modified" in str(exc).lower():
            return
        await message.answer(text, reply_markup=reply_markup)


def _get_scheduled_meetings(telegram_id: int, limit: int = 10) -> dict:
    telegram_user_service = get_telegram_user_service()
    binding = telegram_user_service.get_active_binding(telegram_id)
    if binding is None:
        return {"error": "no_binding"}
    if not binding.contact_id:
        return {"error": "no_contact"}
    client_timezone = (getattr(binding.tenant, "timezone", "") or "").strip()

    schema = _map_schema()
    now = timezone.now().astimezone(UTC_TZ).replace(tzinfo=None)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                e.id,
                e.contact_id,
                e.title,
                e.start_time,
                e.end_time,
                e.location,
                et.name AS event_type
            FROM {schema}.crm_events e
            LEFT JOIN {schema}.crm_event_types et ON et.id = e.event_type_id
            WHERE e.contact_id = %s
              AND e.status = 'scheduled'
              AND e.end_time >= %s
            ORDER BY e.start_time ASC
            LIMIT %s
            """,
            [binding.contact_id, now, limit],
        )
        events = _fetch_all(cursor)

    return {"events": events, "timezone": client_timezone}


def _format_meetings(events: list[dict], tz_name: str | None = None) -> str:
    if not events:
        return "Запланированных встреч нет."

    header = "Ближайшая встреча:" if len(events) == 1 else "Запланированные встречи:"
    lines = [header, ""]
    tz = _resolve_timezone(tz_name)
    for idx, event in enumerate(events, 1):
        start_local = _to_tenant_local(event["start_time"], tz)
        end_local = _to_tenant_local(event["end_time"], tz)
        date_str = start_local.strftime("%d.%m.%Y")
        time_str = start_local.strftime("%H:%M")
        end_str = end_local.strftime("%H:%M")

        title = (event.get("title") or "Встреча").strip() or "Встреча"
        event_type = (event.get("event_type") or "").strip()
        location = (event.get("location") or "").strip()

        parts = [f"{idx}) {date_str} {time_str}-{end_str}", title]
        if event_type:
            parts.append(event_type)
        if location:
            parts.append(location)
        lines.append(" | ".join(parts))

    return "\n".join(lines)


def _date_prompt_text(data: dict) -> str:
    flow = data.get("flow")
    if flow == "reschedule":
        title = (data.get("event_title") or "Встреча").strip() or "Встреча"
        old_start_raw = data.get("old_start")
        old_start = (
            datetime.fromisoformat(old_start_raw)
            if old_start_raw
            else None
        )
        tenant_tz = _resolve_timezone(data.get("timezone"))
        old_start_str = _format_dt(old_start, tenant_tz) if old_start else ""
        return (
            "На какую дату перенести?\n\n"
            f"📝 {title}\n"
            f"Было: {old_start_str}"
        )
    return "На какую дату планируем?"


def _confirmation_text(data: dict, new_start: datetime) -> str:
    flow = data.get("flow")
    title = (data.get("event_title") or "Встреча").strip() or "Встреча"
    tenant_tz = _resolve_timezone(data.get("timezone"))
    if flow == "reschedule":
        old_start_raw = data.get("old_start")
        old_start = (
            datetime.fromisoformat(old_start_raw)
            if old_start_raw
            else None
        )
        old_start_str = _format_dt(old_start, tenant_tz) if old_start else ""
        return (
            "Подтвердите перенос:\n\n"
            f"📝 {title}\n\n"
            f"Было: {old_start_str}\n"
            f"Стало: {_format_dt(new_start, tenant_tz)}"
        )
    return (
        "Подтвердите запись:\n\n"
        f"📝 {title}\n"
        f"Дата и время: {_format_dt(new_start, tenant_tz)}"
    )


# Public API
async def send_meetings(message: Message) -> None:
    """Отправить список запланированных встреч"""
    from_user = message.from_user
    if from_user is None:
        return

    result = await sync_to_async(_get_scheduled_meetings, thread_sensitive=True)(
        from_user.id,
        1,
    )
    if result.get("error") == "no_binding":
        from .ui import main_menu
        await message.answer(
            "❗️Ваш аккаунт ещё не привязан к клиенту.\n"
            "Пожалуйста, используйте персональную ссылку от администратора.",
            reply_markup=main_menu(),
        )
        return
    if result.get("error") == "no_contact":
        from .ui import main_menu
        await message.answer(
            "❗️Ваш аккаунт привязан к клиенту, но контакт не указан.\n"
            "Попросите администратора отправить новую ссылку.",
            reply_markup=main_menu(),
        )
        return

    events = result.get("events") or []
    tz_name = result.get("timezone")
    reply = _format_meetings(events, tz_name)
    event_id = events[0]["id"] if events else None
    await message.answer(reply, reply_markup=_meeting_actions_keyboard(event_id))


def get_binding_meeting_keyboard() -> InlineKeyboardMarkup:
    """Получить клавиатуру для предложения запланировать встречу при привязке"""
    return _binding_meeting_keyboard()


# Handlers
@meetings_router.callback_query(F.data.startswith(f"{CALLBACK_MEETING_RESCHEDULE}:"))
async def handle_reschedule_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        return

    telegram_user_service = get_telegram_user_service()
    binding = await sync_to_async(telegram_user_service.get_active_binding, thread_sensitive=True)(
        callback.from_user.id
    )
    if binding is None:
        await callback.answer("Аккаунт не привязан к клиенту.", show_alert=True)
        return
    if not binding.contact_id:
        await callback.answer("Контакт не найден. Попросите администратора обновить ссылку.", show_alert=True)
        return

    try:
        event_id = int(callback.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Некорректная встреча.", show_alert=True)
        return

    event = await sync_to_async(_fetch_event_by_id, thread_sensitive=True)(
        event_id,
        binding.contact_id,
    )
    if not event:
        await callback.answer("Встреча не найдена.", show_alert=True)
        return

    duration_minutes = 60
    try:
        start_dt = _to_utc(event["start_time"], UTC_TZ)
        end_dt = _to_utc(event["end_time"], UTC_TZ)
        duration_minutes = max(15, int((end_dt - start_dt).total_seconds() // 60) or 60)
    except Exception:
        duration_minutes = 60

    tenant_tz_name = (getattr(binding.tenant, "timezone", "") or "").strip()
    available_dates = await sync_to_async(_get_available_dates, thread_sensitive=True)(
        binding.tenant_id,
        binding.contact_id,
        tz_name=tenant_tz_name,
        required_duration_minutes=duration_minutes,
        exclude_event_id=event_id,
    )
    if not available_dates:
        await _safe_edit_message(
            callback.message,
            "❌ К сожалению, нет доступных дат для переноса.\n"
            "Свяжитесь с администратором.",
            reply_markup=None,
        )
        await state.clear()
        await callback.answer()
        return

    marked_dates = await sync_to_async(_get_contact_busy_dates, thread_sensitive=True)(
        binding.contact_id,
        _resolve_timezone(tenant_tz_name),
        None,
    )
    available_dates_sorted = sorted(available_dates)
    initial_date = available_dates_sorted[0]
    await state.clear()
    await state.update_data(
        flow="reschedule",
        tenant_id=binding.tenant_id,
        contact_id=binding.contact_id,
        event_id=event_id,
        event_title=event.get("title") or "Встреча",
        old_start=_to_utc(event["start_time"], UTC_TZ).isoformat(),
        old_end=_to_utc(event["end_time"], UTC_TZ).isoformat(),
        required_duration=duration_minutes,
        available_dates=[d.isoformat() for d in available_dates_sorted],
        marked_dates=[d.isoformat() for d in sorted(marked_dates)],
        calendar_year=initial_date.year,
        calendar_month=initial_date.month,
        timezone=tenant_tz_name,
    )
    await state.set_state(MeetingFlowStates.waiting_for_date)

    calendar_markup = _build_availability_calendar(
        set(available_dates_sorted),
        marked_dates,
        year=initial_date.year,
        month=initial_date.month,
        min_date=available_dates_sorted[0],
        max_date=available_dates_sorted[-1],
    )
    await _safe_edit_message(
        callback.message,
        _date_prompt_text(await state.get_data()),
        reply_markup=calendar_markup,
    )
    await callback.answer()


@meetings_router.callback_query(F.data == CALLBACK_MEETING_NEW)
async def handle_new_meeting_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        return

    telegram_user_service = get_telegram_user_service()
    binding = await sync_to_async(telegram_user_service.get_active_binding, thread_sensitive=True)(
        callback.from_user.id
    )
    if binding is None:
        await callback.answer("Аккаунт не привязан к клиенту.", show_alert=True)
        return
    if not binding.contact_id:
        await callback.answer("Контакт не найден. Попросите администратора обновить ссылку.", show_alert=True)
        return

    tenant_tz_name = (getattr(binding.tenant, "timezone", "") or "").strip()
    available_dates = await sync_to_async(_get_available_dates, thread_sensitive=True)(
        binding.tenant_id,
        binding.contact_id,
        tz_name=tenant_tz_name,
    )
    if not available_dates:
        await _safe_edit_message(
            callback.message,
            "❌ К сожалению, нет доступных дат для записи.\n"
            "Свяжитесь с администратором.",
            reply_markup=None,
        )
        await state.clear()
        await callback.answer()
        return

    marked_dates = await sync_to_async(_get_contact_busy_dates, thread_sensitive=True)(
        binding.contact_id,
        _resolve_timezone(tenant_tz_name),
        None,
    )
    available_dates_sorted = sorted(available_dates)
    initial_date = available_dates_sorted[0]
    await state.clear()
    await state.update_data(
        flow="new",
        tenant_id=binding.tenant_id,
        contact_id=binding.contact_id,
        event_title="Новая",
        available_dates=[d.isoformat() for d in available_dates_sorted],
        marked_dates=[d.isoformat() for d in sorted(marked_dates)],
        calendar_year=initial_date.year,
        calendar_month=initial_date.month,
        timezone=tenant_tz_name,
    )
    await state.set_state(MeetingFlowStates.waiting_for_date)

    calendar_markup = _build_availability_calendar(
        set(available_dates_sorted),
        marked_dates,
        year=initial_date.year,
        month=initial_date.month,
        min_date=available_dates_sorted[0],
        max_date=available_dates_sorted[-1],
    )
    await _safe_edit_message(
        callback.message,
        _date_prompt_text(await state.get_data()),
        reply_markup=calendar_markup,
    )
    await callback.answer()


@meetings_router.callback_query(
    F.data.startswith(f"{CALLBACK_CALENDAR_PREV}:"),
    MeetingFlowStates.waiting_for_date,
)
async def handle_calendar_prev(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
    try:
        year = int(parts[1])
        month = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    data = await state.get_data()
    available_dates = [date.fromisoformat(d) for d in data.get("available_dates", [])]
    marked_dates = {date.fromisoformat(d) for d in data.get("marked_dates", [])}
    if not available_dates:
        await callback.answer()
        return
    await state.update_data(calendar_year=year, calendar_month=month)

    calendar_markup = _build_availability_calendar(
        set(available_dates),
        marked_dates,
        year=year,
        month=month,
        min_date=min(available_dates),
        max_date=max(available_dates),
    )
    await _safe_edit_message(callback.message, _date_prompt_text(data), reply_markup=calendar_markup)
    await callback.answer()


@meetings_router.callback_query(
    F.data.startswith(f"{CALLBACK_CALENDAR_NEXT}:"),
    MeetingFlowStates.waiting_for_date,
)
async def handle_calendar_next(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return
    try:
        year = int(parts[1])
        month = int(parts[2])
    except ValueError:
        await callback.answer()
        return

    data = await state.get_data()
    available_dates = [date.fromisoformat(d) for d in data.get("available_dates", [])]
    marked_dates = {date.fromisoformat(d) for d in data.get("marked_dates", [])}
    if not available_dates:
        await callback.answer()
        return
    await state.update_data(calendar_year=year, calendar_month=month)

    calendar_markup = _build_availability_calendar(
        set(available_dates),
        marked_dates,
        year=year,
        month=month,
        min_date=min(available_dates),
        max_date=max(available_dates),
    )
    await _safe_edit_message(callback.message, _date_prompt_text(data), reply_markup=calendar_markup)
    await callback.answer()


@meetings_router.callback_query(
    F.data.startswith(f"{CALLBACK_CALENDAR_SELECT}:"),
    MeetingFlowStates.waiting_for_date,
)
async def handle_calendar_select(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    date_str = callback.data.split(":", 1)[1]
    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        await callback.answer("Некорректная дата.", show_alert=True)
        return

    data = await state.get_data()
    available_dates = {date.fromisoformat(d) for d in data.get("available_dates", [])}
    if selected_date not in available_dates:
        await callback.answer("Эта дата недоступна.", show_alert=True)
        return

    tenant_id = data.get("tenant_id")
    contact_id = data.get("contact_id")
    tz_name = data.get("timezone")
    if not tenant_id or not contact_id:
        await callback.answer("Не удалось определить клиента.", show_alert=True)
        return

    required_duration = data.get("required_duration")
    event_id = data.get("event_id")

    slots = await sync_to_async(_get_slots_for_date, thread_sensitive=True)(
        tenant_id,
        contact_id,
        selected_date,
        tz_name=tz_name,
        required_duration_minutes=required_duration,
        exclude_event_id=event_id,
    )
    if not slots:
        await callback.answer("На эту дату нет свободных слотов.", show_alert=True)
        return

    await state.update_data(
        selected_date=selected_date.isoformat(),
        available_slots=[{"time": slot["time"], "duration": slot["duration"]} for slot in slots],
    )
    await state.set_state(MeetingFlowStates.waiting_for_time)

    await _safe_edit_message(
        callback.message,
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\n\nВыберите время:",
        reply_markup=_build_time_slots_keyboard(slots),
    )
    await callback.answer()


@meetings_router.callback_query(
    F.data.startswith(f"{CALLBACK_TIME_SELECT}:"),
    MeetingFlowStates.waiting_for_time,
)
async def handle_time_select(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    time_str = callback.data.split(":", 1)[1]
    try:
        chosen_time = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        await callback.answer("Некорректное время.", show_alert=True)
        return

    data = await state.get_data()
    selected_date_raw = data.get("selected_date")
    if not selected_date_raw:
        await callback.answer("Сначала выберите дату.", show_alert=True)
        return
    selected_date = date.fromisoformat(selected_date_raw)

    slots = data.get("available_slots") or []
    slot = next((item for item in slots if item.get("time") == time_str), None)
    if not slot:
        await callback.answer("Слот недоступен.", show_alert=True)
        return
    duration_minutes = int(slot.get("duration") or 60)

    tenant_tz = _resolve_timezone(data.get("timezone"))
    start_dt_local = datetime.combine(selected_date, chosen_time).replace(tzinfo=tenant_tz)
    start_dt = start_dt_local.astimezone(UTC_TZ)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    await state.update_data(
        selected_time=time_str,
        new_start=start_dt.isoformat(),
        new_end=end_dt.isoformat(),
    )
    await state.set_state(MeetingFlowStates.waiting_for_confirmation)

    await _safe_edit_message(
        callback.message,
        _confirmation_text(data, start_dt),
        reply_markup=_build_confirmation_keyboard(),
    )
    await callback.answer()


@meetings_router.callback_query(
    F.data == CALLBACK_CONFIRM,
    MeetingFlowStates.waiting_for_confirmation,
)
async def handle_meeting_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None or callback.from_user is None:
        return
    data = await state.get_data()

    selected_date_raw = data.get("selected_date")
    selected_time = data.get("selected_time")
    new_start_raw = data.get("new_start")
    new_end_raw = data.get("new_end")

    if not selected_date_raw or not selected_time or not new_start_raw or not new_end_raw:
        await callback.answer("Недостаточно данных для подтверждения.", show_alert=True)
        return

    try:
        selected_date = date.fromisoformat(selected_date_raw)
        new_start = datetime.fromisoformat(new_start_raw)
        new_end = datetime.fromisoformat(new_end_raw)
    except ValueError:
        await callback.answer("Некорректные данные времени.", show_alert=True)
        return

    tenant_id = data.get("tenant_id")
    contact_id = data.get("contact_id")
    event_id = data.get("event_id")
    required_duration = data.get("required_duration")
    tz_name = data.get("timezone")

    slots = await sync_to_async(_get_slots_for_date, thread_sensitive=True)(
        tenant_id,
        contact_id,
        selected_date,
        tz_name=tz_name,
        required_duration_minutes=required_duration,
        exclude_event_id=event_id,
    )
    if not any(slot["time"] == selected_time for slot in slots):
        await state.set_state(MeetingFlowStates.waiting_for_time)
        await _safe_edit_message(
            callback.message,
            "Этот слот уже занят. Выберите другое время:",
            reply_markup=_build_time_slots_keyboard(slots),
        )
        await callback.answer()
        return

    flow = data.get("flow")
    tenant_tz = _resolve_timezone(tz_name)
    if flow == "reschedule":
        updated = await sync_to_async(_update_event_time, thread_sensitive=True)(
            event_id,
            contact_id,
            new_start,
            new_end,
        )
        if not updated:
            await _safe_edit_message(
                callback.message,
                "❌ Не удалось перенести встречу. Попробуйте ещё раз.",
                reply_markup=None,
            )
            await state.clear()
            await callback.answer()
            return

        old_start_raw = data.get("old_start")
        old_start = datetime.fromisoformat(old_start_raw) if old_start_raw else None
        await _safe_edit_message(
            callback.message,
            "✅ Встреча успешно перенесена!\n\n"
            f"📝 {(data.get('event_title') or 'Встреча')}\n"
            f"Было: {_format_dt(old_start, tenant_tz) if old_start else '—'}\n"
            f"Стало: {_format_dt(new_start, tenant_tz)}",
            reply_markup=None,
        )
        await state.clear()
        await callback.answer()
        return

    created_id = await sync_to_async(_create_event, thread_sensitive=True)(
        contact_id=contact_id,
        title=data.get("event_title") or "Новая",
        start_dt=new_start,
        end_dt=new_end,
        event_type_id=None,
    )
    if not created_id:
        await _safe_edit_message(
            callback.message,
            "❌ Не удалось создать встречу. Попробуйте ещё раз.",
            reply_markup=None,
        )
        await state.clear()
        await callback.answer()
        return

    await _safe_edit_message(
        callback.message,
        "✅ Встреча успешно запланирована!\n\n"
        f"📝 {(data.get('event_title') or 'Встреча')}\n"
        f"📅 {_format_dt(new_start, tenant_tz)}",
        reply_markup=None,
    )
    await state.clear()
    await callback.answer()


@meetings_router.callback_query(F.data == CALLBACK_BACK_DATES)
async def handle_back_to_dates(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    data = await state.get_data()
    available_dates = [date.fromisoformat(d) for d in data.get("available_dates", [])]
    marked_dates = {date.fromisoformat(d) for d in data.get("marked_dates", [])}
    if not available_dates:
        await callback.answer()
        return
    year = data.get("calendar_year") or available_dates[0].year
    month = data.get("calendar_month") or available_dates[0].month
    await state.set_state(MeetingFlowStates.waiting_for_date)
    calendar_markup = _build_availability_calendar(
        set(available_dates),
        marked_dates,
        year=year,
        month=month,
        min_date=min(available_dates),
        max_date=max(available_dates),
    )
    await _safe_edit_message(callback.message, _date_prompt_text(data), reply_markup=calendar_markup)
    await callback.answer()


@meetings_router.callback_query(F.data == CALLBACK_BACK_TIMES)
async def handle_back_to_times(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    data = await state.get_data()
    selected_date_raw = data.get("selected_date")
    if not selected_date_raw:
        await callback.answer()
        return
    selected_date = date.fromisoformat(selected_date_raw)
    slots = data.get("available_slots") or []
    if not slots:
        await callback.answer()
        return
    await state.set_state(MeetingFlowStates.waiting_for_time)
    await _safe_edit_message(
        callback.message,
        f"Дата: {selected_date.strftime('%d.%m.%Y')}\n\nВыберите время:",
        reply_markup=_build_time_slots_keyboard(slots),
    )
    await callback.answer()


@meetings_router.callback_query(F.data == CALLBACK_CANCEL)
async def handle_meeting_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        return
    await state.clear()
    await _safe_edit_message(callback.message, "❌ Действие отменено.", reply_markup=None)
    await callback.answer()


@meetings_router.callback_query(F.data == CALLBACK_IGNORE)
async def handle_ignore(callback: CallbackQuery) -> None:
    await callback.answer()