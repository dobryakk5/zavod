from rest_framework import serializers
from core.models import Client as ZavodClient
from core.models import CRMClient, ClientCategory, Event, EventType, Payment, Note
from django.contrib.auth.models import User
from django.utils import timezone


class ClientCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientCategory
        fields = ['id', 'name', 'description', 'color', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class CRMClientSerializer(serializers.ModelSerializer):
    category = ClientCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ClientCategory.objects.all(), 
        source='category',
        write_only=True,
        required=False
    )
    parent_full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CRMClient
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'category', 
            'category_id', 'status', 'photo_url', 'notes', 'parent_id', 
            'created_at', 'updated_at', 'parent_full_name', 'zavod_client_id'
        ]
        read_only_fields = ['created_at', 'updated_at', 'zavod_client_id']

    def get_parent_full_name(self, obj):
        if obj.parent_id:
            try:
                parent = CRMClient.objects.get(id=obj.parent_id)
                return f"{parent.first_name} {parent.last_name}"
            except CRMClient.DoesNotExist:
                return None
        return None

    def validate_email(self, value):
        if value:
            # Проверяем, что email уникален среди CRM клиентов этого zavod клиента
            zavod_client = self.context['request'].user.zavodclient if hasattr(self.context['request'].user, 'zavodclient') else None
            if zavod_client:
                queryset = CRMClient.objects.filter(
                    email=value,
                    zavod_client=zavod_client
                ).exclude(id=self.instance.id if self.instance else None)
                
                if queryset.exists():
                    raise serializers.ValidationError("Клиент с таким email уже существует.")
        
        return value


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ['id', 'name', 'description', 'duration_minutes', 'color', 'created_at']
        read_only_fields = ['created_at']


class EventSerializer(serializers.ModelSerializer):
    client = CRMClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=CRMClient.objects.all(), 
        source='client',
        write_only=True
    )
    event_type = EventTypeSerializer(read_only=True)
    event_type_id = serializers.PrimaryKeyRelatedField(
        queryset=EventType.objects.all(), 
        source='event_type',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Event
        fields = [
            'id', 'client', 'client_id', 'event_type', 'event_type_id', 
            'title', 'description', 'start_time', 'end_time', 'location', 
            'status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({
                'end_time': 'Время окончания должно быть больше времени начала.'
            })
        
        # Проверяем, что клиент принадлежит тому же zavod клиенту, что и пользователь
        request = self.context.get('request')
        if request and data.get('client'):
            user_zavod_client = request.user.zavodclient if hasattr(request.user, 'zavodclient') else None
            if user_zavod_client and data['client'].zavod_client != user_zavod_client:
                raise serializers.ValidationError({
                    'client': 'Вы не можете создавать события для клиентов другого Zavod-клиента.'
                })
        
        return data


class PaymentSerializer(serializers.ModelSerializer):
    client = CRMClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=CRMClient.objects.all(), 
        source='client',
        write_only=True
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'client', 'client_id', 'amount', 'currency', 'status', 
            'payment_method', 'transaction_id', 'description', 'paid_at', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной.")
        return value

    def validate(self, data):
        # Проверяем, что клиент принадлежит тому же zavod клиенту, что и пользователь
        request = self.context.get('request')
        if request and data.get('client'):
            user_zavod_client = request.user.zavodclient if hasattr(request.user, 'zavodclient') else None
            if user_zavod_client and data['client'].zavod_client != user_zavod_client:
                raise serializers.ValidationError({
                    'client': 'Вы не можете создавать платежи для клиентов другого Zavod-клиента.'
                })
        
        return data


class NoteSerializer(serializers.ModelSerializer):
    client = CRMClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=CRMClient.objects.all(), 
        source='client',
        write_only=True
    )
    
    class Meta:
        model = Note
        fields = [
            'id', 'client', 'client_id', 'title', 'content', 
            'is_important', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        # Проверяем, что клиент принадлежит тому же zavod клиенту, что и пользователь
        request = self.context.get('request')
        if request and data.get('client'):
            user_zavod_client = request.user.zavodclient if hasattr(request.user, 'zavodclient') else None
            if user_zavod_client and data['client'].zavod_client != user_zavod_client:
                raise serializers.ValidationError({
                    'client': 'Вы не можете создавать заметки для клиентов другого Zavod-клиента.'
                })
        
        return data