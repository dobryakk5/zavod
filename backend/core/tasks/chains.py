from __future__ import annotations

from datetime import datetime, timedelta
import html
import json
import logging
import re
import secrets
from typing import Any

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from core.models import ChainNode, ChainSession, UserTenantBinding, VkIntegration
from core.services.chain_executor import ChainExecutor


logger = logging.getLogger(__name__)

CHAIN_BUTTON_PREFIX = "chain_btn:"
VK_ID_TOKEN_URL = "https://id.vk.ru/oauth2/auth"
VK_TOKEN_REFRESH_LEEWAY_SECONDS = 60


def _normalize_buttons(buttons: list) -> list[str]:
    normalized = []
    for btn in buttons or []:
        if isinstance(btn, str):
            label = btn
        else:
            label = (btn or {}).get("text")
        if label:
            normalized.append(label)
    return normalized


def _build_inline_keyboard(buttons: list[str]) -> dict:
    keyboard = [[{"text": label, "callback_data": f"{CHAIN_BUTTON_PREFIX}{label}"}] for label in buttons]
    return {"inline_keyboard": keyboard}


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _strip_html(value: str | None) -> str:
    text = (value or "").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = html.unescape(text)
    return _HTML_TAG_RE.sub("", text).strip()


def _build_vk_keyboard(buttons: list[str]) -> str:
    return json.dumps(
        {
            "one_time": False,
            "buttons": [
                [
                    {
                        "action": {
                            "type": "text",
                            "label": label,
                            "payload": json.dumps({"chain_button": label}, ensure_ascii=False),
                        },
                        "color": "primary",
                    }
                ]
                for label in buttons
            ],
        },
        ensure_ascii=False,
    )


def _resolve_vk_integration(tenant_id: int, group_id: int | None) -> VkIntegration | None:
    queryset = VkIntegration.objects.filter(client_id=tenant_id, status=VkIntegration.STATUS_ACTIVE)
    if group_id:
        scoped = queryset.filter(group_id=group_id).order_by("-updated_at", "-id")
        integration = scoped.first()
        if integration:
            return integration
    return queryset.order_by("-updated_at", "-id").first()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    if timezone.is_naive(dt):
        try:
            dt = timezone.make_aware(dt)
        except Exception:  # noqa: BLE001
            return None
    return dt


def _refresh_vk_access_token_if_needed(integration: VkIntegration, *, force: bool = False) -> bool:
    extra = integration.extra if isinstance(integration.extra, dict) else {}
    refresh_token = extra.get("refresh_token")
    device_id = extra.get("device_id")
    if not refresh_token or not device_id:
        return False

    client_id = getattr(settings, "VK_CLIENT_ID", "") or ""
    if not client_id:
        logger.warning("VK token refresh skipped: VK_CLIENT_ID is missing")
        return False

    expires_at = _parse_datetime(extra.get("access_token_expires_at"))
    if not force:
        if expires_at is None:
            return False
        if (expires_at - timezone.now()) > timedelta(seconds=VK_TOKEN_REFRESH_LEEWAY_SECONDS):
            return False

    payload = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "device_id": device_id,
        "state": secrets.token_urlsafe(16),
    }

    try:
        response = requests.post(VK_ID_TOKEN_URL, data=payload, timeout=10)
        data = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Failed to refresh VK access token for integration=%s", integration.id)
        return False

    if data.get("error"):
        logger.warning("VK token refresh failed for integration=%s: %s", integration.id, data.get("error"))
        return False

    new_access_token = data.get("access_token")
    if not new_access_token:
        logger.warning("VK token refresh returned no access_token for integration=%s", integration.id)
        return False

    new_extra = dict(extra)
    new_extra["refresh_token"] = data.get("refresh_token") or refresh_token
    new_extra["device_id"] = device_id
    if data.get("scope"):
        new_extra["scope"] = data.get("scope")
    if data.get("id_token"):
        new_extra["id_token"] = data.get("id_token")

    expires_in = data.get("expires_in")
    if expires_in:
        try:
            expires_seconds = int(expires_in)
            if expires_seconds > 0:
                new_extra["access_token_expires_at"] = (
                    timezone.now() + timedelta(seconds=expires_seconds)
                ).isoformat()
        except (TypeError, ValueError):
            pass

    integration.access_token = new_access_token
    integration.extra = new_extra
    integration.save(update_fields=["access_token", "extra", "updated_at"])
    return True


def _is_vk_token_error(error: Any) -> bool:
    if not isinstance(error, dict):
        return False
    try:
        error_code = int(error.get("error_code"))
    except (TypeError, ValueError):
        error_code = None
    error_msg = str(error.get("error_msg") or "").lower()
    return bool(
        error_code in {5, 27, 28}
        or "access_token" in error_msg
        or "authorization failed" in error_msg
    )


