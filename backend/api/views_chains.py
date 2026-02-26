from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Chain, ChainCondition, ChainEdge, ChainNode
from core.services.chain_service import CHAIN_DEFINITIONS, WELCOME_CHAIN_KEY, ensure_predefined_chains
from api.permissions import IsTenantMember, IsTenantOwnerOrEditor
from api.serializers import (
    ChainSerializer,
    ChainNodeSerializer,
    ChainEdgeSerializer,
    ChainConditionSerializer,
)
from api.utils import get_active_client


def _get_or_create_chain(client, chain_id: int | None = None) -> Chain:
    chains = ensure_predefined_chains(client)
    if chain_id is None:
        return chains[WELCOME_CHAIN_KEY]
    return get_object_or_404(Chain.objects.filter(tenant=client), pk=chain_id)


def _build_graph(chain: Chain) -> dict:
    nodes = list(ChainNode.objects.filter(chain=chain).order_by("created_at", "id"))
    edges = list(ChainEdge.objects.filter(chain=chain).order_by("priority", "id"))

    edge_ids = [edge.id for edge in edges]
    conditions_by_edge: dict[int, list[ChainCondition]] = {edge_id: [] for edge_id in edge_ids}
    if edge_ids:
        for condition in ChainCondition.objects.filter(edge_id__in=edge_ids).order_by("created_at", "id"):
            conditions_by_edge[condition.edge_id].append(condition)

    edge_payload = []
    for edge in edges:
        data = ChainEdgeSerializer(edge).data
        data["conditions"] = ChainConditionSerializer(
            conditions_by_edge.get(edge.id, []),
            many=True,
        ).data
        edge_payload.append(data)

    return {
        "chain": ChainSerializer(chain).data,
        "nodes": ChainNodeSerializer(nodes, many=True).data,
        "edges": edge_payload,
    }


def _get_existing_start_node(chain: Chain) -> ChainNode | None:
    return (
        ChainNode.objects
        .filter(chain=chain, node_type="start")
        .order_by("created_at", "id")
        .first()
    )


def _normalize_node_buttons(node: ChainNode) -> list[str]:
    payload = node.payload if isinstance(node.payload, dict) else {}
    raw_buttons = payload.get("buttons") or []
    result: list[str] = []
    for item in raw_buttons:
        label = item if isinstance(item, str) else (item or {}).get("text")
        text = str(label or "").strip()
        if text:
            result.append(text)
    return result


def _node_label(node: ChainNode) -> str:
    payload = node.payload if isinstance(node.payload, dict) else {}
    if node.node_type in {"router", "timer"} and payload.get("label"):
        return str(payload.get("label"))[:28]
    if payload.get("text"):
        return str(payload.get("text"))[:28]
    if payload.get("caption"):
        return str(payload.get("caption"))[:28]
    return str(node.node_type)


