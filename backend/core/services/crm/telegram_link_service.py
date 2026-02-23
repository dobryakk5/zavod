from __future__ import annotations

from core.models import Client
from core.repositories.crm import contacts_repository, telegram_links_repository
from core.services.tenant_service import TenantService


def build_contact_telegram_link_payload(*, client: Client, contact_id: int) -> dict:
    contact_row = contacts_repository.get_contact_telegram_row(contact_id)
    if contact_row is None:
        raise LookupError("Контакт не найден.")

    contact_tg_username = contact_row.get("tg_username")
    tenant_service = TenantService()
    link = tenant_service.generate_telegram_link(client.id, contact_id=contact_id)

    binding = telegram_links_repository.get_latest_telegram_binding(client=client, contact_id=contact_id)

    telegram_chat_id = None
    tg_name = None
    is_connected = False
    if binding is not None:
        telegram_chat_id = binding.telegram_chat_id
        is_connected = bool(binding.is_active)
        if contact_tg_username:
            tg_name = contact_tg_username
        else:
            task = telegram_links_repository.get_latest_telegram_task(
                client=client,
                telegram_chat_id=telegram_chat_id,
            )
            if task and task.tg_name:
                tg_name = task.tg_name
            else:
                tg_name = f"tg_{telegram_chat_id}"

    return {
        "contact_id": int(contact_id),
        "tenant_id": client.id,
        "telegram_chat_id": telegram_chat_id,
        "tg_name": tg_name,
        "is_connected": is_connected,
        "link": link,
    }

