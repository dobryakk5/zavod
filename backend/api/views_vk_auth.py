from __future__ import annotations

import base64
import hashlib
import logging
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

from core.models import Client, MapContact, UserSocialAccount, UserTenantBinding, UserTenantRole
from core.services.team_invites import accept_pending_team_invites
from core.services.telegram_user_service import TelegramUserService

from .authentication import CookieJWTAuthentication
from .social_avatar_storage import persist_social_avatar
from .views_accounts import COOKIE_MAX_AGE, COOKIE_SAMESITE, REFRESH_COOKIE_MAX_AGE, set_token_cookie

VK_OAUTH_URL = "https://id.vk.com/authorize"
VK_TOKEN_URL = "https://id.vk.com/oauth2/auth"
VK_USERINFO_URL = "https://id.vk.com/oauth2/user_info"
VK_API_VERSION = "5.199"
VK_AUTH_SCOPE = "email"
STATE_CACHE_TIMEOUT = 60 * 10  # 10 minutes

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_vk_config() -> dict[str, str]:
    return {
        "app_id": (getattr(settings, "VK_AUTH_APP_ID", "") or "").strip(),
        "app_secret": (getattr(settings, "VK_AUTH_APP_SECRET", "") or "").strip(),
        "redirect_uri": (getattr(settings, "VK_AUTH_REDIRECT_URI", "") or "").strip(),
    }


