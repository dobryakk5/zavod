from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    ChainSession,
    CRMTask,
    Client,
    InboxEmailMessage,
    InboxReplyMessage,
    MapContact,
    ProductCourseComment,
    ProductCourseEvent,
    ProductCourseLesson,
    ProductCourseProgress,
    TelegramTask,
    UserTenantBinding,
)
from core.tasks.chains import _send_telegram_message, _send_vk_message

from .permissions import IsTenantMember
from .utils import get_active_client


InboxChannel = str
SUPPORTED_REPLY_CHANNELS = {"telegram", "vk", "email", "courses"}
COURSE_THREAD_PREFIX = "course"


def _get_client_tz(client):
    tz_name = str(getattr(client, "timezone", "") or "").strip()
    if not tz_name:
        return timezone.get_current_timezone()
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        return timezone.get_current_timezone()


def _ensure_aware_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    dt: datetime | None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=dt_timezone.utc)
    return dt


def _to_sort_ts(dt: datetime | None) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp() * 1000)


def _format_dt_label(dt: datetime | None, tzinfo) -> str:
    if dt is None:
        return "—"
    local_dt = timezone.localtime(dt, tzinfo)
    now_local = timezone.localtime(timezone.now(), tzinfo)
    day_fmt = local_dt.strftime("%d.%m")
    time_fmt = local_dt.strftime("%H:%M")
    if local_dt.date() == now_local.date():
        return f"Сегодня, {time_fmt}"
    if (now_local.date() - local_dt.date()).days == 1:
        return f"Вчера, {time_fmt}"
    return f"{day_fmt}, {time_fmt}"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _short_text(value: str, max_len: int = 160) -> str:
    text = " ".join(value.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _detect_inquiry_type(text: str, default: str = "support") -> str:
    low = text.lower()
    if any(token in low for token in ("чек", "оплат", "счет", "счёт", "payment")):
        return "payment"
    if any(token in low for token in ("договор", "акт", "документ", "реквизит")):
        return "documents"
    if any(token in low for token in ("цена", "стоим", "тариф", "купить", "коммерчес")):
        return "sales"
    if any(token in low for token in ("отзыв", "обратная связь", "feedback")):
        return "feedback"
    return default


def _detect_service_level(text: str, *, rating: int | None = None, default: str = "normal") -> str:
    if rating is not None:
        if rating <= 5:
            return "critical"
        if rating <= 7:
            return "high"
        if rating <= 9:
            return "normal"
        return "low"

    low = text.lower()
    if any(token in low for token in ("срочно", "не работает", "ошибка", "не могу", "не открыва", "доступ")):
        return "high"
    if any(token in low for token in ("критично", "urgent", "critical")):
        return "critical"
    return default


def _thread_status_from_crm_statuses(statuses: list[str]) -> str:
    if not statuses:
        return "new"
    if any(status_value in {"open", "in_progress"} for status_value in statuses):
        return "in_progress"
    if any(status_value == "done" for status_value in statuses):
        return "closed"
    return "new"


def _service_level_sla_minutes(level: str) -> int:
    if level == "critical":
        return 15
    if level == "high":
        return 30
    if level == "normal":
        return 120
    return 240


def _build_sla_meta(*, last_message_dt: datetime | None, service_level: str, tzinfo) -> tuple[str, str]:
    if last_message_dt is None:
        return "ok", "SLA не рассчитан"

    now = timezone.now()
    age_minutes = max(0, int((now - last_message_dt).total_seconds() // 60))
    limit_minutes = _service_level_sla_minutes(service_level)
    remain = limit_minutes - age_minutes
    if remain < 0:
        return "breached", f"SLA просрочен на {abs(remain)} мин"
    if remain <= max(10, limit_minutes // 3):
        return "risk", f"До SLA {remain} мин"

    deadline = last_message_dt + timedelta(minutes=limit_minutes)
    return "ok", f"SLA до {_format_dt_label(deadline, tzinfo)}"


def _contact_channels(contact: MapContact | None, *, channel: InboxChannel, handle: str | None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(ch: str, value: str | None):
        text = _safe_text(value)
        if not text:
            return
        key = (ch, text)
        if key in seen:
            return
        seen.add(key)
        items.append({"channel": ch, "handle": text})

    add(channel, handle)
    if contact is not None:
        if channel != "telegram":
            username = _safe_text(getattr(contact, "tg_username", None))
            if username:
                add("telegram", f"@{username.lstrip('@')}")
        add("email", getattr(contact, "email", None))
        add("whatsapp", getattr(contact, "phone", None))
    return items


def _contact_payload(contact: MapContact | None, *, fallback_name: str, manager: str, channels: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "id": int(contact.id) if contact is not None else 0,
        "name": _safe_text(getattr(contact, "name", None)) or fallback_name,
        "company": None,
        "manager": manager,
        "phone": _safe_text(getattr(contact, "phone", None)) if contact is not None else None,
        "email": _safe_text(getattr(contact, "email", None)) if contact is not None else None,
        "tags": [],
        "channels": channels,
        "notes": _safe_text(getattr(contact, "notes", None)) if contact is not None else None,
    }


def _history_message_to_text(history_item: dict[str, Any]) -> str:
    message = history_item.get("message") if isinstance(history_item.get("message"), dict) else {}
    text = _safe_text(message.get("text"))
    if text:
        return text
    summary = _safe_text(history_item.get("summary"))
    if summary:
        return summary
    message_type = _safe_text(message.get("message_type"))
    if message_type:
        return f"[{message_type}]"
    return "[сообщение]"


def _reply_log_to_thread_message(log: InboxReplyMessage, *, tzinfo) -> dict[str, Any]:
    dt = _ensure_aware_datetime(log.sent_at)
    return {
        "id": f"inbox-reply-{log.id}",
        "channel": _safe_text(log.channel) or "email",
        "direction": "out",
        "author": _safe_text(log.author) or "Менеджер",
        "text": _safe_text(log.text) or "[пустое сообщение]",
        "createdAtLabel": _format_dt_label(dt, tzinfo),
        "createdAtSort": _to_sort_ts(dt),
        "_created_at": dt.isoformat() if dt else None,
    }


def _recompute_thread_after_message_merge(thread: dict[str, Any], *, tzinfo) -> None:
    messages = list(thread.get("messages") or [])
    messages.sort(key=lambda item: int(item.get("createdAtSort") or 0))
    thread["messages"] = [
        {
            "id": item["id"],
            "channel": item["channel"],
            "direction": item["direction"],
            "author": item["author"],
            "text": item["text"],
            "createdAtLabel": item["createdAtLabel"],
            "createdAtSort": item["createdAtSort"],
        }
        for item in messages
    ]
    latest = messages[-1] if messages else None
    latest_dt = _ensure_aware_datetime(latest.get("_created_at")) if latest else None
    sla_state, sla_label = _build_sla_meta(
        last_message_dt=latest_dt,
        service_level=_safe_text(thread.get("serviceLevel")) or "normal",
        tzinfo=tzinfo,
    )
    thread["slaState"] = sla_state
    thread["slaDeadlineLabel"] = sla_label
    thread["lastMessagePreview"] = _short_text(_safe_text(latest.get("text")) if latest else "") or _safe_text(thread.get("subject"))
    thread["lastMessageAtLabel"] = latest.get("createdAtLabel") if latest else "—"
    thread["lastMessageSort"] = int(latest.get("createdAtSort") or 0) if latest else 0


def _append_reply_logs_to_threads(client, threads: list[dict[str, Any]], *, tzinfo) -> None:
    if not threads:
        return
    try:
        logs = list(
            InboxReplyMessage.objects.filter(client=client)
            .order_by("sent_at", "id")[:2000]
        )
    except (ProgrammingError, OperationalError):
        return
    if not logs:
        return

    thread_map = {str(thread.get("id") or ""): thread for thread in threads}
    touched_ids: set[str] = set()
    for log in logs:
        thread_id = _safe_text(log.thread_id)
        thread = thread_map.get(thread_id)
        if not thread:
            continue
        raw_messages = thread.setdefault("_raw_messages", [])
        if not raw_messages:
            raw_messages.extend(thread.get("messages", []))
        raw_messages.append(_reply_log_to_thread_message(log, tzinfo=tzinfo))
        touched_ids.add(thread_id)

    for thread_id in touched_ids:
        thread = thread_map.get(thread_id)
        if not thread:
            continue
        raw_messages = list(thread.pop("_raw_messages", []))
        if raw_messages:
            # restore hidden datetime payload for existing messages is not available here,
            # but reply messages carry `_created_at`; for existing messages we can still sort by `createdAtSort`.
            normalized: list[dict[str, Any]] = []
            for item in raw_messages:
                normalized_item = dict(item)
                if "_created_at" not in normalized_item:
                    normalized_item["_created_at"] = None
                normalized.append(normalized_item)
            thread["messages"] = normalized
            _recompute_thread_after_message_merge(thread, tzinfo=tzinfo)


def _parse_telegram_thread_id(thread_id: str) -> int | None:
    if not thread_id.startswith("telegram:"):
        return None
    raw = thread_id.split(":", 1)[1]
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_vk_thread_id(thread_id: str) -> str | None:
    if not thread_id.startswith("vk:"):
        return None
    value = _safe_text(thread_id.split(":", 1)[1])
    return value or None


def _build_course_thread_id(*, owner_id: int, contact_id: int, lesson_id: int) -> str:
    return f"{COURSE_THREAD_PREFIX}:{owner_id}:{contact_id}:{lesson_id}"


def _parse_course_thread_id(thread_id: str) -> tuple[int | None, int | None, int | None]:
    raw = _safe_text(thread_id)
    parts = raw.split(":")
    if len(parts) != 4 or parts[0] != COURSE_THREAD_PREFIX:
        return None, None, None
    try:
        owner_id = int(parts[1])
        contact_id = int(parts[2])
        lesson_id = int(parts[3])
    except (TypeError, ValueError):
        return None, None, None
    if owner_id <= 0 or contact_id <= 0 or lesson_id <= 0:
        return None, None, None
    return owner_id, contact_id, lesson_id


def _build_curator_course_module_url(*, product_id: int, module_id: int) -> str:
    base_url = _safe_text(getattr(settings, "SITE_BASE_URL", "")).rstrip("/")
    path = f"/product/{product_id}/course/{module_id}"
    return f"{base_url}{path}" if base_url else path


def _send_telegram_text_message(*, chat_id: int, text: str) -> tuple[str, dict[str, Any]]:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не настроен.")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    data = response.json() if response.content else {}
    if response.status_code != 200 or not bool(data.get("ok")):
        description = _safe_text(data.get("description")) or _safe_text(data)
        raise ValueError(description or "Telegram API вернул ошибку.")
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    external_message_id = _safe_text(result.get("message_id"))
    metadata = {"telegram_chat_id": str(chat_id)}
    return external_message_id, metadata


def _resolve_contact_binding(*, client, contact_id: int, provider: str) -> UserTenantBinding | None:
    return (
        UserTenantBinding.objects
        .filter(
            tenant=client,
            contact_id=int(contact_id),
            provider=provider,
            is_active=True,
        )
        .order_by("-bound_at", "-id")
        .first()
    )


def _send_course_message_via_channel(
    *,
    client,
    contact: MapContact | None,
    contact_id: int,
    channel: str,
    text: str,
) -> tuple[str, dict[str, Any]]:
    if channel == ProductCourseComment.CHANNEL_COURSES:
        return "", {}

    if channel == ProductCourseComment.CHANNEL_TELEGRAM:
        binding = _resolve_contact_binding(client=client, contact_id=contact_id, provider=UserTenantBinding.PROVIDER_TELEGRAM)
        if binding is None:
            raise ValueError("У контакта нет активной Telegram привязки.")
        raw_chat_id = _safe_text(binding.telegram_chat_id) or _safe_text(binding.provider_user_id)
        try:
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError):
            raise ValueError("У контакта некорректный Telegram chat_id.")
        external_message_id, metadata = _send_telegram_text_message(chat_id=chat_id, text=text)
        return external_message_id, {**metadata, "contact_id": int(contact_id)}

    if channel == ProductCourseComment.CHANNEL_VK:
        binding = _resolve_contact_binding(client=client, contact_id=contact_id, provider=UserTenantBinding.PROVIDER_VK)
        if binding is None:
            raise ValueError("У контакта нет активной VK привязки.")
        vk_user_id = _safe_text(binding.provider_user_id)
        if not vk_user_id:
            raise ValueError("У контакта пустой VK идентификатор.")
        ok = _send_vk_message(
            tenant_id=client.id,
            vk_user_id=vk_user_id,
            text=text,
        )
        if not ok:
            raise ValueError("Не удалось отправить сообщение в VK.")
        return "", {"vk_user_id": vk_user_id, "contact_id": int(contact_id)}

    if channel == ProductCourseComment.CHANNEL_EMAIL:
        recipient = _safe_text(getattr(contact, "email", None))
        if not recipient:
            raise ValueError("У контакта нет email для отправки.")
        sent = send_mail(
            "Комментарий по уроку",
            text,
            getattr(settings, "DEFAULT_FROM_EMAIL", "support@fibonatty.ru"),
            [recipient],
            fail_silently=False,
        )
        if not sent:
            raise ValueError("Email backend не подтвердил отправку письма.")
        return "", {"to_email": recipient, "contact_id": int(contact_id)}

    raise ValueError("Канал ответа не поддерживается для курсов.")


def _resolve_course_lesson_context(
    *,
    client,
    thread_id: str,
    lesson_id: int | None = None,
    contact_id: int | None = None,
) -> tuple[ProductCourseLesson, int]:
    parsed_owner_id, parsed_contact_id, parsed_lesson_id = _parse_course_thread_id(thread_id)
    if parsed_owner_id is not None and parsed_owner_id != int(client.id):
        raise ValueError("thread_id относится к другому клиенту.")

    resolved_contact_id = int(parsed_contact_id) if parsed_contact_id else None
    resolved_lesson_id = int(parsed_lesson_id) if parsed_lesson_id else None
    if contact_id is not None:
        resolved_contact_id = int(contact_id)
    if lesson_id is not None:
        resolved_lesson_id = int(lesson_id)

    if not resolved_contact_id or resolved_contact_id <= 0:
        raise ValueError("Не удалось определить contact_id для course thread.")
    if not resolved_lesson_id or resolved_lesson_id <= 0:
        raise ValueError("Не удалось определить lesson_id для course thread.")

    lesson = (
        ProductCourseLesson.objects
        .select_related("module__course__product")
        .filter(id=resolved_lesson_id, module__course__owner_id=client.id)
        .first()
    )
    if lesson is None:
        raise ValueError("Урок не найден или не принадлежит клиенту.")

    return lesson, int(resolved_contact_id)


def _notify_contact_about_course_acceptance(
    *,
    client,
    contact_id: int,
    text: str,
) -> tuple[bool, str | None]:
    telegram_binding = _resolve_contact_binding(
        client=client,
        contact_id=contact_id,
        provider=UserTenantBinding.PROVIDER_TELEGRAM,
    )
    if telegram_binding is not None:
        raw_chat_id = _safe_text(telegram_binding.telegram_chat_id) or _safe_text(telegram_binding.provider_user_id)
        try:
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError):
            chat_id = 0
        if chat_id > 0 and _send_telegram_message(chat_id=chat_id, text=text):
            return True, ProductCourseComment.CHANNEL_TELEGRAM

    vk_binding = _resolve_contact_binding(
        client=client,
        contact_id=contact_id,
        provider=UserTenantBinding.PROVIDER_VK,
    )
    vk_user_id = _safe_text(getattr(vk_binding, "provider_user_id", None))
    if vk_user_id:
        if _send_vk_message(tenant_id=client.id, vk_user_id=vk_user_id, text=text):
            return True, ProductCourseComment.CHANNEL_VK

    return False, None


def _send_telegram_reply(*, client, thread_id: str, text: str) -> tuple[str, dict[str, Any]]:
    telegram_user_id = _parse_telegram_thread_id(thread_id)
    if telegram_user_id is None:
        raise ValueError("Не удалось определить Telegram пользователя для этого диалога.")

    binding = (
        UserTenantBinding.objects.filter(
            tenant=client,
            provider=UserTenantBinding.PROVIDER_TELEGRAM,
            provider_user_id=str(telegram_user_id),
        )
        .order_by("-bound_at", "-id")
        .first()
    )
    chat_id = int(binding.telegram_chat_id) if (binding and binding.telegram_chat_id) else telegram_user_id

    external_message_id, metadata = _send_telegram_text_message(chat_id=chat_id, text=text)
    metadata["telegram_user_id"] = str(telegram_user_id)
    return external_message_id, metadata


def _send_vk_reply(*, client, thread_id: str, text: str) -> tuple[str, dict[str, Any]]:
    vk_user_id = _parse_vk_thread_id(thread_id)
    if vk_user_id is None:
        raise ValueError("Не удалось определить VK пользователя для этого диалога.")

    ok = _send_vk_message(
        tenant_id=client.id,
        vk_user_id=vk_user_id,
        text=text,
    )
    if not ok:
        raise ValueError("Не удалось отправить сообщение в VK. Проверьте интеграцию VK.")

    return "", {"vk_user_id": vk_user_id}


def _email_reply_subject(subject: str) -> str:
    clean = _safe_text(subject)
    if not clean:
        return "Re: Без темы"
    if clean.lower().startswith("re:"):
        return clean
    return f"Re: {clean}"


def _send_email_reply(*, client, thread_id: str, text: str) -> tuple[str, dict[str, Any]]:
    thread_key = _safe_text(thread_id)
    if not thread_key.startswith("email:"):
        raise ValueError("Некорректный email thread_id.")

    try:
        latest_email = (
            InboxEmailMessage.objects.filter(client=client, thread_key=thread_key)
            .order_by("-received_at", "-id")
            .first()
        )
    except (ProgrammingError, OperationalError):
        raise ValueError("Email inbox таблица недоступна. Выполните миграции.")

    if latest_email is None:
        raise ValueError("Не найдено входящее письмо для этого email-диалога.")

    recipient = _safe_text(latest_email.from_email)
    if not recipient:
        raise ValueError("У диалога нет email получателя.")

    subject = _email_reply_subject(_safe_text(latest_email.subject))
    sent = send_mail(
        subject,
        text,
        getattr(settings, "DEFAULT_FROM_EMAIL", "support@fibonatty.ru"),
        [recipient],
        fail_silently=False,
    )
    if not sent:
        raise ValueError("Email backend не подтвердил отправку письма.")
    return "", {"to_email": recipient, "subject": subject, "thread_key": thread_key}


def _thread_base(
    *,
    thread_id: str,
    source_channel: str,
    inquiry_type: str,
    service_level: str,
    status_value: str,
    client_payload: dict[str, Any],
    subject: str,
    messages: list[dict[str, Any]],
    unread_count: int = 0,
    tzinfo=None,
) -> dict[str, Any]:
    sorted_messages = sorted(messages, key=lambda item: int(item.get("createdAtSort") or 0))
    latest_message = sorted_messages[-1] if sorted_messages else None
    latest_dt = _ensure_aware_datetime(latest_message.get("_created_at")) if latest_message else None
    sla_state, sla_label = _build_sla_meta(last_message_dt=latest_dt, service_level=service_level, tzinfo=tzinfo)
    latest_preview = _short_text(_safe_text(latest_message.get("text")) if latest_message else "")
    return {
        "id": thread_id,
        "sourceChannel": source_channel,
        "inquiryType": inquiry_type,
        "serviceLevel": service_level,
        "slaState": sla_state,
        "slaDeadlineLabel": sla_label,
        "status": status_value,
        "unreadCount": int(unread_count),
        "client": client_payload,
        "subject": subject,
        "lastMessagePreview": latest_preview or subject,
        "lastMessageAtLabel": latest_message.get("createdAtLabel") if latest_message else "—",
        "lastMessageSort": int(latest_message.get("createdAtSort") or 0) if latest_message else 0,
        "messages": [
            {
                "id": item["id"],
                "channel": item["channel"],
                "direction": item["direction"],
                "author": item["author"],
                "text": item["text"],
                "createdAtLabel": item["createdAtLabel"],
                "createdAtSort": item["createdAtSort"],
            }
            for item in sorted_messages
        ],
    }


def _build_telegram_threads(client, *, tzinfo) -> list[dict[str, Any]]:
    tg_rows = list(
        TelegramTask.objects.filter(client=client)
        .order_by("-received_at", "-id")[:500]
    )
    if not tg_rows:
        return []

    tg_user_ids = {int(row.telegram_user_id) for row in tg_rows if row.telegram_user_id}
    tg_names = {_safe_text(row.tg_name).lstrip("@").lower() for row in tg_rows if _safe_text(row.tg_name)}

    contacts_by_tg_id: dict[int, MapContact] = {}
    contacts_by_tg_username: dict[str, MapContact] = {}
    if tg_user_ids:
        for contact in MapContact.objects.filter(id__gt=0, tg_user_id__in=tg_user_ids):
            if contact.tg_user_id is not None:
                contacts_by_tg_id[int(contact.tg_user_id)] = contact
    if tg_names:
        for contact in MapContact.objects.filter(id__gt=0, tg_username__isnull=False):
            username = _safe_text(contact.tg_username).lstrip("@").lower()
            if username and username in tg_names and username not in contacts_by_tg_username:
                contacts_by_tg_username[username] = contact

    crm_statuses_by_level: dict[int, list[str]] = defaultdict(list)
    level_ids = [int(row.id) for row in tg_rows]
    for crm_task in CRMTask.objects.filter(level_id__in=level_ids).only("level_id", "status"):
        if crm_task.level_id is not None:
            crm_statuses_by_level[int(crm_task.level_id)].append(_safe_text(crm_task.status))

    groups: dict[str, dict[str, Any]] = {}
    for row in sorted(tg_rows, key=lambda item: (item.received_at, item.id)):
        tg_user_id = int(row.telegram_user_id) if row.telegram_user_id else 0
        tg_name = _safe_text(row.tg_name)
        key = f"telegram:{tg_user_id}" if tg_user_id else f"telegram-name:{tg_name.lower() or row.id}"

        contact = contacts_by_tg_id.get(tg_user_id)
        if contact is None and tg_name:
            contact = contacts_by_tg_username.get(tg_name.lstrip("@").lower())

        thread = groups.get(key)
        if thread is None:
            fallback_name = _safe_text(getattr(contact, "name", None)) or (f"@{tg_name.lstrip('@')}" if tg_name else f"Telegram #{tg_user_id or row.id}")
            channels = _contact_channels(
                contact,
                channel="telegram",
                handle=(f"@{tg_name.lstrip('@')}" if tg_name else (str(tg_user_id) if tg_user_id else None)),
            )
            thread = {
                "contact": contact,
                "client_payload": _contact_payload(
                    contact,
                    fallback_name=fallback_name,
                    manager="Оператор",
                    channels=channels,
                ),
                "messages": [],
                "crm_statuses": [],
                "latest_rating": None,
                "latest_text": "",
                "latest_tg_task_id": None,
            }
            groups[key] = thread

        text = _safe_text(row.message_text)
        dt = _ensure_aware_datetime(row.received_at)
        rating = int(row.rating) if row.rating is not None else None
        display_text = text
        if rating is not None:
            display_text = f"{text}\n\nОценка сервиса: {rating}/10" if text else f"Оценка сервиса: {rating}/10"

        author_name = (
            _safe_text(getattr(contact, "name", None))
            or (f"@{tg_name.lstrip('@')}" if tg_name else f"Telegram #{tg_user_id or row.id}")
        )
        thread["messages"].append(
            {
                "id": f"tg-task-{row.id}",
                "channel": "telegram",
                "direction": "in",
                "author": author_name,
                "text": display_text or "[пустое сообщение]",
                "createdAtLabel": _format_dt_label(dt, tzinfo),
                "createdAtSort": _to_sort_ts(dt),
                "_created_at": dt.isoformat() if dt else None,
            }
        )
        thread["crm_statuses"].extend(crm_statuses_by_level.get(int(row.id), []))
        thread["latest_text"] = text or thread["latest_text"]
        if rating is not None:
            thread["latest_rating"] = rating
        thread["latest_tg_task_id"] = int(row.id)

    result: list[dict[str, Any]] = []
    for key, thread in groups.items():
        latest_rating = thread["latest_rating"]
        latest_text = thread["latest_text"] or "Сообщение из Telegram бота"
        service_level = _detect_service_level(latest_text, rating=latest_rating, default="normal")
        status_value = _thread_status_from_crm_statuses(thread["crm_statuses"])
        subject = (
            f"Telegram бот · Оценка сервиса {latest_rating}/10"
            if latest_rating is not None
            else "Telegram бот · Входящее сообщение"
        )
        result.append(
            _thread_base(
                thread_id=key,
                source_channel="telegram",
                inquiry_type="feedback",
                service_level=service_level,
                status_value=status_value,
                client_payload=thread["client_payload"],
                subject=subject,
                messages=thread["messages"],
                unread_count=0,
                tzinfo=tzinfo,
            )
        )
    return result


def _build_vk_threads(client, *, tzinfo) -> list[dict[str, Any]]:
    sessions = list(
        ChainSession.objects.filter(tenant=client)
        .order_by("-last_activity_at", "-id")[:400]
    )
    if not sessions:
        return []

    bindings = list(
        UserTenantBinding.objects.filter(tenant=client, provider=UserTenantBinding.PROVIDER_VK)
        .order_by("-bound_at", "-id")
    )
    latest_binding_by_provider_user_id: dict[str, UserTenantBinding] = {}
    contact_ids: set[int] = set()
    for binding in bindings:
        provider_user_id = _safe_text(binding.provider_user_id)
        if not provider_user_id or provider_user_id in latest_binding_by_provider_user_id:
            continue
        latest_binding_by_provider_user_id[provider_user_id] = binding
        if binding.contact_id:
            contact_ids.add(int(binding.contact_id))

    contacts_by_id = {
        int(contact.id): contact
        for contact in MapContact.objects.filter(id__in=contact_ids)
    } if contact_ids else {}

    groups: dict[str, dict[str, Any]] = {}
    for session in sessions:
        context = session.context if isinstance(session.context, dict) else {}
        history = context.get("history") if isinstance(context.get("history"), list) else []
        context_provider = _safe_text(context.get("provider")).lower()
        provider_user_id = _safe_text(context.get("provider_user_id")) or str(session.user_id)
        if not provider_user_id:
            provider_user_id = str(session.user_id)

        relevant_items: list[dict[str, Any]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            provider = _safe_text(item.get("provider")).lower() or context_provider
            if provider != UserTenantBinding.PROVIDER_VK:
                continue
            if _safe_text(item.get("direction")).lower() != "incoming":
                continue
            relevant_items.append(item)

        if not relevant_items and context_provider != UserTenantBinding.PROVIDER_VK:
            continue

        key = f"vk:{provider_user_id}"
        binding = latest_binding_by_provider_user_id.get(provider_user_id)
        contact = contacts_by_id.get(int(binding.contact_id)) if (binding and binding.contact_id) else None

        thread = groups.get(key)
        if thread is None:
            vk_handle = f"vk:{provider_user_id}"
            fallback_name = _safe_text(getattr(contact, "name", None)) or f"VK #{provider_user_id}"
            thread = {
                "contact": contact,
                "client_payload": _contact_payload(
                    contact,
                    fallback_name=fallback_name,
                    manager="Менеджер",
                    channels=_contact_channels(contact, channel="vk", handle=vk_handle),
                ),
                "messages": [],
                "has_active_session": False,
                "latest_text": "",
            }
            groups[key] = thread

        if _safe_text(session.status) == "active":
            thread["has_active_session"] = True

        author_name = _safe_text(getattr(contact, "name", None)) or f"VK #{provider_user_id}"
        for item in relevant_items:
            dt = _ensure_aware_datetime(item.get("received_at"))
            text = _history_message_to_text(item)
            thread["messages"].append(
                {
                    "id": f"vk-{provider_user_id}-{_to_sort_ts(dt)}-{len(thread['messages'])}",
                    "channel": "vk",
                    "direction": "in",
                    "author": author_name,
                    "text": text,
                    "createdAtLabel": _format_dt_label(dt, tzinfo),
                    "createdAtSort": _to_sort_ts(dt),
                    "_created_at": dt.isoformat() if dt else None,
                }
            )
            if text:
                thread["latest_text"] = text

    result: list[dict[str, Any]] = []
    for key, thread in groups.items():
        if not thread["messages"]:
            continue
        latest_text = thread["latest_text"] or "Сообщение из VK"
        service_level = _detect_service_level(latest_text, default="normal")
        inquiry_type = _detect_inquiry_type(latest_text, default="support")
        status_value = "in_progress" if thread["has_active_session"] else "closed"
        result.append(
            _thread_base(
                thread_id=key,
                source_channel="vk",
                inquiry_type=inquiry_type,
                service_level=service_level,
                status_value=status_value,
                client_payload=thread["client_payload"],
                subject=f"VK · {_short_text(latest_text, 72)}",
                messages=thread["messages"],
                unread_count=0,
                tzinfo=tzinfo,
            )
        )
    return result


def _build_email_threads(client, *, tzinfo) -> list[dict[str, Any]]:
    try:
        email_rows = list(
            InboxEmailMessage.objects.filter(client=client)
            .order_by("-received_at", "-id")[:500]
        )
    except (ProgrammingError, OperationalError):
        return []
    if not email_rows:
        return []

    contact_ids = {int(item.contact_id) for item in email_rows if item.contact_id}
    contacts_by_id = {
        int(contact.id): contact
        for contact in MapContact.objects.filter(id__in=contact_ids)
    } if contact_ids else {}

    groups: dict[str, dict[str, Any]] = {}
    for row in sorted(email_rows, key=lambda item: (item.received_at, item.id)):
        from_email = _safe_text(row.from_email)
        thread_key = _safe_text(row.thread_key) or f"email:{from_email or row.id}"
        contact = contacts_by_id.get(int(row.contact_id)) if row.contact_id else None

        thread = groups.get(thread_key)
        if thread is None:
            fallback_name = (
                _safe_text(getattr(contact, "name", None))
                or _safe_text(row.from_name)
                or from_email
                or f"Email #{row.id}"
            )
            thread = {
                "client_payload": _contact_payload(
                    contact,
                    fallback_name=fallback_name,
                    manager="Менеджер",
                    channels=_contact_channels(contact, channel="email", handle=from_email or None),
                ),
                "messages": [],
                "latest_text": "",
                "latest_subject": "",
            }
            groups[thread_key] = thread

        body_text = _safe_text(row.body_text)
        if not body_text and _safe_text(row.body_html):
            body_text = "[HTML-письмо]"
        if not body_text:
            body_text = _safe_text(row.subject) or "[письмо без текста]"

        dt = _ensure_aware_datetime(row.received_at)
        author_name = _safe_text(row.from_name) or from_email or "Email"
        thread["messages"].append(
            {
                "id": f"email-{row.id}",
                "channel": "email",
                "direction": "in",
                "author": author_name,
                "text": body_text,
                "createdAtLabel": _format_dt_label(dt, tzinfo),
                "createdAtSort": _to_sort_ts(dt),
                "_created_at": dt.isoformat() if dt else None,
            }
        )
        if body_text:
            thread["latest_text"] = body_text
        if _safe_text(row.subject):
            thread["latest_subject"] = _safe_text(row.subject)

    result: list[dict[str, Any]] = []
    for key, thread in groups.items():
        latest_text = thread["latest_text"] or "Входящее письмо"
        latest_subject = thread["latest_subject"] or "Email · Без темы"
        result.append(
            _thread_base(
                thread_id=key,
                source_channel="email",
                inquiry_type=_detect_inquiry_type(f"{latest_subject}\n{latest_text}", default="support"),
                service_level=_detect_service_level(f"{latest_subject}\n{latest_text}", default="normal"),
                status_value="new",
                client_payload=thread["client_payload"],
                subject=f"Email · {latest_subject}",
                messages=thread["messages"],
                unread_count=0,
                tzinfo=tzinfo,
            )
        )
    return result


def _course_author_name(*, role: str, contact: MapContact | None) -> str:
    if role == ProductCourseComment.AUTHOR_STUDENT:
        return _safe_text(getattr(contact, "name", None)) or "Ученик"
    if role == ProductCourseComment.AUTHOR_CURATOR:
        return "Куратор"
    return "Система"


def _course_event_to_message(event: ProductCourseEvent, *, contact: MapContact | None, tzinfo) -> dict[str, Any]:
    dt = _ensure_aware_datetime(event.created_at)
    course_title = _safe_text(getattr(event.course, "title", None))
    lesson_title = _safe_text(getattr(event.lesson, "title", None))
    curator_url = _build_curator_course_module_url(
        product_id=int(event.product_id),
        module_id=int(event.module_id),
    )

    if event.event_type == ProductCourseEvent.EVENT_LESSON_ACCEPTED:
        text = (
            "Куратор принял урок.\n"
            f"Курс: {course_title or '—'}\n"
            f"Урок: {lesson_title or '—'}\n"
            f"Ссылка куратора: {curator_url}"
        )
    else:
        text = (
            "Ученик отметил урок как завершенный.\n"
            f"Курс: {course_title or '—'}\n"
            f"Урок: {lesson_title or '—'}\n"
            f"Ссылка куратора: {curator_url}"
        )

    direction = "in" if event.actor_role == ProductCourseEvent.ACTOR_STUDENT else "out"
    return {
        "id": f"course-event-{event.id}",
        "channel": ProductCourseComment.CHANNEL_COURSES,
        "direction": direction,
        "author": _course_author_name(role=_safe_text(event.actor_role), contact=contact),
        "text": text,
        "createdAtLabel": _format_dt_label(dt, tzinfo),
        "createdAtSort": _to_sort_ts(dt),
        "_created_at": dt.isoformat() if dt else None,
    }


def _course_comment_to_message(comment: ProductCourseComment, *, contact: MapContact | None, tzinfo) -> dict[str, Any]:
    dt = _ensure_aware_datetime(comment.created_at)
    direction = "in" if comment.author_role == ProductCourseComment.AUTHOR_STUDENT else "out"
    return {
        "id": f"course-comment-{comment.id}",
        "channel": _safe_text(comment.channel) or ProductCourseComment.CHANNEL_COURSES,
        "direction": direction,
        "author": _course_author_name(role=_safe_text(comment.author_role), contact=contact),
        "text": _safe_text(comment.message_text) or "[пустое сообщение]",
        "createdAtLabel": _format_dt_label(dt, tzinfo),
        "createdAtSort": _to_sort_ts(dt),
        "_created_at": dt.isoformat() if dt else None,
    }


def _build_course_threads(client, *, tzinfo) -> list[dict[str, Any]]:
    try:
        events = list(
            ProductCourseEvent.objects
            .filter(owner=client)
            .select_related("product", "course", "module", "lesson")
            .order_by("-created_at", "-id")[:800]
        )
    except (ProgrammingError, OperationalError):
        return []
    if not events:
        return []

    sorted_events = sorted(events, key=lambda item: (item.created_at, item.id))
    contact_ids = {int(item.contact_id) for item in sorted_events if item.contact_id}
    contacts_by_id = {
        int(contact.id): contact
        for contact in MapContact.objects.filter(id__in=contact_ids)
    } if contact_ids else {}

    groups: dict[str, dict[str, Any]] = {}
    for event in sorted_events:
        contact_id = int(event.contact_id)
        lesson_id = int(event.lesson_id)
        thread_id = _build_course_thread_id(owner_id=int(client.id), contact_id=contact_id, lesson_id=lesson_id)
        contact = contacts_by_id.get(contact_id)
        thread = groups.get(thread_id)
        if thread is None:
            fallback_name = _safe_text(getattr(contact, "name", None)) or f"Ученик #{contact_id}"
            channels = _contact_channels(contact, channel=ProductCourseComment.CHANNEL_COURSES, handle=f"course:{contact_id}:{lesson_id}")
            thread = {
                "client_payload": _contact_payload(
                    contact,
                    fallback_name=fallback_name,
                    manager="Куратор",
                    channels=channels,
                ),
                "messages": [],
                "accepted": False,
                "meta": {
                    "contact_id": contact_id,
                    "product_id": int(event.product_id),
                    "course_id": int(event.course_id),
                    "module_id": int(event.module_id),
                    "lesson_id": lesson_id,
                    "course_title": _safe_text(getattr(event.course, "title", None)),
                    "lesson_title": _safe_text(getattr(event.lesson, "title", None)),
                    "curator_url": _build_curator_course_module_url(
                        product_id=int(event.product_id),
                        module_id=int(event.module_id),
                    ),
                },
            }
            groups[thread_id] = thread

        if event.event_type == ProductCourseEvent.EVENT_LESSON_ACCEPTED:
            thread["accepted"] = True
        thread["messages"].append(_course_event_to_message(event, contact=contact, tzinfo=tzinfo))

    lesson_ids = {int(item["meta"]["lesson_id"]) for item in groups.values()}
    comments = list(
        ProductCourseComment.objects
        .filter(owner=client, contact_id__in=contact_ids, lesson_id__in=lesson_ids)
        .order_by("created_at", "id")
    )
    for comment in comments:
        thread_id = _build_course_thread_id(
            owner_id=int(client.id),
            contact_id=int(comment.contact_id),
            lesson_id=int(comment.lesson_id),
        )
        thread = groups.get(thread_id)
        if thread is None:
            continue
        contact = contacts_by_id.get(int(comment.contact_id))
        thread["messages"].append(_course_comment_to_message(comment, contact=contact, tzinfo=tzinfo))

    result: list[dict[str, Any]] = []
    for thread_id, thread in groups.items():
        meta = thread["meta"]
        accepted = bool(thread["accepted"])
        course_title = _safe_text(meta.get("course_title")) or "Курс"
        lesson_title = _safe_text(meta.get("lesson_title")) or "Урок"
        status_value = "closed" if accepted else "new"
        service_level = "normal" if accepted else "high"
        payload = _thread_base(
            thread_id=thread_id,
            source_channel=ProductCourseComment.CHANNEL_COURSES,
            inquiry_type="support",
            service_level=service_level,
            status_value=status_value,
            client_payload=thread["client_payload"],
            subject=f"Курсы · {course_title} / {lesson_title}",
            messages=thread["messages"],
            unread_count=0,
            tzinfo=tzinfo,
        )
        payload["courseEvent"] = {
            "contact_id": int(meta["contact_id"]),
            "product_id": int(meta["product_id"]),
            "course_id": int(meta["course_id"]),
            "module_id": int(meta["module_id"]),
            "lesson_id": int(meta["lesson_id"]),
            "course_title": course_title,
            "lesson_title": lesson_title,
            "curator_url": _safe_text(meta.get("curator_url")),
            "accepted": accepted,
        }
        result.append(payload)
    return result


def _derive_email_thread_key(*, subject: str, from_email: str, raw_thread_key: str) -> str:
    if raw_thread_key:
        return raw_thread_key
    normalized_subject = _safe_text(subject).lower()
    if normalized_subject:
        for prefix in ("re:", "fw:", "fwd:", "ответ:", "пересл:"):
            if normalized_subject.startswith(prefix):
                normalized_subject = normalized_subject[len(prefix):].strip()
    base = normalized_subject or from_email.lower() or "email-thread"
    return f"email:{base[:220]}"


class EmailInboxWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request, client_uuid):
        client = Client.objects.filter(uuid=client_uuid).first()
        if client is None:
            return Response({"error": "Клиент не найден"}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data if isinstance(request.data, dict) else {}

        from_email = _safe_text(payload.get("from_email") or payload.get("from"))
        if not from_email:
            return Response({"error": "Поле from_email обязательно"}, status=status.HTTP_400_BAD_REQUEST)

        subject = _safe_text(payload.get("subject"))
        raw_thread_key = _safe_text(payload.get("thread_key") or payload.get("thread_id"))
        thread_key = _derive_email_thread_key(subject=subject, from_email=from_email, raw_thread_key=raw_thread_key)

        external_message_id = _safe_text(payload.get("external_message_id") or payload.get("message_id"))
        if external_message_id:
            try:
                existing = InboxEmailMessage.objects.filter(client=client, external_message_id=external_message_id).first()
            except (ProgrammingError, OperationalError):
                return Response(
                    {"error": "Email inbox table не создана. Выполните миграции (`backend/core/migrations/0169`)."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if existing is not None:
                return Response({"ok": True, "id": existing.id, "deduplicated": True})

        received_at = _ensure_aware_datetime(payload.get("received_at")) or timezone.now()
        body_text = _safe_text(payload.get("body_text") or payload.get("text"))
        body_html = str(payload.get("body_html") or payload.get("html") or "")
        from_name = _safe_text(payload.get("from_name"))
        to_email = _safe_text(payload.get("to_email") or payload.get("to"))
        provider = _safe_text(payload.get("provider")) or "email"
        source = _safe_text(payload.get("source")) or "webhook"

        contact_id_raw = payload.get("contact_id")
        contact_id: int | None = None
        try:
            if contact_id_raw not in (None, ""):
                contact_id = int(contact_id_raw)
        except (TypeError, ValueError):
            contact_id = None
        if contact_id is None and from_email:
            contact_match = MapContact.objects.filter(email__iexact=from_email).values("id").first()
            if contact_match:
                contact_id = int(contact_match["id"])

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        headers = payload.get("headers")
        if isinstance(headers, dict):
            metadata = {**metadata, "headers": headers}

        try:
            row = InboxEmailMessage.objects.create(
                client=client,
                provider=provider,
                source=source,
                external_message_id=external_message_id,
                thread_key=thread_key,
                from_name=from_name,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                contact_id=contact_id,
                metadata=metadata,
                received_at=received_at,
            )
        except (ProgrammingError, OperationalError):
            return Response(
                {"error": "Email inbox table не создана. Выполните миграции (`backend/core/migrations/0169`)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"ok": True, "id": row.id, "deduplicated": False}, status=status.HTTP_201_CREATED)


class UnifiedInboxReplyView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        tzinfo = _get_client_tz(client)

        thread_id = _safe_text(request.data.get("thread_id"))
        channel = _safe_text(request.data.get("channel")).lower()
        text = _safe_text(request.data.get("text"))
        is_course_thread = _parse_course_thread_id(thread_id)[0] is not None

        if not thread_id:
            return Response({"error": "thread_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        if channel not in SUPPORTED_REPLY_CHANNELS:
            return Response(
                {"error": "Канал ответа пока не поддерживается.", "supported": sorted(SUPPORTED_REPLY_CHANNELS)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not text:
            return Response({"error": "Текст ответа пустой."}, status=status.HTTP_400_BAD_REQUEST)
        if not is_course_thread and channel == ProductCourseComment.CHANNEL_COURSES:
            return Response({"error": "Канал courses доступен только для course thread."}, status=status.HTTP_400_BAD_REQUEST)

        author = (
            _safe_text(getattr(request.user, "first_name", None)) and _safe_text(getattr(request.user, "last_name", None))
            and f"{_safe_text(request.user.first_name)} {_safe_text(request.user.last_name)}"
        ) or _safe_text(getattr(request.user, "first_name", None)) or _safe_text(getattr(request.user, "username", None)) or "Менеджер"

        contact_id_raw = request.data.get("contact_id")
        contact_id: int | None = None
        try:
            if contact_id_raw not in (None, ""):
                contact_id = int(contact_id_raw)
        except (TypeError, ValueError):
            contact_id = None

        if is_course_thread:
            try:
                lesson, resolved_contact_id = _resolve_course_lesson_context(
                    client=client,
                    thread_id=thread_id,
                    lesson_id=None,
                    contact_id=contact_id,
                )
                contact = MapContact.objects.filter(id=resolved_contact_id).first()
                course = lesson.module.course
                product = course.product
                contextual_text = (
                    f"Курс: {_safe_text(course.title) or '—'}\n"
                    f"Урок: {_safe_text(lesson.title) or '—'}\n\n"
                    f"{text}"
                )
                external_message_id, metadata = _send_course_message_via_channel(
                    client=client,
                    contact=contact,
                    contact_id=resolved_contact_id,
                    channel=channel,
                    text=contextual_text,
                )
                comment = ProductCourseComment.objects.create(
                    owner=client,
                    contact_id=resolved_contact_id,
                    product_id=int(product.id),
                    course_id=int(course.id),
                    module_id=int(lesson.module_id),
                    lesson_id=int(lesson.id),
                    author_role=ProductCourseComment.AUTHOR_CURATOR,
                    author_user_id=request.user.id if getattr(request.user, "is_authenticated", False) else None,
                    channel=channel,
                    message_text=text,
                    metadata={
                        "thread_id": thread_id,
                        "course_title": _safe_text(course.title),
                        "lesson_title": _safe_text(lesson.title),
                        "external_message_id": external_message_id,
                        **(metadata if isinstance(metadata, dict) else {}),
                    },
                )
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except requests.RequestException as exc:
                return Response({"error": f"Ошибка сети при отправке: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
            except Exception as exc:  # noqa: BLE001
                return Response({"error": f"Не удалось отправить сообщение: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            message = _course_comment_to_message(comment, contact=contact, tzinfo=tzinfo)
            return Response(
                {
                    "ok": True,
                    "thread_id": thread_id,
                    "channel": channel,
                    "message": {
                        "id": message["id"],
                        "channel": message["channel"],
                        "direction": message["direction"],
                        "author": author,
                        "text": message["text"],
                        "createdAtLabel": message["createdAtLabel"],
                        "createdAtSort": message["createdAtSort"],
                    },
                }
            )

        try:
            if channel == "telegram":
                external_message_id, metadata = _send_telegram_reply(client=client, thread_id=thread_id, text=text)
            elif channel == "vk":
                external_message_id, metadata = _send_vk_reply(client=client, thread_id=thread_id, text=text)
            else:
                external_message_id, metadata = _send_email_reply(client=client, thread_id=thread_id, text=text)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except requests.RequestException as exc:
            return Response({"error": f"Ошибка сети при отправке: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:  # noqa: BLE001
            return Response({"error": f"Не удалось отправить сообщение: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        sent_at = timezone.now()
        try:
            log = InboxReplyMessage.objects.create(
                client=client,
                created_by=request.user if getattr(request.user, "is_authenticated", False) else None,
                thread_id=thread_id,
                channel=channel,
                direction=InboxReplyMessage.DIRECTION_OUT,
                contact_id=contact_id,
                author=author,
                text=text,
                external_message_id=external_message_id,
                metadata=metadata if isinstance(metadata, dict) else {},
                sent_at=sent_at,
            )
        except (ProgrammingError, OperationalError):
            return Response(
                {"error": "Таблица исходящих inbox не создана. Выполните миграции (`backend/core/migrations/0170`)."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        message = _reply_log_to_thread_message(log, tzinfo=tzinfo)
        return Response(
            {
                "ok": True,
                "thread_id": thread_id,
                "channel": channel,
                "message": {
                    "id": message["id"],
                    "channel": message["channel"],
                    "direction": message["direction"],
                    "author": message["author"],
                    "text": message["text"],
                    "createdAtLabel": message["createdAtLabel"],
                    "createdAtSort": message["createdAtSort"],
                },
            }
        )


class UnifiedInboxCourseAcceptView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        tzinfo = _get_client_tz(client)
        thread_id = _safe_text(request.data.get("thread_id"))

        lesson_id_raw = request.data.get("lesson_id")
        contact_id_raw = request.data.get("contact_id")
        lesson_id: int | None = None
        contact_id: int | None = None
        try:
            if lesson_id_raw not in (None, ""):
                lesson_id = int(lesson_id_raw)
        except (TypeError, ValueError):
            return Response({"error": "lesson_id must be integer."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if contact_id_raw not in (None, ""):
                contact_id = int(contact_id_raw)
        except (TypeError, ValueError):
            return Response({"error": "contact_id must be integer."}, status=status.HTTP_400_BAD_REQUEST)

        if not thread_id and (lesson_id is None or contact_id is None):
            return Response(
                {"error": "thread_id или связка lesson_id + contact_id обязательны."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        canonical_thread_id = thread_id or _build_course_thread_id(
            owner_id=int(client.id),
            contact_id=int(contact_id),
            lesson_id=int(lesson_id),
        )

        try:
            lesson, resolved_contact_id = _resolve_course_lesson_context(
                client=client,
                thread_id=canonical_thread_id,
                lesson_id=lesson_id,
                contact_id=contact_id,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        course = lesson.module.course
        product = course.product
        now = timezone.now()
        progress, _ = ProductCourseProgress.objects.get_or_create(
            owner=client,
            contact_id=resolved_contact_id,
            lesson_id=int(lesson.id),
            defaults={"completed_at": now},
        )
        first_accept = progress.curator_completed_at is None
        progress.curator_completed_at = now
        progress.curator_user_id = request.user.id
        progress.save(update_fields=["curator_completed_at", "curator_user_id"])

        notified = False
        notify_channel: str | None = None
        comment: ProductCourseComment | None = None
        if first_accept:
            ProductCourseEvent.objects.create(
                owner=client,
                contact_id=resolved_contact_id,
                product_id=int(product.id),
                course_id=int(course.id),
                module_id=int(lesson.module_id),
                lesson_id=int(lesson.id),
                progress_id=int(progress.id),
                event_type=ProductCourseEvent.EVENT_LESSON_ACCEPTED,
                actor_role=ProductCourseEvent.ACTOR_CURATOR,
                actor_user_id=request.user.id,
            )

            notify_text = (
                "Ваш урок принят куратором.\n"
                f"Курс: {_safe_text(course.title) or '—'}\n"
                f"Урок: {_safe_text(lesson.title) or '—'}"
            )
            notified, notify_channel = _notify_contact_about_course_acceptance(
                client=client,
                contact_id=resolved_contact_id,
                text=notify_text,
            )
            comment = ProductCourseComment.objects.create(
                owner=client,
                contact_id=resolved_contact_id,
                product_id=int(product.id),
                course_id=int(course.id),
                module_id=int(lesson.module_id),
                lesson_id=int(lesson.id),
                author_role=ProductCourseComment.AUTHOR_SYSTEM,
                channel=ProductCourseComment.CHANNEL_COURSES,
                message_text=(
                    "Куратор принял урок."
                    + (" Ученик уведомлен." if notified else " Уведомить ученика не удалось.")
                ),
                metadata={
                    "thread_id": canonical_thread_id,
                    "course_title": _safe_text(course.title),
                    "lesson_title": _safe_text(lesson.title),
                    "notified": bool(notified),
                    "notify_channel": notify_channel,
                },
            )

        response_payload: dict[str, Any] = {
            "ok": True,
            "thread_id": canonical_thread_id,
            "lesson_id": int(lesson.id),
            "contact_id": int(resolved_contact_id),
            "accepted": True,
            "already_accepted": not first_accept,
            "notified": bool(notified),
            "notify_channel": notify_channel,
            "curator_completed_at": now,
        }
        if comment is not None:
            message = _course_comment_to_message(
                comment,
                contact=MapContact.objects.filter(id=resolved_contact_id).first(),
                tzinfo=tzinfo,
            )
            response_payload["message"] = {
                "id": message["id"],
                "channel": message["channel"],
                "direction": message["direction"],
                "author": message["author"],
                "text": message["text"],
                "createdAtLabel": message["createdAtLabel"],
                "createdAtSort": message["createdAtSort"],
            }
        return Response(response_payload)


class UnifiedInboxThreadsView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        client = get_active_client(request.user)
        tzinfo = _get_client_tz(client)

        telegram_threads = _build_telegram_threads(client, tzinfo=tzinfo)
        vk_threads = _build_vk_threads(client, tzinfo=tzinfo)
        email_threads = _build_email_threads(client, tzinfo=tzinfo)
        course_threads = _build_course_threads(client, tzinfo=tzinfo)

        inbox_threads = [*telegram_threads, *vk_threads, *email_threads]
        _append_reply_logs_to_threads(client, inbox_threads, tzinfo=tzinfo)
        all_threads = [*inbox_threads, *course_threads]
        all_threads.sort(key=lambda item: int(item.get("lastMessageSort") or 0), reverse=True)

        channel_counts: dict[str, int] = defaultdict(int)
        for item in all_threads:
            channel_counts[_safe_text(item.get("sourceChannel"))] += 1

        return Response(
            {
                "threads": all_threads,
                "sources": {
                    "telegram": {
                        "enabled": True,
                        "thread_count": len(telegram_threads),
                    },
                    "vk": {
                        "enabled": True,
                        "thread_count": len(vk_threads),
                    },
                    "email": {
                        "enabled": True,
                        "thread_count": len(email_threads),
                        "reason": "Источник принимает письма через webhook /api/inbox/email/webhook/<client_uuid>/",
                    },
                    "courses": {
                        "enabled": True,
                        "thread_count": len(course_threads),
                    },
                },
                "counts": dict(channel_counts),
            }
        )
