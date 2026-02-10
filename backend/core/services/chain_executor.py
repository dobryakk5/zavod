from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from django.utils import timezone

from core.models import ChainCondition, ChainEdge, ChainNode, ChainSession
from core.services.chain_service import get_or_create_chain


logger = logging.getLogger(__name__)


class ChainExecutor:
    """
    Executes a tenant's welcome chain for Telegram users.
    """

    def start_chain(self, user_id: int, tenant_id: int) -> dict[str, Any]:
        chain = get_or_create_chain_for_tenant(tenant_id)
        if not chain.start_node_id:
            raise ValueError("Chain has no start node")

        session = (
            ChainSession.objects.filter(
                user_id=user_id,
                tenant_id=tenant_id,
                chain=chain,
                status="active",
            )
            .order_by("-last_activity_at")
            .first()
        )

        if session:
            session.context = {}
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
                context={},
            )

        actions = self._advance_to_node(session, chain.start_node_id)
        return {"session_id": session.id, "actions": actions}

    def process_user_message(self, user_id: int, tenant_id: int, user_message: dict[str, Any]) -> dict[str, Any]:
        session = (
            ChainSession.objects.filter(user_id=user_id, tenant_id=tenant_id, status="active")
            .order_by("-last_activity_at")
            .first()
        )
        if not session:
            return {"session_id": None, "actions": [], "session_status": "none"}

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
            matching_edge = self._select_router_edge(current_node, user_message, session.context or {})
            if not matching_edge:
                session.status = "completed"
                session.completed_at = timezone.now()
                session.save(update_fields=["status", "completed_at", "updated_at"])
                return {"session_id": session.id, "actions": [], "session_status": "completed"}

            context = dict(session.context or {})
            context.setdefault("answers", {})
            context["answers"][str(session.current_node_id)] = user_message
            context["last_message_at"] = datetime.utcnow().isoformat()

            session.context = context
            session.last_activity_at = timezone.now()
            session.save(update_fields=["context", "last_activity_at", "updated_at"])

            actions = self._advance_to_node(session, matching_edge.target_node_id)
            return {"session_id": session.id, "actions": actions, "session_status": "active"}

        edges = self._get_edges_with_conditions(session.current_node_id)

        matching_edge = None
        for edge in edges:
            if evaluate_conditions(edge["conditions"], user_message, session.context or {}):
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
        context["last_message_at"] = datetime.utcnow().isoformat()

        session.context = context
        session.last_activity_at = timezone.now()
        session.save(update_fields=["context", "last_activity_at", "updated_at"])

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

        if node.node_type == "start":
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            buttons = payload.get("buttons") or []
            has_buttons = len(buttons) > 0
            actions.append({
                "action_type": "send_buttons" if has_buttons else "send_text",
                "payload": payload,
                "delay_seconds": node.delay_seconds,
            })
        elif node.node_type == "text":
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            has_buttons = bool(payload.get("buttons"))
            actions.append({
                "action_type": "send_buttons" if has_buttons else "send_text",
                "payload": payload,
                "delay_seconds": node.delay_seconds,
            })
        elif node.node_type == "photo":
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            actions.append({
                "action_type": "send_photo",
                "payload": payload,
                "delay_seconds": node.delay_seconds,
            })
        elif node.node_type == "buttons":
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            actions.append({
                "action_type": "send_buttons",
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
                matched = _evaluate_single_condition(cond_type or "", params, user_message, session_context)
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


def get_or_create_chain_for_tenant(tenant_id: int):
    from core.models import Client

    client = Client.objects.filter(id=tenant_id).first()
    if client is None:
        raise ValueError(f"Tenant {tenant_id} not found")
    return get_or_create_chain(client)


def evaluate_conditions(
    edge_conditions: list[dict[str, Any]],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
) -> bool:
    if not edge_conditions:
        return True

    for cond in edge_conditions:
        cond_type = cond.get("condition_type")
        params = cond.get("params", {})
        if not _evaluate_single_condition(cond_type, params, user_message, session_context):
            return False
    return True


def _evaluate_single_condition(
    cond_type: str,
    params: dict[str, Any],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
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
    if cond_type == "timeout":
        return False
    if cond_type == "any_reply":
        return _eval_any_reply(user_message)
    return False


def _eval_button_press(params: dict, user_message: dict) -> bool:
    expected_button = params.get("button_label", "")
    pressed_button = user_message.get("button", "")
    return pressed_button == expected_button


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

    if message_type == "text":
        return bool(user_message.get("text"))
    if message_type == "photo":
        return bool(user_message.get("photo"))
    if message_type == "video":
        return bool(user_message.get("video"))
    if message_type == "audio":
        return bool(user_message.get("audio"))
    if message_type == "voice":
        return bool(user_message.get("voice"))
    if message_type == "document":
        return bool(user_message.get("document"))
    if message_type == "sticker":
        return bool(user_message.get("sticker"))
    if message_type == "location":
        return bool(user_message.get("location"))
    if message_type == "contact":
        return bool(user_message.get("contact"))
    return False


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
