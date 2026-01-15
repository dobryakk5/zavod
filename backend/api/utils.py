from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.generation_events import build_limit_error_payload, check_generation_limit
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


def enforce_generation_limit(client: Client, event_type: str):
    limit_info = check_generation_limit(client, event_type)
    if not limit_info:
        return None
    payload = build_limit_error_payload(event_type, limit_info["used"], limit_info["limit"])
    return Response(payload, status=status.HTTP_403_FORBIDDEN)
