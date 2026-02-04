from __future__ import annotations

import logging
from typing import Any

import requests
from celery import shared_task
from django.conf import settings
from core.models import ChainNode, ChainSession
from core.services.chain_executor import ChainExecutor


logger = logging.getLogger(__name__)

CHAIN_BUTTON_PREFIX = "chain_btn:"


def _build_inline_keyboard(buttons: list[str]) -> dict:
    keyboard = [[{"text": label, "callback_data": f"{CHAIN_BUTTON_PREFIX}{label}"}] for label in buttons]
    return {"inline_keyboard": keyboard}


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
        if buttons:
            payload["reply_markup"] = _build_inline_keyboard(buttons)
    else:
        endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text or ""}
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


def _send_node_message(user_id: int, node: ChainNode) -> bool:
    if node.node_type == "text":
        return _send_telegram_message(user_id, text=node.payload.get("text", ""))
    if node.node_type == "photo":
        return _send_telegram_message(
            user_id,
            photo_url=node.payload.get("photo_url"),
            caption=node.payload.get("caption"),
        )
    if node.node_type == "buttons":
        return _send_telegram_message(
            user_id,
            text=node.payload.get("text", ""),
            buttons=node.payload.get("buttons", []),
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

        if action_type == "send_text":
            _send_telegram_message(session.user_id, text=payload.get("text", ""))
        elif action_type == "send_photo":
            _send_telegram_message(
                session.user_id,
                photo_url=payload.get("photo_url"),
                caption=payload.get("caption"),
            )
        elif action_type == "send_buttons":
            _send_telegram_message(
                session.user_id,
                text=payload.get("text", ""),
                buttons=payload.get("buttons", []),
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

    _send_node_message(session.user_id, node)


@shared_task
def chains_check_timeout(session_id: int, edge_id: int) -> None:
    executor = ChainExecutor()
    result = executor.process_timeout(session_id=session_id, edge_id=edge_id)
    for action in result.get("actions", []):
        _execute_action(action, session_id)
