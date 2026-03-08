from __future__ import annotations

import json
import logging

from config.celery import app as celery_app
from core import tasks
from core.generation_events import record_generation_event
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Client,
    ClientProduct,
    GenerationEvent,
    MindEdge,
    MindMap,
    MindNode,
    MindNodePosition,
    MindNodeProperty,
    ProductCourse,
    ProductCourseLesson,
    ProductCourseModule,
    ProductCourseProgress,
    ProductType,
    WeeklySalesPlan,
)
from core.services.product_type_templates import (
    ensure_system_product_type_templates,
    ensure_system_product_type_requirements,
    is_system_product_type_name,
    migrate_client_product_types_to_system,
)
from core.services.product_mindmap import (
    build_all_products_mind_map,
    build_related_products_mind_map,
    sync_core_related_for_edge_create,
    sync_core_related_for_edge_delete,
    sync_core_related_for_node_delete,
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
    ProductCourseLessonSerializer,
    ProductCourseModuleSerializer,
    ProductCourseSerializer,
    ProductTypeSerializer,
    WeeklySalesPlanSerializer,
)
from .utils import enforce_generation_limit, get_active_client

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

    def destroy(self, request, *args, **kwargs):
        product_type = self.get_object()
        if is_system_product_type_name(getattr(product_type, "name", None)):
            raise ValidationError({"detail": "Системные типы продуктов нельзя удалять."})
        return super().destroy(request, *args, **kwargs)

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
        ensure_system_product_type_templates()

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_PRODUCT)
        if limit_response:
            return limit_response

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        requested_name = str(request.data.get("name") or "").strip() or None
        requested_short_description = str(request.data.get("short_description") or "").strip() or None

        task_kwargs = {"language": language}
        if requested_name:
            task_kwargs["name"] = requested_name
        if requested_short_description:
            task_kwargs["short_description"] = requested_short_description

        task = tasks.generate_client_product_for_type_task.delay(
            client.id,
            product_type.id,
            **task_kwargs,
        )
        record_generation_event(
            client,
            GenerationEvent.EVENT_PRODUCT,
            meta={
                "product_type_id": product_type.id,
                "name_prefilled": bool(requested_name),
                "description_prefilled": bool(requested_short_description),
            },
        )
        payload = {"success": True, "message": f"Запущена генерация продукта типа {product_type.name}", "task_id": task.id}
        if getattr(task, "ready", None) and task.ready() and isinstance(getattr(task, "result", None), dict):
            payload["result"] = task.result
            product_id = task.result.get("product_id")
            if product_id:
                product = ClientProduct.objects.select_related("product_type").filter(pk=product_id, owner=client).first()
                if product:
                    payload["product"] = ClientProductSerializer(product).data
        return Response(payload, status=status.HTTP_202_ACCEPTED)


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
        created = ProductType.objects.create(owner=system_client, name="Core", value=None, goal=None)
        ensure_system_product_type_requirements()
        return created

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
        return (
            ClientProduct.objects
            .select_related("product_type", "course")
            .filter(owner=client)
            .order_by("-updated_at")
        )

    @staticmethod
    def _normalize_datetime_input(raw_value):
        if raw_value in (None, "", "null"):
            return None
        if hasattr(raw_value, "isoformat"):
            return raw_value
        parsed = parse_datetime(str(raw_value))
        if parsed is None:
            raise ValidationError({"unlock_at": "unlock_at must be valid ISO datetime."})
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone=timezone.get_current_timezone())
        return parsed

    @staticmethod
    def _to_bool(raw_value, default=False):
        if raw_value is None:
            return default
        if isinstance(raw_value, bool):
            return raw_value
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _normalize_non_negative_int_input(raw_value, field_name: str, default: int = 0) -> int:
        if raw_value in (None, "", "null"):
            return int(default)
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            raise ValidationError({field_name: f"{field_name} must be a non-negative integer."})
        if parsed < 0:
            raise ValidationError({field_name: f"{field_name} must be >= 0."})
        return parsed

    @staticmethod
    def _normalize_module_unlock_condition(raw_value, default: str | None = None) -> str:
        allowed = {
            ProductCourseModule.LESSON_UNLOCK_AFTER_STUDENT_COMPLETE,
            ProductCourseModule.LESSON_UNLOCK_AFTER_CURATOR_COMPLETE,
            ProductCourseModule.LESSON_UNLOCK_AFTER_TIMER,
        }
        fallback = default or ProductCourseModule.LESSON_UNLOCK_AFTER_STUDENT_COMPLETE
        if raw_value in (None, "", "null"):
            return fallback
        value = str(raw_value).strip()
        if value not in allowed:
            raise ValidationError({"lesson_unlock_condition": "Unsupported lesson_unlock_condition value."})
        return value

    def _get_or_create_product_course(self, product: ClientProduct) -> ProductCourse:
        course = getattr(product, "course", None)
        if course:
            return course
        return ProductCourse.objects.create(
            owner_id=product.owner_id,
            product=product,
            title=(product.name or "").strip() or f"Курс продукта #{product.id}",
            description=(product.short_description or "").strip(),
            is_published=False,
        )

    @staticmethod
    def _default_lesson_content() -> dict:
        return {
            "blocks": [
                {
                    "id": "video",
                    "type": "video",
                    "video_url": "",
                    "youtube_video_id": None,
                    "rutube_video_id": None,
                    "vk_owner_id": None,
                    "vk_video_id": None,
                    "vk_hash": None,
                },
                {
                    "id": "tiptap",
                    "type": "tiptap",
                    "content": {"type": "doc", "content": [{"type": "paragraph", "content": []}]},
                },
            ],
        }

    def _serialize_product_course(self, course: ProductCourse) -> dict:
        modules = list(
            ProductCourseModule.objects.filter(course_id=course.id).order_by("position", "id")
        )
        module_ids = [int(item.id) for item in modules]
        lessons_by_module: dict[int, list[ProductCourseLesson]] = {module_id: [] for module_id in module_ids}
        lessons = list(
            ProductCourseLesson.objects.filter(module_id__in=module_ids).order_by("position", "id")
            if module_ids
            else []
        )
        for lesson in lessons:
            key = int(lesson.module_id)
            lessons_by_module.setdefault(key, []).append(lesson)
        for module in modules:
            setattr(module, "_prefetched_lessons", lessons_by_module.get(int(module.id), []))
        setattr(course, "_prefetched_modules", modules)
        return ProductCourseSerializer(course, context=self.get_serializer_context()).data

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

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_PRODUCT)
        if limit_response:
            return limit_response

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        task = tasks.generate_core_product_task.delay(
            client.id,
            name=name,
            short_description=short_description,
            language=language,
        )
        record_generation_event(
            client,
            GenerationEvent.EVENT_PRODUCT,
            meta={"product_type": "core"},
        )
        payload = {"success": True, "message": "Запущена генерация Core-продукта", "task_id": task.id}
        if getattr(task, "ready", None) and task.ready() and isinstance(getattr(task, "result", None), dict):
            payload["result"] = task.result
            product_id = task.result.get("product_id")
            if product_id:
                product = ClientProduct.objects.select_related("product_type").filter(pk=product_id, owner=client).first()
                if product:
                    payload["product"] = ClientProductSerializer(product).data
        return Response(payload, status=status.HTTP_202_ACCEPTED)

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

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_PRODUCT)
        if limit_response:
            return limit_response

        language = (request.data.get("language") or "ru").strip().lower()
        if language not in {"ru", "en"}:
            language = "ru"

        hint = str(request.data.get("short_description") or "").strip()
        ensure_system_product_type_templates()

        task = tasks.generate_related_product_task.delay(
            client.id,
            core_product.id,
            product_type.id,
            name=name or None,
            hint=hint,
            language=language,
        )
        record_generation_event(
            client,
            GenerationEvent.EVENT_PRODUCT,
            meta={"product_type_id": product_type.id, "core_product_id": core_product.id},
        )
        payload = {
            "success": True,
            "message": f"Запущена генерация сопутствующего продукта типа {product_type.name}",
            "task_id": task.id,
        }
        if getattr(task, "ready", None) and task.ready() and isinstance(getattr(task, "result", None), dict):
            payload["result"] = task.result
            product_id = task.result.get("product_id")
            if product_id:
                product = ClientProduct.objects.select_related("product_type").filter(pk=product_id, owner=client).first()
                if product:
                    payload["product"] = ClientProductSerializer(product).data
        return Response(payload, status=status.HTTP_202_ACCEPTED)

    @action(
        detail=True,
        methods=["post"],
        url_path="create-related-map",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_related_map(self, request, pk=None):
        client = get_active_client(request.user)
        core_product = get_object_or_404(ClientProduct.objects.select_related("product_type"), pk=pk, owner=client)
        core_type_name = (getattr(core_product.product_type, "name", None) or "").strip().lower()
        if core_type_name != "core":
            raise ValidationError({"detail": "Карту сопутствующих можно создавать только для Core-продукта."})
        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_PRODUCT_MAP)
        if limit_response:
            return limit_response
        created = build_related_products_mind_map(client, core_product)
        record_generation_event(
            client,
            GenerationEvent.EVENT_PRODUCT_MAP,
            meta={"core_product_id": core_product.id},
        )
        serializer = MindMapSerializer(created, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="generation-status", permission_classes=[IsTenantMember])
    def generation_status(self, request):
        """Вернуть состояние задачи генерации продукта по task_id."""
        task_id = request.query_params.get("task_id")
        if not task_id:
            return Response({"success": False, "error": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            async_result = celery_app.AsyncResult(task_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to fetch product generation status for %s: %s", task_id, exc, exc_info=True)
            return Response({"success": False, "error": "Не удалось получить статус задачи"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        state = (async_result.state or "").lower()
        payload = {"success": state == "success", "status": state, "task_id": task_id}

        if state == "success" and isinstance(async_result.result, dict):
            payload["result"] = async_result.result
            product_id = async_result.result.get("product_id")
            if product_id:
                client = get_active_client(request.user)
                product = ClientProduct.objects.select_related("product_type").filter(pk=product_id, owner=client).first()
                if product:
                    payload["product"] = ClientProductSerializer(product).data
        elif state in ("failure", "revoked"):
            error_info = getattr(async_result, "info", None)
            payload["error"] = str(error_info) if error_info else "Задача завершилась с ошибкой"

        return Response(payload)

    def perform_update(self, serializer):
        client = get_active_client(self.request.user)
        self._ensure_product_type_belongs_to_client(serializer, client)
        serializer.save()

    @action(
        detail=True,
        methods=["get", "put"],
        url_path="course",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def manage_course(self, request, pk=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)

        if request.method.lower() == "get":
            course = getattr(product, "course", None)
            return Response({"course": self._serialize_product_course(course) if course else None})

        course = self._get_or_create_product_course(product)
        update_fields: list[str] = []

        if "title" in request.data:
            course.title = str(request.data.get("title") or "").strip() or course.title
            update_fields.append("title")
        if "description" in request.data:
            course.description = str(request.data.get("description") or "").strip()
            update_fields.append("description")
        if "cover_url" in request.data:
            course.cover_url = str(request.data.get("cover_url") or "").strip() or None
            update_fields.append("cover_url")
        if "is_published" in request.data:
            course.is_published = self._to_bool(request.data.get("is_published"), default=False)
            update_fields.append("is_published")

        if update_fields:
            course.save(update_fields=update_fields)

        return Response({"course": self._serialize_product_course(course)})

    @action(
        detail=True,
        methods=["post"],
        url_path="course/modules",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_course_module(self, request, pk=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = self._get_or_create_product_course(product)

        title = str(request.data.get("title") or "").strip() or "Новый модуль"
        position_raw = request.data.get("position")
        try:
            position = int(position_raw) if position_raw not in (None, "") else ProductCourseModule.objects.filter(course=course).count()
        except (TypeError, ValueError):
            raise ValidationError({"position": "position must be an integer."})

        module = ProductCourseModule.objects.create(
            course=course,
            title=title,
            cover_url=str(request.data.get("cover_url") or "").strip() or None,
            position=position,
            unlock_at=self._normalize_datetime_input(request.data.get("unlock_at")),
            open_lessons_immediately=self._to_bool(request.data.get("open_lessons_immediately"), default=False),
            lesson_unlock_condition=self._normalize_module_unlock_condition(request.data.get("lesson_unlock_condition")),
            unlock_delay_days=self._normalize_non_negative_int_input(request.data.get("unlock_delay_days"), "unlock_delay_days", default=0),
            unlock_delay_hours=self._normalize_non_negative_int_input(request.data.get("unlock_delay_hours"), "unlock_delay_hours", default=0),
            unlock_delay_minutes=self._normalize_non_negative_int_input(request.data.get("unlock_delay_minutes"), "unlock_delay_minutes", default=0),
        )
        payload = ProductCourseModuleSerializer(module, context=self.get_serializer_context()).data
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"course/modules/(?P<module_id>[0-9]+)",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def manage_course_module(self, request, pk=None, module_id=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        module = get_object_or_404(ProductCourseModule, pk=module_id, course=course)
        if request.method.lower() == "delete":
            module.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        update_fields: list[str] = []
        if "title" in request.data:
            module.title = str(request.data.get("title") or "").strip() or module.title
            update_fields.append("title")
        if "cover_url" in request.data:
            module.cover_url = str(request.data.get("cover_url") or "").strip() or None
            update_fields.append("cover_url")
        if "position" in request.data:
            try:
                module.position = int(request.data.get("position"))
            except (TypeError, ValueError):
                raise ValidationError({"position": "position must be an integer."})
            update_fields.append("position")
        if "unlock_at" in request.data:
            module.unlock_at = self._normalize_datetime_input(request.data.get("unlock_at"))
            update_fields.append("unlock_at")
        if "open_lessons_immediately" in request.data:
            module.open_lessons_immediately = self._to_bool(
                request.data.get("open_lessons_immediately"),
                default=False,
            )
            update_fields.append("open_lessons_immediately")
        if "lesson_unlock_condition" in request.data:
            module.lesson_unlock_condition = self._normalize_module_unlock_condition(
                request.data.get("lesson_unlock_condition"),
                default=module.lesson_unlock_condition or ProductCourseModule.LESSON_UNLOCK_AFTER_STUDENT_COMPLETE,
            )
            update_fields.append("lesson_unlock_condition")
        if "unlock_delay_days" in request.data:
            module.unlock_delay_days = self._normalize_non_negative_int_input(
                request.data.get("unlock_delay_days"),
                "unlock_delay_days",
                default=module.unlock_delay_days or 0,
            )
            update_fields.append("unlock_delay_days")
        if "unlock_delay_hours" in request.data:
            module.unlock_delay_hours = self._normalize_non_negative_int_input(
                request.data.get("unlock_delay_hours"),
                "unlock_delay_hours",
                default=module.unlock_delay_hours or 0,
            )
            update_fields.append("unlock_delay_hours")
        if "unlock_delay_minutes" in request.data:
            module.unlock_delay_minutes = self._normalize_non_negative_int_input(
                request.data.get("unlock_delay_minutes"),
                "unlock_delay_minutes",
                default=module.unlock_delay_minutes or 0,
            )
            update_fields.append("unlock_delay_minutes")

        if update_fields:
            module.save(update_fields=update_fields)
        payload = ProductCourseModuleSerializer(module, context=self.get_serializer_context()).data
        return Response(payload)

    @action(
        detail=True,
        methods=["patch"],
        url_path="course/modules/reorder",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def reorder_course_modules(self, request, pk=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        ordered_ids = request.data.get("ordered_ids")
        if not isinstance(ordered_ids, list):
            raise ValidationError({"ordered_ids": "ordered_ids must be a list of module ids."})

        modules = {int(item.id): item for item in ProductCourseModule.objects.filter(course=course)}
        for position, raw_id in enumerate(ordered_ids):
            try:
                module_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            module = modules.get(module_id)
            if not module:
                continue
            module.position = position
            module.save(update_fields=["position"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"course/modules/(?P<module_id>[0-9]+)/lessons",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def create_course_lesson(self, request, pk=None, module_id=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        module = get_object_or_404(ProductCourseModule, pk=module_id, course=course)
        title = str(request.data.get("title") or "").strip() or "Новый урок"
        position_raw = request.data.get("position")
        try:
            position = int(position_raw) if position_raw not in (None, "") else ProductCourseLesson.objects.filter(module=module).count()
        except (TypeError, ValueError):
            raise ValidationError({"position": "position must be an integer."})

        lesson = ProductCourseLesson.objects.create(
            module=module,
            title=title,
            content=request.data.get("content") if isinstance(request.data.get("content"), dict) else self._default_lesson_content(),
            position=position,
            is_preview=self._to_bool(request.data.get("is_preview"), default=False),
            unlock_at=self._normalize_datetime_input(request.data.get("unlock_at")),
            youtube_video_id=str(request.data.get("youtube_video_id") or "").strip() or None,
            rutube_video_id=str(request.data.get("rutube_video_id") or "").strip() or None,
            vk_owner_id=str(request.data.get("vk_owner_id") or "").strip() or None,
            vk_video_id=str(request.data.get("vk_video_id") or "").strip() or None,
            vk_hash=str(request.data.get("vk_hash") or "").strip() or None,
        )
        payload = ProductCourseLessonSerializer(lesson, context=self.get_serializer_context()).data
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"course/lessons/(?P<lesson_id>[0-9]+)",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def manage_course_lesson(self, request, pk=None, lesson_id=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        lesson = get_object_or_404(ProductCourseLesson, pk=lesson_id, module__course=course)
        if request.method.lower() == "delete":
            lesson.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        update_fields: list[str] = []
        if "title" in request.data:
            lesson.title = str(request.data.get("title") or "").strip() or lesson.title
            update_fields.append("title")
        if "content" in request.data:
            raw_content = request.data.get("content")
            if not isinstance(raw_content, dict):
                raise ValidationError({"content": "content must be an object."})
            lesson.content = raw_content
            update_fields.append("content")
        if "position" in request.data:
            try:
                lesson.position = int(request.data.get("position"))
            except (TypeError, ValueError):
                raise ValidationError({"position": "position must be an integer."})
            update_fields.append("position")
        if "is_preview" in request.data:
            lesson.is_preview = self._to_bool(request.data.get("is_preview"), default=False)
            update_fields.append("is_preview")
        if "unlock_at" in request.data:
            lesson.unlock_at = self._normalize_datetime_input(request.data.get("unlock_at"))
            update_fields.append("unlock_at")
        if "youtube_video_id" in request.data:
            lesson.youtube_video_id = str(request.data.get("youtube_video_id") or "").strip() or None
            update_fields.append("youtube_video_id")
        if "rutube_video_id" in request.data:
            lesson.rutube_video_id = str(request.data.get("rutube_video_id") or "").strip() or None
            update_fields.append("rutube_video_id")
        if "vk_owner_id" in request.data:
            lesson.vk_owner_id = str(request.data.get("vk_owner_id") or "").strip() or None
            update_fields.append("vk_owner_id")
        if "vk_video_id" in request.data:
            lesson.vk_video_id = str(request.data.get("vk_video_id") or "").strip() or None
            update_fields.append("vk_video_id")
        if "vk_hash" in request.data:
            lesson.vk_hash = str(request.data.get("vk_hash") or "").strip() or None
            update_fields.append("vk_hash")

        if update_fields:
            lesson.save(update_fields=update_fields)
        payload = ProductCourseLessonSerializer(lesson, context=self.get_serializer_context()).data
        return Response(payload)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"course/lessons/(?P<lesson_id>[0-9]+)/curator-complete",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def curator_complete_course_lesson(self, request, pk=None, lesson_id=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        lesson = get_object_or_404(ProductCourseLesson, pk=lesson_id, module__course=course)
        raw_contact_id = request.data.get("contact_id")
        try:
            contact_id = int(raw_contact_id)
        except (TypeError, ValueError):
            raise ValidationError({"contact_id": "contact_id must be an integer."})
        if contact_id <= 0:
            raise ValidationError({"contact_id": "contact_id must be > 0."})

        now = timezone.now()
        progress, created = ProductCourseProgress.objects.get_or_create(
            owner_id=client.id,
            contact_id=contact_id,
            lesson_id=lesson.id,
            defaults={
                "completed_at": now,
                "curator_completed_at": now,
                "curator_user_id": request.user.id,
            },
        )
        if not created:
            progress.curator_completed_at = now
            progress.curator_user_id = request.user.id
            progress.save(update_fields=["curator_completed_at", "curator_user_id"])

        return Response(
            {
                "ok": True,
                "created": created,
                "lesson_id": int(lesson.id),
                "contact_id": int(contact_id),
                "curator_completed_at": now,
            }
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"course/modules/(?P<module_id>[0-9]+)/lessons/reorder",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def reorder_course_lessons(self, request, pk=None, module_id=None):
        client = get_active_client(request.user)
        product = get_object_or_404(ClientProduct.objects.select_related("course"), pk=pk, owner=client)
        course = getattr(product, "course", None)
        if not course:
            raise ValidationError({"detail": "Курс для продукта не создан."})

        module = get_object_or_404(ProductCourseModule, pk=module_id, course=course)
        ordered_ids = request.data.get("ordered_ids")
        if not isinstance(ordered_ids, list):
            raise ValidationError({"ordered_ids": "ordered_ids must be a list of lesson ids."})

        lessons = {int(item.id): item for item in ProductCourseLesson.objects.filter(module=module)}
        for position, raw_id in enumerate(ordered_ids):
            try:
                lesson_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            lesson = lessons.get(lesson_id)
            if not lesson:
                continue
            lesson.position = position
            lesson.save(update_fields=["position"])
        return Response(status=status.HTTP_204_NO_CONTENT)

class WeeklySalesPlanViewSet(viewsets.ModelViewSet):
    """Weekly sales plan/fact data."""

    permission_classes = [IsTenantMember]
    serializer_class = WeeklySalesPlanSerializer
    pagination_class = None
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return WeeklySalesPlan.objects.filter(client=client).order_by("-week_start")

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)


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

    @action(detail=False, methods=["post"], url_path="create-products-map", permission_classes=[IsTenantOwnerOrEditor])
    def create_products_map(self, request):
        client = get_active_client(request.user)
        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_PRODUCT_MAP)
        if limit_response:
            return limit_response
        created = build_all_products_mind_map(client)
        record_generation_event(
            client,
            GenerationEvent.EVENT_PRODUCT_MAP,
            meta={"map_type": "all_products"},
        )
        serializer = MindMapSerializer(created, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        try:
            client = get_active_client(request.user)
            sync_core_related_for_edge_create(client, mind_map, str(edge.from_node_id), str(edge.to_node_id))
        except Exception:
            logger.exception("Failed to sync product relations after edge create (map=%s edge=%s)", mind_map.id, edge.id)
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
            old_from = str(edge.from_node_id)
            old_to = str(edge.to_node_id)
            edge.delete()
            _touch_mind_map(mind_map.id)
            try:
                client = get_active_client(request.user)
                sync_core_related_for_edge_delete(client, mind_map, old_from, old_to)
            except Exception:
                logger.exception("Failed to sync product relations after edge delete (map=%s edge=%s)", mind_map.id, edge_id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        old_from = str(edge.from_node_id)
        old_to = str(edge.to_node_id)
        serializer = MindEdgeSerializer(edge, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        from_node = serializer.validated_data.get("from_node")
        to_node = serializer.validated_data.get("to_node")

        if from_node and from_node.map_id != mind_map.id:
            return Response({"detail": "from_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)
        if to_node and to_node.map_id != mind_map.id:
            return Response({"detail": "to_node_id не относится к этой карте"}, status=status.HTTP_400_BAD_REQUEST)

        updated_edge = serializer.save()
        _touch_mind_map(mind_map.id)
        try:
            client = get_active_client(request.user)
            new_from = str(updated_edge.from_node_id)
            new_to = str(updated_edge.to_node_id)
            if old_from != new_from or old_to != new_to:
                sync_core_related_for_edge_delete(client, mind_map, old_from, old_to)
                sync_core_related_for_edge_create(client, mind_map, new_from, new_to)
        except Exception:
            logger.exception("Failed to sync product relations after edge update (map=%s edge=%s)", mind_map.id, edge_id)
        return Response(MindEdgeSerializer(updated_edge).data, status=status.HTTP_200_OK)

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
            connected_edges = list(
                MindEdge.objects.filter(map=mind_map).filter(Q(from_node_id=node.id) | Q(to_node_id=node.id))
            )
            try:
                client = get_active_client(request.user)
                sync_core_related_for_node_delete(client, mind_map, node, connected_edges)
            except Exception:
                logger.exception("Failed to sync product relations after node delete (map=%s node=%s)", mind_map.id, node.id)
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
