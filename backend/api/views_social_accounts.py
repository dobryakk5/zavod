from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Client, UserSocialAccount, UserTenantRole  # Client used in resolution

from .authentication import CookieJWTAuthentication
from .social_avatar_storage import persist_social_avatar
from .views_accounts import COOKIE_MAX_AGE, COOKIE_SAMESITE, REFRESH_COOKIE_MAX_AGE, set_token_cookie
from .views_vk_auth import _exchange_code_for_token, _fetch_vk_profile, _get_vk_config

logger = logging.getLogger(__name__)
User = get_user_model()

SUPPORTED_PROVIDERS = {
    UserSocialAccount.PROVIDER_TELEGRAM,
    UserSocialAccount.PROVIDER_VK,
}

CONFLICT_CACHE_TIMEOUT = 60 * 15  # 15 минут


# ---------------------------------------------------------------------------
# auth helper
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


# ---------------------------------------------------------------------------
# profile summary (для модалки выбора на фронте)
# ---------------------------------------------------------------------------

def _client_is_empty(client: Client) -> bool:
    """
    Только UI-подсказка для модалки.
    Пока консервативно считаем, что клиент НЕ пустой, чтобы не вводить в заблуждение.
    """
    return False


def _client_summary(client: Client) -> dict:
    return {
        "id": client.pk,
        "slug": client.slug,
        "name": client.name,
    }


def _client_has_third_party_users(client: Client, *, keep_user, drop_user) -> bool:
    return UserTenantRole.objects.filter(client=client).exclude(user__in=[keep_user, drop_user]).exists()

def _profile_summary(user) -> dict:
    roles = list(UserTenantRole.objects.select_related("client").filter(user=user))
    clients_info = [
        {
            "name": r.client.name,
            "slug": r.client.slug,
            "role": r.role,
            "is_empty": _client_is_empty(r.client),
        }
        for r in roles
    ]
    socials = list(
        UserSocialAccount.objects.filter(user=user).values("provider", "extra_data")
    )
    return {
        "user_id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat(),
        "clients": clients_info,
        "social_accounts": socials,
    }


def _user_data(user) -> dict:
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


# ---------------------------------------------------------------------------
# conflict response builder
# ---------------------------------------------------------------------------

def _build_conflict_response(
    *,
    current_user,
    existing_user,
    provider: str,
    provider_id: str,
    extra_data: dict,
) -> Response:
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


# ---------------------------------------------------------------------------
# link provider (чистая привязка, без side-effects)
# ---------------------------------------------------------------------------