def _validate_chain_graph_for_activation(chain: Chain, *, start_node_id: int | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    nodes = list(ChainNode.objects.filter(chain=chain).order_by("created_at", "id"))
    if not nodes:
        errors.append({
            "type": "empty",
            "severity": "error",
            "msg": "Цепочка пустая — добавьте хотя бы один узел.",
        })
        return {"errors": errors, "warnings": warnings}

    effective_start_node_id = start_node_id if start_node_id is not None else chain.start_node_id
    node_ids = {int(node.id) for node in nodes}
    if not effective_start_node_id or int(effective_start_node_id) not in node_ids:
        errors.append({
            "type": "no_start",
            "severity": "error",
            "msg": "Не выбран корректный стартовый узел.",
        })

    edges = list(ChainEdge.objects.filter(chain=chain).order_by("priority", "id"))
    edge_ids = [edge.id for edge in edges]
    conditions_by_edge: dict[int, list[ChainCondition]] = {edge_id: [] for edge_id in edge_ids}
    if edge_ids:
        for condition in ChainCondition.objects.filter(edge_id__in=edge_ids).order_by("created_at", "id"):
            conditions_by_edge[condition.edge_id].append(condition)

    has_incoming = {int(edge.target_node_id) for edge in edges}
    edges_by_source: dict[int, list[ChainEdge]] = {}
    for edge in edges:
        edges_by_source.setdefault(int(edge.source_node_id), []).append(edge)

    for node in nodes:
        if effective_start_node_id and node.id == int(effective_start_node_id):
            continue
        if int(node.id) not in has_incoming:
            warnings.append({
                "type": "orphan",
                "severity": "warning",
                "nodeId": int(node.id),
                "msg": f"Узел «{_node_label(node)}» недоступен — нет входящих рёбер.",
            })

    for node in nodes:
        payload = node.payload if isinstance(node.payload, dict) else {}
        has_buttons = (
            node.node_type in {"buttons", "start"}
            or (node.node_type == "text" and isinstance(payload.get("buttons"), list) and len(payload.get("buttons")) > 0)
        )
        if not has_buttons:
            continue

        buttons = _normalize_node_buttons(node)
        if not buttons:
            continue

        out_edges = edges_by_source.get(int(node.id), [])
        covered_buttons: set[str] = set()
        has_default_edge = False
        for edge in out_edges:
            edge_conditions = conditions_by_edge.get(edge.id, [])
            if not edge_conditions:
                has_default_edge = True
            for cond in edge_conditions:
                if getattr(cond, "condition_type", None) != "button_press":
                    continue
                params = cond.params if isinstance(cond.params, dict) else {}
                label = str(params.get("button_label") or "").strip()
                if label:
                    covered_buttons.add(label)

        for button_label in buttons:
            if button_label in covered_buttons or has_default_edge:
                continue
            errors.append({
                "type": "uncovered_btn",
                "severity": "error",
                "nodeId": int(node.id),
                "msg": f"Кнопка «{button_label}» в узле не обработана.",
            })

    return {"errors": errors, "warnings": warnings}


class CurrentChainView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method in ("PATCH", "POST", "PUT", "DELETE"):
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        return Response(ChainSerializer(chain).data)

    def patch(self, request, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        serializer = ChainSerializer(chain, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        start_node_id = serializer.validated_data.get("start_node_id")
        if start_node_id is not None:
            node_exists = ChainNode.objects.filter(chain=chain, id=start_node_id).exists()
            if not node_exists:
                return Response({"detail": "start_node_id не относится к этой цепочке"}, status=status.HTTP_400_BAD_REQUEST)

        requested_status = serializer.validated_data.get("status")
        if requested_status == "active":
            validation = _validate_chain_graph_for_activation(chain, start_node_id=start_node_id)
            if validation["errors"]:
                return Response(
                    {
                        "detail": "Нельзя активировать цепочку: исправьте ошибки валидации",
                        "validation_errors": validation["errors"],
                        "validation_warnings": validation["warnings"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save()
        return Response(ChainSerializer(chain).data)


class CurrentChainGraphView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        return Response(_build_graph(chain))


class ChainsListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        client = get_active_client(request.user)
        chains = ensure_predefined_chains(client)
        payload = []
        for definition in CHAIN_DEFINITIONS:
            chain = chains.get(definition["key"])
            if not chain:
                continue
            data = ChainSerializer(chain).data
            data["key"] = definition["key"]
            data["title"] = definition["title"]
            payload.append(data)
        return Response(payload)


class ChainNodesView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        serializer = ChainNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data.get("node_type") == "start":
            existing_start = _get_existing_start_node(chain)
            if existing_start:
                if chain.start_node_id != existing_start.id:
                    chain.start_node_id = existing_start.id
                    chain.save(update_fields=["start_node_id"])
                return Response(ChainNodeSerializer(existing_start).data, status=status.HTTP_200_OK)

        node = serializer.save(chain=chain)
        if node.node_type == "start" and chain.start_node_id != node.id:
            chain.start_node_id = node.id
            chain.save(update_fields=["start_node_id"])
        return Response(ChainNodeSerializer(node).data, status=status.HTTP_201_CREATED)


class ChainNodeDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, node_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        node = get_object_or_404(ChainNode.objects.filter(chain=chain), pk=node_id)
        serializer = ChainNodeSerializer(node, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ChainNodeSerializer(node).data)

    def delete(self, request, node_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        node = get_object_or_404(ChainNode.objects.filter(chain=chain), pk=node_id)
        if node.node_type == "start":
            return Response({"detail": "Нельзя удалить стартовый узел"}, status=status.HTTP_400_BAD_REQUEST)
        node.delete()
        if chain.start_node_id == node_id:
            chain.start_node_id = None
            chain.save(update_fields=["start_node_id"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChainEdgesView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        serializer = ChainEdgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        source_node = serializer.validated_data.get("source_node")
        target_node = serializer.validated_data.get("target_node")
        if source_node and source_node.chain_id != chain.id:
            return Response({"detail": "source_node_id не относится к этой цепочке"}, status=status.HTTP_400_BAD_REQUEST)
        if target_node and target_node.chain_id != chain.id:
            return Response({"detail": "target_node_id не относится к этой цепочке"}, status=status.HTTP_400_BAD_REQUEST)

        edge = serializer.save(chain=chain)
        return Response(ChainEdgeSerializer(edge).data, status=status.HTTP_201_CREATED)


class ChainEdgeDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, edge_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        serializer = ChainEdgeSerializer(edge, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        source_node = serializer.validated_data.get("source_node")
        target_node = serializer.validated_data.get("target_node")
        if source_node and source_node.chain_id != chain.id:
            return Response({"detail": "source_node_id не относится к этой цепочке"}, status=status.HTTP_400_BAD_REQUEST)
        if target_node and target_node.chain_id != chain.id:
            return Response({"detail": "target_node_id не относится к этой цепочке"}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(ChainEdgeSerializer(edge).data)

    def delete(self, request, edge_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        edge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChainEdgeConditionsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request, edge_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        conditions = ChainCondition.objects.filter(edge=edge).order_by("created_at", "id")
        return Response(ChainConditionSerializer(conditions, many=True).data)

    def post(self, request, edge_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        serializer = ChainConditionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        condition = serializer.save(edge=edge)
        return Response(ChainConditionSerializer(condition).data, status=status.HTTP_201_CREATED)


class ChainEdgeConditionDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def delete(self, request, edge_id: int, condition_id: int, chain_id: int | None = None):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client, chain_id=chain_id)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        condition = get_object_or_404(ChainCondition.objects.filter(edge=edge), pk=condition_id)
        condition.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
