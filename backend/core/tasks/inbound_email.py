from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from core.models import Client, InboxEmailMessage, MapContact

logger = logging.getLogger(__name__)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _resolve_client(to_email: str) -> Client | None:
    if not to_email or "@" not in to_email:
        return None

    local = to_email.split("@", 1)[0].strip().lower()
    slug = local.split("+", 1)[1] if "+" in local else local
    slug = slug.strip()
    if not slug:
        return None

    return Client.objects.filter(slug=slug).first()


def _derive_email_thread_key(*, subject: str, from_email: str, raw_thread_key: str) -> str:
    raw = _safe_text(raw_thread_key)
    if raw:
        return raw if raw.startswith("email:") else f"email:{raw[:220]}"

    normalized_subject = _safe_text(subject).lower()
    if normalized_subject:
        for prefix in ("re:", "fw:", "fwd:", "ответ:", "пересл:"):
            if normalized_subject.startswith(prefix):
                normalized_subject = normalized_subject[len(prefix):].strip()

    base = normalized_subject or _safe_text(from_email).lower() or "email-thread"
    return f"email:{base[:220]}"


def _resolve_contact_id(from_email: str) -> int | None:
    email = _safe_text(from_email)
    if not email:
        return None

    try:
        match = MapContact.objects.filter(email__iexact=email).values("id").first()
    except (ProgrammingError, OperationalError):
        return None

    if not match:
        return None
    return int(match["id"])


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="core.tasks.process_inbound_email",
)
def process_inbound_email_task(self, payload: dict[str, Any]) -> None:
    message_id = _safe_text(payload.get("message_id"))
    if not message_id:
        logger.warning("inbound_email: missing message_id")
        return

    try:
        to_email = _safe_text(payload.get("to_email"))
        from_email = _safe_text(payload.get("from_email"))
        subject = _safe_text(payload.get("subject"))
        client = _resolve_client(to_email)

        if client is None:
            logger.warning(
                "inbound_email: no client found for to_email=%s message_id=%s",
                to_email,
                message_id,
            )
            return

        thread_key = _derive_email_thread_key(
            subject=subject,
            from_email=from_email,
            raw_thread_key=_safe_text(payload.get("thread_key")),
        )
        contact_id = _resolve_contact_id(from_email)

        _, created = InboxEmailMessage.objects.get_or_create(
            client=client,
            external_message_id=message_id,
            defaults={
                "provider": "email",
                "source": "mailgun_webhook",
                "thread_key": thread_key,
                "from_name": _safe_text(payload.get("from_name")),
                "from_email": from_email,
                "to_email": to_email,
                "subject": subject,
                "body_text": _safe_text(payload.get("body_text")),
                "body_html": str(payload.get("body_html") or ""),
                "contact_id": contact_id,
                "received_at": timezone.now(),
                "metadata": {
                    "event_id": _safe_text(payload.get("event_id")),
                    "envelope_sender": _safe_text(payload.get("envelope_sender")),
                    "spam_detected": payload.get("spam_detected"),
                    "spam_score": payload.get("spam_score"),
                    "in_reply_to": _safe_text(payload.get("in_reply_to")),
                    "references": _safe_text(payload.get("references")),
                },
            },
        )

        if not created:
            logger.debug("inbound_email: duplicate message_id=%s, skipped", message_id)

    except Exception as exc:
        logger.exception("inbound_email: error processing message_id=%s", message_id)
        raise self.retry(exc=exc)
