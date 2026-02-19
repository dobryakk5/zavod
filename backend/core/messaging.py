from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import UserSocialAccount, UserTenantRole


@dataclass(frozen=True)
class ChannelInfo:
    provider: str
    label: str
    provider_id: str
    is_preferred: bool


LABELS = {
    UserSocialAccount.PROVIDER_TELEGRAM: "Telegram",
    UserSocialAccount.PROVIDER_VK: "ВКонтакте",
    "email": "Email",
}


def _get_primary_user_for_client(client) -> Optional[object]:
    role = (
        UserTenantRole.objects.filter(client=client)
        .select_related("user")
        .order_by("id")
        .first()
    )
    return role.user if role else None


def get_available_channels(client) -> list[ChannelInfo]:
    preferred = (client.preferred_channel or "").strip()
    channels: list[ChannelInfo] = []
    seen: set[str] = set()

    user = _get_primary_user_for_client(client)
    if not user:
        return []

    socials = UserSocialAccount.objects.filter(user=user).values("provider", "provider_id")
    for social in socials:
        provider = social["provider"]
        provider_id = str(social["provider_id"])
        key = f"{provider}:{provider_id}"
        if key in seen:
            continue
        seen.add(key)
        channels.append(
            ChannelInfo(
                provider=provider,
                label=LABELS.get(provider, provider),
                provider_id=provider_id,
                is_preferred=(provider == preferred),
            )
        )

    # Backward-compatible fallback for old users without UserSocialAccount records.
    if not channels:
        username = (user.username or "").strip()
        if username.startswith("vk_"):
            channels.append(
                ChannelInfo(
                    provider=UserSocialAccount.PROVIDER_VK,
                    label=LABELS[UserSocialAccount.PROVIDER_VK],
                    provider_id=username.removeprefix("vk_") or str(user.id),
                    is_preferred=(preferred == UserSocialAccount.PROVIDER_VK),
                )
            )
        else:
            channels.append(
                ChannelInfo(
                    provider=UserSocialAccount.PROVIDER_TELEGRAM,
                    label=LABELS[UserSocialAccount.PROVIDER_TELEGRAM],
                    provider_id=username.removeprefix("tg_") if username.startswith("tg_") else str(user.id),
                    is_preferred=(preferred == UserSocialAccount.PROVIDER_TELEGRAM),
                )
            )

    if channels and not any(channel.is_preferred for channel in channels):
        first = channels[0]
        channels[0] = ChannelInfo(
            provider=first.provider,
            label=first.label,
            provider_id=first.provider_id,
            is_preferred=True,
        )

    return channels


def get_preferred_channel(client) -> Optional[ChannelInfo]:
    channels = get_available_channels(client)
    for channel in channels:
        if channel.is_preferred:
            return channel
    return channels[0] if channels else None
