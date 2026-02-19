from __future__ import annotations

import secrets
import urllib.parse

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Client, UserSocialAccount, UserTenantRole

from .authentication import CookieJWTAuthentication
from .views_accounts import COOKIE_MAX_AGE, COOKIE_SAMESITE, REFRESH_COOKIE_MAX_AGE, set_token_cookie

VK_OAUTH_URL = "https://oauth.vk.com/authorize"
VK_TOKEN_URL = "https://oauth.vk.com/access_token"
VK_API_URL = "https://api.vk.com/method"
VK_API_VERSION = "5.199"
STATE_CACHE_TIMEOUT = 60 * 10  # 10 minutes

User = get_user_model()


def _get_vk_config() -> dict[str, str]:
    return {
        "app_id": (getattr(settings, "VK_AUTH_APP_ID", "") or "").strip(),
        "app_secret": (getattr(settings, "VK_AUTH_APP_SECRET", "") or "").strip(),
        "redirect_uri": (getattr(settings, "VK_AUTH_REDIRECT_URI", "") or "").strip(),
    }


def _build_auth_url(state: str, redirect_uri: str, app_id: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": "email",
        "response_type": "code",
        "v": VK_API_VERSION,
        "state": state,
        "display": "page",
    }
    return f"{VK_OAUTH_URL}?{urllib.parse.urlencode(params)}"