def _vk_messages_send(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post("https://api.vk.com/method/messages.send", data=payload, timeout=10)
        return response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Error while sending VK chain message")
        return None


def _send_telegram_message(
    chat_id: int,
    *,
    text: str | None = None,
    photo_url: str | None = None,
    caption: str | None = None,
    buttons: list[str] | None = None,
) -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token:
        logger.warning("Chain message skipped: TELEGRAM_BOT_TOKEN is missing")
        return False

    if photo_url:
        endpoint = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "HTML"
        if buttons:
            payload["reply_markup"] = _build_inline_keyboard(buttons)
    else:
        endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text or ""}
        payload["parse_mode"] = "HTML"
        if buttons:
            payload["reply_markup"] = _build_inline_keyboard(buttons)

    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error("Failed to send chain message: %s %s", response.status_code, response.text)
            return False
    except Exception:
        logger.exception("Error while sending chain message")
        return False
    return True


def _send_vk_message(
    *,
    tenant_id: int,
    vk_user_id: int | str,
    text: str | None = None,
    photo_url: str | None = None,
    caption: str | None = None,
    buttons: list[str] | None = None,
    group_id: int | None = None,
) -> bool:
    integration = _resolve_vk_integration(tenant_id=tenant_id, group_id=group_id)
    if not integration or not integration.access_token:
        logger.warning("VK chain message skipped: no active VK integration for tenant=%s", tenant_id)
        return False
    _refresh_vk_access_token_if_needed(integration)

    composed_text = _strip_html(text)
    if photo_url:
        photo_text = f"Фото: {photo_url}"
        if caption:
            composed_text = f"{_strip_html(caption)}\n{photo_text}".strip()
        elif composed_text:
            composed_text = f"{composed_text}\n{photo_text}".strip()
        else:
            composed_text = photo_text
    if not composed_text:
        composed_text = " "

    payload: dict[str, Any] = {
        "user_id": int(vk_user_id),
        "random_id": secrets.randbits(31),
        "message": composed_text,
        "access_token": integration.access_token,
        "v": getattr(settings, "VK_API_VERSION", "5.199"),
    }
    if buttons:
        payload["keyboard"] = _build_vk_keyboard(buttons)

    data = _vk_messages_send(payload)
    if data is None:
        return False

    if data.get("error") and _is_vk_token_error(data.get("error")):
        if _refresh_vk_access_token_if_needed(integration, force=True):
            payload["access_token"] = integration.access_token
            data = _vk_messages_send(payload)
            if data is None:
                return False

    if data.get("error"):
        logger.error("Failed to send VK chain message: %s", data.get("error"))
        return False
    return True


def _send_node_message(session: ChainSession, node: ChainNode) -> bool:
    context = dict(session.context or {})
    provider = str(context.get("provider") or UserTenantBinding.PROVIDER_TELEGRAM).lower()
    provider_user_id = str(context.get("provider_user_id") or session.user_id)
    channel_meta = context.get("channel_meta") or {}
    vk_group_id = None
    if isinstance(channel_meta, dict):
        try:
            vk_group_id = int(channel_meta.get("vk_group_id")) if channel_meta.get("vk_group_id") else None
        except (TypeError, ValueError):
            vk_group_id = None

    if node.node_type == "text":
        buttons = _normalize_buttons(node.payload.get("buttons", []))
        if buttons:
            return (
                _send_vk_message(
                    tenant_id=session.tenant_id,
                    vk_user_id=provider_user_id,
                    text=node.payload.get("text", ""),
                    buttons=buttons,
                    group_id=vk_group_id,
                )
                if provider == UserTenantBinding.PROVIDER_VK
                else _send_telegram_message(
                    _safe_int(provider_user_id, session.user_id),
                    text=node.payload.get("text", ""),
                    buttons=buttons,
                )
            )
        return (
            _send_vk_message(
                tenant_id=session.tenant_id,
                vk_user_id=provider_user_id,
                text=node.payload.get("text", ""),
            )
            if provider == UserTenantBinding.PROVIDER_VK
            else _send_telegram_message(_safe_int(provider_user_id, session.user_id), text=node.payload.get("text", ""))
        )
    if node.node_type == "photo":
        return (
            _send_vk_message(
                tenant_id=session.tenant_id,
                vk_user_id=provider_user_id,
                photo_url=node.payload.get("photo_url"),
                caption=node.payload.get("caption"),
                group_id=vk_group_id,
            )
            if provider == UserTenantBinding.PROVIDER_VK
            else _send_telegram_message(
                _safe_int(provider_user_id, session.user_id),
                photo_url=node.payload.get("photo_url"),
                caption=node.payload.get("caption"),
            )
        )
    if node.node_type == "buttons":
        buttons = _normalize_buttons(node.payload.get("buttons", []))
        return (
            _send_vk_message(
                tenant_id=session.tenant_id,
                vk_user_id=provider_user_id,
                text=node.payload.get("text", ""),
                buttons=buttons,
                group_id=vk_group_id,
            )
            if provider == UserTenantBinding.PROVIDER_VK
            else _send_telegram_message(
                _safe_int(provider_user_id, session.user_id),
                text=node.payload.get("text", ""),
                buttons=buttons,
            )
        )
    if node.node_type == "start":
        buttons = _normalize_buttons(node.payload.get("buttons", []))
        return (
            _send_vk_message(
                tenant_id=session.tenant_id,
                vk_user_id=provider_user_id,
                text=node.payload.get("text", ""),
                buttons=buttons,
                group_id=vk_group_id,
            )
            if provider == UserTenantBinding.PROVIDER_VK
            else _send_telegram_message(
                _safe_int(provider_user_id, session.user_id),
                text=node.payload.get("text", ""),
                buttons=buttons,
            )
        )
    return False


