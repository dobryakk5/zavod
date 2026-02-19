from __future__ import annotations

import hashlib
import hmac
import time

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import UserSocialAccount

from .authentication import CookieJWTAuthentication
from .views_vk_auth import _exchange_code_for_token, _fetch_vk_profile, _get_vk_config


SUPPORTED_PROVIDERS = {
    UserSocialAccount.PROVIDER_TELEGRAM,
    UserSocialAccount.PROVIDER_VK,
}


def _authenticate_cookie_user(request):
    authenticator = CookieJWTAuthentication()
    auth_result = authenticator.authenticate(request)
    if not auth_result:
        return None

    user, token = auth_result
    request.user = user
    request.auth = token
    return user


def _link_provider(user, provider: str, provider_id: str, extra_data: dict) -> tuple[bool, str | None]:
    provider_id = str(provider_id).strip()
    if not provider_id:
        return False, "Missing provider id"

    linked_to_other = UserSocialAccount.objects.filter(provider=provider, provider_id=provider_id).exclude(user=user).first()
    if linked_to_other:
        return False, "Этот аккаунт уже привязан к другому пользователю"

    linked_for_user = UserSocialAccount.objects.filter(user=user, provider=provider).first()
    if linked_for_user and linked_for_user.provider_id != provider_id:
        return False, "У пользователя уже привязан другой аккаунт этого провайдера"

    if linked_for_user:
        linked_for_user.extra_data = extra_data
        linked_for_user.save(update_fields=["extra_data", "updated_at"])
    else:
        UserSocialAccount.objects.create(
            user=user,
            provider=provider,
            provider_id=provider_id,
            extra_data=extra_data,
        )

    return True, None


def _verify_telegram_payload(payload: dict) -> bool:
    from django.conf import settings

    if settings.DEBUG:
        return True

    bot_token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    if not bot_token:
        return False

    received_hash = (payload.get("hash") or "").strip()
    if not received_hash:
        return False

    auth_date_raw = payload.get("auth_date")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return False

    if abs(time.time() - auth_date) > 24 * 60 * 60:
        return False

    check_data = {k: v for k, v in payload.items() if k != "hash" and v is not None}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)


class SocialAccountsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request):
        user = _authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        accounts = list(
            UserSocialAccount.objects.filter(user=user)
            .values("provider", "provider_id", "extra_data", "created_at")
            .order_by("provider")
        )
        return Response({"accounts": accounts, "supported": sorted(SUPPORTED_PROVIDERS)})


class LinkVkView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        user = _authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        code = (request.data.get("code") or "").strip()
        state = (request.data.get("state") or "").strip()
        redirect_uri = (request.data.get("redirect_uri") or "").strip()
        config = _get_vk_config()

        if not code:
            return Response({"error": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
        if not state:
            return Response({"error": "Missing state"}, status=status.HTTP_400_BAD_REQUEST)
        if not config["app_id"] or not config["app_secret"] or not config["redirect_uri"]:
            return Response({"error": "VK auth is not configured on server"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not redirect_uri:
            redirect_uri = config["redirect_uri"]
        if redirect_uri != config["redirect_uri"]:
            return Response({"error": "Invalid redirect_uri"}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.cache import cache

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

        ok, error = _link_provider(
            user=user,
            provider=UserSocialAccount.PROVIDER_VK,
            provider_id=str(vk_user_id),
            extra_data={
                "first_name": profile.get("first_name", ""),
                "last_name": profile.get("last_name", ""),
                "screen_name": profile.get("screen_name", ""),
                "photo_url": profile.get("photo_200"),
                "email": email,
            },
        )
        if not ok:
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)

        display_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or profile.get("screen_name", "")
        return Response(
            {
                "linked": True,
                "provider": UserSocialAccount.PROVIDER_VK,
                "providerDisplayName": display_name,
                "photoUrl": profile.get("photo_200"),
            }
        )


class LinkTelegramView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        user = _authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        telegram_data = request.data
        telegram_id = telegram_data.get("id")
        if not telegram_id:
            return Response({"error": "Missing Telegram ID"}, status=status.HTTP_400_BAD_REQUEST)

        if not _verify_telegram_payload(telegram_data):
            return Response({"error": "Invalid Telegram payload signature"}, status=status.HTTP_400_BAD_REQUEST)

        ok, error = _link_provider(
            user=user,
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
            provider_id=str(telegram_id),
            extra_data={
                "first_name": telegram_data.get("first_name", ""),
                "last_name": telegram_data.get("last_name", ""),
                "username": telegram_data.get("username", ""),
                "photo_url": telegram_data.get("photo_url"),
            },
        )
        if not ok:
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "linked": True,
                "provider": UserSocialAccount.PROVIDER_TELEGRAM,
                "providerDisplayName": (
                    f"{telegram_data.get('first_name', '')} {telegram_data.get('last_name', '')}".strip()
                    or telegram_data.get("username", "")
                ),
                "photoUrl": telegram_data.get("photo_url"),
            }
        )


class UnlinkView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def delete(self, request, provider: str):
        user = _authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        if provider not in SUPPORTED_PROVIDERS:
            return Response({"error": f"Unsupported provider: {provider}"}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = UserSocialAccount.objects.filter(user=user, provider=provider).delete()
        if not deleted:
            return Response({"error": "Account is not linked"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"unlinked": True, "provider": provider})
