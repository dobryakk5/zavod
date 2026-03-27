from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.generation_events import build_limit_error_payload, check_generation_limit
from core.models import Client, UserTenantRole
from core.services.team_invites import accept_pending_team_invites, ensure_valid_active_client_preference, list_user_memberships, set_active_client_preference


def get_active_client(user) -> Client:
    """Return the active client associated with the authenticated user."""

    if not user.is_authenticated:
        raise PermissionDenied("Требуется авторизация")

    accept_pending_team_invites(user)
    client = ensure_valid_active_client_preference(user)
    if client is None:
        raise PermissionDenied("Пользователь не привязан ни к одному клиенту")
    return client


def build_client_info_payload(user) -> dict:
    client = get_active_client(user)
    memberships = list_user_memberships(user)
    role_obj = next((item for item in memberships if item.client_id == client.id), None)
    if role_obj is None:
        raise PermissionDenied("Пользователь не привязан к активному клиенту")

    set_active_client_preference(user, client)

    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "slug": client.slug,
            "last_image_generation_at": client.last_image_generation_at,
            "last_video_generation_at": client.last_video_generation_at,
        },
        "role": role_obj.role,
        "active_client_id": client.id,
        "memberships": [
            {
                "client": {
                    "id": membership.client.id,
                    "name": membership.client.name,
                    "slug": membership.client.slug,
                },
                "role": membership.role,
            }
            for membership in memberships
        ],
    }


def enforce_generation_limit(client: Client, event_type: str):
    limit_info = check_generation_limit(client, event_type)
    if not limit_info:
        return None
    payload = build_limit_error_payload(event_type, limit_info["used"], limit_info["limit"])
    return Response(payload, status=status.HTTP_403_FORBIDDEN)
