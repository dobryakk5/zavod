from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.api.v1.crm.views import (
    CRMClientViewSet, ClientCategoryViewSet, 
    EventViewSet, EventTypeViewSet, 
    PaymentViewSet, NoteViewSet
)

# Создаем роутер и регистрируем ViewSets
router = DefaultRouter()
router.register(r'clients', CRMClientViewSet, basename='crm-client')
router.register(r'categories', ClientCategoryViewSet, basename='crm-category')
router.register(r'events', EventViewSet, basename='crm-event')
router.register(r'event-types', EventTypeViewSet, basename='crm-event-type')
router.register(r'payments', PaymentViewSet, basename='crm-payment')
router.register(r'notes', NoteViewSet, basename='crm-note')

urlpatterns = [
    path('', include(router.urls)),
]