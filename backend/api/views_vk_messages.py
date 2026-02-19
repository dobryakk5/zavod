from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.models import UserTenantBinding, VkIntegration
from core.services.chain_executor import ChainExecutor
from core.tasks.chains import dispatch_chain_actions


logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{7,}\d")
_HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
_MENTION_RE = re.compile(r"(?<!\w)@\w+")


def _normalize_entities(text: str) -> list[str]:
    normalized: set[str] = set()
    if _EMAIL_RE.search(text):
        normalized.add("email")
    if _PHONE_RE.search(text):
        normalized.add("phone")
    if _URL_RE.search(text):
        normalized.add("url")
    if _HASHTAG_RE.search(text):
        normalized.add("hashtag")
    if _MENTION_RE.search(text):
        normalized.add("mention")
    return sorted(normalized)


def _parse_vk_button_payload(raw_payload: Any) -> str | None:
    if not raw_payload:
        return None
    payload = raw_payload
    if isinstance(raw_payload, str):
        raw_payload = raw_payload.strip()
        if not raw_payload:
            return None
        try:
            payload = json.loads(raw_payload)
        except ValueError:
            return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("chain_button")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_user_message(message: dict[str, Any]) -> dict[str, Any]:
    text = str(message.get("text") or "").strip()
    payload = _parse_vk_button_payload(message.get("payload"))
    attachments = message.get("attachments") or []

    user_message: dict[str, Any] = {}
    if text:
        user_message["text"] = text
    if payload:
        user_message["button"] = payload

    message_type = "text" if text else None
    for attachment in attachments:
        attachment_type = (attachment or {}).get("type")
        if attachment_type in {"photo", "video", "audio", "doc", "sticker", "audio_message"}:
            key_map = {
                "doc": "document",
                "audio_message": "voice",
            }
            mapped = key_map.get(attachment_type, attachment_type)
            user_message[mapped] = True
            if message_type is None:
                message_type = mapped

    if message.get("geo"):
        user_message["location"] = True
        if message_type is None:
            message_type = "location"

    if message_type:
        user_message["message_type"] = message_type

    entities = _normalize_entities(text)
    if entities:
        user_message["entities"] = entities

    return user_message


class VkMessageCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        event_type = str(payload.get("type") or "")

        if event_type == "confirmation":
            token = (getattr(settings, "VK_CALLBACK_CONFIRMATION_TOKEN", "") or "").strip()
            return HttpResponse(token, content_type="text/plain; charset=utf-8")

        expected_secret = (getattr(settings, "VK_CALLBACK_SECRET", "") or "").strip()
        if expected_secret and payload.get("secret") != expected_secret:
            return HttpResponse("forbidden", status=403, content_type="text/plain; charset=utf-8")

        if event_type != "message_new":
            return HttpResponse("ok", content_type="text/plain; charset=utf-8")

        try:
            self._handle_message_new(payload)
        except Exception:  # noqa: BLE001
            logger.exception("VK callback processing failed")

        return HttpResponse("ok", content_type="text/plain; charset=utf-8")

    def _handle_message_new(self, payload: dict[str, Any]) -> None:
        obj = payload.get("object") if isinstance(payload.get("object"), dict) else {}
        message = obj.get("message") if isinstance(obj.get("message"), dict) else {}

        group_id_raw = payload.get("group_id") or obj.get("group_id")
        from_id_raw = message.get("from_id")
        if group_id_raw is None or from_id_raw is None:
            return

        try:
            group_id = abs(int(group_id_raw))
            from_id = int(from_id_raw)
        except (TypeError, ValueError):
            return

        # Ignore messages from communities/system.
        if from_id <= 0:
            return

        integration = (
            VkIntegration.objects.filter(group_id=group_id, status=VkIntegration.STATUS_ACTIVE)
            .order_by("-updated_at", "-id")
            .first()
        )
        if not integration:
            return

        binding = (
            UserTenantBinding.objects.filter(
                tenant_id=integration.client_id,
                provider=UserTenantBinding.PROVIDER_VK,
                provider_user_id=str(from_id),
            )
            .order_by("-bound_at", "-id")
            .first()
        )
        if not binding:
            binding = UserTenantBinding.objects.create(
                tenant_id=integration.client_id,
                provider=UserTenantBinding.PROVIDER_VK,
                provider_user_id=str(from_id),
                telegram_chat_id=None,
                is_active=True,
                bound_at=timezone.now(),
            )
        elif not binding.is_active:
            binding.is_active = True
            binding.bound_at = timezone.now()
            binding.save(update_fields=["is_active", "bound_at"])

        text_value = str(message.get("text") or "").strip().lower()
        executor = ChainExecutor()
        channel_meta = {"vk_group_id": group_id}

        if text_value in {"welcome", "старт", "начать"}:
            result = executor.start_chain(
                user_id=from_id,
                tenant_id=integration.client_id,
                provider=UserTenantBinding.PROVIDER_VK,
                provider_user_id=str(from_id),
                channel_meta=channel_meta,
            )
            dispatch_chain_actions(
                session_id=result.get("session_id"),
                actions=result.get("actions", []),
            )
            return

        user_message = _build_user_message(message)
        if not user_message:
            return

        result = executor.process_user_message(
            user_id=from_id,
            tenant_id=integration.client_id,
            user_message=user_message,
            provider=UserTenantBinding.PROVIDER_VK,
            provider_user_id=str(from_id),
            channel_meta=channel_meta,
        )
        if result.get("session_status") == "none":
            return

        dispatch_chain_actions(
            session_id=result.get("session_id"),
            actions=result.get("actions", []),
        )
        if result.get("session_status") == "completed":
            dispatch_chain_actions(
                session_id=result.get("session_id"),
                actions=[
                    {
                        "action_type": "send_text",
                        "payload": {"text": "Цепочка завершена."},
                        "delay_seconds": 0,
                    }
                ],
            )

