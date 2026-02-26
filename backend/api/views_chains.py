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
