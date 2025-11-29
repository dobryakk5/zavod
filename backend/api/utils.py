from __future__ import annotations

from rest_framework.exceptions import PermissionDenied

from core.models import Client, UserTenantRole


def get_active_client(user) -> Client:
    """Return the single client associated with the authenticated user."""

    if not user.is_authenticated:
        raise PermissionDenied("Требуется авторизация")

    role = (
        UserTenantRole.objects.select_related("client")
        .filter(user=user)
        .first()
    )
    if role is None:
        raise PermissionDenied("Пользователь не привязан ни к одному клиенту")
    return role.client
