from __future__ import annotations

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from core.ai_generator import AIContentGenerator
from core.generation_events import (
    EVENT_TYPE_LIST,
    get_trial_limit,
    is_trial_client,
    record_generation_event,
)
from django.db import transaction

from core.models import GenerationEvent, Post, Schedule, SemanticGroup

from .authentication import CookieJWTAuthentication
from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .social_avatar_storage import persist_social_avatar
from .serializers import ClientSettingsSerializer, ClientSummarySerializer
from .utils import enforce_generation_limit, get_active_client

User = get_user_model()

COOKIE_SECURE = not settings.DEBUG
COOKIE_SAMESITE = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
COOKIE_MAX_AGE = int(getattr(settings, "JWT_COOKIE_MAX_AGE", 60 * 60))  # 1 hour for access token
REFRESH_COOKIE_MAX_AGE = int(getattr(settings, "JWT_REFRESH_COOKIE_MAX_AGE", 60 * 60 * 24 * 7))

def _is_dev_user(user) -> bool:
    return getattr(user, "is_dev_user", False) or user.username == "dev_user"

def set_token_cookie(response: Response, key: str, value: str, max_age: int):
    response.set_cookie(
        key,
        value,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
        max_age=max_age,
    )


class TelegramAuthView(APIView):
    """Telegram authentication endpoint for frontend"""
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def _authenticate_cookie_user(self, request):
        """
        Manually authenticate the request since the view disables global JWT auth.
        Allows login endpoints to be accessed even when existing tokens are expired.
        """
        authenticator = CookieJWTAuthentication()
        auth_result = authenticator.authenticate(request)
        if not auth_result:
            return None

        user, token = auth_result
        request.user = user
        request.auth = token
        return user

    def get(self, request):
        """Check if user is authenticated"""
        user = self._authenticate_cookie_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        from core.models import UserSocialAccount, UserTenantBinding

        linked_telegram = (
            UserSocialAccount.objects.filter(
                user=user,
                provider=UserSocialAccount.PROVIDER_TELEGRAM,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        telegram_id = str(linked_telegram.provider_id) if linked_telegram and linked_telegram.provider_id else str(user.id)

        active_client_id = None
        try:
            active_client_id = get_active_client(user).id
        except Exception:
            active_client_id = None

        binding_qs = UserTenantBinding.objects.filter(
            provider=UserTenantBinding.PROVIDER_TELEGRAM,
            provider_user_id=telegram_id,
            is_active=True,
        ).order_by("-bound_at", "-id")
        if active_client_id is not None:
            binding_qs = binding_qs.filter(tenant_id=active_client_id)
        binding = binding_qs.first()

        extra_data = linked_telegram.extra_data if linked_telegram and isinstance(linked_telegram.extra_data, dict) else {}
        first_name = str(extra_data.get("first_name") or "").strip() or user.first_name or user.username
        last_name = str(extra_data.get("last_name") or "").strip() or user.last_name
        username = str(extra_data.get("username") or "").strip() or user.username
        photo_url = extra_data.get("photo_url")

        user_data = {
            "user": {
                "telegramId": telegram_id,
                "firstName": first_name,
                "lastName": last_name,
                "username": username,
                "photoUrl": photo_url,
                "authDate": str(user.date_joined),
                "isDev": _is_dev_user(user),
                "contactId": int(binding.contact_id) if binding and binding.contact_id is not None else None,
                "tenantId": int(binding.tenant_id) if binding else (int(active_client_id) if active_client_id is not None else None),
            }
        }
        return Response(user_data)

    def post(self, request):
        """Authenticate user via Telegram"""
        from core.models import Client, MapContact, UserSocialAccount, UserTenantBinding, UserTenantRole
        from core.services.telegram_user_service import TelegramUserService

        # TODO: Verify Telegram data hash for security
        # For now, accepting Telegram auth data as-is

        telegram_data = request.data
        telegram_id = telegram_data.get('id')
        first_name = telegram_data.get('first_name', '')
        last_name = telegram_data.get('last_name', '')
        username = telegram_data.get('username', '')
        photo_url = telegram_data.get('photo_url')

        if not telegram_id:
            return Response(
                {"error": "Missing Telegram ID"},
                status=status.HTTP_400_BAD_REQUEST
            )

        telegram_id_str = str(telegram_id)
        stored_photo_url, avatar_metadata = persist_social_avatar(
            request=request,
            photo_url=photo_url,
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
            provider_id=telegram_id_str,
        )
        photo_url = stored_photo_url or photo_url
        tenant_id_raw = request.data.get("tenant_id")
        tenant_id_hint = None
        if tenant_id_raw not in (None, ""):
            try:
                tenant_id_hint = int(tenant_id_raw)
            except (TypeError, ValueError):
                return Response(
                    {"error": "Некорректный tenant_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if tenant_id_hint <= 0:
                return Response(
                    {"error": "Некорректный tenant_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        linked_social = (
            UserSocialAccount.objects.select_related("user")
            .filter(provider=UserSocialAccount.PROVIDER_TELEGRAM, provider_id=telegram_id_str)
            .first()
        )

        if linked_social:
            user = linked_social.user
            user_created = False
        else:
            # Use telegram username if available, otherwise fallback to tg_{telegram_id}
            user_username = username if username else f"tg_{telegram_id_str}"
            user, user_created = User.objects.get_or_create(
                username=user_username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f"{user_username}@telegram.local"
                }
            )

        # Update user info if it changed
        if not user_created:
            if user.first_name != first_name or user.last_name != last_name:
                user.first_name = first_name
                user.last_name = last_name
                user.save()

        # Ensure provider link points to this user.
        linked_for_user = UserSocialAccount.objects.filter(
            user=user, provider=UserSocialAccount.PROVIDER_TELEGRAM
        ).first()
        if linked_for_user and linked_for_user.provider_id != telegram_id_str:
            return Response(
                {"error": "У пользователя уже привязан другой Telegram-аккаунт"},
                status=status.HTTP_409_CONFLICT,
            )
        extra_data = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "photo_url": photo_url,
            **avatar_metadata,
        }
        if linked_for_user:
            linked_for_user.extra_data = extra_data
            linked_for_user.save(update_fields=["extra_data", "updated_at"])
        elif not linked_social:
            UserSocialAccount.objects.create(
                user=user,
                provider=UserSocialAccount.PROVIDER_TELEGRAM,
                provider_id=telegram_id_str,
                extra_data=extra_data,
            )

        # If the login came from /c/<client_id>, create/bind a CRM contact for that tenant.
        if tenant_id_hint is not None:
            existing_tenant_binding = (
                UserTenantBinding.objects.filter(
                    provider=UserTenantBinding.PROVIDER_TELEGRAM,
                    provider_user_id=telegram_id_str,
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
                    f"{first_name} {last_name}".strip()
                    or username
                    or f"Telegram {telegram_id_str}"
                )
                contact = MapContact.objects.create(name=contact_name)
                contact_id = int(contact.id)

            try:
                TelegramUserService().bind_user_to_tenant(
                    telegram_chat_id=int(telegram_id_str),
                    tenant_id=tenant_id_hint,
                    contact_id=contact_id,
                    telegram_username=(str(username or "").strip() or None),
                )
            except ValueError as exc:
                return Response(
                    {"error": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # For first-time users in regular login flow, create client tenant as before.
        if user_created and tenant_id_hint is None:
            client_slug = telegram_id_str
            client, _ = Client.objects.get_or_create(
                slug=client_slug,
                defaults={
                    'name': f"{first_name} {last_name}".strip() or username or f"User {telegram_id_str}",
                }
            )
            UserTenantRole.objects.get_or_create(
                user=user,
                client=client,
                defaults={'role': 'owner'}
            )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        user_data = {
            "user": {
                "telegramId": telegram_id,
                "firstName": first_name,
                "lastName": last_name,
                "username": username,
                "photoUrl": photo_url,
                "authDate": str(user.date_joined),
                "isDev": _is_dev_user(user)
            }
        }

        response = Response(user_data)
        set_token_cookie(response, "access_token", str(access), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)

        return response

    def put(self, request):
        """Dev mode login - auto-create/login as dev user"""
        if not settings.DEBUG:
            return Response(
                {"error": "Dev mode only available in DEBUG mode"},
                status=status.HTTP_403_FORBIDDEN
            )

        from core.models import Client, UserTenantRole

        # Get or create dev user
        user, created = User.objects.get_or_create(
            username='dev_user',
            defaults={
                'first_name': 'Dev',
                'last_name': 'User',
                'email': 'dev@example.com'
            }
        )

        # Get or create zavod client
        client, _ = Client.objects.get_or_create(
            slug='zavod',
            defaults={
                'name': 'Zavod (Dev Client)',
            }
        )

        # Link user to client if not already linked
        UserTenantRole.objects.get_or_create(
            user=user,
            client=client,
            defaults={'role': 'owner'}
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        user_data = {
            "user": {
                "telegramId": str(user.id),
                "firstName": user.first_name,
                "lastName": user.last_name,
                "username": user.username,
                "photoUrl": None,
                "authDate": str(user.date_joined),
                "isDev": True
            }
        }

        response = Response(user_data)
        set_token_cookie(response, "access_token", str(access), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)

        return response

    def delete(self, request):
        """Logout user"""
        response = Response({"success": True})
        response.delete_cookie("access_token", path="/", samesite=COOKIE_SAMESITE)
        response.delete_cookie("refresh_token", path="/", samesite=COOKIE_SAMESITE)
        return response


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request, *args, **kwargs):
        serializer = TokenObtainPairSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data

        response = Response({"access": tokens.get("access")})

        access = tokens.get("access")
        refresh = tokens.get("refresh")
        if access:
            set_token_cookie(response, "access_token", access, COOKIE_MAX_AGE)
        if refresh:
            set_token_cookie(response, "refresh_token", refresh, REFRESH_COOKIE_MAX_AGE)
        return response


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get("refresh"):
            cookie_refresh = request.COOKIES.get("refresh_token")
            if cookie_refresh:
                data["refresh"] = cookie_refresh

        serializer = TokenRefreshSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data

        response = Response({"access": tokens.get("access")})
        access = tokens.get("access")
        refresh = tokens.get("refresh")
        if access:
            set_token_cookie(response, "access_token", access, COOKIE_MAX_AGE)
        if refresh:
            set_token_cookie(response, "refresh_token", refresh, REFRESH_COOKIE_MAX_AGE)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request, *args, **kwargs):
        response = Response({"success": True})
        response.delete_cookie("access_token", path="/", samesite=COOKIE_SAMESITE)
        response.delete_cookie("refresh_token", path="/", samesite=COOKIE_SAMESITE)
        return response


class ClientInfoView(APIView):
    """Get current client info and user role"""

    def get(self, request, *args, **kwargs):
        from core.models import UserTenantRole

        client = get_active_client(request.user)

        # Get user's role for this client
        role_obj = UserTenantRole.objects.filter(
            user=request.user, client=client
        ).first()
        role = role_obj.role if role_obj else 'viewer'

        return Response({
            'client': {
                'id': client.id,
                'name': client.name,
                'slug': client.slug,
                'last_image_generation_at': client.last_image_generation_at,
                'last_video_generation_at': client.last_video_generation_at,
            },
            'role': role,
        })


class ClientSummaryView(APIView):
    def get(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        posts = Post.objects.filter(client=client)
        schedules = Schedule.objects.filter(client=client)

        platform_counts = (
            schedules.values(platform=F("social_account__platform"))
            .annotate(count=Count("id"))
            .order_by("platform")
        )
        by_platform = [dict(item) for item in platform_counts]

        summary_data = {
            "total_posts": posts.count(),
            "posts_scheduled": posts.filter(status="scheduled").count(),
            "posts_published": posts.filter(status="published").count(),
            "by_platform": by_platform,
        }

        serializer = ClientSummarySerializer(summary_data)
        return Response(serializer.data)


class GenerationEventSummaryView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        rows = (
            GenerationEvent.objects.filter(client=client)
            .values("event_type")
            .annotate(count=Count("id"))
        )
        counts = {row["event_type"]: int(row["count"] or 0) for row in rows}
        limits = {event_type: get_trial_limit(event_type) for event_type in EVENT_TYPE_LIST}
        return Response(
            {
                "counts": counts,
                "limits": limits,
                "is_trial": is_trial_client(client),
            }
        )


class ClientSettingsView(APIView):
    """
    API view for getting and updating client settings.
    Excludes 'id' and 'name' fields - they cannot be edited.
    """

    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request):
        """Get current client settings"""
        client = get_active_client(request.user)
        serializer = ClientSettingsSerializer(client)
        return Response(serializer.data)

    def patch(self, request):
        """Update client settings (excluding id and name)"""
        client = get_active_client(request.user)
        serializer = ClientSettingsSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ClientExpertBooksView(APIView):
    """AI-powered expert book recommendations for active client audience."""

    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        pains = request.data.get("pains") or client.pains or ""
        desires = request.data.get("desires") or client.desires or ""
        avatar = request.data.get("avatar") or client.avatar or ""
        language = request.data.get("language") or "ru"

        if not (pains or desires):
            return Response(
                {
                    "success": False,
                    "error": "Укажите хотя бы одну боль или желание аудитории",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_BOOK_SEARCH)
        if limit_response:
            return limit_response

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        result = generator.generate_book_recommendations(
            pains=pains,
            desires=desires,
            avatar=avatar,
            brand=client.name,
            language=language,
        )

        saved = False
        if result.get("success"):
            record_generation_event(
                client,
                GenerationEvent.EVENT_BOOK_SEARCH,
                meta={"language": language},
            )
            text_value = str(result.get("text") or "").strip()
            if not text_value:
                books_list = result.get("books")
                if isinstance(books_list, list):
                    lines = []
                    for idx, item in enumerate(books_list, start=1):
                        if isinstance(item, dict):
                            title = str(item.get("title") or "").strip()
                            author = str(item.get("author") or "").strip()
                            reason = str(item.get("reason") or "").strip()
                        else:
                            title = str(item or "").strip()
                            author = ""
                            reason = ""
                        if not title:
                            continue
                        suffix = f" — {author}" if author else ""
                        reason_text = f": {reason}" if reason else ""
                        lines.append(f"{idx}. {title}{suffix}{reason_text}")
                    text_value = "\n".join(lines).strip()
            if text_value:
                client.expert_books = text_value
                client.save(update_fields=["expert_books"])
                saved = True
                result["text"] = text_value
        result["saved"] = saved

        http_status = status.HTTP_200_OK if result.get("success") else status.HTTP_502_BAD_GATEWAY
        return Response(result, status=http_status)


class ClientBookSemanticsView(APIView):
    """AI-powered project semantics generation based on expert books."""

    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        books_text = request.data.get("expert_books") or client.expert_books or ""
        books_text = str(books_text or "").strip()
        language = request.data.get("language") or "ru"

        if not books_text:
            return Response(
                {"success": False, "error": "Укажите список книг экспертов"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_BOOK_SEMANTICS)
        if limit_response:
            return limit_response

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        result = generator.generate_semantic_groups_from_books(
            books_text=books_text,
            niche=client.niche,
            audience=client.avatar,
            product=client.product_service,
            language=language,
        )

        if not result.get("success"):
            return Response(
                {"success": False, "error": str(result.get("error") or "AI error")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        groups = result.get("groups") or []
        if not isinstance(groups, list) or not groups:
            return Response(
                {"success": False, "error": "AI вернул пустой список смысловых групп"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        created_groups = []
        whitespace_re = re.compile(r"\s+")

        def normalize_source_books(value):
            if value is None:
                return []
            if isinstance(value, list):
                raw_items = value
            elif isinstance(value, str):
                value = value.strip()
                if not value:
                    return []
                if "\n" in value:
                    raw_items = [item for item in value.splitlines() if item.strip()]
                elif ";" in value and "," not in value:
                    raw_items = [item for item in value.split(";") if str(item).strip()]
                else:
                    raw_items = [value]
            else:
                raw_items = [value]

            cleaned = []
            for item in raw_items:
                text_value = ""
                if isinstance(item, dict):
                    title = str(item.get("title") or item.get("name") or "").strip()
                    author = str(item.get("author") or "").strip()
                    if title and author:
                        text_value = f"{title} — {author}"
                    else:
                        text_value = title or author
                else:
                    text_value = str(item or "").strip()
                text_value = whitespace_re.sub(" ", text_value)
                if text_value:
                    cleaned.append(text_value)

            seen = set()
            unique = []
            for item in cleaned:
                key = item.lower()
                if key in seen:
                    continue
                seen.add(key)
                unique.append(item)
            return unique

        with transaction.atomic():
            SemanticGroup.objects.filter(client=client, source="ai").exclude(status="archived").update(
                status="archived"
            )
            for item in groups:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                scope = str(item.get("scope") or "normal").strip().lower() or "normal"
                if scope not in {"narrow", "normal", "wide"}:
                    scope = "normal"
                expected_clusters = item.get("expected_clusters")
                if expected_clusters is not None:
                    try:
                        expected_clusters = int(expected_clusters)
                    except (TypeError, ValueError):
                        expected_clusters = None
                source_books_raw = item.get("source_books") or item.get("sources") or item.get("books")
                source_books = normalize_source_books(source_books_raw)
                created_groups.append(
                    SemanticGroup(
                        client=client,
                        name=name,
                        description=str(item.get("description") or "").strip(),
                        scope=scope,
                        expected_clusters=expected_clusters,
                        source_books=source_books,
                        source="ai",
                    )
                )
            if created_groups:
                SemanticGroup.objects.bulk_create(created_groups)

        record_generation_event(
            client,
            GenerationEvent.EVENT_BOOK_SEMANTICS,
            meta={"source": "expert_books", "groups_count": len(created_groups)},
        )

        return Response(
            {
                "success": True,
                "saved": True,
                "groups_count": len(created_groups),
            },
            status=status.HTTP_200_OK,
        )
