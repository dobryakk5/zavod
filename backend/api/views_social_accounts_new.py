from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Client, UserSocialAccount, UserTenantRole

from .authentication import CookieJWTAuthentication
from .views_accounts import COOKIE_MAX_AGE, COOKIE_SAMESITE, REFRESH_COOKIE_MAX_AGE, set_token_cookie
from .views_vk_auth import _exchange_code_for_token, _fetch_vk_profile, _get_vk_config

User = get_user_model()

SUPPORTED_PROVIDERS = {
    UserSocialAccount.PROVIDER_TELEGRAM,
    UserSocialAccount.PROVIDER_VK,
}

CONFLICT_CACHE_TIMEOUT = 60 * 15  # 15 минут


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _authenticate_cookie_user(request):
    authenticator = CookieJWTAuthentication()
    auth_result = authenticator.authenticate(request)
    if not auth_result:
        return None
    user, token = auth_result
    request.user = user
    request.auth = token
    return user


def _profile_summary(user) -> dict:
    """Краткая сводка профиля для отображения в модалке выбора."""
    role = UserTenantRole.objects.select_related("client").filter(user=user).first()
    client = role.client if role else None

    # Проверяем «пустоту» клиента через обратные связи.
    # Добавьте сюда модели, которые считаются «контентом» в вашем проекте.
    is_empty = True
    content_hint: list[str] = []
    if client:
        # Примеры — раскомментируйте / замените реальными моделями:
        # if client.posts.exists():
        #     content_hint.append("посты")
        #     is_empty = False
        # if client.chains.exists():
        #     content_hint.append("цепочки")
        #     is_empty = False
        pass  # пока считаем пустым по умолчанию

    socials = list(
        UserSocialAccount.objects.filter(user=user).values("provider", "provider_id", "extra_data")
    )

    return {
        "user_id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat(),
        "client_name": client.name if client else None,
        "social_accounts": socials,
        "is_empty": is_empty,
        "content_hint": content_hint,
    }


def _build_conflict_response(
    *,
    current_user,
    existing_user,
    provider: str,
    provider_id: str,
    extra_data: dict,
) -> Response:
    """
    Формирует 409-ответ с данными обоих профилей и resolution_token.
    Токен кладём в кэш; он нужен при POST /auth/social/conflict/resolve.
    """
    resolution_token = secrets.token_urlsafe(32)
    cache.set(
        f"social_conflict:{resolution_token}",
        {
            "current_user_id": current_user.pk,
            "existing_user_id": existing_user.pk,
            "provider": provider,
            "provider_id": str(provider_id),
            "extra_data": extra_data,
        },
        CONFLICT_CACHE_TIMEOUT,
    )

    return Response(
        {
            "conflict": True,
            "conflict_type": "social_account_already_linked",
            "resolution_token": resolution_token,
            "current_profile": _profile_summary(current_user),
            "existing_profile": _profile_summary(existing_user),
        },
        status=status.HTTP_409_CONFLICT,
    )


