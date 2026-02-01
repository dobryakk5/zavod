from django.utils import timezone

from core.models import Client, UserTenantBinding


class TelegramUserService:
    def __init__(self, binding_model=UserTenantBinding, client_model=Client):
        self.binding_model = binding_model
        self.client_model = client_model

    def bind_user_to_tenant(
        self,
        telegram_chat_id: int,
        tenant_id: int | str,
        contact_id: int | None = None,
    ) -> dict:
        """Bind a Telegram user to a client (tenant)."""
        tenant = self.client_model.objects.filter(id=tenant_id).first()
        if tenant is None:
            raise ValueError(f"Tenant {tenant_id} not found")

        self.binding_model.objects.filter(
            telegram_chat_id=telegram_chat_id,
            is_active=True,
        ).exclude(tenant=tenant).update(is_active=False)

        defaults = {
            "bound_at": timezone.now(),
            "is_active": True,
        }
        if contact_id is not None:
            defaults["contact_id"] = contact_id

        binding, created = self.binding_model.objects.get_or_create(
            telegram_chat_id=telegram_chat_id,
            tenant=tenant,
            defaults=defaults,
        )

        if created:
            status = "newly_bound"
        else:
            update_fields = ["bound_at", "is_active"]
            binding.bound_at = timezone.now()
            binding.is_active = True
            if contact_id is not None and binding.contact_id != contact_id:
                binding.contact_id = contact_id
                update_fields.append("contact_id")
            binding.save(update_fields=update_fields)
            status = "already_bound"

        return {"status": status, "binding": binding}

    def get_active_binding(self, telegram_chat_id: int) -> UserTenantBinding | None:
        return (
            self.binding_model.objects.select_related("tenant")
            .filter(telegram_chat_id=telegram_chat_id, is_active=True)
            .order_by("-bound_at", "-id")
            .first()
        )

    def get_active_client(self, telegram_chat_id: int) -> Client | None:
        binding = self.get_active_binding(telegram_chat_id)
        if binding is None:
            return None
        return binding.tenant

    def get_user_tenants(self, telegram_chat_id: int) -> list[UserTenantBinding]:
        return list(
            self.binding_model.objects.select_related("tenant")
            .filter(telegram_chat_id=telegram_chat_id)
            .order_by("-bound_at", "-id")
        )