def _exchange_code_for_token(code: str, redirect_uri: str, app_id: str, app_secret: str) -> dict | None:
    try:
        response = requests.get(
            VK_TOKEN_URL,
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    if "error" in payload:
        return None
    return payload


def _fetch_vk_profile(access_token: str, user_id: int | str) -> dict | None:
    try:
        response = requests.get(
            f"{VK_API_URL}/users.get",
            params={
                "user_ids": user_id,
                "fields": "photo_200,screen_name",
                "access_token": access_token,
                "v": VK_API_VERSION,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None

    items = payload.get("response") or []
    return items[0] if items else None


def _get_or_create_user_and_client(profile: dict, vk_user_id: int | str, email: str | None):
    first_name = (profile.get("first_name") or "").strip()
    last_name = (profile.get("last_name") or "").strip()
    screen_name = (profile.get("screen_name") or "").strip()

    username = screen_name or f"vk_{vk_user_id}"
    user, user_created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "email": email or f"{username}@vk.local",
        },
    )

    if not user_created:
        changed = False
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if user.last_name != last_name:
            user.last_name = last_name
            changed = True
        if changed:
            user.save(update_fields=["first_name", "last_name"])

    client_slug = str(vk_user_id)
    client, _ = Client.objects.get_or_create(
        slug=client_slug,
        defaults={
            "name": f"{first_name} {last_name}".strip() or username or f"User {vk_user_id}",
        },
    )
    UserTenantRole.objects.get_or_create(
        user=user,
        client=client,
        defaults={"role": "owner"},
    )

    return user


def _find_user_by_vk_provider_id(vk_user_id: int | str):
    social = (
        UserSocialAccount.objects.select_related("user")
        .filter(provider=UserSocialAccount.PROVIDER_VK, provider_id=str(vk_user_id))
        .first()
    )
    return social.user if social else None


def _link_vk_to_user(user, vk_user_id: int | str, profile: dict, email: str | None) -> tuple[bool, str | None]:
    provider_id = str(vk_user_id)
    linked_to_other = (
        UserSocialAccount.objects.filter(
            provider=UserSocialAccount.PROVIDER_VK,
            provider_id=provider_id,
        )
        .exclude(user=user)
        .first()
    )
    if linked_to_other:
        return False, "Этот VK-аккаунт уже привязан к другому пользователю"

    linked_for_user = UserSocialAccount.objects.filter(user=user, provider=UserSocialAccount.PROVIDER_VK).first()
    if linked_for_user and linked_for_user.provider_id != provider_id:
        return False, "У пользователя уже привязан другой аккаунт VK"

    extra_data = {
        "first_name": profile.get("first_name", ""),
        "last_name": profile.get("last_name", ""),
        "screen_name": profile.get("screen_name", ""),
        "photo_url": profile.get("photo_200"),
        "email": email,
    }

    if linked_for_user:
        linked_for_user.extra_data = extra_data
        linked_for_user.save(update_fields=["extra_data", "updated_at"])
    else:
        UserSocialAccount.objects.create(
            user=user,
            provider=UserSocialAccount.PROVIDER_VK,
            provider_id=provider_id,
            extra_data=extra_data,
        )

    return True, None


class VkAuthUrlView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request):
        config = _get_vk_config()
        if not config["app_id"] or not config["app_secret"] or not config["redirect_uri"]:
            return Response(
                {"error": "VK auth is not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state = secrets.token_urlsafe(32)
        cache.set(f"vk_auth_state:{state}", True, STATE_CACHE_TIMEOUT)

        return Response(
            {
                "url": _build_auth_url(
                    state=state,
                    redirect_uri=config["redirect_uri"],
                    app_id=config["app_id"],
                ),
                "state": state,
            }
        )


class VkAuthView(APIView):
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

    def get(self, request):
        user = self._authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        return Response(
            {
                "user": {
                    "vkId": str(user.id),
                    "firstName": user.first_name or user.username,
                    "lastName": user.last_name,
                    "username": user.username,
                    "photoUrl": None,
                    "authDate": str(user.date_joined),
                }
            }
        )

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        state = (request.data.get("state") or "").strip()
        redirect_uri = (request.data.get("redirect_uri") or "").strip()
        config = _get_vk_config()

        if not code:
            return Response({"error": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
        if not state:
            return Response({"error": "Missing state"}, status=status.HTTP_400_BAD_REQUEST)
        if not config["app_id"] or not config["app_secret"] or not config["redirect_uri"]:
            return Response(
                {"error": "VK auth is not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not redirect_uri:
            redirect_uri = config["redirect_uri"]
        if redirect_uri != config["redirect_uri"]:
            return Response({"error": "Invalid redirect_uri"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"vk_auth_state:{state}"
        if not cache.get(cache_key):
            return Response({"error": "Invalid or expired state"}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(cache_key)

        token_data = _exchange_code_for_token(
            code=code,
            redirect_uri=redirect_uri,
            app_id=config["app_id"],
            app_secret=config["app_secret"],
        )
        if not token_data:
            return Response({"error": "Failed to exchange code"}, status=status.HTTP_400_BAD_REQUEST)

        access_token = token_data.get("access_token")
        vk_user_id = token_data.get("user_id")
        email = token_data.get("email")
        if not access_token or not vk_user_id:
            return Response({"error": "Invalid token response"}, status=status.HTTP_400_BAD_REQUEST)

        profile = _fetch_vk_profile(access_token=access_token, user_id=vk_user_id) or {}

        user = _find_user_by_vk_provider_id(vk_user_id)
        if user is None:
            user = _get_or_create_user_and_client(profile=profile, vk_user_id=vk_user_id, email=email)

        linked, error = _link_vk_to_user(user=user, vk_user_id=vk_user_id, profile=profile, email=email)
        if not linked:
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response(
            {
                "user": {
                    "vkId": str(vk_user_id),
                    "firstName": profile.get("first_name", "") or user.first_name,
                    "lastName": profile.get("last_name", "") or user.last_name,
                    "username": profile.get("screen_name", "") or user.username,
                    "photoUrl": profile.get("photo_200"),
                    "authDate": str(user.date_joined),
                }
            }
        )
        set_token_cookie(response, "access_token", str(access), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
        return response

    def delete(self, request):
        response = Response({"success": True})
        response.delete_cookie("access_token", path="/", samesite=COOKIE_SAMESITE)
        response.delete_cookie("refresh_token", path="/", samesite=COOKIE_SAMESITE)
        return response