def _link_provider(
    user, provider: str, provider_id: str, extra_data: dict
) -> tuple[bool, str | None, object | None]:
    """
    Returns (ok, error_message, conflicting_user_or_None).
    conflicting_user is not None → показать модалку конфликта.
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
            user=user, provider=provider, provider_id=provider_id, extra_data=extra_data,
        )
    return True, None, None


# ---------------------------------------------------------------------------
# telegram verification
# ---------------------------------------------------------------------------

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

    try:
        auth_date = int(payload.get("auth_date"))
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
# resolution logic (transaction body)
# ---------------------------------------------------------------------------

@dataclass
class ResolutionResult:
    keep_user: object
    deleted_user_id: int | None = None
    warnings: list[str] = field(default_factory=list)
    clients_deleted: list[dict] = field(default_factory=list)
    clients_detached: list[dict] = field(default_factory=list)


def _resolve_conflict_in_transaction(
    *,
    keep_user,
    drop_user,
    provider: str,
    provider_id: str,
    extra_data: dict,
) -> ResolutionResult:
    """
    Вся логика разрешения конфликта. Вызывается внутри transaction.atomic().

    Политика:
    - Данные НЕ merge'им между клиентами.
    - Переносим все соцаккаунты drop_user -> keep_user (с правилами конфликтов по provider).
    - Профиль drop_user удаляем.
    - Клиенты drop_user удаляем полностью, если они не shared.
    - Если есть shared-клиент с третьими лицами (кроме keep_user/drop_user) — прерываем операцию.
    """
    result = ResolutionResult(keep_user=keep_user)

    drop_roles = list(
        UserTenantRole.objects.select_related("client").filter(user=drop_user)
    )
    drop_clients = [role.client for role in drop_roles]

    # Pre-check: запрещаем удаление, если есть shared-клиенты с третьими лицами.
    shared_third_party = []
    for client in drop_clients:
        if _client_has_third_party_users(client, keep_user=keep_user, drop_user=drop_user):
            shared_third_party.append(_client_summary(client))
    if shared_third_party:
        raise ValueError({"error": "cannot_delete_shared_clients", "details": {"shared_clients": shared_third_party}})

    # Шаг 1: переносим ВСЕ соцаккаунты drop_user -> keep_user.
    for social in list(UserSocialAccount.objects.filter(user=drop_user)):
        keep_same_provider = UserSocialAccount.objects.filter(
            user=keep_user,
            provider=social.provider,
        ).first()

        if keep_same_provider is None:
            social.user = keep_user
            social.save(update_fields=["user"])
            continue

        if keep_same_provider.provider_id == social.provider_id:
            # Точный дубль, оставляем запись keep_user.
            # Обновим extra_data у keep_user для конфликтного провайдера, если это тот самый аккаунт.
            if social.provider == provider and str(social.provider_id) == str(provider_id):
                keep_same_provider.extra_data = extra_data
                keep_same_provider.save(update_fields=["extra_data", "updated_at"])
            social.delete()
            continue

        # Один provider, но другой provider_id — по модели хранить оба нельзя.
        result.warnings.append(
            f"Провайдер {social.provider}: у выбранного профиля уже есть аккаунт "
            f"(id={keep_same_provider.provider_id}), аккаунт id={social.provider_id} удалён."
        )
        social.delete()

    # Шаг 2: убеждаемся, что конфликтный соцаккаунт существует у keep_user и актуализирован.
    target_social = UserSocialAccount.objects.filter(
        user=keep_user, provider=provider, provider_id=str(provider_id)
    ).first()
    if target_social:
        target_social.extra_data = extra_data
        target_social.save(update_fields=["extra_data", "updated_at"])
    else:
        # Возможен только если keep_user уже имел другой аккаунт того же провайдера; создаём нельзя.
        # Оставляем предупреждение вместо падения.
        result.warnings.append(
            f"Не удалось привязать {provider} id={provider_id}: у выбранного профиля уже есть другой аккаунт этого провайдера."
        )

    # Шаг 3: удаляем/отвязываем роли drop_user и чистим его клиентов.
    for role in drop_roles:
        client = role.client
        client_data = _client_summary(client)

        # Есть только keep_user (или никого) кроме drop_user — операцию можно завершить безопасно.
        has_keep_user = UserTenantRole.objects.filter(client=client, user=keep_user).exists()

        # Удаляем роль drop_user первой.
        role.delete()

        if has_keep_user:
            # Клиент shared только с keep_user — оставляем клиент, профиль drop_user от него отсоединён.
            result.clients_detached.append(client_data)
            continue

        # После удаления роли drop_user ролей не осталось -> удаляем клиент полностью (данные каскадом).
        if not UserTenantRole.objects.filter(client=client).exists():
            client.delete()
            result.clients_deleted.append(client_data)
            logger.info("conflict_resolve: deleted client=%s", client_data["slug"])

    # Шаг 4: удаляем drop_user (после переноса соцаккаунтов и ролей).
    drop_user_pk = drop_user.pk
    drop_user.delete()
    result.deleted_user_id = drop_user_pk
    logger.info("conflict_resolve: deleted user=%s, kept user=%s", drop_user_pk, keep_user.pk)

    return result


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
            return Response(
                {"error": "VK auth is not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
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
        stored_photo_url, avatar_metadata = persist_social_avatar(
            request=request,
            photo_url=profile.get("avatar"),
            provider=UserSocialAccount.PROVIDER_VK,
            provider_id=str(vk_user_id),
        )
        extra_data = {
            "first_name": profile.get("first_name", ""),
            "last_name": profile.get("last_name", ""),
            "screen_name": profile.get("screen_name", ""),
            "photo_url": stored_photo_url or profile.get("avatar"),
            "email": email or profile.get("email"),
            **avatar_metadata,
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

        display_name = (
            f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
            or profile.get("screen_name", "")
        )
        return Response(
            {
                "linked": True,
                "provider": UserSocialAccount.PROVIDER_VK,
                "providerDisplayName": display_name,
                "photoUrl": extra_data.get("photo_url"),
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
            return Response(
                {"error": "Invalid Telegram payload signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stored_photo_url, avatar_metadata = persist_social_avatar(
            request=request,
            photo_url=telegram_data.get("photo_url"),
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
            provider_id=str(telegram_id),
        )
        extra_data = {
            "first_name": telegram_data.get("first_name", ""),
            "last_name": telegram_data.get("last_name", ""),
            "username": telegram_data.get("username", ""),
            "photo_url": stored_photo_url or telegram_data.get("photo_url"),
            **avatar_metadata,
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
                "photoUrl": extra_data.get("photo_url"),
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
            return Response(
                {"error": f"Unsupported provider: {provider}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = UserSocialAccount.objects.filter(user=user, provider=provider).delete()
        if not deleted:
            return Response({"error": "Account is not linked"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"unlinked": True, "provider": provider})


class ResolveConflictView(APIView):
    """
    POST /auth/social/conflict/resolve

    Payload:
        resolution_token  — из 409-ответа (живёт 15 мин, одноразовый)
        keep              — "current" | "existing"

    Response 200:
        {
            "resolved": true,
            "kept": "current" | "existing",
            "warnings": [...],   // пустой список если всё чисто
            "user": { id, username, email, first_name, last_name }
        }
        + новые JWT-куки (access_token, refresh_token) на keep_user
    """

    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        current_user = _authenticate_cookie_user(request)
        if not current_user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        resolution_token = (request.data.get("resolution_token") or "").strip()
        keep_choice = (request.data.get("keep") or "").strip()

        if not resolution_token:
            return Response({"error": "Missing resolution_token"}, status=status.HTTP_400_BAD_REQUEST)
        if keep_choice not in ("current", "existing"):
            return Response(
                {"error": "keep must be 'current' or 'existing'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"social_conflict:{resolution_token}"
        conflict_data = cache.get(cache_key)
        if not conflict_data:
            return Response(
                {"error": "Invalid or expired resolution_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем, что токен принадлежит именно текущему пользователю.
        if conflict_data["current_user_id"] != current_user.pk:
            return Response(
                {"error": "resolution_token does not match current user"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Одноразовый токен — сразу удаляем.
        cache.delete(cache_key)

        try:
            existing_user = User.objects.get(pk=conflict_data["existing_user_id"])
        except User.DoesNotExist:
            # Второй профиль уже не существует — просто продолжаем с текущим.
            refresh = RefreshToken.for_user(current_user)
            response = Response({
                "resolved": True,
                "kept": "current",
                "warnings": ["Второй профиль уже не существует, изменений не потребовалось."],
                "deleted": {
                    "user_id": None,
                    "clients_deleted": [],
                    "clients_detached": [],
                },
                "user": _user_data(current_user),
            })
            set_token_cookie(response, "access_token", str(refresh.access_token), COOKIE_MAX_AGE)
            set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
            return response

        keep_user = current_user if keep_choice == "current" else existing_user
        drop_user = existing_user if keep_choice == "current" else current_user

        try:
            with transaction.atomic():
                result = _resolve_conflict_in_transaction(
                    keep_user=keep_user,
                    drop_user=drop_user,
                    provider=conflict_data["provider"],
                    provider_id=conflict_data["provider_id"],
                    extra_data=conflict_data["extra_data"],
                )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else None
            if isinstance(payload, dict) and payload.get("error") == "cannot_delete_shared_clients":
                return Response(payload, status=status.HTTP_409_CONFLICT)
            logger.exception("conflict_resolve: value error")
            return Response(
                {"error": "Ошибка при разрешении конфликта. Попробуйте ещё раз или обратитесь в поддержку."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("conflict_resolve: unexpected error")
            return Response(
                {"error": "Ошибка при разрешении конфликта. Попробуйте ещё раз или обратитесь в поддержку."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        refresh = RefreshToken.for_user(result.keep_user)
        response = Response({
            "resolved": True,
            "kept": keep_choice,
            "warnings": result.warnings,
            "deleted": {
                "user_id": result.deleted_user_id,
                "clients_deleted": result.clients_deleted,
                "clients_detached": result.clients_detached,
            },
            "user": _user_data(result.keep_user),
        })
        set_token_cookie(response, "access_token", str(refresh.access_token), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
        return response
