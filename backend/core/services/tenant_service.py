import base64
import json
from datetime import datetime

from django.conf import settings

from core.models import Client


class TenantService:
    def __init__(self, client_model=Client, bot_username: str | None = None):
        self.client_model = client_model
        self.bot_username = bot_username or getattr(settings, "TELEGRAM_BOT_USERNAME", "")

    def generate_telegram_link(self, tenant_id: int | str, contact_id: int | None = None) -> str:
        """Generate a permanent Telegram deep link for a client."""
        tenant = self.client_model.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} not found")
        if not self.bot_username:
            raise ValueError("TELEGRAM_BOT_USERNAME is not configured")

        payload = {
            "tid": str(tenant.id),
            "ts": int(datetime.now().timestamp()),
        }
        if contact_id is not None:
            payload["cid"] = int(contact_id)

        encoded = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("utf-8").rstrip("=")

        if len(encoded) > 64:
            raise ValueError("Encoded payload exceeds Telegram limit")

        return f"https://t.me/{self.bot_username}?start={encoded}"
