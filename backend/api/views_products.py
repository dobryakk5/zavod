from __future__ import annotations

import logging
from typing import List

from django.db import IntegrityError, connection, transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.ai_generator import AIContentGenerator
from core.models import Client, ClientProduct, ProductType, WordstatResult
from core.services.product_type_templates import ensure_system_product_type_templates, sync_product_types

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import ClientProductSerializer, ProductTypeSerializer
from .utils import get_active_client

logger = logging.getLogger(__name__)


class ProductTypeViewSet(viewsets.ModelViewSet):
    """CRUD for the active client's product types directory."""

    permission_classes = [IsTenantMember]
    serializer_class = ProductTypeSerializer
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return ProductType.objects.filter(owner=client).order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        if not ProductType.objects.filter(owner=client).exists():
            with transaction.atomic():
                if not ProductType.objects.filter(owner=client).exists():
                    ensure_system_product_type_templates()
                    system_client = Client.get_system_client()
                    sync_product_types(system_client, client)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(owner=client)

    @action(
        detail=False,
        methods=["post"],
        url_path="load-template",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def load_template(self, request):
        """
        Copy system product type templates into the active client.

        Only allowed when the client has no product types yet.
        """

        client = get_active_client(request.user)

        with transaction.atomic():
            if ProductType.objects.filter(owner=client).exists():
                raise ValidationError({"detail": "У клиента уже есть типы продукта."})

            ensure_system_product_type_templates()
            system_client = Client.get_system_client()
            templates = list(ProductType.objects.filter(owner=system_client).order_by("id"))
            if not templates:
                return Response(
                    {"detail": "В системе нет шаблонных типов продукта."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            ProductType.objects.bulk_create(
                [
                    ProductType(
                        owner=client,
                        name=tpl.name,
                        value=tpl.value,
                        goal=tpl.goal,
                    )
                    for tpl in templates
                ]
            )

        queryset = ProductType.objects.filter(owner=client).order_by("-updated_at")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
            if all(isinstance(v, str) and v.strip() for v in candidate.values()):
                saved_requirements = {k: str(v).strip() for k, v in candidate.items()}
        except Exception:
            saved_requirements = None

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

        requirements = result.get("requirements")
        if not isinstance(requirements, dict):
            raw = result.get("raw_response") or {}
            requirements = raw.get("requirements") if isinstance(raw, dict) else None

        if isinstance(requirements, dict):
            product_type.requirements_name = str(requirements.get("name") or "").strip() or None
            product_type.requirements_packages = str(requirements.get("packages") or "").strip() or None
            product_type.requirements_audience = str(requirements.get("audience") or "").strip() or None
            product_type.requirements_transformation = str(requirements.get("transformation") or "").strip() or None
            product_type.requirements_metrics = str(requirements.get("metrics") or "").strip() or None
            product_type.requirements_method = str(requirements.get("method") or "").strip() or None
            product_type.requirements_lesson_format = str(requirements.get("lesson_format") or "").strip() or None
            product_type.requirements_program_modules = str(requirements.get("program_modules") or "").strip() or None
            product_type.requirements_packaging = str(requirements.get("packaging") or "").strip() or None
            product_type.save(
                update_fields=[
                    "requirements_name",
                    "requirements_packages",
                    "requirements_audience",
                    "requirements_transformation",
                    "requirements_metrics",
                    "requirements_method",
                    "requirements_lesson_format",
                    "requirements_program_modules",
                    "requirements_packaging",
                    "updated_at",
                ]
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
    def _ensure_core_product_type(client: Client) -> ProductType:
        core_type = ProductType.objects.filter(owner=client, name__iexact="Core").first()
        if core_type:
            return core_type
        return ProductType.objects.create(owner=client, name="Core", value=None, goal=None)

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
        return ClientProduct.objects.select_related("product_type").filter(owner=client).order_by("-updated_at")

    def _ensure_product_type_belongs_to_client(self, serializer, client: Client) -> None:
        product_type = serializer.validated_data.get("product_type")
        if product_type and product_type.owner_id != client.id:
            raise ValidationError({"product_type_id": "Этот тип продукта не принадлежит активному клиенту."})

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

    def perform_update(self, serializer):
        client = get_active_client(self.request.user)
        self._ensure_product_type_belongs_to_client(serializer, client)
        serializer.save()

