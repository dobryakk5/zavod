from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

from django.db import connection
from django.db.models import Q
from django.utils import timezone

from core.models import (
    Chain,
    ChainCondition,
    ChainEdge,
    ChainNode,
    ChainSession,
    Client,
    ClientProduct,
    ContactFact,
    MapAvailabilityEvent,
    MapCRMEvent,
    MapCRMPayment,
    MapContactTag,
    UserTenantBinding,
)
from core.services.chain_service import get_or_create_chain, get_or_create_chain_by_key


logger = logging.getLogger(__name__)
MAX_CHAIN_HISTORY_ITEMS = 200
MAX_AI_HISTORY_ITEMS = 20

_NODE_TYPE_TO_ACTION: dict[str, str] = {
    "photo": "send_photo",
    "buttons": "send_buttons",
}
_EVENT_PRODUCT_TYPE_KEYS = frozenset({"мероприятие", "event"})


def _is_chain_active(obj: Any) -> bool:
    """Return True when the chain attached to *obj* (Chain or ChainSession) has status 'active'."""
    chain = getattr(obj, "chain", obj)
    return str(getattr(chain, "status", "") or "").lower() == "active"


class ChainExecutor:
    """
    Executes tenant chains for multiple inbound providers (Telegram, VK).
    """

    def start_chain(
        self,
        user_id: int,
        tenant_id: int,
        *,
        provider: str = UserTenantBinding.PROVIDER_TELEGRAM,
        provider_user_id: str | None = None,
        channel_meta: dict[str, Any] | None = None,
        chain_id: int | None = None,
        chain_key: str | None = None,
        initial_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = _normalize_provider(provider)
        resolved_provider_user_id = str(provider_user_id or user_id)
        chain = get_or_create_chain_for_tenant(tenant_id, chain_id=chain_id, chain_key=chain_key)
        if not chain.start_node_id:
            raise ValueError("Chain has no start node")
        if not _is_chain_active(chain):
            return {"session_id": None, "actions": [], "session_status": "chain_not_active"}

        session = self._get_active_session(
            user_id=user_id,
            tenant_id=tenant_id,
            chain_id=chain.id,
            provider=provider,
        )
        preserved_ai_summary: dict[str, Any] | None = None
        if session and isinstance(session.context, dict):
            ai_summary_value = session.context.get("ai_summary")
            if isinstance(ai_summary_value, dict) and ai_summary_value:
                preserved_ai_summary = dict(ai_summary_value)
        if not preserved_ai_summary:
            preserved_ai_summary = self._get_latest_ai_summary(
                user_id=user_id,
                tenant_id=tenant_id,
                chain_id=chain.id,
                provider=provider,
            )

        context = {
            "provider": provider,
            "provider_user_id": resolved_provider_user_id,
        }
        if preserved_ai_summary:
            context["ai_summary"] = preserved_ai_summary
        if channel_meta:
            context["channel_meta"] = dict(channel_meta)
        if initial_context:
            for key, value in dict(initial_context).items():
                if key in {"provider", "provider_user_id"}:
                    continue
                context[key] = value

        if session:
            session.context = context
            session.current_node_id = chain.start_node_id
            session.status = "active"
            session.last_activity_at = timezone.now()
            session.save(update_fields=["context", "current_node_id", "status", "last_activity_at", "updated_at"])
        else:
            session = ChainSession.objects.create(
                user_id=user_id,
                tenant_id=tenant_id,
                chain=chain,
                current_node_id=chain.start_node_id,
                status="active",
                context=context,
            )

        actions = self._advance_to_node(session, chain.start_node_id)
        return {"session_id": session.id, "actions": actions}

    def process_user_message(
        self,
        user_id: int,
        tenant_id: int,
        user_message: dict[str, Any],
        *,
        provider: str = UserTenantBinding.PROVIDER_TELEGRAM,
        provider_user_id: str | None = None,
        channel_meta: dict[str, Any] | None = None,
        session_id: int | None = None,
    ) -> dict[str, Any]:
        provider = _normalize_provider(provider)
        resolved_provider_user_id = str(provider_user_id or user_id)
        session = self._get_active_session(
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            session_id=session_id,
        )
        if not session:
            return {"session_id": None, "actions": [], "session_status": "none"}
        if not _is_chain_active(session):
            return {"session_id": session.id, "actions": [], "session_status": "chain_not_active"}

        context = dict(session.context or {})
        context_provider = _normalize_provider(context.get("provider"))
        if context_provider != provider:
            context["provider"] = provider
        if str(context.get("provider_user_id") or "") != resolved_provider_user_id:
            context["provider_user_id"] = resolved_provider_user_id
        if channel_meta:
            current_meta = dict(context.get("channel_meta") or {})
            merged_meta = {**current_meta, **channel_meta}
            if merged_meta != current_meta:
                context["channel_meta"] = merged_meta

        context = self._append_incoming_history(
            context=context,
            session=session,
            user_message=user_message,
            provider=provider,
            provider_user_id=resolved_provider_user_id,
        )
        self._save_session_context(session, context)

        if not session.current_node_id:
            logger.warning("Chain session %s has no current node", session.id)
            return {"session_id": session.id, "actions": [], "session_status": session.status}

        current_node = ChainNode.objects.filter(id=session.current_node_id).first()
        if current_node is None:
            logger.warning("Chain node %s not found for session %s", session.current_node_id, session.id)
            return {"session_id": session.id, "actions": [], "session_status": session.status}

        if current_node.node_type == "timer":
            return {"session_id": session.id, "actions": [], "session_status": session.status}

        if current_node.node_type == "router":
            matching_edge = self._select_router_edge(
                current_node,
                user_message,
                context,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                provider=provider,
                provider_user_id=resolved_provider_user_id,
            )
            if not matching_edge:
                session.status = "completed"
                session.completed_at = timezone.now()
                session.save(update_fields=["status", "completed_at", "updated_at"])
                return {"session_id": session.id, "actions": [], "session_status": "completed"}

            context = dict(session.context or {})
            context.setdefault("answers", {})
            context["answers"][str(session.current_node_id)] = user_message
            context["last_message_at"] = timezone.now().isoformat()

            self._save_session_context(session, context)

            actions = self._advance_to_node(session, matching_edge.target_node_id)
            return {"session_id": session.id, "actions": actions, "session_status": "active"}

        if current_node.node_type == "booking":
            return self._process_booking_message(
                session=session,
                current_node=current_node,
                user_message=user_message,
                provider=provider,
                provider_user_id=resolved_provider_user_id,
            )
        if current_node.node_type == "product_list":
            return self._process_product_list_message(
                session=session,
                current_node=current_node,
                user_message=user_message,
            )
        if current_node.node_type == "ai_assistant":
            return self._process_ai_assistant_message(
                session=session,
                current_node=current_node,
                user_message=user_message,
            )

        edges = self._get_edges_with_conditions(session.current_node_id)

        matching_edge = None
        for edge in edges:
            if evaluate_conditions(
                edge["conditions"],
                user_message,
                    context,
                    user_id=session.user_id,
                    tenant_id=session.tenant_id,
                    provider=provider,
                    provider_user_id=resolved_provider_user_id,
                ):
                    matching_edge = edge
                    break

        if not matching_edge:
            session.status = "completed"
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at", "updated_at"])
            return {"session_id": session.id, "actions": [], "session_status": "completed"}

        context = dict(session.context or {})
        context.setdefault("answers", {})
        context["answers"][str(session.current_node_id)] = user_message
        context["last_message_at"] = timezone.now().isoformat()

        self._save_session_context(session, context)

        actions = self._advance_to_node(session, matching_edge["target_node_id"])
        return {"session_id": session.id, "actions": actions, "session_status": "active"}

    def process_timeout(self, session_id: int, edge_id: int) -> dict[str, Any]:
        edge = ChainEdge.objects.filter(id=edge_id).first()
        if edge is None:
            logger.warning("Timeout edge %s not found", edge_id)
            return {"actions": []}

        session = ChainSession.objects.filter(id=session_id).first()
        if session is None:
            logger.warning("Timeout session %s not found", session_id)
            return {"actions": []}

        if session.status != "active":
            return {"actions": []}
        if not _is_chain_active(session):
            return {"actions": []}

        if session.current_node_id != edge.source_node_id:
            return {"actions": []}

        actions = self._advance_to_node(session, edge.target_node_id)
        return {"actions": actions}

    def _advance_to_node(self, session: ChainSession, node_id: int) -> list[dict[str, Any]]:
        node = ChainNode.objects.filter(id=node_id).first()
        if node is None:
            logger.warning("Chain node %s not found", node_id)
            return []

        session.current_node_id = node_id
        session.last_activity_at = timezone.now()
        session.save(update_fields=["current_node_id", "last_activity_at", "updated_at"])

        actions: list[dict[str, Any]] = []
        if node.node_type == "timer":
            payload = dict(node.payload or {})
            raw_duration = payload.get("duration_seconds", 60)
            try:
                duration = max(1, int(raw_duration))
            except (TypeError, ValueError):
                duration = 60

            edges = self._get_edges_with_conditions(node_id)
            if not edges:
                logger.warning("Timer node %s has no outgoing edges", node_id)
                return actions

            first_edge = edges[0]
            actions.append({
                "action_type": "schedule_timeout",
                "payload": {
                    "session_id": session.id,
                    "edge_id": first_edge["id"],
                    "timeout_seconds": duration,
                },
                "delay_seconds": 0,
            })
            return actions

        if node.node_type == "booking":
            actions.extend(self._enter_booking_node(session, node))
            return actions
        if node.node_type == "product_list":
            actions.extend(self._enter_product_list_node(session, node))
            return actions
        if node.node_type == "ai_assistant":
            actions.extend(self._enter_ai_assistant_node(session, node))
            return actions

        if node.node_type in ("start", "text", "photo", "buttons"):
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            # start/text: prefer send_buttons when buttons are present, otherwise send_text
            if node.node_type in ("start", "text"):
                action_type = "send_buttons" if payload.get("buttons") else "send_text"
            else:
                action_type = _NODE_TYPE_TO_ACTION[node.node_type]
            actions.append({
                "action_type": action_type,
                "payload": payload,
                "delay_seconds": node.delay_seconds,
            })

        edges = self._get_edges_with_conditions(node_id)

        # Если узел отправляет кнопки и следующий — router,
        # сразу переводим сессию на router. Иначе первое нажатие кнопки
        # приходит когда current_node ещё = start/buttons и попадает
        # в ветку обычных edges (ChainCondition) где ничего нет → session completed.
        has_buttons = node.node_type in ("start", "buttons", "text") and bool(
            (node.payload or {}).get("buttons")
        )
        if has_buttons and len(edges) == 1:
            next_node = ChainNode.objects.filter(id=edges[0]["target_node_id"]).first()
            if next_node and next_node.node_type == "router":
                session.current_node_id = next_node.id
                session.last_activity_at = timezone.now()
                session.save(update_fields=["current_node_id", "last_activity_at", "updated_at"])

        for edge in edges:
            for cond in edge.get("conditions", []):
                if cond.get("condition_type") == "timeout":
                    timeout_seconds = int(cond.get("params", {}).get("timeout_seconds", 300))
                    actions.append({
                        "action_type": "schedule_timeout",
                        "payload": {
                            "session_id": session.id,
                            "edge_id": edge["id"],
                            "timeout_seconds": timeout_seconds,
                        },
                        "delay_seconds": 0,
                    })

        return actions

    def _enter_product_list_node(self, session: ChainSession, node: ChainNode) -> list[dict[str, Any]]:
        payload = dict(node.payload or {})
        context = dict(session.context or {})
        node_key = str(node.id)

        products = list(
            ClientProduct.objects
            .filter(owner_id=session.tenant_id, status=ClientProduct.STATUS_ACTIVE)
            .order_by("name", "id")[:20]
        )
        if not products:
            no_products_text = str(payload.get("no_products_text") or "Продуктов пока нет.")
            return [{
                "action_type": "send_text",
                "payload": {"text": no_products_text, "node_id": node.id},
                "delay_seconds": node.delay_seconds,
            }]

        products_map: dict[str, int] = {}
        buttons: list[str] = []
        for item in products:
            base_label = str(item.name or "").strip() or f"Продукт #{item.id}"
            label = base_label
            suffix = 2
            while label in products_map:
                label = f"{base_label} ({suffix})"
                suffix += 1
            products_map[label] = int(item.id)
            buttons.append(label)

        context.setdefault("product_list_state", {})
        context["product_list_state"][node_key] = {"products_map": products_map}
        self._save_session_context(session, context)

        intro_text = str(payload.get("intro_text") or "Выберите продукт:")
        return [{
            "action_type": "send_buttons",
            "payload": {
                "text": intro_text,
                "buttons": buttons,
                "node_id": node.id,
            },
            "delay_seconds": node.delay_seconds,
        }]

    def _enter_booking_node(self, session: ChainSession, node: ChainNode) -> list[dict[str, Any]]:
        payload = dict(node.payload or {})
        mode = str(payload.get("mode") or "create").strip().lower()
        context = dict(session.context or {})
        node_key = str(node.id)

        if mode == "reschedule":
            contact_id = _resolve_contact_id(
                session_context=context,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                provider=str(context.get("provider") or ""),
                provider_user_id=str(context.get("provider_user_id") or ""),
            )
            nearest_event = None
            if contact_id:
                nearest_event = (
                    MapCRMEvent.objects
                    .filter(contact_id=contact_id, status="scheduled", start_time__gt=timezone.now())
                    .order_by("start_time")
                    .first()
                )
            if nearest_event:
                slot_label = _format_booking_slot_label(nearest_event.start_time, payload.get("timezone"))
                context.setdefault("booking_state", {})
                context["booking_state"][node_key] = {
                    "step": "confirm_nearest",
                    "mode": "reschedule",
                    "event_id": int(nearest_event.id),
                    "event_label": slot_label,
                }
                self._save_session_context(session, context)

                text = str(payload.get("confirm_reschedule_text") or "Переносим встречу {slot}?")
                return [{
                    "action_type": "send_buttons",
                    "payload": {
                        "text": text.replace("{slot}", slot_label),
                        "buttons": ["Да", "Выбрать другую"],
                        "node_id": node.id,
                    },
                    "delay_seconds": node.delay_seconds,
                }]

        # create mode or fallback when nothing to reschedule
        return self._send_slots(
            session=session,
            node=node,
            context=context,
            event_id=None,
            mode="create",
            delay_seconds=node.delay_seconds,
        )

    def _send_slots(
        self,
        *,
        session: ChainSession,
        node: ChainNode,
        context: dict[str, Any],
        event_id: int | None,
        mode: str,
        delay_seconds: int = 0,
    ) -> list[dict[str, Any]]:
        payload = dict(node.payload or {})
        node_key = str(node.id)
        slots = self._build_booking_slots(tenant_id=session.tenant_id, exclude_event_id=event_id)

        if not slots:
            no_slots_text = str(payload.get("no_slots_text") or "Свободных слотов пока нет.")
            context.setdefault("booking_state", {})
            context["booking_state"][node_key] = {
                "step": "no_slots",
                "mode": mode,
                "event_id": event_id,
            }
            self._save_session_context(session, context)
            return [{
                "action_type": "send_text",
                "payload": {"text": no_slots_text, "node_id": node.id},
                "delay_seconds": delay_seconds,
            }]

        slot_map: dict[str, dict[str, Any]] = {}
        buttons: list[str] = []
        tz_name = payload.get("timezone")
        for item in slots:
            base_label = _format_booking_slot_label(item["start_time"], tz_name)
            label = base_label
            suffix = 2
            while label in slot_map:
                label = f"{base_label} ({suffix})"
                suffix += 1
            slot_map[label] = {
                "start_time": item["start_time"].isoformat(),
                "duration_minutes": int(item["duration_minutes"]),
            }
            buttons.append(label)

        context.setdefault("booking_state", {})
        context["booking_state"][node_key] = {
            "step": "select_slot",
            "mode": mode,
            "event_id": event_id,
            "slots_map": slot_map,
        }
        self._save_session_context(session, context)

        slots_intro_text = str(payload.get("slots_intro_text") or "Выберите удобное время:")
        return [{
            "action_type": "send_buttons",
            "payload": {
                "text": slots_intro_text,
                "buttons": buttons,
                "node_id": node.id,
            },
            "delay_seconds": delay_seconds,
        }]

    def _build_booking_slots(self, *, tenant_id: int, exclude_event_id: int | None = None) -> list[dict[str, Any]]:
        now = timezone.now()
        window_end = now + timedelta(days=90)
        tenant_tz_name = _get_tenant_timezone_name(tenant_id)
        availability_items = list(
            MapAvailabilityEvent.objects
            .filter(tenant_id=tenant_id, start_time__gt=now)
            .order_by("start_time")[:30]
        )
        if not availability_items:
            return []

        busy_qs = MapCRMEvent.objects.filter(status="scheduled", start_time__lt=window_end)
        if exclude_event_id:
            busy_qs = busy_qs.exclude(id=exclude_event_id)
        busy_intervals: list[tuple[datetime, datetime]] = []
        for event in busy_qs.only("start_time", "end_time"):
            start_at = _coerce_datetime(event.start_time)
            if not start_at:
                continue
            end_at = _coerce_datetime(event.end_time) or (start_at + timedelta(hours=1))
            busy_intervals.append((start_at, end_at))
        for interval_start, interval_end in _collect_product_event_intervals(
            tenant_id=tenant_id,
            tenant_tz_name=tenant_tz_name,
        ):
            if interval_start < window_end and interval_end > now:
                busy_intervals.append((interval_start, interval_end))

        result: list[dict[str, Any]] = []
        for availability in availability_items:
            start_at = _coerce_datetime(availability.start_time)
            if not start_at:
                continue
            duration = int(getattr(availability, "duration_minutes", 0) or 60)
            if duration <= 0:
                duration = 60
            end_at = start_at + timedelta(minutes=duration)
            if end_at <= now:
                continue
            if _interval_overlaps_any(start_at, end_at, busy_intervals):
                continue
            result.append({
                "start_time": start_at,
                "duration_minutes": duration,
            })

        return result[:10]

    def _process_booking_message(
        self,
        *,
        session: ChainSession,
        current_node: ChainNode,
        user_message: dict[str, Any],
        provider: str,
        provider_user_id: str,
    ) -> dict[str, Any]:
        payload = dict(current_node.payload or {})
        context = dict(session.context or {})
        node_key = str(current_node.id)
        booking_state_root = context.get("booking_state")
        booking_state = booking_state_root.get(node_key) if isinstance(booking_state_root, dict) else None
        state = booking_state if isinstance(booking_state, dict) else {}
        step = str(state.get("step") or "")
        pressed_raw = user_message.get("button") or user_message.get("text") or ""
        pressed = str(pressed_raw).strip()

        if not step:
            return self._respond(session, self._enter_booking_node(session, current_node))

        if step == "confirm_nearest":
            if pressed == "Да":
                return self._respond(
                    session,
                    self._send_slots(
                        session=session,
                        node=current_node,
                        context=context,
                        event_id=_safe_int(state.get("event_id"), None),
                        mode="reschedule",
                    ),
                )
            if pressed == "Выбрать другую":
                contact_id = _resolve_contact_id(
                    session_context=context,
                    user_id=session.user_id,
                    tenant_id=session.tenant_id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                )
                events_qs = MapCRMEvent.objects.none()
                if contact_id:
                    events_qs = (
                        MapCRMEvent.objects
                        .filter(contact_id=contact_id, status="scheduled", start_time__gt=timezone.now())
                        .order_by("start_time")[:10]
                    )
                events = list(events_qs)
                if not events:
                    no_events_text = str(
                        payload.get("no_events_text")
                        or payload.get("no_slots_text")
                        or "Нет встреч для переноса."
                    )
                    return self._respond(session, [{
                        "action_type": "send_text",
                        "payload": {"text": no_events_text, "node_id": current_node.id},
                        "delay_seconds": 0,
                    }])

                events_map: dict[str, int] = {}
                buttons: list[str] = []
                tz_name = payload.get("timezone")
                for event in events:
                    base_label = _format_booking_slot_label(event.start_time, tz_name)
                    label = base_label
                    suffix = 2
                    while label in events_map:
                        label = f"{base_label} ({suffix})"
                        suffix += 1
                    events_map[label] = int(event.id)
                    buttons.append(label)

                context.setdefault("booking_state", {})
                context["booking_state"][node_key] = {
                    "step": "select_event",
                    "mode": "reschedule",
                    "events_map": events_map,
                }
                self._save_session_context(session, context)

                return self._respond(session, [{
                    "action_type": "send_buttons",
                    "payload": {
                        "text": str(payload.get("select_event_text") or "Выберите встречу для переноса:"),
                        "buttons": buttons,
                        "node_id": current_node.id,
                    },
                    "delay_seconds": 0,
                }])
            return {"session_id": session.id, "actions": [], "session_status": "active"}

        if step == "select_event":
            events_map = state.get("events_map") if isinstance(state.get("events_map"), dict) else {}
            event_id = _safe_int(events_map.get(pressed), None)
            if not event_id:
                return {"session_id": session.id, "actions": [], "session_status": "active"}
            return self._respond(
                session,
                self._send_slots(
                    session=session,
                    node=current_node,
                    context=context,
                    event_id=event_id,
                    mode="reschedule",
                ),
            )

        if step == "select_slot":
            slots_map = state.get("slots_map") if isinstance(state.get("slots_map"), dict) else {}
            slot_data = slots_map.get(pressed) if isinstance(slots_map.get(pressed), dict) else None
            if not slot_data:
                return {"session_id": session.id, "actions": [], "session_status": "active"}

            start_at = _parse_iso_datetime(slot_data.get("start_time"))
            if not start_at:
                logger.warning("Booking slot parse failed for node=%s session=%s", current_node.id, session.id)
                return {"session_id": session.id, "actions": [], "session_status": "active"}

            duration_minutes = _safe_int(slot_data.get("duration_minutes"), 60) or 60
            if duration_minutes <= 0:
                duration_minutes = 60
            end_at = start_at + timedelta(minutes=duration_minutes)

            mode = str(state.get("mode") or "create")
            event_id = _safe_int(state.get("event_id"), None)
            contact_id = _resolve_contact_id(
                session_context=context,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                provider=provider,
                provider_user_id=provider_user_id,
            )
            if not contact_id:
                return self._respond(session, [{
                    "action_type": "send_text",
                    "payload": {
                        "text": "Для записи войдите как контакт через Telegram или VK.",
                        "node_id": current_node.id,
                    },
                    "delay_seconds": 0,
                }])

            if self._is_booking_interval_busy(
                start_at=start_at,
                end_at=end_at,
                tenant_id=session.tenant_id,
                exclude_event_id=event_id if mode == "reschedule" else None,
            ):
                busy_text = str(payload.get("slot_busy_text") or "Этот слот уже занят. Выберите другой.")
                return self._respond(session, [{
                    "action_type": "send_text",
                    "payload": {"text": busy_text, "node_id": current_node.id},
                    "delay_seconds": 0,
                }])

            booked_event_id: int | None = None
            if mode == "reschedule" and event_id:
                update_qs = MapCRMEvent.objects.filter(id=event_id, contact_id=contact_id)
                if not update_qs.exists():
                    return self._respond(session, [{
                        "action_type": "send_text",
                        "payload": {
                            "text": "Встреча для переноса больше недоступна.",
                            "node_id": current_node.id,
                        },
                        "delay_seconds": 0,
                    }])
                update_qs.update(start_time=start_at, end_time=end_at)
                booked_event_id = int(event_id)
            else:
                created = MapCRMEvent.objects.create(
                    contact_id=contact_id,
                    event_type_id=None,
                    title=str(payload.get("event_title") or "Встреча"),
                    description="",
                    start_time=start_at,
                    end_time=end_at,
                    location="",
                    status="scheduled",
                    notes="",
                )
                booked_event_id = int(created.id)

            context["booked_event_id"] = booked_event_id
            context["booked_slot"] = pressed
            context.setdefault("booking_state", {})
            context["booking_state"].pop(node_key, None)
            self._save_session_context(session, context)

            confirmation_text = str(payload.get("confirmation_text") or "Вы записаны на {slot}!").replace("{slot}", pressed)
            actions: list[dict[str, Any]] = [{
                "action_type": "send_text",
                "payload": {"text": confirmation_text, "node_id": current_node.id},
                "delay_seconds": 0,
            }]

            edges = self._get_edges_with_conditions(current_node.id)
            if edges:
                actions.extend(self._advance_to_node(session, int(edges[0]["target_node_id"])))
            return self._respond(session, actions)

        if step == "no_slots":
            return self._respond(
                session,
                self._send_slots(
                    session=session,
                    node=current_node,
                    context=context,
                    event_id=_safe_int(state.get("event_id"), None),
                    mode=str(state.get("mode") or "create"),
                ),
            )

        return {"session_id": session.id, "actions": [], "session_status": "active"}

    def _process_product_list_message(
        self,
        *,
        session: ChainSession,
        current_node: ChainNode,
        user_message: dict[str, Any],
    ) -> dict[str, Any]:
        context = dict(session.context or {})
        node_key = str(current_node.id)

        state_root = context.get("product_list_state")
        state = state_root.get(node_key) if isinstance(state_root, dict) else None
        products_map = (
            state.get("products_map")
            if isinstance(state, dict) and isinstance(state.get("products_map"), dict)
            else {}
        )

        pressed = str(user_message.get("button") or user_message.get("text") or "").strip()
        product_id = _safe_int(products_map.get(pressed), None)
        if not product_id:
            return self._respond(session, self._enter_product_list_node(session, current_node))

        context["selected_product_id"] = product_id
        context["selected_product_name"] = pressed
        context.setdefault("product_list_state", {})
        context["product_list_state"].pop(node_key, None)
        self._save_session_context(session, context)

        edges = self._get_edges_with_conditions(current_node.id)
        if not edges:
            session.status = "completed"
            session.completed_at = timezone.now()
            session.save(update_fields=["status", "completed_at", "updated_at"])
            return {"session_id": session.id, "actions": [], "session_status": "completed"}

        actions = self._advance_to_node(session, int(edges[0]["target_node_id"]))
        return {"session_id": session.id, "actions": actions, "session_status": "active"}

    def _is_booking_interval_busy(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        tenant_id: int,
        exclude_event_id: int | None = None,
    ) -> bool:
        query = MapCRMEvent.objects.filter(
            status="scheduled",
            start_time__lt=end_at,
            end_time__gt=start_at,
        )
        if exclude_event_id:
            query = query.exclude(id=exclude_event_id)
        if query.exists():
            return True

        tenant_tz_name = _get_tenant_timezone_name(tenant_id)
        product_intervals = _collect_product_event_intervals(
            tenant_id=tenant_id,
            tenant_tz_name=tenant_tz_name,
        )
        return _interval_overlaps_any(start_at, end_at, product_intervals)

    def _enter_ai_assistant_node(self, session: ChainSession, node: ChainNode) -> list[dict[str, Any]]:
        payload = dict(node.payload or {})
        context = dict(session.context or {})
        node_key = str(node.id)
        summary_raw = (context.get("ai_summary") or {}).get(node_key) if isinstance(context.get("ai_summary"), dict) else None
        summary = str(summary_raw).strip() if summary_raw is not None else None
        if summary == "":
            summary = None

        contact_id = _resolve_contact_id(
            session_context=context,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            provider=str(context.get("provider") or ""),
            provider_user_id=str(context.get("provider_user_id") or ""),
        )
        contact_facts = _build_contact_facts_context(contact_id, session.tenant_id) if contact_id else None

        context.setdefault("ai_history", {})
        context["ai_history"][node_key] = []
        self._save_session_context(session, context)

        ai_response = _call_ai(
            system_prompt=_build_ai_system_prompt(payload, summary=summary, contact_facts=contact_facts),
            history=[],
            user_text=None,
        )
        if not ai_response:
            logger.error("AI assistant node %s: empty response on enter", node.id)
            return []

        message_text = str(ai_response.get("message") or "").strip()
        if not message_text:
            return []

        history = [{"role": "assistant", "content": message_text}]
        context.setdefault("ai_history", {})
        context["ai_history"][node_key] = history[-MAX_AI_HISTORY_ITEMS:]
        self._save_session_context(session, context)

        return [{
            "action_type": "send_text",
            "payload": {"text": message_text, "node_id": node.id},
            "delay_seconds": node.delay_seconds,
        }]

    def _process_ai_assistant_message(
        self,
        *,
        session: ChainSession,
        current_node: ChainNode,
        user_message: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(current_node.payload or {})
        context = dict(session.context or {})
        node_key = str(current_node.id)
        summary_raw = (context.get("ai_summary") or {}).get(node_key) if isinstance(context.get("ai_summary"), dict) else None
        summary = str(summary_raw).strip() if summary_raw is not None else None
        if summary == "":
            summary = None

        ai_history_raw = (context.get("ai_history") or {}).get(node_key)
        history: list[dict[str, Any]] = ai_history_raw if isinstance(ai_history_raw, list) else []

        user_text = str(user_message.get("text") or user_message.get("button") or "").strip()
        if not user_text:
            return {"session_id": session.id, "actions": [], "session_status": "active"}

        contact_id = _resolve_contact_id(
            session_context=context,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            provider=str(context.get("provider") or ""),
            provider_user_id=str(context.get("provider_user_id") or ""),
        )
        contact_facts = _build_contact_facts_context(contact_id, session.tenant_id) if contact_id else None

        ai_response = _call_ai(
            system_prompt=_build_ai_system_prompt(payload, summary=summary, contact_facts=contact_facts),
            history=history,
            user_text=user_text,
        )
        if not ai_response:
            logger.error("AI assistant node %s: empty response", current_node.id)
            return {"session_id": session.id, "actions": [], "session_status": "active"}

        message_text = str(ai_response.get("message") or "").strip()
        intent_value = ai_response.get("intent")
        intent = str(intent_value).strip() if intent_value is not None else ""
        if not intent or intent.lower() == "null":
            intent = ""

        raw_intents = payload.get("intents") if isinstance(payload.get("intents"), list) else []
        allowed_intents = {
            str(item.get("id") or "").strip()
            for item in raw_intents
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        if intent and allowed_intents and intent not in allowed_intents:
            logger.warning(
                "AI assistant node %s returned unknown intent '%s' (allowed=%s)",
                current_node.id,
                intent,
                sorted(allowed_intents),
            )
            intent = ""

        updated_history = list(history)
        updated_history.append({"role": "user", "content": user_text})
        if message_text:
            updated_history.append({"role": "assistant", "content": message_text})
        updated_history = updated_history[-MAX_AI_HISTORY_ITEMS:]

        context.setdefault("ai_history", {})
        context["ai_history"][node_key] = updated_history
        if intent:
            context["ai_intent"] = intent
        else:
            context.pop("ai_intent", None)

        edge = None
        if intent:
            edge = (
                ChainEdge.objects
                .filter(source_node_id=current_node.id, source_port_id=intent)
                .order_by("priority", "id")
                .first()
            )

        if edge:
            summary_system_prompt = str(payload.get("system_prompt") or "").strip()
            if summary:
                summary_system_prompt = (
                    f"{summary_system_prompt}\n\n"
                    "Контекст предыдущих диалогов:\n"
                    f"{summary}"
                ).strip()
            summary_text = _summarize_ai_history(
                system_prompt=summary_system_prompt,
                history=updated_history,
            )
            if summary_text:
                context.setdefault("ai_summary", {})
                context["ai_summary"][node_key] = summary_text

            contact_id = _resolve_contact_id(
                session_context=context,
                user_id=session.user_id,
                tenant_id=session.tenant_id,
                provider=str(context.get("provider") or ""),
                provider_user_id=str(context.get("provider_user_id") or ""),
            )
            if contact_id:
                _update_contact_facts(
                    contact_id=contact_id,
                    tenant_id=session.tenant_id,
                    session_id=session.id,
                    history=updated_history,
                )

        self._save_session_context(session, context)

        actions: list[dict[str, Any]] = []
        if message_text:
            actions.append({
                "action_type": "send_text",
                "payload": {"text": message_text, "node_id": current_node.id},
                "delay_seconds": 0,
            })
        if edge:
            actions.extend(self._advance_to_node(session, edge.target_node_id))

        return {"session_id": session.id, "actions": actions, "session_status": "active"}

    @staticmethod
    def _respond(session: ChainSession, actions: list[dict[str, Any]]) -> dict[str, Any]:
        return {"session_id": session.id, "actions": actions, "session_status": "active"}

    @staticmethod
    def _save_session_context(session: ChainSession, context: dict[str, Any]) -> None:
        """Persist updated context and refresh last_activity_at in a single save call."""
        session.context = context
        session.last_activity_at = timezone.now()
        session.save(update_fields=["context", "last_activity_at", "updated_at"])

    def _get_edges_with_conditions(self, source_node_id: int) -> list[dict[str, Any]]:
        edges = list(
            ChainEdge.objects.filter(source_node_id=source_node_id).order_by("priority", "id")
        )
        edge_ids = [edge.id for edge in edges]
        if not edge_ids:
            return []

        conditions_by_edge: dict[int, list[dict[str, Any]]] = {edge_id: [] for edge_id in edge_ids}
        for cond in ChainCondition.objects.filter(edge_id__in=edge_ids).order_by("created_at", "id"):
            conditions_by_edge[cond.edge_id].append({
                "id": cond.id,
                "edge_id": cond.edge_id,
                "condition_type": cond.condition_type,
                "params": cond.params or {},
            })

        edge_payload = []
        for edge in edges:
            edge_payload.append({
                "id": edge.id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "priority": edge.priority,
                "source_port_id": edge.source_port_id,
                "conditions": conditions_by_edge.get(edge.id, []),
            })
        return edge_payload

    def _select_router_edge(
        self,
        node: ChainNode,
        user_message: dict[str, Any],
        session_context: dict[str, Any],
        *,
        user_id: int | None = None,
        tenant_id: int | None = None,
        provider: str = UserTenantBinding.PROVIDER_TELEGRAM,
        provider_user_id: str | None = None,
    ) -> ChainEdge | None:
        conditions = node.payload.get("conditions") or []
        if not conditions:
            return None

        ordered = sorted(
            enumerate(conditions),
            key=lambda item: int(item[1].get("port_index") if item[1].get("port_index") is not None else item[0]),
        )
        for _, cond in ordered:
            cond_type = cond.get("condition_type")
            params = cond.get("params", {})
            if cond_type == "fallback":
                matched = True
            else:
                matched = _evaluate_single_condition(
                    cond_type or "",
                    params,
                    user_message,
                    session_context,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                )
            if not matched:
                continue

            cond_id = cond.get("id")
            if not cond_id:
                continue
            edge = (
                ChainEdge.objects
                .filter(source_node_id=node.id, source_port_id=cond_id)
                .order_by("priority", "id")
                .first()
            )
            if edge is not None:
                return edge

        return None

    def _get_active_session(
        self,
        *,
        user_id: int,
        tenant_id: int,
        provider: str,
        chain_id: int | None = None,
        session_id: int | None = None,
    ) -> ChainSession | None:
        queryset = ChainSession.objects.filter(user_id=user_id, tenant_id=tenant_id, status="active")
        if session_id is not None:
            queryset = queryset.filter(id=session_id)
        if chain_id is not None:
            queryset = queryset.filter(chain_id=chain_id)
        limit = 1 if session_id is not None else 10
        sessions = list(queryset.order_by("-last_activity_at")[:limit])
        if not sessions:
            return None

        for session in sessions:
            context_provider = _normalize_provider((session.context or {}).get("provider"))
            if context_provider == provider:
                return session

        # Backward-compatible fallback for legacy sessions without provider in context.
        # For explicit session targeting we prefer strict routing and do not fallback.
        if session_id is None:
            return sessions[0]
        return None

    def _get_latest_ai_summary(
        self,
        *,
        user_id: int,
        tenant_id: int,
        chain_id: int,
        provider: str,
    ) -> dict[str, Any] | None:
        sessions = list(
            ChainSession.objects
            .filter(user_id=user_id, tenant_id=tenant_id, chain_id=chain_id)
            .order_by("-last_activity_at", "-id")[:30]
        )
        for item in sessions:
            context = item.context if isinstance(item.context, dict) else {}
            context_provider_raw = context.get("provider")
            if context_provider_raw:
                if _normalize_provider(context_provider_raw) != provider:
                    continue
            ai_summary = context.get("ai_summary")
            if isinstance(ai_summary, dict) and ai_summary:
                return dict(ai_summary)
        return None

    def _append_incoming_history(
        self,
        *,
        context: dict[str, Any],
        session: ChainSession,
        user_message: dict[str, Any],
        provider: str,
        provider_user_id: str,
    ) -> dict[str, Any]:
        history_raw = context.get("history")
        history: list[dict[str, Any]] = history_raw if isinstance(history_raw, list) else []
        history.append(
            {
                "direction": "incoming",
                "sender": "client",
                "message": dict(user_message),
                "summary": _build_history_summary(user_message),
                "node_id": session.current_node_id,
                "provider": provider,
                "provider_user_id": provider_user_id,
                "received_at": timezone.now().isoformat(),
            }
        )
        context["history"] = history[-MAX_CHAIN_HISTORY_ITEMS:]
        context["last_message_at"] = timezone.now().isoformat()
        return context


def get_or_create_chain_for_tenant(
    tenant_id: int,
    *,
    chain_id: int | None = None,
    chain_key: str | None = None,
) -> Chain:
    from core.models import Client

    if chain_id is not None and chain_key is not None:
        raise ValueError("Specify either chain_id or chain_key, not both")

    client = Client.objects.filter(id=tenant_id).first()
    if client is None:
        raise ValueError(f"Tenant {tenant_id} not found")
    if chain_id is not None:
        chain = Chain.objects.filter(tenant=client, id=chain_id).first()
        if chain is None:
            raise ValueError(f"Chain {chain_id} not found for tenant {tenant_id}")
        return chain
    if chain_key is not None:
        return get_or_create_chain_by_key(client, chain_key)
    return get_or_create_chain(client)


def evaluate_conditions(
    edge_conditions: list[dict[str, Any]],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
    *,
    user_id: int | None = None,
    tenant_id: int | None = None,
    provider: str = UserTenantBinding.PROVIDER_TELEGRAM,
    provider_user_id: str | None = None,
) -> bool:
    if not edge_conditions:
        return True

    for cond in edge_conditions:
        cond_type = cond.get("condition_type")
        params = cond.get("params", {})
        if not _evaluate_single_condition(
            cond_type,
            params,
            user_message,
            session_context,
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            provider_user_id=provider_user_id,
        ):
            return False
    return True


def _evaluate_single_condition(
    cond_type: str,
    params: dict[str, Any],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
    *,
    user_id: int | None = None,
    tenant_id: int | None = None,
    provider: str = UserTenantBinding.PROVIDER_TELEGRAM,
    provider_user_id: str | None = None,
) -> bool:
    if cond_type == "button_press":
        return _eval_button_press(params, user_message)
    if cond_type == "text_contains":
        return _eval_text_contains(params, user_message)
    if cond_type == "text_regex":
        return _eval_text_regex(params, user_message)
    if cond_type == "content_type":
        return _eval_content_type(params, user_message)
    if cond_type == "has_media":
        return _eval_has_media(user_message)
    if cond_type == "text_equals":
        return _eval_text_equals(params, user_message)
    if cond_type == "has_entities":
        return _eval_has_entities(params, user_message)
    if cond_type == "client_tag_contains":
        return _eval_client_tag_contains(
            params,
            session_context,
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
    if cond_type == "client_has_meeting":
        return _eval_client_has_meeting(
            params,
            session_context,
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
    if cond_type == "client_has_payment":
        return _eval_client_has_payment(
            params,
            session_context,
            user_id=user_id,
            tenant_id=tenant_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
    if cond_type == "timeout":
        return False
    if cond_type == "any_reply":
        return _eval_any_reply(user_message)
    return False


def _eval_button_press(params: dict, user_message: dict) -> bool:
    expected_button = params.get("button_label", "")
    pressed_button = user_message.get("button", "")
    if pressed_button == expected_button:
        return True
    # Fallback for channels where keyboard clicks arrive as plain text.
    text_value = user_message.get("text", "")
    return text_value == expected_button


def _eval_text_contains(params: dict, user_message: dict) -> bool:
    substring = params.get("substring", "")
    case_sensitive = params.get("case_sensitive", False)
    user_text = user_message.get("text", "")

    if not case_sensitive:
        substring = substring.lower()
        user_text = user_text.lower()

    return substring in user_text


def _eval_text_regex(params: dict, user_message: dict) -> bool:
    pattern = params.get("pattern", "")
    flags_str = params.get("flags", "")
    user_text = user_message.get("text", "")

    flags = 0
    if "i" in flags_str.lower():
        flags |= re.IGNORECASE
    if "m" in flags_str.lower():
        flags |= re.MULTILINE
    if "s" in flags_str.lower():
        flags |= re.DOTALL

    try:
        return re.search(pattern, user_text, flags) is not None
    except re.error:
        return False


def _eval_content_type(params: dict, user_message: dict) -> bool:
    message_type = params.get("message_type") or ""
    if not message_type:
        return False

    declared_type = user_message.get("message_type")
    if declared_type:
        return declared_type == message_type

    return bool(user_message.get(message_type))


def _eval_has_media(user_message: dict) -> bool:
    return any(
        user_message.get(key)
        for key in ("photo", "video", "audio", "voice", "document")
    )


def _eval_text_equals(params: dict, user_message: dict) -> bool:
    exact_text = params.get("exact_text", "")
    user_text = user_message.get("text", "")
    return user_text == exact_text


def _eval_has_entities(params: dict, user_message: dict) -> bool:
    expected = params.get("entity_type")
    if not expected:
        return False
    entities = user_message.get("entities") or []
    return expected in entities


def _eval_any_reply(user_message: dict) -> bool:
    return bool(
        user_message.get("text")
        or user_message.get("button")
        or user_message.get("photo")
        or user_message.get("video")
        or user_message.get("audio")
        or user_message.get("voice")
        or user_message.get("document")
        or user_message.get("sticker")
        or user_message.get("location")
        or user_message.get("contact")
    )


def _resolve_contact_id(
    *,
    session_context: dict[str, Any],
    user_id: int | None,
    tenant_id: int | None,
    provider: str,
    provider_user_id: str | None,
) -> int | None:
    context_contact_id = session_context.get("contact_id")
    if context_contact_id is not None:
        try:
            resolved = int(context_contact_id)
            if resolved > 0:
                return resolved
        except (TypeError, ValueError):
            pass

    if tenant_id is None:
        return None

    normalized_provider = _normalize_provider(provider)
    resolved_provider_user_id = str(provider_user_id or user_id or "").strip()
    if not resolved_provider_user_id:
        return None

    filters = Q(
        provider=normalized_provider,
        provider_user_id=resolved_provider_user_id,
    )
    if normalized_provider == UserTenantBinding.PROVIDER_TELEGRAM and user_id is not None:
        filters |= Q(provider__isnull=True, telegram_chat_id=user_id)

    binding = (
        UserTenantBinding.objects.filter(filters, tenant_id=tenant_id, is_active=True)
        .order_by("-bound_at", "-id")
        .first()
    )
    if not binding or not binding.contact_id:
        return None
    return int(binding.contact_id)


def _map_schema() -> str:
    schema = (os.getenv("MAP_SCHEMA", "map") or "map").strip()
    if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        return "map"
    return schema


def _safe_int(value: Any, fallback: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return value
        return timezone.make_aware(value, timezone.get_current_timezone())
    return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timezone.is_aware(parsed):
        return parsed
    return timezone.make_aware(parsed, timezone.get_current_timezone())


def _interval_overlaps_any(
    start_at: datetime,
    end_at: datetime,
    intervals: list[tuple[datetime, datetime]],
) -> bool:
    for interval_start, interval_end in intervals:
        if interval_start < end_at and interval_end > start_at:
            return True
    return False


def _get_tz(tz_name: str | None):
    try:
        import zoneinfo

        return zoneinfo.ZoneInfo(str(tz_name or "Europe/Moscow"))
    except Exception:
        return None


def _get_tenant_timezone_name(tenant_id: int) -> str:
    tz_name = Client.objects.filter(id=tenant_id).values_list("timezone", flat=True).first()
    return str(tz_name or "Europe/Moscow")


def _parse_product_event_datetime(value: Any, tenant_tz_name: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    tz = _get_tz(tenant_tz_name) or timezone.get_current_timezone()

    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})$", raw, flags=re.IGNORECASE):
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed, tz)

    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$", raw):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed, tz)

    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        try:
            parsed = datetime.fromisoformat(f"{raw}T12:00:00")
        except ValueError:
            return None
        return timezone.make_aware(parsed, tz)

    return None


def _collect_product_event_intervals(
    *,
    tenant_id: int,
    tenant_tz_name: str,
) -> list[tuple[datetime, datetime]]:
    intervals: list[tuple[datetime, datetime]] = []
    products = (
        ClientProduct.objects.select_related("product_type")
        .filter(owner_id=tenant_id)
        .only("id", "structure", "product_type__name")
    )
    for product in products:
        type_name = (getattr(getattr(product, "product_type", None), "name", "") or "").strip().lower()
        if type_name not in _EVENT_PRODUCT_TYPE_KEYS:
            continue

        structure = product.structure if isinstance(product.structure, dict) else {}
        event_payload = structure.get("event")
        if not isinstance(event_payload, dict):
            continue

        start_at = _parse_product_event_datetime(event_payload.get("date"), tenant_tz_name)
        if not start_at:
            continue

        duration_raw = event_payload.get("duration_minutes")
        try:
            duration_minutes = int(duration_raw)
        except (TypeError, ValueError):
            duration_minutes = 60
        if duration_minutes <= 0:
            duration_minutes = 60

        end_at = start_at + timedelta(minutes=max(15, duration_minutes))
        intervals.append((start_at, end_at))

    return intervals


def _format_booking_slot_label(value: Any, tz_name: Any) -> str:
    dt = _coerce_datetime(value)
    if not dt:
        return str(value or "")
    tz = _get_tz(str(tz_name or ""))
    if tz:
        dt = dt.astimezone(tz)
    # %-d для Unix без ведущего нуля; если платформа не поддерживает, fallback на %d.
    try:
        return dt.strftime("%-d %b, %H:%M")
    except ValueError:
        return dt.strftime("%d %b, %H:%M")


def _build_ai_system_prompt(
    payload: dict[str, Any],
    summary: str | None = None,
    contact_facts: str | None = None,
) -> str:
    intents_raw = payload.get("intents") if isinstance(payload.get("intents"), list) else []
    intents: list[dict[str, str]] = []
    for item in intents_raw:
        if not isinstance(item, dict):
            continue
        intent_id = str(item.get("id") or "").strip()
        if not intent_id:
            continue
        intents.append({
            "id": intent_id,
            "label": str(item.get("label") or intent_id).strip(),
        })

    base_prompt = str(payload.get("system_prompt") or "").strip()

    summary_block = ""
    if summary:
        summary_block = (
            "\n\nКраткое резюме предыдущих диалогов с пользователем:\n"
            f"{summary.strip()}"
        )

    facts_block = ""
    if contact_facts:
        facts_block = (
            "\n\nИзвестные факты о клиенте (используй для персонализации, не спрашивай повторно):\n"
            f"{contact_facts}"
        )

    intents_block = ""
    if intents:
        intents_lines = "\n".join(f'- "{item["id"]}": {item["label"]}' for item in intents)
        intents_block = (
            "\n\nДоступные intent (выбирай только при явном намерении пользователя):\n"
            f"{intents_lines}\n\n"
            "Если явного намерения нет, возвращай intent = null."
        )

    output_block = (
        "\n\nВерни только JSON-объект без markdown и без дополнительного текста:\n"
        '{"message":"<ответ пользователю>", "intent": null}'
    )

    return f"{base_prompt}{summary_block}{facts_block}{intents_block}{output_block}".strip()


def _format_ai_history_lines(history: list[dict[str, Any]]) -> list[str]:
    """Convert AI history dicts to human-readable lines for prompt construction."""
    lines: list[str] = []
    for item in history[-MAX_AI_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        role_label = "Пользователь" if role == "user" else "Ассистент"
        lines.append(f"{role_label}: {content}")
    return lines


def _call_ai(
    *,
    system_prompt: str,
    history: list[dict[str, Any]],
    user_text: str | None,
) -> dict[str, Any] | None:
    try:
        from core.ai_generator import AIContentGenerator
        from core.ai_generator_content import _parse_ai_json_response
    except Exception:
        logger.exception("AI assistant: failed to import ai_generator")
        return None

    history_lines = _format_ai_history_lines(history)

    user_part = (
        "Это первый вход в диалог. Начни разговор с короткого уместного приветствия."
        if user_text is None
        else f"Новое сообщение пользователя: {user_text}"
    )
    history_block = "\n".join(history_lines) if history_lines else "История пуста."

    prompt = (
        f"{system_prompt}\n\n"
        f"История диалога:\n{history_block}\n\n"
        f"{user_part}"
    )

    try:
        generator = AIContentGenerator()
    except Exception:
        logger.exception("AI assistant: failed to initialize AIContentGenerator")
        return None

    model = str(os.getenv("CHAIN_AI_MODEL") or "").strip() or None

    try:
        raw = generator.get_ai_response(
            prompt=prompt,
            max_tokens=500,
            temperature=0.2,
            model=model,
            allow_fallback=True,
            response_format={"type": "json_object"},
            retry_without_format=True,
        )
    except Exception:
        logger.exception("AI assistant: get_ai_response failed")
        return None

    if not raw:
        logger.error("AI assistant: empty model response")
        return None

    parsed, _, _ = _parse_ai_json_response(raw)
    if not isinstance(parsed, dict):
        logger.error("AI assistant: response is not a JSON object")
        return None

    message = str(parsed.get("message") or "").strip()
    intent_value = parsed.get("intent")
    intent = str(intent_value).strip() if intent_value is not None else None
    if intent in {"", "null", "None"}:
        intent = None

    return {
        "message": message,
        "intent": intent,
    }


def _summarize_ai_history(
    *,
    system_prompt: str,
    history: list[dict[str, Any]],
) -> str | None:
    if not history:
        return None

    try:
        from core.ai_generator import AIContentGenerator
    except Exception:
        logger.exception("AI assistant: failed to import ai_generator for summary")
        return None

    history_lines = _format_ai_history_lines(history)

    if not history_lines:
        return None

    prompt = (
        f"{system_prompt}\n\n"
        "Сделай краткое резюме диалога в 2-3 предложениях:\n"
        "- главная потребность пользователя,\n"
        "- договоренности/статус,\n"
        "- что важно помнить в следующих сообщениях.\n\n"
        "История:\n"
        f"{chr(10).join(history_lines)}"
    )

    try:
        generator = AIContentGenerator()
    except Exception:
        logger.exception("AI assistant: failed to initialize AIContentGenerator for summary")
        return None

    model = str(os.getenv("CHAIN_AI_SUMMARY_MODEL") or os.getenv("CHAIN_AI_MODEL") or "").strip() or None

    try:
        raw = generator.get_ai_response(
            prompt=prompt,
            max_tokens=220,
            temperature=0.2,
            model=model,
            allow_fallback=True,
            response_format=None,
            retry_without_format=False,
        )
    except Exception:
        logger.exception("AI assistant: summary generation failed")
        return None

    if not raw:
        return None

    summary = str(raw).strip()
    if summary.startswith("```"):
        summary = re.sub(r"^```[a-zA-Z]*\n?", "", summary).strip()
        summary = re.sub(r"\n?```$", "", summary).strip()
    if not summary:
        return None
    return summary


def _eval_client_tag_contains(
    params: dict[str, Any],
    session_context: dict[str, Any],
    *,
    user_id: int | None,
    tenant_id: int | None,
    provider: str,
    provider_user_id: str | None,
) -> bool:
    substring = str(params.get("substring") or "").strip()
    if not substring:
        return False

    contact_id = _resolve_contact_id(
        session_context=session_context,
        user_id=user_id,
        tenant_id=tenant_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    if not contact_id:
        return False

    case_sensitive = bool(params.get("case_sensitive", False))
    needle = substring if case_sensitive else substring.lower()

    for item in MapContactTag.objects.filter(contact_id=contact_id).select_related("tag"):
        tag_value = str(getattr(getattr(item, "tag", None), "value", "") or "")
        haystack = tag_value if case_sensitive else tag_value.lower()
        if needle in haystack:
            return True

    return False


def _eval_client_has_meeting(
    params: dict[str, Any],
    session_context: dict[str, Any],
    *,
    user_id: int | None,
    tenant_id: int | None,
    provider: str,
    provider_user_id: str | None,
) -> bool:
    contact_id = _resolve_contact_id(
        session_context=session_context,
        user_id=user_id,
        tenant_id=tenant_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    if not contact_id:
        return False

    status = str(params.get("status") or "").strip().lower()
    allowed_statuses = {"scheduled", "completed", "cancelled", "no_show"}
    if status and status not in allowed_statuses:
        return False

    relation = _extract_nearest_relation(params)
    schema = _map_schema()
    if not relation:
        query = f"SELECT 1 FROM {schema}.crm_events WHERE contact_id = %s"
        args: list[Any] = [contact_id]
        if status:
            query += " AND status = %s"
            args.append(status)
        query += " LIMIT 1"

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, args)
                return cursor.fetchone() is not None
        except Exception:
            logger.exception("Failed to evaluate client_has_meeting for contact %s", contact_id)
            return False

    query = f"""
        SELECT start_time
        FROM {schema}.crm_events
        WHERE contact_id = %s
          AND start_time IS NOT NULL
    """
    args = [contact_id]
    if status:
        query += " AND status = %s"
        args.append(status)
    query += " ORDER BY ABS(EXTRACT(EPOCH FROM (start_time - NOW()))) ASC LIMIT 1"

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, args)
            row = cursor.fetchone()
    except Exception:
        logger.exception("Failed to evaluate nearest client_has_meeting for contact %s", contact_id)
        return False

    if not row or not row[0]:
        return False
    nearest_dt = _ensure_datetime_aware(row[0])
    now = timezone.now()
    return _compare_relation(now, nearest_dt, relation)


def _eval_client_has_payment(
    params: dict[str, Any],
    session_context: dict[str, Any],
    *,
    user_id: int | None,
    tenant_id: int | None,
    provider: str,
    provider_user_id: str | None,
) -> bool:
    contact_id = _resolve_contact_id(
        session_context=session_context,
        user_id=user_id,
        tenant_id=tenant_id,
        provider=provider,
        provider_user_id=provider_user_id,
    )
    if not contact_id:
        return False

    status = str(params.get("status") or "").strip().lower()
    allowed_statuses = {"pending", "paid", "failed", "refunded"}
    if status and status not in allowed_statuses:
        return False

    relation = _extract_nearest_relation(params)
    queryset = MapCRMPayment.objects.filter(contact_id=contact_id)
    if status:
        queryset = queryset.filter(status=status)
    if not relation:
        return queryset.exists()

    now = timezone.now()
    nearest: datetime | None = None
    nearest_delta: float | None = None

    for payment in queryset.only("planned_at", "paid_at", "created_at"):
        dt = payment.planned_at or payment.paid_at or payment.created_at
        if not dt:
            continue
        dt = _ensure_datetime_aware(dt)
        delta = abs((dt - now).total_seconds())
        if nearest is None or nearest_delta is None or delta < nearest_delta:
            nearest = dt
            nearest_delta = delta

    if nearest is None:
        return False

    return _compare_relation(now, nearest, relation)


def _extract_nearest_relation(params: dict[str, Any]) -> str:
    relation = str(params.get("nearest_relation") or "").strip().lower()
    if relation in {"before", "after"}:
        return relation
    return ""


def _normalize_provider(provider: str | None) -> str:
    candidate = str(provider or "").strip().lower()
    if candidate in {UserTenantBinding.PROVIDER_TELEGRAM, UserTenantBinding.PROVIDER_VK}:
        return candidate
    return UserTenantBinding.PROVIDER_TELEGRAM


def _build_history_summary(user_message: dict[str, Any]) -> str:
    text_value = str(user_message.get("text") or "").strip()
    if text_value:
        return text_value

    message_type = str(user_message.get("message_type") or "").strip().lower()
    if message_type:
        return f"[{message_type}]"

    for key in ("photo", "video", "audio", "voice", "document", "sticker", "location", "contact"):
        if user_message.get(key):
            return f"[{key}]"
    return "[unknown]"


def _ensure_datetime_aware(value: datetime) -> datetime:
    if timezone.is_aware(value):
        return value
    return timezone.make_aware(value, timezone.get_current_timezone())


def _compare_relation(now: datetime, target: datetime, relation: str) -> bool:
    if relation == "before":
        return now < target
    if relation == "after":
        return now > target
    return False


def _build_contact_facts_context(contact_id: int, tenant_id: int) -> str:
    """
    Собирает активные факты о контакте в читаемый текст для AI-промпта.
    """
    facts = list(
        ContactFact.objects
        .filter(contact_id=contact_id, tenant_id=tenant_id, is_active=True)
        .order_by("category", "fact_type", "-created_at")
        .values("category", "fact_type", "fact_value", "confidence")
    )
    if not facts:
        return ""

    by_category: dict[str, list[str]] = {}
    for fact in facts:
        line = str(fact["fact_value"])
        if fact["confidence"] == 1:
            line += " (предположение)"
        by_category.setdefault(str(fact["category"]), []).append(f'{fact["fact_type"]}: {line}')

    blocks: list[str] = []
    for category, lines in by_category.items():
        blocks.append(f"[{category}]\n" + "\n".join(f"  - {line}" for line in lines))

    return "\n\n".join(blocks)


# Полный справочник допустимых типов фактов по категориям.
# AI получает его в промпте — это снижает галлюцинации с произвольными ключами.
_FACT_SCHEMA: dict[str, list[str]] = {
    "purchase": [
        "pain",
        "desire",
        "objection",
        "decision_style",
        "previous_purchase",
        "churn_reason",
    ],
    "context": [
        "location",
        "role",
        "company",
        "life_moment",
        "timeline",
        "budget",
    ],
    "environment": [
        "family",
        "partner",
        "team",
        "influencer",
    ],
    "attitude": [
        "trust_level",
        "source",
        "competitor",
        "communication_style",
        "trigger",
    ],
    "constraints": [
        "budget_flexibility",
        "technical",
        "deadline",
    ],
}


def _extract_contact_facts(
    history: list[dict[str, Any]],
    existing_context: str,
) -> list[dict[str, Any]] | None:
    """
    Возвращает список вида:
    [{"category": "...", "fact_type": "...", "fact_value": "...", "confidence": 1..3}]
    либо None, если новых значимых фактов нет.
    """
    try:
        from core.ai_generator import AIContentGenerator
        from core.ai_generator_content import _parse_ai_json_response
    except Exception:
        logger.exception("ContactFacts: failed to import ai_generator")
        return None

    history_lines = _format_ai_history_lines(history)
    if not history_lines:
        return None

    schema_text = "\n".join(
        f"  {category}: {', '.join(types)}"
        for category, types in _FACT_SCHEMA.items()
    )
    history_text = "\n".join(history_lines)

    prompt = (
        "Ты — система анализа диалогов. Извлекай только значимые факты о клиенте.\n\n"
        "ИГНОРИРУЙ полностью:\n"
        "- приветствия, прощания, благодарности\n"
        "- общие вопросы без конкретики о клиенте\n"
        "- технические уточнения по работе сервиса\n\n"
        "Допустимые категории и типы фактов:\n"
        f"{schema_text}\n\n"
        "confidence: 1=AI предположил, 2=клиент явно сказал, 3=подтверждено действием\n\n"
        "Уже известно о клиенте:\n"
        f"{existing_context or 'ничего'}\n\n"
        f"Диалог:\n{history_text}\n\n"
        "Верни JSON:\n"
        '{"facts": ['
        '{"category": "purchase", "fact_type": "pain", "fact_value": "текст", "confidence": 2}'
        "]}\n"
        "Включай только факты, которых ЕЩЁ НЕТ в разделе «Уже известно». "
        'Если новых значимых фактов нет — верни {"facts": []}.'
    )

    try:
        generator = AIContentGenerator()
    except Exception:
        logger.exception("ContactFacts: failed to initialize AIContentGenerator")
        return None

    model = str(os.getenv("CHAIN_AI_MODEL") or "").strip() or None

    try:
        raw = generator.get_ai_response(
            prompt=prompt,
            max_tokens=600,
            temperature=0.1,
            model=model,
            allow_fallback=True,
            response_format={"type": "json_object"},
            retry_without_format=True,
        )
    except Exception:
        logger.exception("ContactFacts: get_ai_response failed")
        return None

    if not raw:
        return None

    try:
        parsed, _, _ = _parse_ai_json_response(raw)
    except Exception:
        logger.exception("ContactFacts: failed to parse AI response")
        return None

    if not isinstance(parsed, dict):
        return None

    raw_facts = parsed.get("facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        return None

    valid: list[dict[str, Any]] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        fact_type = str(item.get("fact_type") or "").strip()
        fact_value = str(item.get("fact_value") or "").strip()
        if not category or not fact_type or not fact_value:
            continue
        if category not in _FACT_SCHEMA:
            continue
        if fact_type not in _FACT_SCHEMA[category]:
            logger.debug("ContactFacts: unknown fact_type '%s' for category '%s'", fact_type, category)
            continue
        try:
            confidence = max(1, min(3, int(item.get("confidence", 2))))
        except (TypeError, ValueError):
            confidence = 2
        valid.append({
            "category": category,
            "fact_type": fact_type,
            "fact_value": fact_value,
            "confidence": confidence,
        })

    return valid if valid else None


def _update_contact_facts(
    *,
    contact_id: int,
    tenant_id: int,
    session_id: int | None = None,
    history: list[dict[str, Any]],
) -> None:
    """
    Извлекает факты из AI-истории диалога и сохраняет их в contact_facts.
    Дубли не создаёт: проверка по (contact_id, tenant_id, category, fact_type, fact_value).
    """
    existing_context = _build_contact_facts_context(contact_id, tenant_id)
    new_facts = _extract_contact_facts(
        history=history,
        existing_context=existing_context,
    )
    if not new_facts:
        return

    created_count = 0
    for fact in new_facts:
        try:
            _, created = ContactFact.objects.get_or_create(
                contact_id=contact_id,
                tenant_id=tenant_id,
                category=fact["category"],
                fact_type=fact["fact_type"],
                fact_value=fact["fact_value"],
                defaults={
                    "confidence": fact["confidence"],
                    "source": "ai_chat",
                    "session_id": session_id,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
        except Exception:
            logger.exception(
                "ContactFacts: failed to save fact %s/%s for contact %s",
                fact["category"],
                fact["fact_type"],
                contact_id,
            )

    if created_count:
        logger.info(
            "ContactFacts: added %d new facts for contact=%s tenant=%s",
            created_count,
            contact_id,
            tenant_id,
        )
