from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.messaging import get_available_channels
from core.models import UserTenantRole

from .authentication import CookieJWTAuthentication
from .utils import get_active_client


class ClientChannelView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def _authenticate_cookie_user(self, request):
        authenticator = CookieJWTAuthentication()
        auth_result = authenticator.authenticate(request)
        if not auth_result:
            return None

        user, token = auth_result
        request.user = user
        request.auth = token
        return user

    def _resolve_client(self, user, request):
        client_id = request.query_params.get("client_id") or request.data.get("client_id")
        if client_id:
            role = (
                UserTenantRole.objects.select_related("client")
                .filter(user=user, client_id=client_id)
                .first()
            )
            return role.client if role else None
        return get_active_client(user)

    def get(self, request):
        user = self._authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        client = self._resolve_client(user, request)
        if not client:
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

        channels = get_available_channels(client)
        return Response(
            {
                "preferred": client.preferred_channel or (channels[0].provider if channels else None),
                "channels": [
                    {
                        "provider": channel.provider,
                        "label": channel.label,
                        "provider_id": channel.provider_id,
                        "is_preferred": channel.is_preferred,
                    }
                    for channel in channels
                ],
            }
        )

    def post(self, request):
        user = self._authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        client = self._resolve_client(user, request)
        if not client:
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)

        channel = (request.data.get("channel") or "").strip()
        if not channel:
            return Response({"error": "Missing channel"}, status=status.HTTP_400_BAD_REQUEST)

        channels = get_available_channels(client)
        available = {entry.provider for entry in channels}
        if channel not in available:
            return Response(
                {"error": f"Channel '{channel}' is not available", "available": sorted(available)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client.preferred_channel = channel
        client.save(update_fields=["preferred_channel"])

        return Response({"preferred": channel})
