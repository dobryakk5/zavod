from __future__ import annotations

import logging

from typing import Optional

from .models import Client, SocialAccount
from .telegram_client import (
    TelegramPublisher,
    normalize_telegram_channel_identifier,
    run_async_task,
)


logger = logging.getLogger(__name__)


def _publisher_session_name(client: Client) -> str:
    return f"session_publisher_client_{client.id}"


def _fetch_telegram_channel_title(
    client: Client,
    channel: str,
    *,
    bot_token: Optional[str] = None,
) -> Optional[str]:
    if not client.telegram_api_id or not client.telegram_api_hash:
        return None

    publisher = TelegramPublisher(
        api_id=client.telegram_api_id,
        api_hash=client.telegram_api_hash,
        session_name=_publisher_session_name(client),
        bot_token=bot_token or None,
    )

    async def _task():
        await publisher.connect()
        try:
            return await publisher.get_channel_title(channel)
        finally:
            await publisher.disconnect()

    try:
        return run_async_task(_task())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось получить название Telegram канала %s: %s", channel, exc)
        return None


def ensure_telegram_account_metadata(
    social_account: SocialAccount,
    *,
    channel_value: Optional[str] = None,
    force_refresh: bool = False,
) -> Optional[str]:
    """
    Обновить название Telegram SocialAccount, получив его из API.
    """
    if social_account.platform != "telegram":
        return None

    extra = dict(social_account.extra or {})
    normalized_channel = normalize_telegram_channel_identifier(
        channel_value or extra.get("channel") or ""
    )
    if not normalized_channel:
        return None

    changed = False
    if extra.get("channel") != normalized_channel:
        extra["channel"] = normalized_channel
        changed = True

    channel_title = extra.get("channel_title")
    need_fetch = force_refresh or changed or not channel_title
    fetched_title = None

    if need_fetch:
        fetched_title = _fetch_telegram_channel_title(
            social_account.client,
            normalized_channel,
            bot_token=social_account.access_token or None,
        )
        if fetched_title:
            extra["channel_title"] = fetched_title
            channel_title = fetched_title
            changed = True

    desired_name = channel_title or normalized_channel

    if social_account.extra != extra:
        social_account.extra = extra
        changed = True

    if desired_name and social_account.name != desired_name:
        social_account.name = desired_name
        changed = True

    if changed:
        social_account.save(update_fields=["name", "extra"])

    return desired_name


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

    if account:
        extra = dict(account.extra or {})
        channel_changed = extra.get("channel") != normalized_channel
        updated_fields: list[str] = []

        if channel_changed or extra.get("source") != "client_settings":
            extra["source"] = "client_settings"
            extra["channel"] = normalized_channel
            account.extra = extra
            updated_fields.append("extra")

        if account.access_token is None:
            account.access_token = ""
            updated_fields.append("access_token")

        if updated_fields:
            account.save(update_fields=updated_fields)
        ensure_telegram_account_metadata(
            account,
            channel_value=normalized_channel,
            force_refresh=channel_changed,
        )
        return account

    account = SocialAccount.objects.create(
        client=client,
        platform="telegram",
        name=normalized_channel,
        access_token="",
        extra={
            "channel": normalized_channel,
            "source": "client_settings",
        },
    )
    ensure_telegram_account_metadata(account, channel_value=normalized_channel, force_refresh=True)
    return account
