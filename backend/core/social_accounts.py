from __future__ import annotations

from typing import Optional

from .models import Client, SocialAccount
from .telegram_client import normalize_telegram_channel_identifier


DEFAULT_TELEGRAM_ACCOUNT_NAME = "Telegram канал из настроек"


def _build_default_account_name(channel: str) -> str:
    """Собрать человеко-понятное имя аккаунта на основе канала."""
    return f"{DEFAULT_TELEGRAM_ACCOUNT_NAME} ({channel})"


def sync_client_default_telegram_account(
    client: Client,
    channel_value: Optional[str] = None,
) -> Optional[SocialAccount]:
    """
    Убедиться, что у клиента есть SocialAccount для Telegram канала из настроек.

    Если канал указан — создаем/обновляем специальный SocialAccount с extra.source=client_settings.
    Если канал очищен — удаляем такой SocialAccount.

    Returns:
        Найденный или созданный SocialAccount, либо None если канал отсутствует.
    """
    channel_input = channel_value if channel_value is not None else client.telegram_client_channel
    normalized_channel = normalize_telegram_channel_identifier(channel_input or "")

    accounts = list(
        SocialAccount.objects.filter(
            client=client,
            platform="telegram",
            extra__source="client_settings",
        ).order_by("id")
    )
    account = accounts[0] if accounts else None

    # Если ранее было создано несколько "системных" аккаунтов, удаляем дубликаты
    for duplicate in accounts[1:]:
        duplicate.delete()

    if not normalized_channel:
        if account:
            account.delete()
        return None

    desired_name = _build_default_account_name(normalized_channel)

    if account:
        updated_fields: list[str] = []
        extra = dict(account.extra or {})

        if extra.get("channel") != normalized_channel or extra.get("source") != "client_settings":
            extra["channel"] = normalized_channel
            extra["source"] = "client_settings"
            account.extra = extra
            updated_fields.append("extra")

        if account.name != desired_name:
            account.name = desired_name
            updated_fields.append("name")

        if account.access_token is None:
            account.access_token = ""
            updated_fields.append("access_token")

        if updated_fields:
            account.save(update_fields=updated_fields)

        return account

    return SocialAccount.objects.create(
        client=client,
        platform="telegram",
        name=desired_name,
        access_token="",
        extra={
            "channel": normalized_channel,
            "source": "client_settings",
        },
    )
