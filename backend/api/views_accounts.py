from __future__ import annotations

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
from core.models import GenerationEvent, Post, ProjectSemanticSet, Schedule

from .authentication import CookieJWTAuthentication
from .permissions import IsTenantMember, IsTenantOwnerOrEditor
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

        user_data = {
            "user": {
                "telegramId": str(user.id),
                "firstName": user.first_name or user.username,
                "lastName": user.last_name,
                "username": user.username,
                "photoUrl": None,
                "authDate": str(user.date_joined),
                "isDev": _is_dev_user(user)
            }
        }
        return Response(user_data)

    def post(self, request):
        """Authenticate user via Telegram"""
        from core.models import Client, UserTenantRole

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

        # Get or create user based on telegram username or ID
        # Use telegram username if available, otherwise fallback to tg_{telegram_id}
        user_username = username if username else f"tg_{telegram_id}"
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

        # Get or create client for this user (using telegram_id as slug)
        client_slug = str(telegram_id)
        client, client_created = Client.objects.get_or_create(
            slug=client_slug,
            defaults={
                'name': f"{first_name} {last_name}".strip() or username or f"User {telegram_id}",
            }
        )

        # Link user to their client
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

        semantic_set = ProjectSemanticSet.objects.create(
            client=client,
            source=ProjectSemanticSet.SOURCE_EXPERT_BOOKS,
            status="generating",
            books_text=books_text,
        )

        result = generator.generate_project_semantics_from_books(
            books_text=books_text,
            brand=client.name,
            language=language,
        )

        if not result.get("success"):
            semantic_set.status = "failed"
            semantic_set.error_log = str(result.get("error") or "AI error")
            semantic_set.prompt_used = str(result.get("prompt_used") or "")
            semantic_set.ai_model = str(generator.model or "")
            semantic_set.raw_response = result.get("raw_response") or {}
            semantic_set.save(
                update_fields=[
                    "status",
                    "error_log",
                    "prompt_used",
                    "ai_model",
                    "raw_response",
                    "updated_at",
                ]
            )
            return Response(
                {"success": False, "error": semantic_set.error_log},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        keyword_groups = result.get("groups") or {}
        keywords_list = result.get("keywords") or []

        semantic_set.status = "completed"
        semantic_set.keyword_groups = keyword_groups
        semantic_set.keywords_list = keywords_list
        semantic_set.prompt_used = str(result.get("prompt_used") or "")
        semantic_set.ai_model = str(generator.model or "")
        semantic_set.raw_response = result.get("raw_response") or {}
        semantic_set.error_log = ""
        semantic_set.save(
            update_fields=[
                "status",
                "keyword_groups",
                "keywords_list",
                "prompt_used",
                "ai_model",
                "raw_response",
                "error_log",
                "updated_at",
            ]
        )

        record_generation_event(
            client,
            GenerationEvent.EVENT_BOOK_SEMANTICS,
            meta={"source": "expert_books", "keywords_count": len(keywords_list)},
        )

        return Response(
            {
                "success": True,
                "saved": True,
                "semantic_set_id": semantic_set.id,
                "keywords_count": len(keywords_list),
                "groups_count": len(keyword_groups),
            },
            status=status.HTTP_200_OK,
        )
