"""
Сериализаторы для CRM API (map schema, Django ORM)
Замена для ручной сериализации из views_map_crm.py
"""
from rest_framework import serializers

from core.models import MapContact, MapCRMPayment, MapCRMTag, MapContactTag, MapCRMCategory


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
    tag_type = serializers.CharField(source="tag.type", read_only=True)
    tag_value = serializers.CharField(source="tag.value", read_only=True)

    class Meta:
        model = MapContactTag
        fields = ["id", "contact_id", "tag_id", "tag_type", "tag_value", "description"]


class MapContactSerializer(serializers.ModelSerializer):
    """Совместим с frontend (tags в формате goal/pain/experience)."""

    tags = serializers.SerializerMethodField()

    class Meta:
        model = MapContact
        fields = [
            "id",
            "name",
            "email",
            "phone",
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


class MapCRMPaymentSerializer(serializers.ModelSerializer):
    contact_id = serializers.IntegerField(write_only=True)
    contact_name = serializers.CharField(source="contact.name", read_only=True)
    contact_email = serializers.CharField(source="contact.email", read_only=True)

    class Meta:
        model = MapCRMPayment
        fields = [
            "id",
            "contact_id",
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
        if not MapContact.objects.filter(id=value).exists():
            raise serializers.ValidationError("Контакт не найден.")
        return value

    def create(self, validated_data):
        contact_id = validated_data.pop("contact_id")
        contact = MapContact.objects.get(id=contact_id)
        return MapCRMPayment.objects.create(contact=contact, **validated_data)

    def update(self, instance, validated_data):
        if "contact_id" in validated_data:
            contact_id = validated_data.pop("contact_id")
            instance.contact = MapContact.objects.get(id=contact_id)
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
            "contact_name",
            "event_id",
            "amount",
            "currency",
            "status",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields
