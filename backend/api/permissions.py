from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import BasePermission

from api.utils import get_active_client
from core.models import UserTenantRole


class IsTenantMember(BasePermission):
    """
    Permission check: user must be a member of a client (any role: owner, editor, viewer).
    Used for read-only operations.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            get_active_client(request.user)
            return True
        except Exception:
            return False


class IsTenantOwnerOrEditor(BasePermission):
    """
    Permission check: user must have 'owner' or 'editor' role for the client.
    Used for create/update/delete operations.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            client = get_active_client(request.user)
            role = UserTenantRole.objects.filter(
                user=request.user,
                client=client
            ).first()

            if role and role.role in ['owner', 'editor']:
                return True
            return False
        except Exception:
            return False


class CanGenerateVideo(BasePermission):
    """
    Permission check: video generation is only available in DEBUG mode or for 'zavod' client.
    Regular users cannot generate videos.
    """

    def has_permission(self, request, view):
        # Dev mode: always allow
        if settings.DEBUG:
            return True

        # Check if user's client is 'zavod'
        try:
            client = get_active_client(request.user)
            return client.slug == 'zavod'
        except Exception:
            return False
