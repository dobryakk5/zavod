from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Chain, ChainCondition, ChainEdge, ChainNode
from core.services.chain_service import get_or_create_chain
from api.permissions import IsTenantMember, IsTenantOwnerOrEditor
from api.serializers import (
    ChainSerializer,
    ChainNodeSerializer,
    ChainEdgeSerializer,
    ChainConditionSerializer,
)
from api.utils import get_active_client


def _get_or_create_chain(client) -> Chain:
    return get_or_create_chain(client)


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


class CurrentChainView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method in ("PATCH", "POST", "PUT", "DELETE"):
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        return Response(ChainSerializer(chain).data)

    def patch(self, request):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
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

    def get(self, request):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        return Response(_build_graph(chain))


class ChainNodesView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        serializer = ChainNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        node = serializer.save(chain=chain)
        return Response(ChainNodeSerializer(node).data, status=status.HTTP_201_CREATED)


class ChainNodeDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, node_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        node = get_object_or_404(ChainNode.objects.filter(chain=chain), pk=node_id)
        serializer = ChainNodeSerializer(node, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ChainNodeSerializer(node).data)

    def delete(self, request, node_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
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

    def post(self, request):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
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

    def patch(self, request, edge_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
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

    def delete(self, request, edge_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        edge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChainEdgeConditionsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request, edge_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        conditions = ChainCondition.objects.filter(edge=edge).order_by("created_at", "id")
        return Response(ChainConditionSerializer(conditions, many=True).data)

    def post(self, request, edge_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        serializer = ChainConditionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        condition = serializer.save(edge=edge)
        return Response(ChainConditionSerializer(condition).data, status=status.HTTP_201_CREATED)


class ChainEdgeConditionDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def delete(self, request, edge_id: int, condition_id: int):
        client = get_active_client(request.user)
        chain = _get_or_create_chain(client)
        edge = get_object_or_404(ChainEdge.objects.filter(chain=chain), pk=edge_id)
        condition = get_object_or_404(ChainCondition.objects.filter(edge=edge), pk=condition_id)
        condition.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
