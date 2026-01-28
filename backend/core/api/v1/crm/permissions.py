from rest_framework import permissions
from core.models import UserTenantRole


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Права доступа: владельцы могут редактировать, другие только чтение
    """
    def has_object_permission(self, request, view, obj):
        # Права на чтение разрешены для любого запроса
        if request.method in permissions.SAFE_METHODS:
            return True

        # Права на редактирование только у владельца
        # Для CRM объектов проверяем zavod_client
        if hasattr(obj, 'zavod_client'):
            user_zavod_client = None
            if hasattr(request.user, 'zavodclient'):
                user_zavod_client = request.user.zavodclient
            elif hasattr(request.user, 'usertenantrole_set'):
                # Проверяем через UserTenantRole
                user_role = request.user.usertenantrole_set.first()
                if user_role:
                    user_zavod_client = user_role.client
            
            return obj.zavod_client == user_zavod_client

        return False


class HasZavodClientAccess(permissions.BasePermission):
    """
    Проверяет, имеет ли пользователь доступ к Zavod клиенту
    """
    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True

        # Проверяем, есть ли у пользователя связанный Zavod клиент
        user_zavod_client = None
        if hasattr(request.user, 'zavodclient'):
            user_zavod_client = request.user.zavodclient
        elif hasattr(request.user, 'usertenantrole_set'):
            # Проверяем через UserTenantRole
            user_role = request.user.usertenantrole_set.first()
            if user_role:
                user_zavod_client = user_role.client

        return user_zavod_client is not None

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        user_zavod_client = None
        if hasattr(request.user, 'zavodclient'):
            user_zavod_client = request.user.zavodclient
        elif hasattr(request.user, 'usertenantrole_set'):
            user_role = request.user.usertenantrole_set.first()
            if user_role:
                user_zavod_client = user_role.client

        # Проверяем, принадлежит ли объект пользовательскому Zavod клиенту
        if hasattr(obj, 'zavod_client'):
            return obj.zavod_client == user_zavod_client
        elif hasattr(obj, 'client') and hasattr(obj.client, 'zavod_client'):
            # Для объектов, связанных с CRMClient
            return obj.client.zavod_client == user_zavod_client

        return False