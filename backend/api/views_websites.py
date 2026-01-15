from __future__ import annotations

import logging

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core import tasks
from core.generation_events import record_generation_event
from core.models import GenerationEvent, WebsiteScan, WebsiteScanPage

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    WebsiteScanCreateSerializer,
    WebsiteScanDetailSerializer,
    WebsiteScanListSerializer,
    WebsiteScanPageSerializer,
)
from .utils import enforce_generation_limit, get_active_client

logger = logging.getLogger(__name__)


class WebsiteScanViewSet(viewsets.ModelViewSet):
    """
    Crawl a website (respecting robots.txt) and store:
    - up to `max_pages` pages
    - link-depth tree up to `max_depth`
    - wordstats from title/meta/headings
    - optional mind map in map.* tables (if available)
    """

    permission_classes = [IsTenantMember]
    pagination_class = None
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "destroy", "rerun"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return WebsiteScanCreateSerializer
        if self.action == "retrieve":
            return WebsiteScanDetailSerializer
        if self.action == "pages":
            return WebsiteScanPageSerializer
        return WebsiteScanListSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        qs = (
            WebsiteScan.objects.filter(client=client)
            .annotate(pages_count=Count("pages", filter=Q(pages__is_helper=False)))
            .order_by("-created_at")
        )
        return qs

    def create(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        base_url = str(serializer.validated_data.get("base_url") or "").strip()
        if not base_url:
            raise ValidationError({"base_url": "Введите URL сайта"})

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_WEBSITE_ANALYSIS)
        if limit_response:
            return limit_response

        scan = WebsiteScan.objects.create(
            client=client,
            base_url=base_url,
            max_depth=int(serializer.validated_data.get("max_depth") or 3),
            max_pages=int(serializer.validated_data.get("max_pages") or 100),
            status=WebsiteScan.STATUS_PENDING,
            progress=0,
        )
        try:
            tasks.maybe_schedule_next_website_scan_for_client(int(client.id))
        except Exception:
            logger.warning("Failed to schedule WebsiteScan for client %s", client.id, exc_info=True)

        record_generation_event(
            client,
            GenerationEvent.EVENT_WEBSITE_ANALYSIS,
            meta={"base_url": base_url},
        )

        scan.refresh_from_db()
        data = WebsiteScanDetailSerializer(scan, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="pages")
    def pages(self, request, pk=None):
        scan = self.get_object()
        pages = WebsiteScanPage.objects.filter(scan=scan).order_by("depth", "id")
        serializer = WebsiteScanPageSerializer(pages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="mind-map")
    def mind_map(self, request, pk=None):
        scan = self.get_object()
        return Response({"mind_map_id": scan.mind_map_id})

    @action(detail=True, methods=["post"], url_path="rerun", permission_classes=[IsTenantOwnerOrEditor])
    def rerun(self, request, pk=None):
        scan = self.get_object()
        client = get_active_client(request.user)

        if scan.client_id != client.id:
            raise ValidationError({"detail": "Скан не принадлежит текущему клиенту"})

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_WEBSITE_ANALYSIS)
        if limit_response:
            return limit_response

        new_scan = WebsiteScan.objects.create(
            client=client,
            base_url=scan.base_url,
            max_depth=scan.max_depth,
            max_pages=scan.max_pages,
            status=WebsiteScan.STATUS_PENDING,
            progress=0,
        )
        try:
            tasks.maybe_schedule_next_website_scan_for_client(int(client.id))
        except Exception:
            logger.warning("Failed to schedule WebsiteScan for client %s", client.id, exc_info=True)
        new_scan.refresh_from_db()

        record_generation_event(
            client,
            GenerationEvent.EVENT_WEBSITE_ANALYSIS,
            meta={"base_url": scan.base_url, "rerun": True},
        )

        return Response(
            {
                "success": True,
                "scan_id": new_scan.id,
                "task_id": new_scan.task_id,
                "updated_at": timezone.now(),
            }
        )
