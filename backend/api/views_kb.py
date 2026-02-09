from __future__ import annotations

import logging
import secrets
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsTenantMember, IsTenantOwnerOrEditor
from api.utils import get_active_client
from core.models import (
    KbFolder,
    KbDocument,
    KbDocumentVersion,
    KbComment,
    KbDocumentShare,
    KbTag,
)
from .serializers import (
    KbFolderSerializer,
    KbFolderTreeSerializer,
    KbDocumentListSerializer,
    KbDocumentDetailSerializer,
    KbDocumentVersionSerializer,
    KbCommentSerializer,
    KbDocumentShareSerializer,
    KbTagSerializer,
    KbDocumentMoveSerializer,
    KbDocumentDuplicateSerializer,
    KbBulkDocumentArchiveSerializer,
)

logger = logging.getLogger(__name__)


def _issue_share_token() -> str:
    return secrets.token_hex(16)


def _extract_meta_content(tag) -> str:
    if not tag:
        return ""
    content = tag.get("content")
    if content:
        return str(content).strip()
    text = tag.get_text(strip=True)
    return str(text).strip() if text else ""


def _extract_favicon_url(soup: BeautifulSoup, page_url: str) -> str:
    for link in soup.find_all("link"):
        rel = link.get("rel")
        if isinstance(rel, str):
            rel_values = [rel]
        else:
            rel_values = rel or []
        if any("icon" in str(value).lower() for value in rel_values):
            href = str(link.get("href") or "").strip()
            if href:
                return urljoin(page_url, href)
    return ""


class KbFolderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]
    serializer_class = KbFolderSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return KbFolder.objects.filter(workspace=client).order_by("position", "id")

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(workspace=client, created_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="tree")
    def tree(self, request, pk=None):
        folder = self.get_object()
        serializer = KbFolderTreeSerializer(folder, context=self.get_serializer_context())
        return Response(serializer.data)


class KbDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {
            "create",
            "update",
            "partial_update",
            "destroy",
            "move",
            "duplicate",
            "archive",
            "restore",
            "bulk_archive",
            "versions",
            "restore_version",
        }:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        qs = (
            KbDocument.objects.filter(workspace=client)
            .select_related("folder", "created_by", "last_edited_by")
            .prefetch_related("tags")
            .annotate(
                has_children=Exists(
                    KbDocument.objects.filter(parent_document_id=OuterRef("pk"))
                )
            )
        )

        folder_id = self.request.query_params.get("folder")
        parent_id = self.request.query_params.get("parent")
        archived = self.request.query_params.get("archived")
        template = self.request.query_params.get("template")
        search = self.request.query_params.get("search") or self.request.query_params.get("q")

        if folder_id is not None:
            qs = qs.filter(folder_id=folder_id)

        if parent_id is not None:
            qs = qs.filter(parent_document_id=parent_id)

        if archived is not None:
            if str(archived).lower() in {"1", "true", "yes"}:
                qs = qs.filter(is_archived=True)
            else:
                qs = qs.filter(is_archived=False)
        elif self.action == "list":
            qs = qs.filter(is_archived=False)

        if template is not None:
            if str(template).lower() in {"1", "true", "yes"}:
                qs = qs.filter(is_template=True)
            else:
                qs = qs.filter(is_template=False)

        if search:
            qs = qs.filter(Q(title__icontains=search))

        ordering = self.request.query_params.get("ordering")
        if ordering:
            return qs.order_by(ordering)

        return qs.order_by("-updated_at", "id")

    def get_serializer_class(self):
        if self.action == "list":
            return KbDocumentListSerializer
        return KbDocumentDetailSerializer

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        folder = serializer.validated_data.get("folder")
        parent_document = serializer.validated_data.get("parent_document")
        if folder and folder.workspace_id != client.id:
            raise ValidationError("Папка не принадлежит текущему клиенту")
        if parent_document and parent_document.workspace_id != client.id:
            raise ValidationError("Родительский документ не принадлежит текущему клиенту")
        serializer.save(workspace=client, created_by=self.request.user, last_edited_by=self.request.user)

    def perform_update(self, serializer):
        client = get_active_client(self.request.user)
        folder = serializer.validated_data.get("folder")
        parent_document = serializer.validated_data.get("parent_document")
        if folder and folder.workspace_id != client.id:
            raise ValidationError("Папка не принадлежит текущему клиенту")
        if parent_document and parent_document.workspace_id != client.id:
            raise ValidationError("Родительский документ не принадлежит текущему клиенту")
        serializer.save(last_edited_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="move")
    def move(self, request, pk=None):
        document = self.get_object()
        serializer = KbDocumentMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        client = get_active_client(request.user)
        if "folder_id" in data and data.get("folder_id") is not None:
            if not KbFolder.objects.filter(id=data["folder_id"], workspace=client).exists():
                raise ValidationError("Папка не принадлежит текущему клиенту")
        if "parent_document_id" in data and data.get("parent_document_id") is not None:
            if data["parent_document_id"] == document.id:
                raise ValidationError("Документ не может быть своим родителем")
            if not KbDocument.objects.filter(id=data["parent_document_id"], workspace=client).exists():
                raise ValidationError("Родительский документ не принадлежит текущему клиенту")
        if "folder_id" in data:
            document.folder_id = data.get("folder_id")
        if "parent_document_id" in data:
            document.parent_document_id = data.get("parent_document_id")
        if "position" in data:
            document.position = data.get("position")

        document.last_edited_by = request.user
        document.save(update_fields=["folder_id", "parent_document_id", "position", "last_edited_by", "updated_at"])
        return Response(KbDocumentDetailSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        document = self.get_object()
        serializer = KbDocumentDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data.get("title") or f"{document.title} (копия)"
        include_children = serializer.validated_data.get("include_children", False)

        def _duplicate_doc(source: KbDocument, parent: Optional[KbDocument] = None) -> KbDocument:
            new_doc = KbDocument.objects.create(
                workspace=source.workspace,
                folder=source.folder,
                parent_document=parent,
                title=title if parent is None else source.title,
                icon=source.icon,
                cover_image=source.cover_image,
                content=source.content,
                created_by=request.user,
                last_edited_by=request.user,
                is_published=source.is_published,
                is_archived=False,
                is_template=source.is_template,
                position=source.position,
            )
            new_doc.tags.set(source.tags.all())

            if include_children:
                for child in source.child_documents.all().order_by("position", "id"):
                    _duplicate_doc(child, new_doc)
            return new_doc

        duplicated = _duplicate_doc(document)
        return Response(KbDocumentDetailSerializer(duplicated, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        document = self.get_object()
        document.is_archived = True
        document.last_edited_by = request.user
        document.save(update_fields=["is_archived", "last_edited_by", "updated_at"])
        return Response({"success": True})

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        document = self.get_object()
        document.is_archived = False
        document.last_edited_by = request.user
        document.save(update_fields=["is_archived", "last_edited_by", "updated_at"])
        return Response({"success": True})

    @action(detail=False, methods=["post"], url_path="bulk_archive")
    def bulk_archive(self, request):
        serializer = KbBulkDocumentArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["document_ids"]
        archive = serializer.validated_data["archive"]

        client = get_active_client(request.user)
        updated = KbDocument.objects.filter(workspace=client, id__in=ids).update(
            is_archived=archive,
            last_edited_by=request.user,
            updated_at=timezone.now(),
        )
        return Response({"success": True, "updated": updated})

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request, pk=None):
        document = self.get_object()
        if request.method.upper() == "POST":
            latest = (
                KbDocumentVersion.objects.filter(document=document)
                .order_by("-version_number")
                .first()
            )
            next_number = (latest.version_number if latest else 0) + 1
            version = KbDocumentVersion.objects.create(
                document=document,
                title=document.title,
                content=document.content,
                created_by=request.user,
                version_number=next_number,
            )
            return Response(KbDocumentVersionSerializer(version, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

        versions = document.versions.all().order_by("-version_number")
        return Response(KbDocumentVersionSerializer(versions, many=True, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path=r"restore_version/(?P<version_id>[^/.]+)")
    def restore_version(self, request, pk=None, version_id=None):
        document = self.get_object()
        version = get_object_or_404(KbDocumentVersion, document=document, pk=version_id)
        document.title = version.title or document.title
        document.content = version.content
        document.last_edited_by = request.user
        document.save(update_fields=["title", "content", "last_edited_by", "updated_at"])
        return Response(KbDocumentDetailSerializer(document, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        document = self.get_object()
        return Response(KbDocumentDetailSerializer(document, context=self.get_serializer_context()).data)


class KbCommentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]
    serializer_class = KbCommentSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "resolve", "unresolve"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        qs = KbComment.objects.filter(document__workspace=client)
        document_id = self.request.query_params.get("document")
        if document_id:
            qs = qs.filter(document_id=document_id)
        return qs.order_by("created_at", "id")

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        document = serializer.validated_data.get("document")
        if document and document.workspace_id != client.id:
            raise ValidationError("Документ не принадлежит текущему клиенту")
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        comment = self.get_object()
        comment.is_resolved = True
        comment.save(update_fields=["is_resolved", "updated_at"])
        return Response({"success": True})

    @action(detail=True, methods=["post"], url_path="unresolve")
    def unresolve(self, request, pk=None):
        comment = self.get_object()
        comment.is_resolved = False
        comment.save(update_fields=["is_resolved", "updated_at"])
        return Response({"success": True})


class KbDocumentShareViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]
    serializer_class = KbDocumentShareSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "revoke"}:
            return [IsTenantOwnerOrEditor()]
        if self.action in {"by_token"}:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return KbDocumentShare.objects.filter(document__workspace=client).order_by("-created_at")

    def perform_create(self, serializer):
        token = _issue_share_token()
        while KbDocumentShare.objects.filter(share_token=token).exists():
            token = _issue_share_token()
        client = get_active_client(self.request.user)
        document = serializer.validated_data.get("document")
        if document and document.workspace_id != client.id:
            raise ValidationError("Документ не принадлежит текущему клиенту")
        serializer.save(created_by=self.request.user, share_token=token)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        share = self.get_object()
        share.is_active = False
        share.save(update_fields=["is_active"])
        return Response({"success": True, "is_active": False})

    @action(detail=False, methods=["get"], url_path=r"by_token/(?P<token>[^/.]+)", permission_classes=[AllowAny])
    def by_token(self, request, token=None):
        share = get_object_or_404(KbDocumentShare, share_token=token)
        if not share.is_active:
            return Response({"detail": "Ссылка не активна"}, status=status.HTTP_404_NOT_FOUND)
        if share.expires_at and share.expires_at < timezone.now():
            return Response({"detail": "Ссылка истекла"}, status=status.HTTP_410_GONE)

        KbDocumentShare.objects.filter(pk=share.pk).update(visit_count=share.visit_count + 1)
        share.refresh_from_db(fields=["visit_count"])
        data = KbDocumentShareSerializer(share, context=self.get_serializer_context()).data
        data["document_detail"] = KbDocumentDetailSerializer(share.document, context=self.get_serializer_context()).data
        return Response(data)


class KbTagViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTenantMember]
    serializer_class = KbTagSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return KbTag.objects.filter(workspace=client).order_by("name", "id")

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(workspace=client)

    @action(detail=True, methods=["get"], url_path="documents")
    def documents(self, request, pk=None):
        tag = self.get_object()
        documents = tag.documents.filter(is_archived=False).order_by("-updated_at")
        return Response(KbDocumentListSerializer(documents, many=True, context=self.get_serializer_context()).data)


class KbSearchViewSet(viewsets.ViewSet):
    permission_classes = [IsTenantMember]

    def list(self, request):
        client = get_active_client(request.user)
        query = request.query_params.get("q") or ""
        qs = KbDocument.objects.filter(workspace=client)
        if query:
            qs = qs.filter(Q(title__icontains=query))
        qs = qs.order_by("-updated_at")[:50]
        return Response(KbDocumentListSerializer(qs, many=True, context={"request": request}).data)


class KbLinkPreviewView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request, *args, **kwargs):
        raw_url = str(request.data.get("url") or "").strip()
        if not raw_url:
            return Response({"detail": "URL required"}, status=status.HTTP_400_BAD_REQUEST)

        if "://" not in raw_url:
            raw_url = f"https://{raw_url}"

        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return Response({"detail": "Invalid URL"}, status=status.HTTP_400_BAD_REQUEST)

        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return Response({"detail": "Host is not allowed"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            response = requests.get(
                parsed.geturl(),
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ZAVOD LinkPreview/1.0)"},
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.warning("Link preview fetch failed for url=%r", raw_url, exc_info=True)
            return Response({"detail": "Preview failed"}, status=status.HTTP_400_BAD_REQUEST)

        soup = BeautifulSoup(response.text, "html.parser")

        title = _extract_meta_content(soup.find("meta", property="og:title")) or _extract_meta_content(soup.find("title"))
        description = _extract_meta_content(soup.find("meta", property="og:description")) or _extract_meta_content(
            soup.find("meta", attrs={"name": "description"})
        )
        favicon = _extract_favicon_url(soup, response.url)

        return Response(
            {
                "title": title,
                "description": description,
                "favicon": favicon,
                "url": response.url,
            }
        )
