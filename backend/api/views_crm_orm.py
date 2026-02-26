"""
ViewSets для CRM API (map schema, Django ORM)
Замена Raw SQL views из views_map_crm.py для contacts, tags, categories, payments
"""
from decimal import Decimal

from django.db.models import Count, Prefetch, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    ClientProduct,
    MapAvailabilityEvent,
    MapContact,
    MapContactTag,
    MapCRMCategory,
    MapCRMEvent,
    MapCRMEventType,
    MapCRMNote,
    MapCRMPayment,
    MapCRMTag,
    ContactProductPurchase,
    TelegramTask,
    UserTenantBinding,
)
from core.services.contact_service_packages import (
    grant_service_package_to_purchase,
    list_contact_service_package_items,
    remove_service_package_usage_for_event,
    sync_service_package_usage_for_event,
)
from core.services.crm_workflow_dispatcher import CRMWorkflowDispatcher
from core.services.tenant_service import TenantService

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


crm_workflow_dispatcher = CRMWorkflowDispatcher()


def _upsert_event_payment(event: MapCRMEvent) -> int | None:
    if event.price is None:
        return None

    description = f"Оплата встречи: {event.title}".strip() or "Оплата встречи"
    amount = Decimal(event.price)
    payment = MapCRMPayment.objects.filter(event_id=event.id).order_by("-id").first()

    if payment:
        if payment.status == "pending":
            payment.contact_id = event.contact_id
            payment.amount = amount
            payment.currency = "RUB"
            payment.description = description
            payment.planned_at = event.start_time
            payment.save(
                update_fields=[
                    "contact",
                    "amount",
                    "currency",
                    "description",
                    "planned_at",
                    "updated_at",
                ]
            )
        return int(payment.id)

    created = MapCRMPayment.objects.create(
        contact_id=event.contact_id,
        event_id=event.id,
        product_id=None,
        amount=amount,
        currency="RUB",
        status="pending",
        payment_method="",
        transaction_id="",
        description=description,
        planned_at=event.start_time,
        paid_at=None,
    )
    return int(created.id)


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

    @action(detail=True, methods=["get"], url_path="service-packages")
    def service_packages(self, request, pk=None):
        contact = self.get_object()
        client = get_active_client(request.user)
        items = list_contact_service_package_items(client=client, contact_id=int(contact.id))
        return Response({
            "contact_id": int(contact.id),
            "items": items,
        })

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
    filterset_fields = ["status", "currency", "contact_id", "product_id", "event_id"]
    ordering_fields = ["created_at", "paid_at", "amount", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return MapCRMPaymentListSerializer
        return MapCRMPaymentSerializer

    def get_queryset(self):
        return MapCRMPayment.objects.select_related("contact")

    def _record_paid_product_purchase(self, payment: MapCRMPayment) -> None:
        if str(getattr(payment, "status", "") or "") != "paid":
            return
        product_id = getattr(payment, "product_id", None)
        contact_id = getattr(payment, "contact_id", None)
        if not product_id or not contact_id:
            return

        client = get_active_client(self.request.user)
        product = (
            ClientProduct.objects
            .filter(owner_id=client.id, id=product_id)
            .only("id", "name", "packages")
            .first()
        )
        if product is None:
            return

        purchase, _ = ContactProductPurchase.objects.update_or_create(
            client=client,
            contact_id=int(contact_id),
            product_id=int(product_id),
            defaults={
                "product_name": (product.name or "").strip()[:255],
                "amount": getattr(payment, "amount", None),
                "currency": str(getattr(payment, "currency", "RUB") or "RUB").strip().upper()[:3] or "RUB",
                "paid_at": getattr(payment, "paid_at", None),
            },
        )
        grant_service_package_to_purchase(purchase=purchase, product=product, top_up=True)

    def perform_create(self, serializer):
        payment = serializer.save()
        self._record_paid_product_purchase(payment)
        if str(getattr(payment, "status", "") or "") == "paid":
            client = get_active_client(self.request.user)
            crm_workflow_dispatcher.dispatch_payment_paid(
                tenant_id=client.id,
                payment=payment,
            )

    def perform_update(self, serializer):
        previous_status = str(getattr(serializer.instance, "status", "") or "")
        payment = serializer.save()
        if previous_status != "paid" and str(getattr(payment, "status", "") or "") == "paid":
            self._record_paid_product_purchase(payment)
            client = get_active_client(self.request.user)
            crm_workflow_dispatcher.dispatch_payment_paid(
                tenant_id=client.id,
                payment=payment,
            )

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


class MapCRMEventTypeViewSet(viewsets.ModelViewSet):
    queryset = MapCRMEventType.objects.all()
    serializer_class = MapCRMEventTypeSerializer
    permission_classes = [IsTenantMember]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

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
        return MapCRMEvent.objects.select_related("contact", "event_type").order_by("-start_time")

    def perform_create(self, serializer):
        event = serializer.save()
        _upsert_event_payment(event)
        client = get_active_client(self.request.user)
        sync_service_package_usage_for_event(client=client, event=event)
        crm_workflow_dispatcher.dispatch_event_created(
            tenant_id=client.id,
            event=event,
        )

    def perform_update(self, serializer):
        prev_status = str(getattr(serializer.instance, "status", "") or "")
        prev_start_time = getattr(serializer.instance, "start_time", None)
        prev_end_time = getattr(serializer.instance, "end_time", None)
        event = serializer.save()
        if "price" in self.request.data and event.price is not None:
            _upsert_event_payment(event)
        client = get_active_client(self.request.user)
        sync_service_package_usage_for_event(client=client, event=event)
        next_status = str(getattr(event, "status", "") or "")
        if prev_status != "cancelled" and next_status == "cancelled":
            crm_workflow_dispatcher.dispatch_event_cancelled(
                tenant_id=client.id,
                event=event,
            )
        elif prev_start_time != getattr(event, "start_time", None) or prev_end_time != getattr(event, "end_time", None):
            crm_workflow_dispatcher.dispatch_event_rescheduled(
                tenant_id=client.id,
                event=event,
            )

    def perform_destroy(self, instance):
        remove_service_package_usage_for_event(event_id=int(instance.id))
        instance.delete()


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
        return MapAvailabilityEvent.objects.filter(tenant_id=client.id).order_by("-start_time")

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(tenant_id=client.id)


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
        return MapCRMNote.objects.select_related("contact").order_by("-created_at")


class ContactTelegramLinkView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        contact_row = MapContact.objects.filter(id=contact_id).values("tg_username").first()
        if contact_row is None:
            return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)
        contact_tg_username = contact_row.get("tg_username")

        client = get_active_client(request.user)
        tenant_service = TenantService()
        try:
            link = tenant_service.generate_telegram_link(client.id, contact_id=contact_id)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        binding_qs = (
            UserTenantBinding.objects.filter(
                tenant=client,
                contact_id=contact_id,
                provider=UserTenantBinding.PROVIDER_TELEGRAM,
            )
            .order_by("-bound_at", "-id")
        )
        binding = binding_qs.filter(is_active=True).first() or binding_qs.first()

        telegram_chat_id = None
        tg_name = None
        is_connected = False
        if binding is not None:
            telegram_chat_id = binding.telegram_chat_id
            is_connected = bool(binding.is_active)
            if contact_tg_username:
                tg_name = contact_tg_username
            else:
                task = (
                    TelegramTask.objects.filter(
                        client=client,
                        telegram_user_id=telegram_chat_id,
                    )
                    .order_by("-received_at", "-id")
                    .first()
                )
                if task and task.tg_name:
                    tg_name = task.tg_name
                else:
                    tg_name = f"tg_{telegram_chat_id}"

        return Response(
            {
                "contact_id": int(contact_id),
                "tenant_id": client.id,
                "telegram_chat_id": telegram_chat_id,
                "tg_name": tg_name,
                "is_connected": is_connected,
                "link": link,
            }
        )
