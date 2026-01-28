from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Основной роутер для API v1
router = DefaultRouter()

# Подключаем маршруты CRM
crm_urls = [
    path('crm/', include('core.api.v1.crm.urls')),
]

urlpatterns = [
    path('', include(router.urls)),
    # Добавляем CRM маршруты
    *crm_urls,
]