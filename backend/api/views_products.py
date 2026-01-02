from __future__ import annotations

import json
import logging
from typing import List

from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai_generator import AIContentGenerator
from core.models import (
    Client,
    ClientProduct,
    MindEdge,
    MindMap,
    MindNode,
    MindNodePosition,
    MindNodeProperty,
    ProductType,
    WordstatResult,
)
from core.services.product_type_templates import (
    ensure_system_product_type_templates,
    migrate_client_product_types_to_system,
)

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ClientProductSerializer,
    MindEdgeSerializer,
    MindMapDetailSerializer,
    MindMapSerializer,
    MindNodePositionSerializer,
    MindNodePropertySerializer,
    MindNodeSerializer,
    ProductTypeSerializer,
)
from .utils import get_active_client

logger = logging.getLogger(__name__)


class ProductTypeViewSet(viewsets.ModelViewSet):
    """Global product types directory (system templates)."""

    permission_classes = [IsTenantMember]
    serializer_class = ProductTypeSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        system_client = Client.get_system_client()
        return ProductType.objects.filter(owner=system_client).order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        ensure_system_product_type_templates()
        if not client.is_system:
            try:
                migrate_client_product_types_to_system(client)
            except Exception:
                logger.exception("Failed to migrate client product types to system templates")
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        system_client = Client.get_system_client()
        serializer.save(owner=system_client)

    @action(
        detail=False,
        methods=["post"],
        url_path="load-template",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def load_template(self, request):
        """
        Deprecated: product types are global now.

        Kept for backward compatibility with old UI flows.
        """
        raise ValidationError({"detail": "Типы продуктов глобальные. Управляйте ими в системном справочнике."})

    @action(
        detail=True,
        methods=["post"],
        url_path="generate-product",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def generate_product(self, request, pk=None):
        """Generate a client product for this product type using the default AI model."""
        product_type = self.get_object()
        client = get_active_client(request.user)

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        favorites_qs = (
            WordstatResult.objects.filter(query__client=client, result_type="favorite")
            .order_by("-count", "phrase")
            .values_list("phrase", flat=True)
        )
        favorites: List[str] = []
        for phrase in favorites_qs[:200]:
            value = (phrase or "").strip()
            if value and value not in favorites:
                favorites.append(value)
            if len(favorites) >= 40:
                break

        if not favorites:
            return Response(
                {
                    "success": False,
                    "error": "В Wordstat нет избранных фраз. Отметьте нужные фразы как «избранное» и повторите.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        saved_requirements = None
        try:
            candidate = {
                "name": getattr(product_type, "requirements_name", None),
                "packages": getattr(product_type, "requirements_packages", None),
                "audience": getattr(product_type, "requirements_audience", None),
                "transformation": getattr(product_type, "requirements_transformation", None),
                "metrics": getattr(product_type, "requirements_metrics", None),
                "method": getattr(product_type, "requirements_method", None),
                "lesson_format": getattr(product_type, "requirements_lesson_format", None),
                "program_modules": getattr(product_type, "requirements_program_modules", None),
                "packaging": getattr(product_type, "requirements_packaging", None),
            }
            missing = [k for k, v in candidate.items() if not isinstance(v, str) or not v.strip()]
            if missing:
                return Response(
                    {
                        "success": False,
                        "error": (
                            "У типа продукта нет AI-требований для генерации. "
                            "Заполните requirements_* в /django-admin/core/producttypeadminproxy/ "
                            f"(пустые: {', '.join(missing)})."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            saved_requirements = {k: str(v).strip() for k, v in candidate.items()}  # type: ignore[arg-type]
        except Exception:
            logger.exception("Failed to load product type requirements for generation")
            return Response(
                {"success": False, "error": "Не удалось прочитать requirements_* для типа продукта."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        result = generator.generate_client_product_from_type(
            product_type_name=product_type.name,
            product_type_value=product_type.value or "",
            product_type_goal=product_type.goal or "",
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=favorites,
            brand=client.name,
            language=language,
            requirements_override=saved_requirements,
        )

        if not result.get("success"):
            return Response(
                {
                    "success": False,
                    "error": result.get("error") or "Не удалось сгенерировать продукт",
                    "raw_response": result.get("raw_response"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return Response(
                {"success": False, "error": "Некорректный ответ генератора"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        def _create_product():
            return ClientProduct.objects.create(
                owner=client,
                product_type=product_type,
                name=str(product_data.get("name") or product_type.name).strip() or product_type.name,
                short_description=(str(product_data.get("short_description") or "").strip() or None),
                packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
                structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
            )

        try:
            with transaction.atomic():
                created = _create_product()
        except IntegrityError as exc:
            # map.products is managed outside Django migrations; occasionally the ID sequence can drift.
            if "products_pkey" not in str(exc):
                raise
            logger.warning(
                "ClientProduct insert failed due to primary key conflict; resetting sequence and retrying"
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT setval(
                      pg_get_serial_sequence('map.products','id'),
                      COALESCE((SELECT MAX(id) FROM map.products), 1)
                    )
                    """
                )
            with transaction.atomic():
                created = _create_product()
        serializer = ClientProductSerializer(created)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ClientProductViewSet(viewsets.ModelViewSet):
    """CRUD for the active client's product list."""

    permission_classes = [IsTenantMember]
    serializer_class = ClientProductSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    @staticmethod
    def _ensure_core_product_type(_: Client) -> ProductType:
        ensure_system_product_type_templates()
        system_client = Client.get_system_client()
        core_type = ProductType.objects.filter(owner=system_client, name__iexact="Core").first()
        if core_type:
            return core_type
        return ProductType.objects.create(owner=system_client, name="Core", value=None, goal=None)

    @staticmethod
    def _normalize_core_description(value: str) -> str:
        cleaned = (value or "").strip()
        prefix = "Core:"
        if cleaned.lower().startswith(prefix.lower()):
            return cleaned
        return f"{prefix} {cleaned}".strip()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        ensure_system_product_type_templates()
        if not client.is_system:
            try:
                migrate_client_product_types_to_system(client)
            except Exception:
                logger.exception("Failed to migrate client product types to system templates")
        return ClientProduct.objects.select_related("product_type").filter(owner=client).order_by("-updated_at")

    def _ensure_product_type_belongs_to_client(self, serializer, client: Client) -> None:
        product_type = serializer.validated_data.get("product_type")
        if not product_type:
            return
        system_client = Client.get_system_client()
        if product_type.owner_id != system_client.id:
            raise ValidationError({"product_type_id": "Тип продукта должен быть системным (общим для всех)."})

    @staticmethod
    def _normalize_typed_description(type_name: str, value: str) -> str:
        cleaned = (value or "").strip()
        prefix = f"{(type_name or '').strip()}:".strip()
        if not prefix or prefix == ":":
            return cleaned
        if cleaned.lower().startswith(prefix.lower()):
            return cleaned
        return f"{prefix} {cleaned}".strip()

    @staticmethod
    def _format_core_context(core_product: ClientProduct) -> str:
        structure = core_product.structure if isinstance(core_product.structure, dict) else {}
        packages = core_product.packages if isinstance(core_product.packages, list) else []

        summary = {
            "core": {
                "id": core_product.id,
                "name": core_product.name,
                "short_description": core_product.short_description,
            },
            "packages": packages,
            "structure": structure,
        }

        return json.dumps(summary, ensure_ascii=False)

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        self._ensure_product_type_belongs_to_client(serializer, client)
        serializer.save(owner=client)

    @action(
        detail=False,
        methods=["post"],
        url_path="create-core",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_core(self, request):
        client = get_active_client(request.user)
        name = str(request.data.get("name") or "").strip()
        short_description = str(request.data.get("short_description") or "").strip()

        if not name:
            raise ValidationError({"name": "Название обязательно."})
        if not short_description:
            raise ValidationError({"short_description": "Описание обязательно."})

        core_type = self._ensure_core_product_type(client)
        created = ClientProduct.objects.create(
            owner=client,
            product_type=core_type,
            name=name,
            short_description=self._normalize_core_description(short_description),
            packages=[],
            structure={},
        )
        serializer = self.get_serializer(created)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        url_path="create-core-ai",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_core_ai(self, request):
        client = get_active_client(request.user)
        name = str(request.data.get("name") or "").strip()
        short_description = str(request.data.get("short_description") or "").strip()

        if not name:
            raise ValidationError({"name": "Название обязательно."})
        if not short_description:
            raise ValidationError({"short_description": "Описание обязательно."})

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        core_type = self._ensure_core_product_type(client)

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        requirements_override = {
            "name": (
                f"Используй название строго: '{name}'. "
                f"short_description должен начинаться с 'Core:' и передавать смысл: {short_description}."
            )
        }

        result = generator.generate_client_product_from_type(
            product_type_name=core_type.name,
            product_type_value=core_type.value or "",
            product_type_goal=short_description,
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=[],
            brand=client.name,
            language=language,
            requirements_override=requirements_override,
        )

        if not result.get("success"):
            return Response(
                {
                    "detail": result.get("error") or "Не удалось сгенерировать core-продукт",
                    "raw_response": result.get("raw_response"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return Response({"detail": "Некорректный ответ генератора"}, status=status.HTTP_502_BAD_GATEWAY)

        created = ClientProduct.objects.create(
            owner=client,
            product_type=core_type,
            name=name,
            short_description=self._normalize_core_description(short_description),
            packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
            structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
        )
        serializer = self.get_serializer(created)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="create-related-ai",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_related_ai(self, request, pk=None):
        """
        Create a related product inside a Core product using the Core context.

        Payload:
        - name: string (required)
        - product_type_id: number (required, must be system/global)
        - short_description: string (optional, used as extra hint)
        - language: 'ru' | 'en' (optional)
        """

        client = get_active_client(request.user)
        core_product = get_object_or_404(ClientProduct.objects.select_related("product_type"), pk=pk, owner=client)
        core_type_name = (getattr(core_product.product_type, "name", None) or "").strip().lower()
        if core_type_name != "core":
            raise ValidationError({"detail": "Сопутствующие продукты можно создавать только внутри Core-продукта."})

        name = str(request.data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Название обязательно."})

        try:
            product_type_id = int(request.data.get("product_type_id"))
        except (TypeError, ValueError):
            raise ValidationError({"product_type_id": "Укажите product_type_id (число)."})

        system_client = Client.get_system_client()
        product_type = get_object_or_404(ProductType.objects.select_related("owner"), pk=product_type_id)
        if product_type.owner_id != system_client.id:
            raise ValidationError({"product_type_id": "Тип продукта должен быть системным (общим для всех)."})
        if (product_type.name or "").strip().lower() == "core":
            raise ValidationError({"product_type_id": "Core создаётся в общем списке. Внутри Core создавайте сопутствующие типы."})

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        hint = str(request.data.get("short_description") or "").strip()

        candidate = {
            "name": getattr(product_type, "requirements_name", None),
            "packages": getattr(product_type, "requirements_packages", None),
            "audience": getattr(product_type, "requirements_audience", None),
            "transformation": getattr(product_type, "requirements_transformation", None),
            "metrics": getattr(product_type, "requirements_metrics", None),
            "method": getattr(product_type, "requirements_method", None),
            "lesson_format": getattr(product_type, "requirements_lesson_format", None),
            "program_modules": getattr(product_type, "requirements_program_modules", None),
            "packaging": getattr(product_type, "requirements_packaging", None),
        }
        missing = [k for k, v in candidate.items() if not isinstance(v, str) or not v.strip()]
        if missing:
            raise ValidationError(
                {
                    "detail": (
                        "У типа продукта нет AI-требований для генерации. "
                        "Заполните requirements_* в /django-admin/core/producttypeadminproxy/ "
                        f"(пустые: {', '.join(missing)})."
                    )
                }
            )

        requirements_override = {k: str(v).strip() for k, v in candidate.items()}  # type: ignore[arg-type]
        requirements_override["name"] = (
            f"{requirements_override['name']}\n\n"
            "ДОПОЛНИТЕЛЬНО ДЛЯ ЭТОГО ПРОДУКТА\n"
            f"- Название строго: '{name}'.\n"
            f"- short_description должен начинаться с '{product_type.name}:' и быть связан с Core.\n"
            + (f"- Уточнение от пользователя: {hint}\n" if hint else "")
        ).strip()

        core_context = self._format_core_context(core_product)

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        result = generator.generate_client_product_from_type(
            product_type_name=product_type.name,
            product_type_value=product_type.value or "",
            product_type_goal=product_type.goal or "",
            avatar=client.avatar or "",
            pains=client.pains or "",
            desires=client.desires or "",
            objections=client.objections or "",
            wordstat_favorites=[],
            brand=client.get_brand_display_name(),
            language=language,
            requirements_override=requirements_override,
            additional_context=core_context,
        )

        if not result.get("success"):
            return Response(
                {"detail": result.get("error") or "Не удалось сгенерировать сопутствующий продукт", "raw_response": result.get("raw_response")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        product_data = result.get("product") or {}
        if not isinstance(product_data, dict):
            return Response({"detail": "Некорректный ответ генератора"}, status=status.HTTP_502_BAD_GATEWAY)

        generated_short_description = str(product_data.get("short_description") or "").strip()
        if not generated_short_description:
            generated_short_description = f"{product_type.name}: {name}"

        created = ClientProduct.objects.create(
            owner=client,
            product_type=product_type,
            name=name,
            short_description=self._normalize_typed_description(product_type.name, generated_short_description) or None,
            packages=product_data.get("packages") if isinstance(product_data.get("packages"), list) else [],
            structure=product_data.get("structure") if isinstance(product_data.get("structure"), dict) else {},
        )
        serializer = self.get_serializer(created)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        client = get_active_client(self.request.user)
        self._ensure_product_type_belongs_to_client(serializer, client)
        serializer.save()


def _touch_mind_map(map_id: int) -> None:
    MindMap.objects.filter(pk=map_id).update(updated_at=timezone.now())


class MindMapViewSet(viewsets.ModelViewSet):
    """Mind map CRUD limited to the active client."""

    permission_classes = [IsTenantMember]
    serializer_class = MindMapSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "create_node", "create_edge"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MindMapDetailSerializer
        if self.action == "create_node":
            return MindNodeSerializer
        if self.action == "create_edge":
            return MindEdgeSerializer
        return MindMapSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        base_qs = MindMap.objects.filter(owner=client).annotate(
            nodes_count=Count("nodes", distinct=True),
            edges_count=Count("edges", distinct=True),
        )

        if self.action == "list":
            return base_qs.order_by("-updated_at")

        return base_qs.prefetch_related(
            Prefetch("nodes", queryset=MindNode.objects.select_related("position").prefetch_related("properties")),
            Prefetch("edges", queryset=MindEdge.objects.all()),
        )

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(owner=client)

    @action(detail=True, methods=["post"], url_path="nodes", permission_classes=[IsTenantOwnerOrEditor])
    def create_node(self, request, pk=None):
        mind_map = self.get_object()
        serializer = MindNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        node = serializer.save(map=mind_map)
        _touch_mind_map(mind_map.id)
        return Response(MindNodeSerializer(node).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="edges", permission_classes=[IsTenantOwnerOrEditor])
    def create_edge(self, request, pk=None):
        mind_map = self.get_object()
        serializer = MindEdgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from_node = serializer.validated_data.get("from_node")
        to_node = serializer.validated_data.get("to_node")

        if from_node and from_node.map_id != mind_map.id:
            return Response({"detail": "from_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)
        if to_node and to_node.map_id != mind_map.id:
            return Response({"detail": "to_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)

        edge = serializer.save(map=mind_map)
        _touch_mind_map(mind_map.id)
        return Response(MindEdgeSerializer(edge).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"edges/(?P<edge_id>[^/.]+)",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def update_edge(self, request, pk=None, edge_id=None):
        mind_map = self.get_object()
        edge = get_object_or_404(MindEdge.objects.filter(map=mind_map), pk=edge_id)

        if request.method.upper() == "DELETE":
            edge.delete()
            _touch_mind_map(mind_map.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = MindEdgeSerializer(edge, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        from_node = serializer.validated_data.get("from_node")
        to_node = serializer.validated_data.get("to_node")

        if from_node and from_node.map_id != mind_map.id:
            return Response({"detail": "from_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)
        if to_node and to_node.map_id != mind_map.id:
            return Response({"detail": "to_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        _touch_mind_map(mind_map.id)
        return Response(MindEdgeSerializer(edge).data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"nodes/(?P<node_id>[^/.]+)",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def update_node(self, request, pk=None, node_id=None):
        mind_map = self.get_object()
        node = get_object_or_404(MindNode.objects.filter(map=mind_map), pk=node_id)

        if request.method.upper() == "DELETE":
            node.delete()
            _touch_mind_map(mind_map.id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = MindNodeSerializer(node, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _touch_mind_map(mind_map.id)
        return Response(MindNodeSerializer(node).data, status=status.HTTP_200_OK)


class MindNodePositionView(APIView):
    """Upsert node coordinates for the active client's map."""

    permission_classes = [IsTenantOwnerOrEditor]

    def put(self, request, node_id):
        client = get_active_client(request.user)
        node = get_object_or_404(
            MindNode.objects.select_related("map", "position"),
            pk=node_id,
            map__owner=client,
        )

        try:
            position_instance = node.position
        except MindNodePosition.DoesNotExist:
            position_instance = None

        serializer = MindNodePositionSerializer(
            instance=position_instance,
            data=request.data,
            partial=position_instance is not None,
        )
        serializer.is_valid(raise_exception=True)
        position = serializer.save(node=node)
        _touch_mind_map(node.map_id)
        return Response(MindNodePositionSerializer(position).data, status=status.HTTP_200_OK)


class MindNodePropertyViewSet(viewsets.ModelViewSet):
    """CRUD для свойств узлов карты."""

    serializer_class = MindNodePropertySerializer
    permission_classes = [IsTenantMember]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        qs = (
            MindNodeProperty.objects.select_related("node", "node__map")
            .filter(node__map__owner=client)
            .order_by("order_index", "id")
        )
        node_id = self.request.query_params.get("node_id")
        if node_id:
            qs = qs.filter(node_id=node_id)
        return qs

    def perform_create(self, serializer):
        node = serializer.validated_data.get("node")
        if node is None:
            raise ValidationError("Не указан node")

        client = get_active_client(self.request.user)
        if node.map.owner_id != client.id:
            raise PermissionDenied("Узел не относится к текущему клиенту")

        serializer.save()
        _touch_mind_map(node.map_id)

    def perform_update(self, serializer):
        instance = serializer.instance
        serializer.save()
        if instance is not None:
            _touch_mind_map(instance.node.map_id)

    def perform_destroy(self, instance):
        map_id = instance.node.map_id
        instance.delete()
        _touch_mind_map(map_id)