def _build_auth_url(state: str, redirect_uri: str, app_id: str, code_challenge: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": VK_AUTH_SCOPE,
        "response_type": "code",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{VK_OAUTH_URL}?{urllib.parse.urlencode(params)}"


def _request_meta(request) -> str:
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    client_ip = forwarded_for or (request.META.get("REMOTE_ADDR") or "-")
    origin = request.META.get("HTTP_ORIGIN") or "-"
    referer = request.META.get("HTTP_REFERER") or "-"
    user_agent = (request.META.get("HTTP_USER_AGENT") or "-")[:160]
    return f"ip={client_ip} origin={origin!r} referer={referer!r} ua={user_agent!r}"


def _sanitize_vk_payload(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return payload

    sanitized: dict = {}
    for key, value in payload.items():
        if key in {"access_token", "refresh_token", "id_token"} and isinstance(value, str):
            sanitized[key] = f"<hidden len={len(value)}>"
        else:
            sanitized[key] = value
    return sanitized


def _exchange_code_for_token(
    code: str,
    redirect_uri: str,
    app_id: str,
    app_secret: str,
    code_verifier: str,
    device_id: str,
) -> dict | None:
    try:
        response = requests.post(
            VK_TOKEN_URL,
            data={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "code_verifier": code_verifier,
                "device_id": device_id,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
    except requests.RequestException as error:
        logger.warning("VK token exchange request error device_id_prefix=%s error=%s", device_id[:8], error)
        return None

    try:
        payload = response.json()
    except ValueError as error:
        logger.warning("VK token response parse error: status=%s body=%r error=%s", response.status_code, response.text, error)
        return None

    if response.ok and not payload.get("error"):
        logger.info(
            "VK token exchange success status=%s user_id=%s keys=%s",
            response.status_code,
            payload.get("user_id"),
            sorted(payload.keys()),
        )
    else:
        logger.warning(
            "VK token exchange rejected status=%s payload=%s",
            response.status_code,
            _sanitize_vk_payload(payload),
        )
    return payload


def _fetch_vk_profile(access_token: str, user_id: int | str) -> dict | None:
    try:
        response = requests.post(
            VK_USERINFO_URL,
            data={"access_token": access_token},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        logger.warning("VK profile fetch request error user_id=%s error=%s", user_id, error)
        return None
    except ValueError as error:
        logger.warning("VK profile fetch parse error user_id=%s error=%s", user_id, error)
        return None

    if not (payload.get("user_id") or payload.get("id")):
        logger.warning("VK profile fetch returned unexpected payload user_id=%s payload=%s", user_id, _sanitize_vk_payload(payload))
        return None

    return payload


def _get_or_create_user_and_client(
    profile: dict,
    vk_user_id: int | str,
    email: str | None,
):
    first_name = (profile.get("first_name") or "").strip()
    last_name = (profile.get("last_name") or "").strip()
    screen_name = (profile.get("screen_name") or "").strip()

    username = screen_name or f"vk_{vk_user_id}"
    user, user_created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "email": email or (profile.get("email") or "").strip() or f"{username}@vk.local",
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

    return user, user_created


def _find_user_by_vk_provider_id(vk_user_id: int | str):
    social = (
        UserSocialAccount.objects.select_related("user")
        .filter(provider=UserSocialAccount.PROVIDER_VK, provider_id=str(vk_user_id))
        .first()
    )
    return social.user if social else None


def _link_vk_to_user(
    user,
    vk_user_id: int | str,
    profile: dict,
    email: str | None,
    *,
    photo_url: str | None = None,
    avatar_metadata: dict | None = None,
) -> tuple[bool, str | None]:
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
        "photo_url": photo_url or profile.get("avatar"),
        "email": email or profile.get("email"),
    }
    if avatar_metadata:
        extra_data.update(avatar_metadata)

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
            missing = [key for key, value in config.items() if not value]
            logger.warning("VK auth url rejected: missing config fields=%s %s", ",".join(missing), _request_meta(request))
            return Response(
                {"error": "VK auth is not configured on server"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        cache.set(f"vk_auth_state:{state}", code_verifier, STATE_CACHE_TIMEOUT)
        logger.info("VK auth url issued state_suffix=%s redirect_uri=%s %s", state[-6:], config["redirect_uri"], _request_meta(request))

        return Response(
            {
                "url": _build_auth_url(
                    state=state,
                    redirect_uri=config["redirect_uri"],
                    app_id=config["app_id"],
                    code_challenge=code_challenge,
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

        linked_vk = (
            UserSocialAccount.objects.filter(
                user=user,
                provider=UserSocialAccount.PROVIDER_VK,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        vk_provider_id = str(linked_vk.provider_id) if linked_vk and linked_vk.provider_id else str(user.id)
        binding = (
            UserTenantBinding.objects.filter(
                provider=UserTenantBinding.PROVIDER_VK,
                provider_user_id=vk_provider_id,
                is_active=True,
            )
            .order_by("-bound_at", "-id")
            .first()
        )
        extra = linked_vk.extra_data if linked_vk and isinstance(linked_vk.extra_data, dict) else {}
        return Response(
            {
                "user": {
                    "vkId": vk_provider_id,
                    "firstName": extra.get("first_name") or user.first_name or user.username,
                    "lastName": extra.get("last_name") or user.last_name,
                    "username": extra.get("screen_name") or user.username,
                    "photoUrl": extra.get("photo_url"),
                    "authDate": str(user.date_joined),
                    "contactId": int(binding.contact_id) if binding and binding.contact_id is not None else None,
                    "tenantId": int(binding.tenant_id) if binding else None,
                }
            }
        )

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        state = (request.data.get("state") or "").strip()
        device_id = (request.data.get("device_id") or "").strip()
        redirect_uri = (request.data.get("redirect_uri") or "").strip()
        tenant_id_raw = request.data.get("tenant_id")
        tenant_id_hint = None
        config = _get_vk_config()

        logger.info(
            "VK auth attempt state_suffix=%s device_id_prefix=%s tenant_id_raw=%r redirect_uri=%r %s",
            state[-6:] if state else "-",
            device_id[:8] if device_id else "-",
            tenant_id_raw,
            redirect_uri or config["redirect_uri"],
            _request_meta(request),
        )

        try:
            if tenant_id_raw not in (None, ""):
                try:
                    tenant_id_hint = int(tenant_id_raw)
                except (TypeError, ValueError):
                    logger.warning(
                        "VK auth rejected: invalid tenant_id tenant_id_raw=%r state_suffix=%s %s",
                        tenant_id_raw,
                        state[-6:] if state else "-",
                        _request_meta(request),
                    )
                    return Response({"error": "Некорректный tenant_id"}, status=status.HTTP_400_BAD_REQUEST)
                if tenant_id_hint <= 0:
                    logger.warning(
                        "VK auth rejected: non-positive tenant_id tenant_id=%s state_suffix=%s %s",
                        tenant_id_hint,
                        state[-6:] if state else "-",
                        _request_meta(request),
                    )
                    return Response({"error": "Некорректный tenant_id"}, status=status.HTTP_400_BAD_REQUEST)

            if not code:
                logger.warning("VK auth rejected: missing code state_suffix=%s %s", state[-6:] if state else "-", _request_meta(request))
                return Response({"error": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
            if not state:
                logger.warning("VK auth rejected: missing state %s", _request_meta(request))
                return Response({"error": "Missing state"}, status=status.HTTP_400_BAD_REQUEST)
            if not device_id:
                logger.warning("VK auth rejected: missing device_id state_suffix=%s %s", state[-6:] if state else "-", _request_meta(request))
                return Response({"error": "Missing device_id"}, status=status.HTTP_400_BAD_REQUEST)
            if not config["app_id"] or not config["app_secret"] or not config["redirect_uri"]:
                missing = [key for key, value in config.items() if not value]
                logger.warning("VK auth rejected: missing config fields=%s state_suffix=%s %s", ",".join(missing), state[-6:] if state else "-", _request_meta(request))
                return Response(
                    {"error": "VK auth is not configured on server"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            if not redirect_uri:
                redirect_uri = config["redirect_uri"]
            if redirect_uri != config["redirect_uri"]:
                logger.warning(
                    "VK auth rejected: invalid redirect_uri provided=%r expected=%r state_suffix=%s %s",
                    redirect_uri,
                    config["redirect_uri"],
                    state[-6:] if state else "-",
                    _request_meta(request),
                )
                return Response({"error": "Invalid redirect_uri"}, status=status.HTTP_400_BAD_REQUEST)

            cache_key = f"vk_auth_state:{state}"
            code_verifier = cache.get(cache_key)
            if not code_verifier:
                logger.warning("VK auth rejected: invalid or expired state state_suffix=%s %s", state[-6:], _request_meta(request))
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
                logger.warning(
                    "VK auth rejected: token exchange returned no payload state_suffix=%s device_id_prefix=%s %s",
                    state[-6:],
                    device_id[:8],
                    _request_meta(request),
                )
                return Response({"error": "Failed to exchange code"}, status=status.HTTP_400_BAD_REQUEST)
            if token_data.get("error"):
                logger.warning(
                    "VK auth rejected: token exchange error state_suffix=%s payload=%s %s",
                    state[-6:],
                    _sanitize_vk_payload(token_data),
                    _request_meta(request),
                )
                return Response(
                    {"error": token_data.get("error_description") or token_data.get("error") or "Failed to exchange code"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            access_token = token_data.get("access_token")
            vk_user_id = token_data.get("user_id")
            email = token_data.get("email")
            if not access_token or not vk_user_id:
                logger.warning("VK auth rejected: invalid token response payload=%s %s", _sanitize_vk_payload(token_data), _request_meta(request))
                return Response({"error": "Invalid token response"}, status=status.HTTP_400_BAD_REQUEST)

            profile = _fetch_vk_profile(access_token=access_token, user_id=vk_user_id) or {}
            if not profile:
                logger.warning("VK auth profile fetch returned empty profile vk_user_id=%s %s", vk_user_id, _request_meta(request))
            stored_photo_url, avatar_metadata = persist_social_avatar(
                request=request,
                photo_url=profile.get("avatar"),
                provider=UserSocialAccount.PROVIDER_VK,
                provider_id=str(vk_user_id),
            )

            user = _find_user_by_vk_provider_id(vk_user_id)
            user_created = False
            if user is None:
                user, user_created = _get_or_create_user_and_client(
                    profile=profile,
                    vk_user_id=vk_user_id,
                    email=email,
                )

            linked, error = _link_vk_to_user(
                user=user,
                vk_user_id=vk_user_id,
                profile=profile,
                email=email,
                photo_url=stored_photo_url,
                avatar_metadata=avatar_metadata,
            )
            if not linked:
                logger.warning(
                    "VK auth conflict user_id=%s vk_user_id=%s error=%s %s",
                    user.id,
                    vk_user_id,
                    error,
                    _request_meta(request),
                )
                return Response({"error": error}, status=status.HTTP_409_CONFLICT)

            if tenant_id_hint is not None:
                existing_tenant_binding = (
                    UserTenantBinding.objects.filter(
                        provider=UserTenantBinding.PROVIDER_VK,
                        provider_user_id=str(vk_user_id),
                        tenant_id=tenant_id_hint,
                    )
                    .order_by("-bound_at", "-id")
                    .first()
                )
                contact_id = int(existing_tenant_binding.contact_id) if (
                    existing_tenant_binding and existing_tenant_binding.contact_id is not None
                ) else None
                if contact_id is None:
                    contact_name = (
                        f"{(profile.get('first_name') or '').strip()} {(profile.get('last_name') or '').strip()}".strip()
                        or (profile.get("screen_name") or "").strip()
                        or f"VK {vk_user_id}"
                    )
                    contact = MapContact.objects.create(name=contact_name)
                    contact_id = int(contact.id)

                try:
                    TelegramUserService().bind_identity_to_tenant(
                        provider=UserTenantBinding.PROVIDER_VK,
                        provider_user_id=str(vk_user_id),
                        tenant_id=tenant_id_hint,
                        contact_id=contact_id,
                        telegram_username=None,
                    )
                except ValueError as exc:
                    logger.warning(
                        "VK auth tenant bind failed vk_user_id=%s tenant_id=%s contact_id=%s error=%s %s",
                        vk_user_id,
                        tenant_id_hint,
                        contact_id,
                        exc,
                        _request_meta(request),
                    )
                    return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            accepted_invites = accept_pending_team_invites(user)

            if user_created and tenant_id_hint is None and not accepted_invites:
                client_slug = str(vk_user_id)
                client, _ = Client.objects.get_or_create(
                    slug=client_slug,
                    defaults={
                        "name": (
                            f"{(profile.get('first_name') or '').strip()} {(profile.get('last_name') or '').strip()}".strip()
                            or (profile.get("screen_name") or "").strip()
                            or f"User {vk_user_id}"
                        ),
                    },
                )
                UserTenantRole.objects.get_or_create(
                    user=user,
                    client=client,
                    defaults={"role": "owner"},
                )

            binding = (
                UserTenantBinding.objects.filter(
                    provider=UserTenantBinding.PROVIDER_VK,
                    provider_user_id=str(vk_user_id),
                    is_active=True,
                )
                .order_by("-bound_at", "-id")
                .first()
            )

            refresh = RefreshToken.for_user(user)
            access = refresh.access_token

            response = Response(
                {
                    "user": {
                        "vkId": str(vk_user_id),
                        "firstName": profile.get("first_name", "") or user.first_name,
                        "lastName": profile.get("last_name", "") or user.last_name,
                        "username": profile.get("screen_name", "") or user.username,
                        "photoUrl": stored_photo_url or profile.get("avatar"),
                        "authDate": str(user.date_joined),
                        "contactId": int(binding.contact_id) if binding and binding.contact_id is not None else None,
                        "tenantId": int(binding.tenant_id) if binding else None,
                    }
                }
            )
            set_token_cookie(response, "access_token", str(access), COOKIE_MAX_AGE)
            set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
            logger.info(
                "VK auth success vk_user_id=%s user_id=%s user_created=%s tenant_id=%s accepted_invites=%s %s",
                vk_user_id,
                user.id,
                user_created,
                tenant_id_hint,
                bool(accepted_invites),
                _request_meta(request),
            )
            return response
        except Exception:
            logger.exception(
                "VK auth unexpected error state_suffix=%s device_id_prefix=%s tenant_id_raw=%r %s",
                state[-6:] if state else "-",
                device_id[:8] if device_id else "-",
                tenant_id_raw,
                _request_meta(request),
            )
            raise

    def delete(self, request):
        response = Response({"success": True})
        response.delete_cookie("access_token", path="/", samesite=COOKIE_SAMESITE)
        response.delete_cookie("refresh_token", path="/", samesite=COOKIE_SAMESITE)
        return response
