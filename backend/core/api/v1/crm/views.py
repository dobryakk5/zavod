from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Count, Sum, Case, When, IntegerField
from datetime import datetime, timedelta
from core.models import Client as ZavodClient
from core.models import CRMClient, ClientCategory, Event, EventType, Payment, Note
from core.api.v1.crm.serializers import (
    CRMClientSerializer, ClientCategorySerializer, 
    EventSerializer, EventTypeSerializer, 
    PaymentSerializer, NoteSerializer
)
from core.models import UserTenantRole


class ZavodClientRequiredMixin:
    """
    Миксин для проверки наличия связанного Zavod клиента у пользователя
    """
    def get_zavod_client(self):
        """
        Получить Zavod клиента, связанного с текущим пользователем
        """
        if hasattr(self.request.user, 'zavodclient'):
            return self.request.user.zavodclient
        
        # Если у пользователя нет напрямую связанного клиента,
        # проверяем через UserTenantRole
        user_role = UserTenantRole.objects.filter(user=self.request.user).first()
        if user_role:
            return user_role.client
        
        return None

    def get_filtered_queryset(self, queryset):
        """
        Фильтровать queryset по Zavod клиенту текущего пользователя
        """
        zavod_client = self.get_zavod_client()
        if zavod_client:
            return queryset.filter(zavod_client=zavod_client)
        else:
            # Если нет связанного клиента, возвращаем пустой queryset
            return queryset.none()


class CRMClientViewSet(ZavodClientRequiredMixin, viewsets.ModelViewSet):
    serializer_class = CRMClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category_id']
    search_fields = ['first_name', 'last_name', 'email']
    ordering_fields = ['created_at', 'first_name', 'last_name', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = CRMClient.objects.select_related('category', 'zavod_client')
        return self.get_filtered_queryset(queryset)

    def perform_create(self, serializer):
        zavod_client = self.get_zavod_client()
        if not zavod_client:
            raise Exception("У пользователя нет связанного Zavod клиента")
        
        serializer.save(zavod_client=zavod_client)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """
        Возвращает древовидную структуру клиентов (родитель-ребенок)
        """
        queryset = self.get_queryset().select_related('category')
        clients = list(queryset)
        
        # Строим дерево
        tree = []
        client_dict = {client.id: client for client in clients}
        
        # Сначала добавляем родительские узлы (без parent_id)
        for client in clients:
            if client.parent_id is None:
                tree.append(self._build_client_tree(client, client_dict))
        
        return Response(tree)

    def _build_client_tree(self, client, client_dict):
        """
        Рекурсивно строит дерево клиента
        """
        client_data = CRMClientSerializer(client, context={'request': self.request}).data
        client_data['children'] = []
        
        # Ищем дочерние узлы
        for potential_child in client_dict.values():
            if potential_child.parent_id == client.id:
                client_data['children'].append(self._build_client_tree(potential_child, client_dict))
        
        return client_data


class ClientCategoryViewSet(ZavodClientRequiredMixin, viewsets.ModelViewSet):
    serializer_class = ClientCategorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        queryset = ClientCategory.objects.all()
        # Для категорий не нужна фильтрация по zavod клиенту, так как они могут быть общими
        return queryset


class EventViewSet(ZavodClientRequiredMixin, viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'event_type_id', 'client_id']
    ordering_fields = ['start_time', 'created_at', 'status']
    ordering = ['-start_time']

    def get_queryset(self):
        queryset = Event.objects.select_related('client', 'event_type', 'client__zavod_client')
        return self.get_filtered_queryset(queryset)

    def perform_create(self, serializer):
        zavod_client = self.get_zavod_client()
        if not zavod_client:
            raise Exception("У пользователя нет связанного Zavod клиента")
        
        # Проверяем, что клиент события принадлежит этому zavod клиенту
        client = serializer.validated_data['client']
        if client.zavod_client != zavod_client:
            raise Exception("Нельзя создать событие для клиента, не принадлежащего вашему аккаунту")
        
        serializer.save()

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """
        Возвращает предстоящие события (на 30 дней вперед)
        """
        queryset = self.get_queryset().filter(
            start_time__gte=timezone.now(),
            start_time__lte=timezone.now() + timedelta(days=30)
        ).order_by('start_time')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_date_range(self, request):
        """
        Возвращает события в заданном диапазоне дат
        """
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if not date_from or not date_to:
            return Response(
                {'error': 'Параметры date_from и date_to обязательны'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except ValueError:
            return Response(
                {'error': 'Неверный формат даты'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(
            start_time__gte=date_from,
            start_time__lte=date_to
        ).order_by('start_time')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class EventTypeViewSet(viewsets.ModelViewSet):
    serializer_class = EventTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        # Типы событий общие для всех, не привязаны к конкретному zavod клиенту
        return EventType.objects.all()


class PaymentViewSet(ZavodClientRequiredMixin, viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'currency', 'client_id']
    ordering_fields = ['created_at', 'paid_at', 'amount']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Payment.objects.select_related('client', 'client__zavod_client')
        return self.get_filtered_queryset(queryset)

    def perform_create(self, serializer):
        zavod_client = self.get_zavod_client()
        if not zavod_client:
            raise Exception("У пользователя нет связанного Zavod клиента")
        
        # Проверяем, что клиент платежа принадлежит этому zavod клиенту
        client = serializer.validated_data['client']
        if client.zavod_client != zavod_client:
            raise Exception("Нельзя создать платеж для клиента, не принадлежащего вашему аккаунту")
        
        serializer.save()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Возвращает сводку по платежам
        """
        queryset = self.get_queryset()
        
        total_paid = queryset.filter(status='paid').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        total_pending = queryset.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        by_currency = queryset.values('currency').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        stats = {
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
            'by_currency': list(by_currency),
            'total_count': queryset.count()
        }
        
        return Response(stats)


class NoteViewSet(ZavodClientRequiredMixin, viewsets.ModelViewSet):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_important', 'client_id']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'is_important']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Note.objects.select_related('client', 'client__zavod_client')
        return self.get_filtered_queryset(queryset)

    def perform_create(self, serializer):
        zavod_client = self.get_zavod_client()
        if not zavod_client:
            raise Exception("У пользователя нет связанного Zavod клиента")
        
        # Проверяем, что клиент заметки принадлежит этому zavod клиенту
        client = serializer.validated_data['client']
        if client.zavod_client != zavod_client:
            raise Exception("Нельзя создать заметку для клиента, не принадлежащего вашему аккаунту")
        
        serializer.save()