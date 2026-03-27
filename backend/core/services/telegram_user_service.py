import os
import re

from django.db import connection
from django.utils import timezone

from core.models import Client, UserTenantBinding


class TelegramUserService:
    def __init__(self, binding_model=UserTenantBinding, client_model=Client):
        self.binding_model = binding_model
        self.client_model = client_model
        self.provider_telegram = getattr(UserTenantBinding, "PROVIDER_TELEGRAM", "telegram")
        self.provider_vk = getattr(UserTenantBinding, "PROVIDER_VK", "vk")
        self.provider_contact = getattr(UserTenantBinding, "PROVIDER_CONTACT", "contact")

    def _map_schema(self) -> str:
        schema = os.getenv("MAP_SCHEMA", "map").strip()
        if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
            return "map"
        return schema

    def _store_contact_telegram_data(
        self,
        *,
        contact_id: int,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> None:
        schema = self._map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {schema}.contacts
                SET tg_user_id = %s,
                    tg_username = %s,
                    tg_connected_at = %s
                WHERE id = %s
                """,
                [telegram_user_id, telegram_username, timezone.now().date(), contact_id],
            )

    def bind_identity_to_tenant(
        self,
        *,
        provider: str,
        provider_user_id: int | str,
        tenant_id: int | str,
        contact_id: int | None = None,
        telegram_username: str | None = None,
    ) -> dict:
        provider = (provider or "").strip().lower()
        if provider not in {self.provider_telegram, self.provider_vk}:
            raise ValueError(f"Unsupported provider: {provider}")

        provider_user_id_str = str(provider_user_id).strip()
        if not provider_user_id_str:
            raise ValueError("provider_user_id is required")

        tenant = self.client_model.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} not found")

        self.binding_model.objects.filter(
            provider=provider,
            provider_user_id=provider_user_id_str,
            is_active=True,
        ).exclude(tenant=tenant).update(is_active=False)

        defaults = {
            "bound_at": timezone.now(),
            "is_active": True,
            "telegram_chat_id": int(provider_user_id_str) if provider == self.provider_telegram else None,
        }
        if contact_id is not None:
            defaults["contact_id"] = contact_id

        binding, created = self.binding_model.objects.get_or_create(
            provider=provider,
            provider_user_id=provider_user_id_str,
            tenant=tenant,
            defaults=defaults,
        )

        if provider == self.provider_telegram and contact_id is not None:
            self._store_contact_telegram_data(
                contact_id=contact_id,
                telegram_user_id=int(provider_user_id_str),
                telegram_username=telegram_username,
            )

        if contact_id is not None:
            self._ensure_contact_binding(
                tenant=tenant,
                contact_id=int(contact_id),
            )

        if created:
            status = "newly_bound"
        else:
            update_fields = ["bound_at", "is_active"]
            binding.bound_at = timezone.now()
            binding.is_active = True
            if provider == self.provider_telegram:
                telegram_chat_id = int(provider_user_id_str)
                if binding.telegram_chat_id != telegram_chat_id:
                    binding.telegram_chat_id = telegram_chat_id
                    update_fields.append("telegram_chat_id")
            if contact_id is not None and binding.contact_id != contact_id:
                binding.contact_id = contact_id
                update_fields.append("contact_id")
            binding.save(update_fields=update_fields)
            status = "already_bound"

        return {"status": status, "binding": binding}

    def _ensure_contact_binding(self, *, tenant: Client, contact_id: int) -> None:
        provider_user_id = f"contact:{int(contact_id)}"
        binding, created = self.binding_model.objects.get_or_create(
            tenant=tenant,
            provider=self.provider_contact,
            provider_user_id=provider_user_id,
            defaults={
                "contact_id": int(contact_id),
                "is_active": True,
                "bound_at": timezone.now(),
            },
        )
        if created:
            return

        update_fields: list[str] = []
        if binding.contact_id != int(contact_id):
            binding.contact_id = int(contact_id)
            update_fields.append("contact_id")
        if not binding.is_active:
            binding.is_active = True
            update_fields.append("is_active")
        binding.bound_at = timezone.now()
        update_fields.append("bound_at")
        if update_fields:
            binding.save(update_fields=update_fields)

    def bind_user_to_tenant(
        self,
        telegram_chat_id: int,
        tenant_id: int | str,
        contact_id: int | None = None,
        telegram_username: str | None = None,
    ) -> dict:
        """Bind a Telegram user to a client (tenant)."""
        return self.bind_identity_to_tenant(
            provider=self.provider_telegram,
            provider_user_id=telegram_chat_id,
            tenant_id=tenant_id,
            contact_id=contact_id,
            telegram_username=telegram_username,
        )

    def get_active_binding_by_identity(self, *, provider: str, provider_user_id: int | str) -> UserTenantBinding | None:
        provider = (provider or "").strip().lower()
        provider_user_id_str = str(provider_user_id).strip()
        if not provider_user_id_str:
            return None

        return (
            self.binding_model.objects.select_related("tenant")
            .filter(provider=provider, provider_user_id=provider_user_id_str, is_active=True)
            .order_by("-bound_at", "-id")
            .first()
        )

    def get_active_binding(self, telegram_chat_id: int) -> UserTenantBinding | None:
        return self.get_active_binding_by_identity(
            provider=self.provider_telegram,
            provider_user_id=telegram_chat_id,
        )

    def get_active_client(self, telegram_chat_id: int) -> Client | None:
        binding = self.get_active_binding(telegram_chat_id)
        if binding is None:
            return None
        return binding.tenant

    def get_user_tenants(self, telegram_chat_id: int) -> list[UserTenantBinding]:
        return list(
            self.binding_model.objects.select_related("tenant")
            .filter(provider=self.provider_telegram, provider_user_id=str(telegram_chat_id))
            .order_by("-bound_at", "-id")
        )