def _link_provider(user, provider: str, provider_id: str, extra_data: dict) -> tuple[bool, str | None, object | None]:
    """
    Возвращает (ok, error_message, conflicting_user_or_None).
    Если ok=False и conflicting_user is not None → нужна conflict-модалка.
    """
    provider_id = str(provider_id).strip()
    if not provider_id:
        return False, "Missing provider id", None

    existing_social = (
        UserSocialAccount.objects.select_related("user")
        .filter(provider=provider, provider_id=provider_id)
        .exclude(user=user)
        .first()
    )
    if existing_social:
        return False, "conflict", existing_social.user

    linked_for_user = UserSocialAccount.objects.filter(user=user, provider=provider).first()
    if linked_for_user and linked_for_user.provider_id != provider_id:
        return False, "У пользователя уже привязан другой аккаунт этого провайдера", None

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

    return True, None, None


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


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

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
        device_id = (request.data.get("device_id") or "").strip()
        redirect_uri = (request.data.get("redirect_uri") or "").strip()
        config = _get_vk_config()

        if not code:
            return Response({"error": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
        if not state:
            return Response({"error": "Missing state"}, status=status.HTTP_400_BAD_REQUEST)
        if not device_id:
            return Response({"error": "Missing device_id"}, status=status.HTTP_400_BAD_REQUEST)
        if not config["app_id"] or not config["app_secret"] or not config["redirect_uri"]:
            return Response({"error": "VK auth is not configured on server"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if not redirect_uri:
            redirect_uri = config["redirect_uri"]
        if redirect_uri != config["redirect_uri"]:
            return Response({"error": "Invalid redirect_uri"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"vk_auth_state:{state}"
        code_verifier = cache.get(cache_key)
        if not code_verifier:
            return Response({"error": "Invalid or expired state"}, status=status.HTTP_400_BAD_REQUEST)
        cache.delete(cache_key)

        token_data = _exchange_code_for_token(
            code=code,
            redirect_uri=redirect_uri,
            app_id=config["app_id"],
            app_secret=config["app_secret"],
            code_verifier=code_verifier,
            device_id=device_id,
        )
        if not token_data:
            return Response({"error": "Failed to exchange code"}, status=status.HTTP_400_BAD_REQUEST)
        if token_data.get("error"):
            return Response(
                {"error": token_data.get("error_description") or token_data.get("error") or "Failed to exchange code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = token_data.get("access_token")
        vk_user_id = token_data.get("user_id")
        email = token_data.get("email")
        if not access_token or not vk_user_id:
            return Response({"error": "Invalid token response"}, status=status.HTTP_400_BAD_REQUEST)

        profile = _fetch_vk_profile(access_token=access_token, user_id=vk_user_id) or {}
        extra_data = {
            "first_name": profile.get("first_name", ""),
            "last_name": profile.get("last_name", ""),
            "screen_name": profile.get("screen_name", ""),
            "photo_url": profile.get("avatar"),
            "email": email or profile.get("email"),
        }

        ok, error, conflicting_user = _link_provider(
            user=user,
            provider=UserSocialAccount.PROVIDER_VK,
            provider_id=str(vk_user_id),
            extra_data=extra_data,
        )

        if not ok:
            if conflicting_user is not None:
                return _build_conflict_response(
                    current_user=user,
                    existing_user=conflicting_user,
                    provider=UserSocialAccount.PROVIDER_VK,
                    provider_id=str(vk_user_id),
                    extra_data=extra_data,
                )
            return Response({"error": error}, status=status.HTTP_409_CONFLICT)

        display_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or profile.get("screen_name", "")
        return Response(
            {
                "linked": True,
                "provider": UserSocialAccount.PROVIDER_VK,
                "providerDisplayName": display_name,
                "photoUrl": profile.get("avatar"),
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

        extra_data = {
            "first_name": telegram_data.get("first_name", ""),
            "last_name": telegram_data.get("last_name", ""),
            "username": telegram_data.get("username", ""),
            "photo_url": telegram_data.get("photo_url"),
        }

        ok, error, conflicting_user = _link_provider(
            user=user,
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
            provider_id=str(telegram_id),
            extra_data=extra_data,
        )

        if not ok:
            if conflicting_user is not None:
                return _build_conflict_response(
                    current_user=user,
                    existing_user=conflicting_user,
                    provider=UserSocialAccount.PROVIDER_TELEGRAM,
                    provider_id=str(telegram_id),
                    extra_data=extra_data,
                )
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


class ResolveConflictView(APIView):
    """
    POST /auth/social/conflict/resolve

    payload:
        resolution_token  — токен из 409-ответа
        keep              — "current" | "existing"

    Логика:
    1. Достаём из кэша данные конфликта.
    2. Определяем keep_user / drop_user.
    3. В транзакции переносим все UserSocialAccount drop_user → keep_user,
       удаляем UserTenantRole drop_user, при необходимости удаляем drop_user.
    4. Если Client drop_user не пустой — только отвязываем роль, не удаляем,
       и возвращаем предупреждение.
    5. Выдаём новые JWT-куки на keep_user.
    """

    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        # Текущий пользователь должен быть авторизован
        current_user = _authenticate_cookie_user(request)
        if not current_user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        resolution_token = (request.data.get("resolution_token") or "").strip()
        keep_choice = (request.data.get("keep") or "").strip()  # "current" | "existing"

        if not resolution_token:
            return Response({"error": "Missing resolution_token"}, status=status.HTTP_400_BAD_REQUEST)
        if keep_choice not in ("current", "existing"):
            return Response({"error": "keep must be 'current' or 'existing'"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"social_conflict:{resolution_token}"
        conflict_data = cache.get(cache_key)
        if not conflict_data:
            return Response({"error": "Invalid or expired resolution_token"}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, что токен принадлежит именно текущему пользователю
        if conflict_data["current_user_id"] != current_user.pk:
            return Response({"error": "resolution_token does not match current user"}, status=status.HTTP_403_FORBIDDEN)

        cache.delete(cache_key)

        try:
            existing_user = User.objects.get(pk=conflict_data["existing_user_id"])
        except User.DoesNotExist:
            return Response({"error": "Conflicting user no longer exists"}, status=status.HTTP_404_NOT_FOUND)

        if keep_choice == "current":
            keep_user, drop_user = current_user, existing_user
        else:
            keep_user, drop_user = existing_user, current_user

        warning = None

        with transaction.atomic():
            # 1. Перенести все соцаккаунты drop_user → keep_user
            #    (пропустить, если провайдер уже есть у keep_user — дубль не нужен)
            for social in UserSocialAccount.objects.filter(user=drop_user):
                already_on_keep = UserSocialAccount.objects.filter(
                    user=keep_user,
                    provider=social.provider,
                    provider_id=social.provider_id,
                ).exists()
                if not already_on_keep:
                    social.user = keep_user
                    social.save(update_fields=["user"])
                else:
                    social.delete()

            # 2. Убедиться, что нужный соцаккаунт (из конфликта) привязан к keep_user
            UserSocialAccount.objects.update_or_create(
                user=keep_user,
                provider=conflict_data["provider"],
                defaults={
                    "provider_id": conflict_data["provider_id"],
                    "extra_data": conflict_data["extra_data"],
                },
            )

            # 3. Проверяем drop_client на «пустоту»
            drop_role = UserTenantRole.objects.select_related("client").filter(user=drop_user).first()
            drop_client: Client | None = drop_role.client if drop_role else None

            client_is_empty = True
            if drop_client:
                # Добавьте сюда реальные проверки контента:
                # client_is_empty = not (
                #     drop_client.posts.exists()
                #     or drop_client.chains.exists()
                # )
                client_is_empty = True  # заглушка — замените реальной проверкой

            # 4. Отвязываем UserTenantRole drop_user
            UserTenantRole.objects.filter(user=drop_user).delete()

            if client_is_empty:
                # Клиент пустой — удаляем вместе с пользователем
                if drop_client:
                    drop_client.delete()
                drop_user.delete()
            else:
                # Клиент не пустой — удаляем только пользователя, клиент остаётся
                drop_user.delete()
                warning = (
                    f"Профиль переключён, но клиент «{drop_client.name}» содержит данные "
                    f"и требует ручной проверки (slug: {drop_client.slug})"
                )

        # 5. Выдаём JWT на keep_user
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(keep_user)
        access = refresh.access_token

        response_data = {
            "resolved": True,
            "kept": keep_choice,
            "user": {
                "id": keep_user.pk,
                "username": keep_user.username,
                "email": keep_user.email,
                "first_name": keep_user.first_name,
                "last_name": keep_user.last_name,
            },
        }
        if warning:
            response_data["warning"] = warning

        response = Response(response_data)
        set_token_cookie(response, "access_token", str(access), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
        return response
