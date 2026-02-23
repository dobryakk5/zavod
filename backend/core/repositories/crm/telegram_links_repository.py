from __future__ import annotations

from core.models import Client, TelegramTask, UserTenantBinding


def get_latest_telegram_binding(client: Client, contact_id: int) -> UserTenantBinding | None:
    binding_qs = (
        UserTenantBinding.objects.filter(
            tenant=client,
            contact_id=contact_id,
            provider=UserTenantBinding.PROVIDER_TELEGRAM,
        )
        .order_by("-bound_at", "-id")
    )
    return binding_qs.filter(is_active=True).first() or binding_qs.first()


def get_latest_telegram_task(client: Client, telegram_chat_id: int) -> TelegramTask | None:
    return (
        TelegramTask.objects.filter(
            client=client,
            telegram_user_id=telegram_chat_id,
        )
        .order_by("-received_at", "-id")
        .first()
    )

