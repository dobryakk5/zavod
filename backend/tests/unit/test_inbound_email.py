from types import SimpleNamespace

import pytest

from core.models import Client, InboxEmailMessage
from core.signals.inbound_email import handle_inbound_email
from core.tasks.inbound_email import process_inbound_email_task


@pytest.mark.django_db
def test_process_inbound_email_creates_message():
    client = Client.objects.create(name="Mailgun Tenant", slug="mailgun-tenant")

    process_inbound_email_task.run(
        {
            "event_id": "evt-1",
            "message_id": "<msg-1@example.com>",
            "envelope_sender": "sender@example.com",
            "to_email": "inbox+mailgun-tenant@mg.fibonatty.ru",
            "from_email": "sender@example.com",
            "from_name": "Sender",
            "subject": "Re: Payment question",
            "body_text": "Need invoice copy",
            "body_html": "<p>Need invoice copy</p>",
            "spam_detected": False,
            "spam_score": 0.1,
        }
    )

    row = InboxEmailMessage.objects.get(client=client)
    assert row.external_message_id == "<msg-1@example.com>"
    assert row.source == "mailgun_webhook"
    assert row.provider == "email"
    assert row.thread_key == "email:payment question"
    assert row.from_email == "sender@example.com"
    assert row.to_email == "inbox+mailgun-tenant@mg.fibonatty.ru"
    assert row.metadata["event_id"] == "evt-1"


@pytest.mark.django_db
def test_process_inbound_email_deduplicates_by_message_id():
    client = Client.objects.create(name="Mailgun Tenant", slug="mailgun-tenant")
    payload = {
        "message_id": "<dup@example.com>",
        "to_email": "inbox+mailgun-tenant@mg.fibonatty.ru",
        "from_email": "sender@example.com",
        "subject": "Hello",
    }

    process_inbound_email_task.run(payload)
    process_inbound_email_task.run(payload)

    assert InboxEmailMessage.objects.filter(client=client, external_message_id="<dup@example.com>").count() == 1


@pytest.mark.django_db
def test_process_inbound_email_skips_unknown_client():
    process_inbound_email_task.run(
        {
            "message_id": "<missing@example.com>",
            "to_email": "inbox+missing@mg.fibonatty.ru",
            "from_email": "sender@example.com",
            "subject": "Hello",
        }
    )

    assert InboxEmailMessage.objects.count() == 0


def test_handle_inbound_email_queues_mailgun_payload(monkeypatch):
    captured = {}

    def fake_delay(payload):
        captured["payload"] = payload

    monkeypatch.setattr("core.signals.inbound_email.process_inbound_email_task.delay", fake_delay)

    message = SimpleNamespace(
        from_email=SimpleNamespace(addr_spec="sender@example.com", display_name="Sender"),
        envelope_sender="sender@example.com",
        envelope_recipient="inbox+mailgun-tenant@mg.fibonatty.ru",
        subject="Need help",
        text="Plain body",
        html="<p>Plain body</p>",
        spam_detected=False,
        spam_score=0.0,
        get=lambda key: {
            "Message-ID": "<signal@example.com>",
            "In-Reply-To": "<parent@example.com>",
            "References": "<parent@example.com>",
        }.get(key, ""),
    )
    event = SimpleNamespace(event_id="evt-123", message=message)

    handle_inbound_email(sender=None, event=event, esp_name="Mailgun")

    assert captured["payload"]["message_id"] == "<signal@example.com>"
    assert captured["payload"]["to_email"] == "inbox+mailgun-tenant@mg.fibonatty.ru"
    assert captured["payload"]["in_reply_to"] == "<parent@example.com>"


def test_handle_inbound_email_ignores_non_mailgun(monkeypatch):
    called = {"delay": 0}

    def fake_delay(payload):
        called["delay"] += 1

    monkeypatch.setattr("core.signals.inbound_email.process_inbound_email_task.delay", fake_delay)

    message = SimpleNamespace(
        from_email=None,
        envelope_sender="",
        envelope_recipient="",
        subject="",
        text="",
        html="",
        get=lambda key: "<msg@example.com>" if key == "Message-ID" else "",
    )
    event = SimpleNamespace(event_id="evt-456", message=message)

    handle_inbound_email(sender=None, event=event, esp_name="OtherESP")

    assert called["delay"] == 0
