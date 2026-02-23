"""
ViewSets для CRM API (map schema, Django ORM).
Active CRM surface: orchestration only, use-cases and data access are delegated
to `core.services.crm.*` and `core.repositories.crm.*`.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.repositories.crm import (
    categories_repository,
    contact_tags_repository,
    contacts_repository,
    events_repository,
    payments_repository,
    tags_repository,
)
from core.services.crm import (
    availability_events_service,
    contact_tags_service,
    events_service,
    payments_service,
    tags_service,
    telegram_link_service,
)

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers_crm_orm import (
    MapAvailabilityEventSerializer,
    MapContactSerializer,
    MapCRMCategorySerializer,
    MapCRMEventSerializer,
    MapCRMEventTypeSerializer,
    MapCRMNoteSerializer,
    MapCRMPaymentListSerializer,
    MapCRMPaymentSerializer,
    MapCRMTagSerializer,
    MapContactTagSerializer,
)
from .utils import get_active_client


class MapContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet для контактов (map.contacts)
    Эндпоинты: list, create, retrieve, update, partial_update, destroy
    Дополнительно: add_tag, remove_tag
    """

    serializer_class = MapContactSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "category_id", "parent_id"]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "created_at", "email"]
    ordering = ["name"]

    def get_queryset(self):
        return contacts_repository.get_contacts_queryset()

    @action(detail=True, methods=["post"])
    def add_tag(self, request, pk=None):
        contact = self.get_object()
        tag_id = request.data.get("tag_id") or request.data.get("tagId")
        description = request.data.get("description", "")

        try:
            contact_tag, created = contact_tags_service.add_tag_to_contact(
                contact=contact,
                tag_id=tag_id,
                description=description,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "success": True,
                "created": created,
                "contact_tag": MapContactTagSerializer(contact_tag).data,
            }
        )

    @action(detail=True, methods=["delete", "post"])
    def remove_tag(self, request, pk=None):
        contact = self.get_object()
        tag_id = request.data.get("tag_id") or request.data.get("tagId")

        try:
            deleted_count = contact_tags_service.remove_tag_from_contact(
                contact=contact,
                tag_id=tag_id,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"success": True, "deleted": deleted_count > 0},
            status=status.HTTP_200_OK if deleted_count > 0 else status.HTTP_404_NOT_FOUND,
        )


class MapCRMPaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet для платежей (map.crm_payments)
    Эндпоинты: list, create, retrieve, update, partial_update, destroy
    Дополнительно: summary, by_contact
    """

    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "currency", "contact_id", "product_id", "event_id"]
    ordering_fields = ["created_at", "paid_at", "amount", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return MapCRMPaymentListSerializer
        return MapCRMPaymentSerializer

    def get_queryset(self):
        return payments_repository.get_payments_queryset()

    @action(detail=False, methods=["get"])
    def summary(self, request):
        payload = payments_service.build_payments_summary(self.get_queryset())
        return Response(payload)

    @action(detail=False, methods=["get"])
    def by_contact(self, request):
        contact_id = request.query_params.get("contact_id")
        try:
            queryset = payments_service.filter_payments_by_contact(
                self.get_queryset(),
                contact_id=contact_id,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MapCRMTagViewSet(viewsets.ModelViewSet):
    """ViewSet для тегов (map.crm_tags)."""

    serializer_class = MapCRMTagSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["type"]
    ordering_fields = ["type", "value", "created_at"]
    ordering = ["type", "value"]

    def get_queryset(self):
        return tags_repository.get_tags_queryset()

    @action(detail=False, methods=["get"])
    def by_type(self, request):
        grouped = tags_service.group_tags_by_type(list(self.get_queryset()))
        return Response(
            {
                key: MapCRMTagSerializer(items, many=True).data
                for key, items in grouped.items()
            }
        )


class MapCRMCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для категорий (map.crm_categories)."""

    serializer_class = MapCRMCategorySerializer
    permission_classes = [IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return categories_repository.get_categories_queryset()


# Алиас для совместимости с ContactTagsView (CRUD по contact-tags)
# Используется в api/urls.py как contact-tags
class MapContactTagsViewSet(viewsets.ModelViewSet):
    """
    ViewSet для связей контакт-тег (map.contact_tags)
    GET ?contact_id= — список тегов контакта
    POST — создать связь {contact_id, tag_id, description?}
    DELETE /contact-tags/remove/ body {contact_id, tag_id} — совместимость со старым API
    DELETE /contact-tags/<id>/ — удалить по pk
    """

    serializer_class = MapContactTagSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["contact_id", "tag_id"]

    def get_queryset(self):
        return contact_tags_repository.get_contact_tags_queryset()

    @action(detail=False, methods=["delete"], url_path="remove")
    def remove_by_ids(self, request):
        """DELETE с body {contact_id, tag_id} — совместимость со старым ContactTagsView."""

        contact_id = request.data.get("contact_id") or request.data.get("contactId")
        tag_id = request.data.get("tag_id") or request.data.get("tagId")

        try:
            deleted = contact_tags_service.remove_tag_by_ids(
                contact_id=contact_id,
                tag_id=tag_id,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Связь между контактом и тегом не найдена."},
            status=status.HTTP_404_NOT_FOUND,
        )


class MapCRMEventTypeViewSet(viewsets.ModelViewSet):
    serializer_class = MapCRMEventTypeSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return events_repository.get_event_types_queryset()

    def get_permissions(self):
        if self.request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()


class MapCRMEventViewSet(viewsets.ModelViewSet):
    serializer_class = MapCRMEventSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "event_type_id", "contact_id"]
    ordering_fields = ["start_time", "created_at", "status"]
    ordering = ["-start_time"]

    def get_permissions(self):
        if self.request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        return events_repository.get_events_queryset()

    def perform_create(self, serializer):
        event = serializer.save()
        events_service.on_event_created(event)

    def perform_update(self, serializer):
        event = serializer.save()
        events_service.on_event_updated(event, request_data=self.request.data)


class MapAvailabilityEventViewSet(viewsets.ModelViewSet):
    serializer_class = MapAvailabilityEventSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["repeat_type"]
    ordering_fields = ["start_time", "created_at"]
    ordering = ["-start_time"]

    def get_permissions(self):
        if self.request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return events_repository.get_availability_events_queryset(tenant_id=client.id)

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        availability_events_service.create_availability_event_for_tenant(
            serializer=serializer,
            tenant_id=client.id,
        )


class MapCRMNoteViewSet(viewsets.ModelViewSet):
    serializer_class = MapCRMNoteSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["contact_id", "is_important"]
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "is_important"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        return events_repository.get_notes_queryset()


class ContactTelegramLinkView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        client = get_active_client(request.user)
        try:
            payload = telegram_link_service.build_contact_telegram_link_payload(
                client=client,
                contact_id=contact_id,
            )
        except LookupError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

