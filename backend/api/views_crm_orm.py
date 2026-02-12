"""
ViewSets для CRM API (map schema, Django ORM)
Замена Raw SQL views из views_map_crm.py для contacts, tags, categories, payments
"""
from django.db.models import Count, Prefetch, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import MapContact, MapCRMCategory, MapCRMPayment, MapCRMTag, MapContactTag

from .permissions import IsTenantMember
from .serializers_crm_orm import (
    MapContactSerializer,
    MapCRMCategorySerializer,
    MapCRMPaymentListSerializer,
    MapCRMPaymentSerializer,
    MapCRMTagSerializer,
    MapContactTagSerializer,
)


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
        return MapContact.objects.prefetch_related(
            Prefetch(
                "contact_tags",
                queryset=MapContactTag.objects.select_related("tag"),
            )
        )

    @action(detail=True, methods=["post"])
    def add_tag(self, request, pk=None):
        contact = self.get_object()
        tag_id = request.data.get("tag_id") or request.data.get("tagId")
        description = request.data.get("description", "")

        if not tag_id:
            return Response(
                {"error": "Укажите tag_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tag = MapCRMTag.objects.get(id=tag_id)
        except MapCRMTag.DoesNotExist:
            return Response(
                {"error": "Тег не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        contact_tag, created = MapContactTag.objects.update_or_create(
            contact=contact,
            tag=tag,
            defaults={"description": description},
        )

        return Response({
            "success": True,
            "created": created,
            "contact_tag": MapContactTagSerializer(contact_tag).data,
        })

    @action(detail=True, methods=["delete", "post"])
    def remove_tag(self, request, pk=None):
        contact = self.get_object()
        tag_id = request.data.get("tag_id") or request.data.get("tagId")

        if not tag_id:
            return Response(
                {"error": "Укажите tag_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_count, _ = MapContactTag.objects.filter(
            contact=contact,
            tag_id=tag_id,
        ).delete()

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
    filterset_fields = ["status", "currency", "contact_id", "product_id"]
    ordering_fields = ["created_at", "paid_at", "amount", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return MapCRMPaymentListSerializer
        return MapCRMPaymentSerializer

    def get_queryset(self):
        return MapCRMPayment.objects.select_related("contact")

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.get_queryset()
        stats = queryset.aggregate(
            total_paid=Sum("amount", filter=Q(status="paid")) or 0,
            total_pending=Sum("amount", filter=Q(status="pending")) or 0,
            count_paid=Count("id", filter=Q(status="paid")),
            count_pending=Count("id", filter=Q(status="pending")),
        )
        by_currency = list(
            queryset.values("currency")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("currency")
        )
        return Response({
            **stats,
            "by_currency": by_currency,
            "total_count": queryset.count(),
        })

    @action(detail=False, methods=["get"])
    def by_contact(self, request):
        contact_id = request.query_params.get("contact_id")
        if not contact_id:
            return Response(
                {"error": "Укажите contact_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        queryset = self.get_queryset().filter(contact_id=contact_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MapCRMTagViewSet(viewsets.ModelViewSet):
    """ViewSet для тегов (map.crm_tags)."""
    queryset = MapCRMTag.objects.all()
    serializer_class = MapCRMTagSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["type"]
    ordering_fields = ["type", "value", "created_at"]
    ordering = ["type", "value"]

    @action(detail=False, methods=["get"])
    def by_type(self, request):
        tags = self.get_queryset()
        result = {"goal": [], "pain": [], "experience": []}
        for tag in tags:
            if tag.type in result:
                result[tag.type].append(MapCRMTagSerializer(tag).data)
        return Response(result)


class MapCRMCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для категорий (map.crm_categories)."""
    queryset = MapCRMCategory.objects.all()
    serializer_class = MapCRMCategorySerializer
    permission_classes = [IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


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
    queryset = MapContactTag.objects.select_related("contact", "tag")
    serializer_class = MapContactTagSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["contact_id", "tag_id"]

    @action(detail=False, methods=["delete"], url_path="remove")
    def remove_by_ids(self, request):
        """DELETE с body {contact_id, tag_id} — совместимость со старым ContactTagsView."""
        contact_id = request.data.get("contact_id") or request.data.get("contactId")
        tag_id = request.data.get("tag_id") or request.data.get("tagId")
        if contact_id is None or tag_id is None:
            return Response(
                {"error": "contact_id и tag_id обязательны."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = MapContactTag.objects.filter(
            contact_id=contact_id,
            tag_id=tag_id,
        ).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Связь между контактом и тегом не найдена."},
            status=status.HTTP_404_NOT_FOUND,
        )
