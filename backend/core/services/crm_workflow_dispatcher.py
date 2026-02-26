from __future__ import annotations

import logging
from typing import Any

from core.models import Client, MapCRMPayment, MapCRMEvent, UserTenantBinding
from core.services.chain_executor import ChainExecutor
from core.services.chain_service import (
    PAYMENT_PAID_CHAIN_KEY,
    POST_MEETING_CHAIN_KEY,
    RESCHEDULE_MEETING_CHAIN_KEY,
    get_or_create_chain_by_key,
)


logger = logging.getLogger(__name__)

CRM_TRIGGER_EVENT_CREATED = "event_created"
CRM_TRIGGER_EVENT_RESCHEDULED = "event_rescheduled"
CRM_TRIGGER_EVENT_CANCELLED = "event_cancelled"
CRM_TRIGGER_PAYMENT_PAID = "payment_paid"

# Default mapping for existing predefined chains.
DEFAULT_CHAIN_KEY_BY_TRIGGER: dict[str, str | None] = {
    CRM_TRIGGER_EVENT_CREATED: POST_MEETING_CHAIN_KEY,
    CRM_TRIGGER_EVENT_RESCHEDULED: RESCHEDULE_MEETING_CHAIN_KEY,
    CRM_TRIGGER_EVENT_CANCELLED: RESCHEDULE_MEETING_CHAIN_KEY,
    CRM_TRIGGER_PAYMENT_PAID: PAYMENT_PAID_CHAIN_KEY,
}


def _normalize_provider(provider: str | None) -> str:
    value = str(provider or "").strip().lower()
    if value == UserTenantBinding.PROVIDER_VK:
        return UserTenantBinding.PROVIDER_VK
    return UserTenantBinding.PROVIDER_TELEGRAM


