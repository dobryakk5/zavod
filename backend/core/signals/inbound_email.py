from __future__ import annotations

from anymail.signals import inbound
from django.dispatch import receiver

from core.tasks.inbound_email import process_inbound_email_task


@receiver(inbound)
def handle_inbound_email(sender, event, esp_name, **kwargs):
    if str(esp_name).strip().lower() != "mailgun":
        return

    message = event.message
    message_id = str(message.get("Message-ID") or "").strip()
    if not message_id:
        return

    from_email = message.from_email.addr_spec if message.from_email else ""
    from_name = message.from_email.display_name if message.from_email else ""
    to_email = message.envelope_recipient or ""

    payload = {
        "event_id": getattr(event, "event_id", "") or "",
        "message_id": message_id,
        "envelope_sender": message.envelope_sender or "",
        "envelope_recipient": to_email,
        "from_email": from_email,
        "from_name": from_name,
        "to_email": to_email,
        "subject": message.subject or "",
        "body_text": message.text or "",
        "body_html": message.html or "",
        "spam_detected": getattr(message, "spam_detected", None),
        "spam_score": getattr(message, "spam_score", None),
        "in_reply_to": str(message.get("In-Reply-To") or "").strip(),
        "references": str(message.get("References") or "").strip(),
    }
    process_inbound_email_task.delay(payload)
