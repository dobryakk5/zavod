"""
Сериализаторы для CRM API (map schema, Django ORM)
Замена для ручной сериализации из views_map_crm.py
"""
from django.utils import timezone
from rest_framework import serializers

from core.models import (
    MapAvailabilityEvent,
    MapContact,
    MapContactTag,
    MapCRMCategory,
    MapCRMDeal,
    MapCRMEvent,
    MapCRMEventType,
    MapCRMNote,
    MapCRMPayment,
    MapCRMTag,
    UserTenantBinding,
)
from .utils import get_active_client


def _active_client_id_from_context(serializer: serializers.Serializer) -> int | None:
    request = serializer.context.get("request")
    if not request or not getattr(request, "user", None):
        return None
    try:
        return int(get_active_client(request.user).id)
    except Exception:
        return None


def _tenant_contact_queryset(tenant_id: int):
    contact_ids = (
        UserTenantBinding.objects
        .filter(tenant_id=tenant_id, contact_id__isnull=False, contact_id__gt=0)
        .values_list("contact_id", flat=True)
    )
    return MapContact.objects.filter(id__in=contact_ids)


class MapCRMCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MapCRMCategory
        fields = [
            "id",
            "name",
            "description",
            "color",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class MapCRMTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapCRMTag
        fields = ["id", "type", "value", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, data):
        tag_type = data.get("type")
        value = data.get("value")
        if not self.instance:
            if MapCRMTag.objects.filter(type=tag_type, value=value).exists():
                raise serializers.ValidationError({"value": "Такой тег уже существует."})
        else:
            if (
                MapCRMTag.objects.filter(type=tag_type, value=value)
                .exclude(id=self.instance.id)
                .exists()
            ):
                raise serializers.ValidationError({"value": "Такой тег уже существует."})
        return data


class MapContactTagSerializer(serializers.ModelSerializer):
    contact_id = serializers.IntegerField()
    tag_id = serializers.IntegerField()
    type = serializers.CharField(source="tag.type", read_only=True)
    value = serializers.CharField(source="tag.value", read_only=True)
    tag_type = serializers.CharField(source="tag.type", read_only=True)
    tag_value = serializers.CharField(source="tag.value", read_only=True)

    class Meta:
        model = MapContactTag
        fields = ["id", "contact_id", "tag_id", "type", "value", "tag_type", "tag_value", "description"]

    def validate_contact_id(self, value: int) -> int:
        tenant_id = _active_client_id_from_context(self)
        if tenant_id is None:
            if not MapContact.objects.filter(id=value).exists():
                raise serializers.ValidationError("Контакт не найден.")
            return value
        if not _tenant_contact_queryset(tenant_id).filter(id=value).exists():
            raise serializers.ValidationError("Контакт недоступен в этом тенанте.")
        return value

    def validate_tag_id(self, value: int) -> int:
        if not MapCRMTag.objects.filter(id=value).exists():
            raise serializers.ValidationError("Тег не найден.")
        return value

    def create(self, validated_data):
        contact_id = int(validated_data.pop("contact_id"))
        tag_id = int(validated_data.pop("tag_id"))
        description = validated_data.pop("description", serializers.empty)

        defaults = {
            "description": "" if description in (serializers.empty, None) else str(description),
        }
        contact_tag, created = MapContactTag.objects.get_or_create(
            contact_id=contact_id,
            tag_id=tag_id,
            defaults=defaults,
        )

        # Preserve legacy raw-SQL behaviour:
        # repeated POST acts like upsert and only updates description when it is provided.
        if not created and description not in (serializers.empty, None):
            next_description = str(description)
            if contact_tag.description != next_description:
                contact_tag.description = next_description
                contact_tag.save(update_fields=["description"])

        return contact_tag

    def update(self, instance, validated_data):
        if "contact_id" in validated_data:
            instance.contact_id = int(validated_data["contact_id"])
        if "tag_id" in validated_data:
            instance.tag_id = int(validated_data["tag_id"])
        if "description" in validated_data and validated_data["description"] is not None:
            instance.description = str(validated_data["description"])
        instance.save()
        return instance


class MapContactSerializer(serializers.ModelSerializer):
    """Совместим с frontend (tags в формате goal/pain/experience)."""

    tags = serializers.SerializerMethodField()
    DEAL_STAGE_CHOICES = {
        "",
        "new_lead",
        "interest",
        "call",
        "payment_expected",
        "paid",
        "lost",
    }
    DEAL_LOSS_REASON_CHOICES = {
        "",
        "price",
        "timing",
        "no_response",
        "not_fit",
        "competitor",
        "priority_changed",
        "other",
    }

    class Meta:
        model = MapContact
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "source",
            "deal_stage",
            "deal_amount",
            "deal_loss_reason_code",
            "deal_loss_reason_text",
            "deal_lost_at",
            "category_id",
            "status",
            "photo_url",
            "notes",
            "parent_id",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_tags(self, obj):
        contact_tags = MapContactTag.objects.filter(contact=obj).select_related("tag")
        result = {"goal": [], "pain": [], "experience": []}
        for ct in contact_tags:
            if ct.tag.type in result:
                result[ct.tag.type].append(ct.tag.id)
        return result

    def validate_deal_stage(self, value):
        normalized = str(value or "").strip().lower()
        if normalized not in self.DEAL_STAGE_CHOICES:
            raise serializers.ValidationError("Некорректная стадия сделки.")
        return normalized

    def validate_deal_loss_reason_code(self, value):
        normalized = str(value or "").strip().lower()
        if normalized not in self.DEAL_LOSS_REASON_CHOICES:
            raise serializers.ValidationError("Некорректная причина потери.")
        return normalized

    def validate_deal_amount(self, value):
        if value is None:
            return None
        if value < 0:
            raise serializers.ValidationError("Сумма сделки не может быть отрицательной.")
        return value

    def validate_parent_id(self, value):
        if value is None:
            return None
        tenant_id = _active_client_id_from_context(self)
        if tenant_id is None:
            if not MapContact.objects.filter(id=value).exists():
                raise serializers.ValidationError("Родительский контакт не найден.")
            return value
        if not _tenant_contact_queryset(tenant_id).filter(id=value).exists():
            raise serializers.ValidationError("Родительский контакт недоступен в этом тенанте.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)

        next_stage = str(
            attrs.get(
                "deal_stage",
                getattr(instance, "deal_stage", "") if instance is not None else "",
            )
            or ""
        ).strip().lower()
        next_reason_code = str(
            attrs.get(
                "deal_loss_reason_code",
                getattr(instance, "deal_loss_reason_code", "") if instance is not None else "",
            )
            or ""
        ).strip().lower()
        next_reason_text = str(
            attrs.get(
                "deal_loss_reason_text",
                getattr(instance, "deal_loss_reason_text", "") if instance is not None else "",
            )
            or ""
        ).strip()

        if next_stage == "lost" and not next_reason_code:
            raise serializers.ValidationError(
                {
                    "deal_loss_reason_code": "Укажите причину потери.",
                }
            )
        return attrs

    def create(self, validated_data):
        if str(validated_data.get("deal_stage", "") or "").strip().lower() == "lost":
            validated_data.setdefault("deal_lost_at", timezone.now())
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "deal_stage" in validated_data:
            next_stage = str(validated_data.get("deal_stage", "") or "").strip().lower()
            if next_stage == "lost":
                if not validated_data.get("deal_lost_at") and getattr(instance, "deal_lost_at", None) is None:
                    validated_data["deal_lost_at"] = timezone.now()
            else:
                # If a deal returns from "lost", clear loss metadata to avoid stale reasons.
                validated_data.setdefault("deal_loss_reason_code", "")
                validated_data.setdefault("deal_loss_reason_text", "")
                validated_data.setdefault("deal_lost_at", None)
        return super().update(instance, validated_data)


class MapCRMPaymentSerializer(serializers.ModelSerializer):
    contact_id = serializers.IntegerField()
    deal_id = serializers.IntegerField(required=False, allow_null=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    contact_email = serializers.CharField(source="contact.email", read_only=True)

    class Meta:
        model = MapCRMPayment
        fields = [
            "id",
            "contact_id",
            "deal_id",
            "contact_name",
            "contact_email",
            "event_id",
            "product_id",
            "amount",
            "currency",
            "status",
            "payment_method",
            "transaction_id",
            "description",
            "planned_at",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "contact_name", "contact_email"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной.")
        return value

    def validate_contact_id(self, value):
        tenant_id = _active_client_id_from_context(self)
        queryset = _tenant_contact_queryset(tenant_id) if tenant_id is not None else MapContact.objects.all()
        if not queryset.filter(id=value).exists():
            raise serializers.ValidationError("Контакт не найден.")
        return value

    def validate_deal_id(self, value):
        if value is None:
            return None
        tenant_id = _active_client_id_from_context(self)
        queryset = MapCRMDeal.objects.filter(id=value)
        if tenant_id is not None:
            queryset = queryset.filter(contact_id__in=_tenant_contact_queryset(tenant_id).values_list("id", flat=True))
        if not queryset.exists():
            raise serializers.ValidationError("Сделка не найдена.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        next_contact_id = attrs.get("contact_id")
        if next_contact_id is None and instance is not None:
            next_contact_id = getattr(instance, "contact_id", None)

        next_deal_id = attrs.get("deal_id")
        if next_deal_id is None and instance is not None:
            next_deal_id = getattr(instance, "deal_id", None)

        if next_deal_id:
            deal_queryset = MapCRMDeal.objects.filter(id=next_deal_id)
            tenant_id = _active_client_id_from_context(self)
            if tenant_id is not None:
                deal_queryset = deal_queryset.filter(
                    contact_id__in=_tenant_contact_queryset(tenant_id).values_list("id", flat=True)
                )
            deal = deal_queryset.only("id", "contact_id").first()
            if deal is None:
                raise serializers.ValidationError({"deal_id": "Сделка не найдена."})
            if next_contact_id is None:
                attrs["contact_id"] = int(deal.contact_id)
            elif int(next_contact_id) != int(deal.contact_id):
                raise serializers.ValidationError(
                    {"deal_id": "Сделка принадлежит другому клиенту."}
                )
        return attrs

    def create(self, validated_data):
        contact_id = validated_data.pop("contact_id")
        deal_id = validated_data.pop("deal_id", None)
        contact = MapContact.objects.get(id=contact_id)
        deal = MapCRMDeal.objects.get(id=deal_id) if deal_id else None
        return MapCRMPayment.objects.create(contact=contact, deal=deal, **validated_data)

    def update(self, instance, validated_data):
        if "contact_id" in validated_data:
            contact_id = validated_data.pop("contact_id")
            instance.contact = MapContact.objects.get(id=contact_id)
        if "deal_id" in validated_data:
            deal_id = validated_data.pop("deal_id")
            instance.deal = MapCRMDeal.objects.get(id=deal_id) if deal_id else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class MapCRMPaymentListSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.name", read_only=True)

    class Meta:
        model = MapCRMPayment
        fields = [
            "id",
            "contact_id",
            "deal_id",
            "contact_name",
            "event_id",
            "product_id",
            "amount",
            "currency",
            "status",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class MapCRMDealSerializer(serializers.ModelSerializer):
    contact_id = serializers.IntegerField()
    contact_name = serializers.CharField(source="contact.name", read_only=True)

    STAGE_CHOICES = {
        "new_lead",
        "interest",
        "call",
        "payment_expected",
        "paid",
        "lost",
    }
    LOST_REASON_CHOICES = {
        "",
        "price",
        "timing",
        "no_response",
        "not_fit",
        "competitor",
        "priority_changed",
        "other",
    }

    class Meta:
        model = MapCRMDeal
        fields = [
            "id",
            "contact_id",
            "contact_name",
            "product_id",
            "stage",
            "amount",
            "currency",
            "description",
            "lost_reason_code",
            "lost_reason_text",
            "lost_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "contact_name"]

    def validate_contact_id(self, value):
        tenant_id = _active_client_id_from_context(self)
        queryset = _tenant_contact_queryset(tenant_id) if tenant_id is not None else MapContact.objects.all()
        if not queryset.filter(id=value).exists():
            raise serializers.ValidationError("Контакт не найден.")
        return value

    def validate_product_id(self, value):
        if value is None or int(value) <= 0:
            raise serializers.ValidationError("Продукт обязателен.")
        return int(value)

    def validate_stage(self, value):
        normalized = str(value or "").strip().lower()
        if normalized not in self.STAGE_CHOICES:
            raise serializers.ValidationError("Некорректная стадия сделки.")
        return normalized

    def validate_lost_reason_code(self, value):
        normalized = str(value or "").strip().lower()
        if normalized not in self.LOST_REASON_CHOICES:
            raise serializers.ValidationError("Некорректная причина срыва.")
        return normalized

    def validate_amount(self, value):
        if value is None:
            return None
        if value < 0:
            raise serializers.ValidationError("Сумма сделки не может быть отрицательной.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        stage = str(attrs.get("stage", getattr(instance, "stage", "new_lead")) or "").strip().lower()
        lost_reason = str(
            attrs.get("lost_reason_code", getattr(instance, "lost_reason_code", "")) or ""
        ).strip().lower()
        if stage == "lost" and not lost_reason:
            raise serializers.ValidationError({"lost_reason_code": "Укажите причину срыва."})
        return attrs

    def create(self, validated_data):
        contact_id = validated_data.pop("contact_id")
        contact = MapContact.objects.get(id=contact_id)
        if str(validated_data.get("stage", "") or "").strip().lower() == "lost":
            validated_data.setdefault("lost_at", timezone.now())
        return MapCRMDeal.objects.create(contact=contact, **validated_data)

    def update(self, instance, validated_data):
        if "contact_id" in validated_data:
            contact_id = validated_data.pop("contact_id")
            instance.contact = MapContact.objects.get(id=contact_id)
        if "stage" in validated_data:
            next_stage = str(validated_data.get("stage", "") or "").strip().lower()
            if next_stage == "lost":
                if not validated_data.get("lost_at") and getattr(instance, "lost_at", None) is None:
                    validated_data["lost_at"] = timezone.now()
            else:
                validated_data.setdefault("lost_reason_code", "")
                validated_data.setdefault("lost_reason_text", "")
                validated_data.setdefault("lost_at", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class MapCRMDealListSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    payments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = MapCRMDeal
        fields = [
            "id",
            "contact_id",
            "contact_name",
            "product_id",
            "stage",
            "amount",
            "currency",
            "lost_reason_code",
            "payments_count",
            "updated_at",
            "created_at",
        ]
        read_only_fields = fields


class MapCRMEventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapCRMEventType
        fields = [
            "id",
            "name",
            "description",
            "duration_minutes",
            "color",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class MapCRMEventSerializer(serializers.ModelSerializer):
    contact_id = serializers.PrimaryKeyRelatedField(source="contact", queryset=MapContact.objects.all())
    event_type_id = serializers.PrimaryKeyRelatedField(
        source="event_type",
        queryset=MapCRMEventType.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = MapCRMEvent
        fields = [
            "id",
            "contact_id",
            "event_type_id",
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
            "status",
            "notes",
            "price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = _active_client_id_from_context(self)
        if tenant_id is not None:
            self.fields["contact_id"].queryset = _tenant_contact_queryset(tenant_id)


class MapAvailabilityEventSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(source="tenant.id", read_only=True)

    class Meta:
        model = MapAvailabilityEvent
        fields = [
            "id",
            "tenant_id",
            "start_time",
            "duration_minutes",
            "repeat_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["tenant_id", "created_at", "updated_at"]

    def validate_repeat_type(self, value):
        if value not in {0, 1, 2, 3}:
            raise serializers.ValidationError("Недопустимое значение.")
        return value


class MapCRMNoteSerializer(serializers.ModelSerializer):
    contact_id = serializers.PrimaryKeyRelatedField(source="contact", queryset=MapContact.objects.all())

    class Meta:
        model = MapCRMNote
        fields = [
            "id",
            "contact_id",
            "title",
            "content",
            "is_important",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant_id = _active_client_id_from_context(self)
        if tenant_id is not None:
            self.fields["contact_id"].queryset = _tenant_contact_queryset(tenant_id)