class CRMWorkflowDispatcher:
    """
    Bridges CRM domain events (meeting/payment) with chain execution.
    """

    def dispatch_trigger(
        self,
        *,
        tenant_id: int,
        contact_id: int | None,
        trigger_key: str,
        trigger_payload: dict[str, Any] | None = None,
        chain_key: str | None = None,
    ) -> dict[str, Any]:
        resolved_trigger_key = str(trigger_key or "").strip().lower()
        if not resolved_trigger_key:
            return {"dispatched": False, "reason": "empty_trigger_key"}

        try:
            contact_id_int = int(contact_id) if contact_id is not None else None
        except (TypeError, ValueError):
            contact_id_int = None
        if not contact_id_int or contact_id_int <= 0:
            return {"dispatched": False, "reason": "missing_contact_id"}

        resolved_chain_key = (
            str(chain_key).strip().lower()
            if chain_key is not None
            else DEFAULT_CHAIN_KEY_BY_TRIGGER.get(resolved_trigger_key)
        )
        if not resolved_chain_key:
            logger.info(
                "CRM workflow skipped: trigger=%s tenant=%s contact=%s (no chain mapping)",
                resolved_trigger_key,
                tenant_id,
                contact_id_int,
            )
            return {"dispatched": False, "reason": "no_chain_mapping", "trigger_key": resolved_trigger_key}

        binding = self._resolve_binding(tenant_id=tenant_id, contact_id=contact_id_int)
        if binding is None:
            logger.info(
                "CRM workflow skipped: trigger=%s tenant=%s contact=%s (no active binding)",
                resolved_trigger_key,
                tenant_id,
                contact_id_int,
            )
            return {"dispatched": False, "reason": "no_active_binding", "trigger_key": resolved_trigger_key}

        provider = _normalize_provider(getattr(binding, "provider", None))
        provider_user_id = self._resolve_provider_user_id(binding=binding, provider=provider)
        if not provider_user_id:
            return {"dispatched": False, "reason": "missing_provider_user_id", "trigger_key": resolved_trigger_key}

        try:
            session_user_id = int(provider_user_id)
        except (TypeError, ValueError):
            logger.warning(
                "CRM workflow skipped: trigger=%s tenant=%s contact=%s provider=%s non-numeric provider_user_id=%r",
                resolved_trigger_key,
                tenant_id,
                contact_id_int,
                provider,
                provider_user_id,
            )
            return {"dispatched": False, "reason": "invalid_provider_user_id", "trigger_key": resolved_trigger_key}

        client = Client.objects.filter(id=tenant_id).only("id").first()
        if client is None:
            return {"dispatched": False, "reason": "tenant_not_found", "trigger_key": resolved_trigger_key}

        try:
            chain = get_or_create_chain_by_key(client, resolved_chain_key)
        except Exception:
            logger.exception(
                "CRM workflow chain resolve failed: trigger=%s tenant=%s chain_key=%s",
                resolved_trigger_key,
                tenant_id,
                resolved_chain_key,
            )
            return {"dispatched": False, "reason": "chain_resolve_failed", "trigger_key": resolved_trigger_key}

        if str(getattr(chain, "status", "") or "").lower() != "active":
            return {
                "dispatched": False,
                "reason": "chain_not_active",
                "trigger_key": resolved_trigger_key,
                "chain_key": resolved_chain_key,
                "chain_status": getattr(chain, "status", None),
            }

        payload = dict(trigger_payload or {})
        initial_context: dict[str, Any] = {
            "contact_id": contact_id_int,
            "trigger_key": resolved_trigger_key,
            "trigger_payload": payload,
        }
        if "event_id" in payload:
            initial_context["event_id"] = payload.get("event_id")
        if "payment_id" in payload:
            initial_context["payment_id"] = payload.get("payment_id")

        channel_meta: dict[str, Any] | None = None
        # `UserTenantBinding` currently doesn't store vk_group_id, keep hook for future.

        executor = ChainExecutor()
        try:
            result = executor.start_chain(
                user_id=session_user_id,
                tenant_id=tenant_id,
                provider=provider,
                provider_user_id=str(provider_user_id),
                channel_meta=channel_meta,
                chain_key=resolved_chain_key,
                initial_context=initial_context,
            )
        except Exception:
            logger.exception(
                "CRM workflow start_chain failed: trigger=%s tenant=%s contact=%s chain_key=%s",
                resolved_trigger_key,
                tenant_id,
                contact_id_int,
                resolved_chain_key,
            )
            return {"dispatched": False, "reason": "start_chain_failed", "trigger_key": resolved_trigger_key}

        from core.tasks.chains import dispatch_chain_actions  # local import to avoid import-time cycles

        try:
            dispatch_chain_actions(
                session_id=result.get("session_id"),
                actions=result.get("actions", []),
            )
        except Exception:
            logger.exception(
                "CRM workflow dispatch actions failed: trigger=%s tenant=%s contact=%s chain_key=%s",
                resolved_trigger_key,
                tenant_id,
                contact_id_int,
                resolved_chain_key,
            )
            return {"dispatched": False, "reason": "dispatch_actions_failed", "trigger_key": resolved_trigger_key}

        return {
            "dispatched": True,
            "trigger_key": resolved_trigger_key,
            "chain_key": resolved_chain_key,
            "session_id": result.get("session_id"),
            "actions_count": len(result.get("actions", [])),
        }

    def dispatch_event_created(self, *, tenant_id: int, event: MapCRMEvent) -> dict[str, Any]:
        return self.dispatch_trigger(
            tenant_id=tenant_id,
            contact_id=getattr(event, "contact_id", None),
            trigger_key=CRM_TRIGGER_EVENT_CREATED,
            trigger_payload=self._build_event_payload(event),
        )

    def dispatch_event_rescheduled(self, *, tenant_id: int, event: MapCRMEvent) -> dict[str, Any]:
        return self.dispatch_trigger(
            tenant_id=tenant_id,
            contact_id=getattr(event, "contact_id", None),
            trigger_key=CRM_TRIGGER_EVENT_RESCHEDULED,
            trigger_payload=self._build_event_payload(event),
        )

    def dispatch_event_cancelled(self, *, tenant_id: int, event: MapCRMEvent) -> dict[str, Any]:
        return self.dispatch_trigger(
            tenant_id=tenant_id,
            contact_id=getattr(event, "contact_id", None),
            trigger_key=CRM_TRIGGER_EVENT_CANCELLED,
            trigger_payload=self._build_event_payload(event),
        )

    def dispatch_payment_paid(
        self,
        *,
        tenant_id: int,
        payment: MapCRMPayment | None = None,
        contact_id: int | None = None,
        payment_payload: dict[str, Any] | None = None,
        chain_key: str | None = None,
    ) -> dict[str, Any]:
        resolved_contact_id = contact_id
        if resolved_contact_id is None and payment is not None:
            resolved_contact_id = getattr(payment, "contact_id", None)

        payload = dict(payment_payload or {})
        if payment is not None and "payment_id" not in payload:
            payload["payment_id"] = int(getattr(payment, "id"))
        if payment is not None and "status" not in payload:
            payload["status"] = str(getattr(payment, "status", "") or "")
        if payment is not None and "amount" not in payload:
            try:
                payload["amount"] = str(getattr(payment, "amount", ""))
            except Exception:
                pass
        if payment is not None and "currency" not in payload:
            payload["currency"] = str(getattr(payment, "currency", "") or "")

        return self.dispatch_trigger(
            tenant_id=tenant_id,
            contact_id=resolved_contact_id,
            trigger_key=CRM_TRIGGER_PAYMENT_PAID,
            trigger_payload=payload,
            chain_key=chain_key,
        )

    def _resolve_binding(self, *, tenant_id: int, contact_id: int) -> UserTenantBinding | None:
        return (
            UserTenantBinding.objects
            .filter(tenant_id=tenant_id, contact_id=contact_id, is_active=True)
            .order_by("-bound_at", "-id")
            .first()
        )

    def _resolve_provider_user_id(self, *, binding: UserTenantBinding, provider: str) -> str | None:
        raw_provider_user_id = str(getattr(binding, "provider_user_id", "") or "").strip()
        if raw_provider_user_id:
            return raw_provider_user_id
        if provider == UserTenantBinding.PROVIDER_TELEGRAM:
            telegram_chat_id = getattr(binding, "telegram_chat_id", None)
            if telegram_chat_id is not None:
                return str(telegram_chat_id)
        return None

    def _build_event_payload(self, event: MapCRMEvent) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": int(getattr(event, "id")),
            "status": str(getattr(event, "status", "") or ""),
            "title": str(getattr(event, "title", "") or ""),
        }
        start_time = getattr(event, "start_time", None)
        end_time = getattr(event, "end_time", None)
        if start_time is not None:
            try:
                payload["start_time"] = start_time.isoformat()
            except Exception:
                payload["start_time"] = str(start_time)
        if end_time is not None:
            try:
                payload["end_time"] = end_time.isoformat()
            except Exception:
                payload["end_time"] = str(end_time)
        event_type_id = getattr(event, "event_type_id", None)
        if event_type_id is not None:
            payload["event_type_id"] = int(event_type_id)
        return payload
