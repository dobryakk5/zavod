from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from .client import Client


class InboxEmailMessage(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="inbox_email_messages")

    provider = models.CharField(max_length=64, blank=True, default="email")
    source = models.CharField(max_length=64, blank=True, default="webhook")
    external_message_id = models.CharField(max_length=512, blank=True, default="")
    thread_key = models.CharField(max_length=512, blank=True, default="", db_index=True)

    from_name = models.CharField(max_length=255, blank=True, default="")
    from_email = models.EmailField(blank=True, default="", db_index=True)
    to_email = models.EmailField(blank=True, default="")
    subject = models.CharField(max_length=500, blank=True, default="")

    body_text = models.TextField(blank=True, default="")
    body_html = models.TextField(blank=True, default="")

    contact_id = models.IntegerField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    received_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-received_at", "-id")
        indexes = [
            models.Index(fields=("client", "received_at")),
            models.Index(fields=("client", "thread_key")),
            models.Index(fields=("client", "from_email")),
            models.Index(fields=("client", "external_message_id")),
        ]

    def __str__(self) -> str:
        sender = self.from_email or self.from_name or "unknown"
        subject = (self.subject or "").strip() or "Без темы"
        return f"{sender}: {subject[:80]}"


class InboxReplyMessage(models.Model):
    DIRECTION_OUT = "out"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="inbox_reply_messages")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inbox_reply_messages_created",
    )

    thread_id = models.CharField(max_length=512, db_index=True)
    channel = models.CharField(max_length=32, db_index=True)
    direction = models.CharField(max_length=8, default=DIRECTION_OUT)

    contact_id = models.IntegerField(null=True, blank=True, db_index=True)
    author = models.CharField(max_length=255, blank=True, default="")
    text = models.TextField(blank=True, default="")
    external_message_id = models.CharField(max_length=512, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-sent_at", "-id")
        indexes = [
            models.Index(fields=("client", "thread_id")),
            models.Index(fields=("client", "channel")),
            models.Index(fields=("client", "sent_at")),
        ]

    def __str__(self) -> str:
        return f"{self.channel}:{self.thread_id}:{self.author or self.created_by_id}"
