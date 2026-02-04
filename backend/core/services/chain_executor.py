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
        if node.node_type == "text":
            payload = dict(node.payload or {})
            payload["node_id"] = node.id
            actions.append({
                "action_type": "send_text",
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
                "conditions": conditions_by_edge.get(edge.id, []),
            })
        return edge_payload


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


def _eval_any_reply(user_message: dict) -> bool:
    return bool(user_message.get("text") or user_message.get("button") or user_message.get("photo"))