def _execute_action(action: dict, session_id: int) -> None:
    action_type = action.get("action_type")
    payload = action.get("payload", {})
    delay = int(action.get("delay_seconds", 0) or 0)

    if action_type in {"send_text", "send_photo", "send_buttons"}:
        if delay > 0:
            node_id = payload.get("node_id")
            if node_id:
                chains_send_delayed_message.apply_async(args=[session_id, node_id], countdown=delay)
            return

        session = ChainSession.objects.filter(id=session_id).first()
        if not session:
            return

        context = dict(session.context or {})
        provider = str(context.get("provider") or UserTenantBinding.PROVIDER_TELEGRAM).lower()
        provider_user_id = str(context.get("provider_user_id") or session.user_id)
        channel_meta = context.get("channel_meta") or {}
        vk_group_id = None
        if isinstance(channel_meta, dict):
            try:
                vk_group_id = int(channel_meta.get("vk_group_id")) if channel_meta.get("vk_group_id") else None
            except (TypeError, ValueError):
                vk_group_id = None

        if action_type == "send_text":
            if provider == UserTenantBinding.PROVIDER_VK:
                _send_vk_message(
                    tenant_id=session.tenant_id,
                    vk_user_id=provider_user_id,
                    text=payload.get("text", ""),
                    group_id=vk_group_id,
                )
            else:
                _send_telegram_message(_safe_int(provider_user_id, session.user_id), text=payload.get("text", ""))
        elif action_type == "send_photo":
            if provider == UserTenantBinding.PROVIDER_VK:
                _send_vk_message(
                    tenant_id=session.tenant_id,
                    vk_user_id=provider_user_id,
                    photo_url=payload.get("photo_url"),
                    caption=payload.get("caption"),
                    group_id=vk_group_id,
                )
            else:
                _send_telegram_message(
                    _safe_int(provider_user_id, session.user_id),
                    photo_url=payload.get("photo_url"),
                    caption=payload.get("caption"),
                )
        elif action_type == "send_buttons":
            buttons = _normalize_buttons(payload.get("buttons", []))
            if provider == UserTenantBinding.PROVIDER_VK:
                _send_vk_message(
                    tenant_id=session.tenant_id,
                    vk_user_id=provider_user_id,
                    text=payload.get("text", ""),
                    buttons=buttons,
                    group_id=vk_group_id,
                )
            else:
                _send_telegram_message(
                    _safe_int(provider_user_id, session.user_id),
                    text=payload.get("text", ""),
                    buttons=buttons,
                )

    if action_type == "schedule_timeout":
        timeout_payload = payload
        chains_check_timeout.apply_async(
            args=[timeout_payload["session_id"], timeout_payload["edge_id"]],
            countdown=int(timeout_payload.get("timeout_seconds", 300)),
        )


@shared_task
def chains_send_delayed_message(session_id: int, node_id: int) -> None:
    session = ChainSession.objects.filter(id=session_id).first()
    if not session:
        return

    if session.status != "active":
        return

    if session.current_node_id != node_id:
        return

    node = ChainNode.objects.filter(id=node_id).first()
    if not node:
        return

    _send_node_message(session, node)


@shared_task
def chains_check_timeout(session_id: int, edge_id: int) -> None:
    executor = ChainExecutor()
    result = executor.process_timeout(session_id=session_id, edge_id=edge_id)
    for action in result.get("actions", []):
        _execute_action(action, session_id)


def dispatch_chain_actions(*, session_id: int | None, actions: list[dict[str, Any]]) -> None:
    if not session_id:
        return
    for action in actions:
        _execute_action(action, int(session_id))


_HTML_TAG_RE = re.compile(r"<[^>]+>")
