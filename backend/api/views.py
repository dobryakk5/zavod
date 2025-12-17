from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode

import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from rest_framework import generics, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from core.audience_profiles import merge_audience_profiles
from core.ai_generator import AIContentGenerator
from core.models import (
    Client,
    ContentTemplate,
    Post,
    PostImage,
    PostVideo,
    PostTone,
    PostType,
    Schedule,
    SocialAccount,
    Story,
    Topic,
    TrendItem,
    ChannelAnalysis,
    SEOKeywordSet,
    VkIntegration,
)
from core import tasks
from core.telegram_client import normalize_telegram_channel_identifier
from core.social_accounts import sync_client_default_telegram_account
from core.system_settings import get_image_generation_model, get_image_generation_method

from .authentication import CookieJWTAuthentication
from .permissions import CanGenerateVideo, IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ChannelAnalysisDetailSerializer,
    ChannelAnalysisListSerializer,
    ClientSettingsSerializer,
    ClientSummarySerializer,
    ContentTemplateSerializer,
    PostDetailSerializer,
    PostSerializer,
    PostToneSerializer,
    PostTypeSerializer,
    ScheduleSerializer,
    SocialAccountSerializer,
    StoryDetailSerializer,
    StorySerializer,
    TopicDetailSerializer,
    TopicSerializer,
    TrendItemDetailSerializer,
    TrendItemSerializer,
    VkIntegrationSerializer,
    SEOKeywordSetSerializer,
)
from .utils import get_active_client

User = get_user_model()

COOKIE_SECURE = not settings.DEBUG
COOKIE_SAMESITE = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
COOKIE_MAX_AGE = int(getattr(settings, "JWT_COOKIE_MAX_AGE", 60 * 60))  # 1 hour for access token
REFRESH_COOKIE_MAX_AGE = int(getattr(settings, "JWT_REFRESH_COOKIE_MAX_AGE", 60 * 60 * 24 * 7))
MAX_WEEKLY_POSTS = 21
VK_SCOPE = "wall,photos,groups"
VK_TIMEOUT = 15
MEDIA_GENERATION_COOLDOWN = timedelta(hours=1)

logger = logging.getLogger(__name__)


def _cooldown_remaining(last_triggered_at):
    """Return remaining cooldown timedelta for media generation."""
    if not last_triggered_at:
        return timedelta(0)
    cooldown_ends_at = last_triggered_at + MEDIA_GENERATION_COOLDOWN
    remaining = cooldown_ends_at - timezone.now()
    if remaining.total_seconds() <= 0:
        return timedelta(0)
    return remaining


def _format_cooldown_message(kind: str, remaining: timedelta) -> str:
    """Return user-friendly cooldown message in Russian."""
    total_seconds = int(max(0, remaining.total_seconds()))
    minutes, seconds = divmod(total_seconds, 60)
    if minutes > 0:
        return f"Генерация {kind} будет доступна через {minutes} мин {seconds:02d} сек"
    return f"Генерация {kind} будет доступна через {seconds} сек"


class VkApiError(Exception):
    """Raised when VK API responds with an error."""

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


def _missing_vk_settings() -> list[str]:
    missing: list[str] = []
    if not getattr(settings, "VK_CLIENT_ID", ""):
        missing.append("VK_CLIENT_ID")
    if not getattr(settings, "VK_CLIENT_SECRET", ""):
        missing.append("VK_CLIENT_SECRET")
    if not getattr(settings, "VK_REDIRECT_URI", ""):
        missing.append("VK_REDIRECT_URI")
    return missing


def _popup_response(message: str, *, success: bool = True, title: str = "VK интеграция"):
    """
    Returns a tiny HTML page that notifies the user and attempts to close the popup.
    """
    status_value = "success" if success else "error"
    html = f"""
<!DOCTYPE html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <title>{title}</title>
    <style>
      body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding: 24px; }}
    </style>
  </head>
  <body>
    <p>{message}</p>
    <script>
      try {{
        window.opener && window.opener.postMessage({{ type: 'vk-connect', status: '{status_value}' }}, '*');
      }} catch (err) {{}}
      setTimeout(function () {{ window.close(); }}, 1200);
    </script>
  </body>
</html>
    """.strip()
    return HttpResponse(html)


def _vk_api_request(method: str, *, access_token: str, params: dict | None = None,
                    http_method: str = "get"):
    url = f"https://api.vk.com/method/{method}"
    payload = dict(params or {})
    payload.setdefault("access_token", access_token)
    payload.setdefault("v", getattr(settings, "VK_API_VERSION", "5.131"))

    if http_method.lower() == "post":
        response = requests.post(url, data=payload, timeout=VK_TIMEOUT)
    else:
        response = requests.get(url, params=payload, timeout=VK_TIMEOUT)

    data = response.json()
    if "error" in data:
        raise VkApiError(data["error"].get("error_msg", "VK API error"), data["error"])
    return data.get("response")


def _normalize_group_identifier(value: str) -> str:
    slug = value.strip()
    slug = slug.replace("https://vk.com/", "").replace("http://vk.com/", "")
    slug = slug.replace("vk.com/", "")
    slug = slug.lstrip("@")
    for prefix in ("public", "club"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
    if slug.startswith("-"):
        slug = slug[1:]
    return slug


def _fetch_admin_groups(access_token: str, user_id: int | None) -> list[dict]:
    params = {
        "extended": 1,
        "filter": "admin",
        "fields": "screen_name,type,members_count",
    }
    if user_id:
        params["user_id"] = user_id
    response = _vk_api_request("groups.get", access_token=access_token, params=params)
    if isinstance(response, dict):
        items = response.get("items", [])
    else:
        items = response or []
    return [item for item in items if item.get("is_admin")]


def _fetch_single_group(access_token: str, identifier: str) -> dict:
    response = _vk_api_request(
        "groups.getById",
        access_token=access_token,
        params={"group_id": identifier, "fields": "is_admin,screen_name,type,members_count"},
    )
    if not response:
        raise VkApiError("Группа не найдена")
    group = response[0]
    if not group.get("is_admin"):
        raise VkApiError("У вас нет прав администратора этой группы")
    return group


def _save_vk_integration(client: Client, owner, group_data: dict, access_token: str, user_id: int | None):
    group_id = int(group_data.get("id"))
    defaults = {
        "owner": owner,
        "group_name": group_data.get("name", ""),
        "screen_name": group_data.get("screen_name", ""),
        "access_token": access_token,
        "user_id": user_id,
        "status": VkIntegration.STATUS_ACTIVE,
        "extra": {
            "type": group_data.get("type"),
            "members_count": group_data.get("members_count"),
        },
    }
    VkIntegration.objects.update_or_create(
        client=client,
        group_id=group_id,
        defaults=defaults,
    )


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
                "isDev": getattr(user, 'is_dev_user', False)
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
                "isDev": False
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


class PostsListView(generics.ListAPIView):
    serializer_class = PostSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = (
            Post.objects.filter(client=client)
            .prefetch_related("schedules__social_account")
            .order_by("-created_at")
        )

        status_param = self.request.query_params.get("status")
        platform_param = self.request.query_params.get("platform")

        if status_param:
            queryset = queryset.filter(status=status_param)
        if platform_param:
            queryset = queryset.filter(schedules__social_account__platform=platform_param)

        return queryset.distinct()


class ScheduleListView(generics.ListAPIView):
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = (
            Schedule.objects.filter(client=client)
            .select_related("post", "social_account")
            .order_by("scheduled_at")
        )
        post_id = self.request.query_params.get("post")
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        return queryset


# ============================================================================
# VIEWSETS FOR CRUD OPERATIONS
# ============================================================================


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Post CRUD operations and generation actions.
    Reuses existing functions from core.tasks and core.views.
    """

    permission_classes = [IsTenantMember]

    def get_permissions(self):
        """Different permissions for different actions"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_serializer_class(self):
        """Use detailed serializer for retrieve, create, update"""
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return PostDetailSerializer
        return PostSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return Post.objects.filter(client=client).order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set client when creating post"""
        client = get_active_client(self.request.user)
        serializer.save(client=client, created_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_image(self, request, pk=None):
        """
        Generate image for post using AI.
        Uses image_generation_method from SystemSetting if no model specified.
        Model choices: openrouter, veo_photo, giga_photo
        """
        post = self.get_object()
        client = post.client
        remaining = _cooldown_remaining(client.last_image_generation_at)
        if remaining:
            cooldown_ends_at = client.last_image_generation_at + MEDIA_GENERATION_COOLDOWN
            return Response(
                {
                    'success': False,
                    'error': _format_cooldown_message('изображения', remaining),
                    'cooldown_seconds': int(remaining.total_seconds()),
                    'cooldown_ends_at': cooldown_ends_at,
                    'cooldown_type': 'image',
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        model_param = (request.data.get('model') or '').lower()

        # If no model specified, use the method from SystemSetting
        if not model_param:
            model = get_image_generation_method()
        else:
            alias_map = {
                'nanobanana': 'openrouter',
                'pollinations': 'openrouter',
                'huggingface': 'openrouter',
                'flux2': 'openrouter',
                'sora_images': 'veo_photo',
                'telegram_bot': 'veo_photo',
                'veo': 'veo_photo',
                'giga': 'giga_photo',
            }
            model = alias_map.get(model_param, model_param)

        allowed_models = {'openrouter', 'veo_photo', 'giga_photo'}
        if model not in allowed_models:
            return Response(
                {
                    'success': False,
                    'error': f'Unknown image model "{model_param}"'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call existing Celery task
        task = tasks.generate_image_for_post.delay(post.id, model=model)
        client.last_image_generation_at = timezone.now()
        client.save(update_fields=["last_image_generation_at"])

        model_names = {
            'openrouter': f"OpenRouter ({get_image_generation_model()})",
            'veo_photo': 'VEO (Telegram)',
        }

        return Response({
            'success': True,
            'message': f'Image generation started: {model_names.get(model, model)}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[CanGenerateVideo, IsTenantOwnerOrEditor])
    def generate_video(self, request, pk=None):
        """
        Generate video from post image.
        Only available in DEBUG mode or for zavod client.
        """
        post = self.get_object()
        client = post.client
        remaining = _cooldown_remaining(client.last_video_generation_at)
        if remaining:
            cooldown_ends_at = client.last_video_generation_at + MEDIA_GENERATION_COOLDOWN
            return Response({
                'success': False,
                'error': _format_cooldown_message('видео', remaining),
                'cooldown_seconds': int(remaining.total_seconds()),
                'cooldown_ends_at': cooldown_ends_at,
                'cooldown_type': 'video',
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        method = (request.data.get('method') or 'wan').lower()
        allowed_methods = {'wan', 'veo'}
        if method not in allowed_methods:
            return Response({
                'success': False,
                'error': f'Unknown video method "{method}"'
            }, status=status.HTTP_400_BAD_REQUEST)

        source = (request.data.get('source') or 'image').lower()
        allowed_sources = {'image', 'text'}
        if source not in allowed_sources:
            return Response({
                'success': False,
                'error': f'Unknown video source "{source}"'
            }, status=status.HTTP_400_BAD_REQUEST)

        if source == 'image' and not post.images.exists():
            return Response({
                'success': False,
                'error': 'Post must have an image before generating video'
            }, status=status.HTTP_400_BAD_REQUEST)

        if source == 'text' and not post.text:
            return Response({
                'success': False,
                'error': 'Post must have text before generating text-based video'
            }, status=status.HTTP_400_BAD_REQUEST)

        if source == 'text' and method != 'veo':
            return Response({
                'success': False,
                'error': 'Text-based video currently supported only via VEO'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Call existing Celery task
        task = tasks.generate_video_from_image.delay(post.id, method=method, source=source)
        client.last_video_generation_at = timezone.now()
        client.save(update_fields=["last_video_generation_at"])

        return Response({
            'success': True,
            'message': f'Video generation started ({method}/{source})',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def regenerate_text(self, request, pk=None):
        """Regenerate post text using AI"""
        post = self.get_object()

        # Call existing Celery task
        task = tasks.regenerate_post_text.delay(post.id)

        return Response({
            'success': True,
            'message': 'Text regeneration started',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def quick_publish(self, request, pk=None):
        """
        Quick publish post to a social account without creating schedule.
        Requires social_account_id in request body.
        """
        post = self.get_object()
        social_account_id = request.data.get('social_account_id')

        if not social_account_id:
            return Response({
                'success': False,
                'error': 'social_account_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get social account and verify it belongs to same client
        social_account = get_object_or_404(SocialAccount, id=social_account_id)

        if social_account.client != post.client:
            return Response({
                'success': False,
                'error': 'Social account does not belong to post client'
            }, status=status.HTTP_403_FORBIDDEN)

        # Create a schedule and publish immediately
        from django.utils import timezone
        schedule = Schedule.objects.create(
            client=post.client,
            post=post,
            social_account=social_account,
            scheduled_at=timezone.now(),
            status='pending'
        )

        # Call existing Celery task
        task = tasks.publish_schedule.delay(schedule.id)

        return Response({
            'success': True,
            'message': 'Publishing started',
            'schedule_id': schedule.id,
            'task_id': task.id
        })

    @action(
        detail=False,
        methods=['post'],
        url_path='plan-weekly',
        permission_classes=[IsTenantOwnerOrEditor]
    )
    def plan_weekly(self, request):
        """Запустить генерацию постов на следующую неделю по выбранному шаблону."""

        client = get_active_client(request.user)
        template_id = request.data.get('template_id')
        posts_per_week = request.data.get('posts_per_week')
        social_account_id = request.data.get('social_account_id')

        try:
            template_id_int = int(template_id)
        except (TypeError, ValueError):
            return Response({'error': 'Укажите корректный шаблон'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            posts_count = int(posts_per_week)
        except (TypeError, ValueError):
            return Response({'error': 'Некорректное количество постов'}, status=status.HTTP_400_BAD_REQUEST)

        if posts_count <= 0 or posts_count > MAX_WEEKLY_POSTS:
            return Response(
                {'error': f'Количество постов должно быть от 1 до {MAX_WEEKLY_POSTS}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            template = ContentTemplate.get_for_client_or_system(client, template_id_int)
        except ContentTemplate.DoesNotExist:
            return Response({'error': 'Шаблон недоступен'}, status=status.HTTP_404_NOT_FOUND)

        social_account_id_int = None
        if social_account_id is not None:
            try:
                social_account_id_int = int(social_account_id)
            except (TypeError, ValueError):
                return Response({'error': 'Некорректный ID соц. аккаунта'}, status=status.HTTP_400_BAD_REQUEST)

            if not SocialAccount.objects.filter(id=social_account_id_int, client=client).exists():
                return Response({'error': 'Соц. аккаунт не найден'}, status=status.HTTP_404_NOT_FOUND)

        task = tasks.generate_weekly_posts_from_template.delay(
            client.id,
            template.id,
            posts_count,
            request.user.id if request.user and request.user.is_authenticated else None,
            social_account_id_int,
        )

        return Response({
            'success': True,
            'message': f'Запущена генерация {posts_count} постов по шаблону «{template.name}»',
            'task_id': task.id
        })

    @action(detail=True, methods=['delete'], permission_classes=[IsTenantOwnerOrEditor])
    def delete_image(self, request, pk=None):
        """
        Delete a specific image from the post.
        Requires image_id in query parameters.
        """
        post = self.get_object()
        image_id = request.query_params.get('image_id')

        if not image_id:
            return Response({
                'success': False,
                'error': 'image_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            image_id_int = int(image_id)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': 'image_id must be an integer'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Find the image and verify it belongs to this post
        try:
            image = PostImage.objects.get(id=image_id_int, post=post)
        except PostImage.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Image not found or does not belong to this post'
            }, status=status.HTTP_404_NOT_FOUND)

        # Delete the image file and database record
        if image.image:
            # Delete the file from storage
            image.image.delete(save=False)

        # Delete the database record
        image.delete()

        return Response({
            'success': True,
            'message': 'Image deleted successfully'
        })

    @action(detail=True, methods=['delete'], permission_classes=[IsTenantOwnerOrEditor])
    def delete_video(self, request, pk=None):
        """
        Delete a specific video from the post.
        Requires video_id in query parameters.
        """
        post = self.get_object()
        video_id = request.query_params.get('video_id')

        if not video_id:
            return Response({
                'success': False,
                'error': 'video_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            video_id_int = int(video_id)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': 'video_id must be an integer'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Find the video and verify it belongs to this post
        try:
            video = PostVideo.objects.get(id=video_id_int, post=post)
        except PostVideo.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Video not found or does not belong to this post'
            }, status=status.HTTP_404_NOT_FOUND)

        # Delete the video file and database record
        if video.video:
            # Delete the file from storage
            video.video.delete(save=False)

        # Delete the database record
        video.delete()

        return Response({
            'success': True,
            'message': 'Video deleted successfully'
        })


class TopicViewSet(viewsets.ModelViewSet):
    """ViewSet for Topic CRUD operations and content discovery"""

    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TopicDetailSerializer
        return TopicSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return Topic.objects.filter(client=client).order_by('-created_at')

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def discover_content(self, request, pk=None):
        """Discover new content (trends) for this topic from enabled sources"""
        topic = self.get_object()

        # Call existing Celery task
        task = tasks.discover_content_for_topic.delay(topic.id)

        return Response({
            'success': True,
            'message': f'Content discovery started for topic: {topic.name}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_posts(self, request, pk=None):
        """Generate posts from all unused trends for this topic"""
        topic = self.get_object()

        # Call existing Celery task
        task = tasks.generate_posts_for_topic.delay(topic.id)

        return Response({
            'success': True,
            'message': f'Post generation started for topic: {topic.name}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_seo(self, request, pk=None):
        """Generate SEO keywords for the topic's client"""
        topic = self.get_object()

        # Trigger client-level SEO generation (deduplicated per client)
        task = tasks.generate_seo_keywords_for_client.delay(topic.client_id)

        return Response({
            'success': True,
            'message': f'SEO keyword generation started for client: {topic.client.name}',
            'task_id': task.id
        })


class TrendItemViewSet(viewsets.ModelViewSet):
    """ViewSet for TrendItem operations"""

    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.action in ['destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TrendItemDetailSerializer
        return TrendItemSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = TrendItem.objects.filter(client=client).order_by('-discovered_at')

        # Filter by topic if provided
        topic_id = self.request.query_params.get('topic')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)

        # Filter unused trends
        unused_only = self.request.query_params.get('unused')
        if unused_only == 'true':
            queryset = queryset.filter(used_for_post__isnull=True)

        return queryset

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_post(self, request, pk=None):
        """Generate a single post from this trend"""
        trend = self.get_object()

        # Call existing Celery task
        task = tasks.generate_post_from_trend.delay(trend.id)

        return Response({
            'success': True,
            'message': f'Post generation started from trend: {trend.title}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_story(self, request, pk=None):
        """Generate a story (mini-series) from this trend"""
        trend = self.get_object()
        episode_count = request.data.get('episode_count', 3)

        # Call existing Celery task
        task = tasks.generate_story_from_trend.delay(trend.id, episode_count)

        return Response({
            'success': True,
            'message': f'Story generation started with {episode_count} episodes',
            'task_id': task.id
        })


class StoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Story CRUD operations"""

    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_serializer_class(self):
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return StoryDetailSerializer
        return StorySerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return Story.objects.filter(client=client).order_by('-created_at')

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_posts(self, request, pk=None):
        """Generate posts from story episodes"""
        story = self.get_object()

        # Call existing Celery task
        task = tasks.generate_posts_from_story.delay(story.id)

        return Response({
            'success': True,
            'message': f'Generating posts from story: {story.title}',
            'task_id': task.id
        })


class ContentTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ContentTemplate CRUD operations.
    Basic fields (type, tone, length, language) are read-only in serializer.
    """

    permission_classes = [IsTenantMember]

    serializer_class = ContentTemplateSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = ContentTemplate.objects.for_client(client).select_related("client").order_by('-created_at')
        if getattr(self, "action", None) in ['update', 'partial_update', 'destroy']:
            return queryset.filter(client=client)
        return queryset

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)


class ScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for Schedule CRUD operations"""

    permission_classes = [IsTenantMember]
    serializer_class = ScheduleSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = Schedule.objects.filter(client=client).select_related(
            'post', 'social_account'
        ).order_by('scheduled_at')
        post_id = self.request.query_params.get("post")
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["client"] = get_active_client(self.request.user)
        return context

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def publish_now(self, request, pk=None):
        """Publish this schedule immediately"""
        schedule = self.get_object()

        # Call existing Celery task
        task = tasks.publish_schedule.delay(schedule.id)

        return Response({
            'success': True,
            'message': 'Publishing started',
            'task_id': task.id
        })


class SocialAccountViewSet(viewsets.ModelViewSet):
    """ViewSet for SocialAccount CRUD operations"""

    permission_classes = [IsTenantOwnerOrEditor]
    serializer_class = SocialAccountSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        sync_client_default_telegram_account(client)
        return SocialAccount.objects.filter(client=client).order_by('platform', 'name')

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)


class VkIntegrationViewSet(mixins.ListModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """List or delete VK integrations for the active client."""

    permission_classes = [IsTenantOwnerOrEditor]
    serializer_class = VkIntegrationSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            VkIntegration.objects.filter(client=client)
            .select_related("owner")
            .order_by("-updated_at")
        )


class VkConnectView(APIView):
    """Starts VK OAuth flow and redirects user to VK."""

    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request):
        # Ensure current user has an active client (raises if not)
        get_active_client(request.user)

        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK OAuth не настроен. Укажите переменные "
                f"{', '.join(missing)} на сервере."
            )
            return _popup_response(msg, success=False)

        state = secrets.token_urlsafe(16)
        request.session["vk_oauth_state"] = state
        target_group = request.query_params.get("group_id")
        if target_group:
            request.session["vk_target_group"] = target_group
        request.session.modified = True

        params = {
            "client_id": settings.VK_CLIENT_ID,
            "display": "page",
            "redirect_uri": settings.VK_REDIRECT_URI,
            "scope": VK_SCOPE,
            "response_type": "code",
            "state": state,
            "v": getattr(settings, "VK_API_VERSION", "5.131"),
        }
        auth_url = "https://oauth.vk.com/authorize?" + urlencode(params)
        return redirect(auth_url)


class VkCallbackView(APIView):
    """Handles VK OAuth callback, saves integrations and closes the popup."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK OAuth не настроен. Обратитесь к администратору: "
                f"{', '.join(missing)}"
            )
            return _popup_response(msg, success=False)

        provided_state = request.GET.get("state")
        saved_state = request.session.pop("vk_oauth_state", None)
        if not provided_state or provided_state != saved_state:
            return _popup_response("Некорректный ответ авторизации VK", success=False)

        code = request.GET.get("code")
        if not code:
            error_description = request.GET.get("error_description") or "VK не вернул код авторизации"
            return _popup_response(error_description, success=False)

        try:
            client = get_active_client(request.user)
        except PermissionDenied:
            return _popup_response("Пользователь не привязан к клиенту", success=False)

        token_url = "https://oauth.vk.com/access_token"
        params = {
            "client_id": settings.VK_CLIENT_ID,
            "client_secret": settings.VK_CLIENT_SECRET,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "code": code,
        }
        try:
            token_response = requests.get(token_url, params=params, timeout=VK_TIMEOUT)
            token_data = token_response.json()
        except requests.RequestException as exc:
            logger.exception("VK token exchange failed: %s", exc)
            return _popup_response("Не удалось связаться с VK. Попробуйте позже.", success=False)

        if "error" in token_data:
            message = token_data.get("error_description") or token_data.get("error") or "Ошибка VK OAuth"
            return _popup_response(f"Ошибка VK OAuth: {message}", success=False)

        access_token = token_data.get("access_token")
        user_id = token_data.get("user_id")
        if not access_token:
            return _popup_response("VK не вернул токен доступа", success=False)

        target_group = request.GET.get("group_id") or request.session.pop("vk_target_group", None)
        groups: list[dict]
        try:
            if target_group:
                identifier = _normalize_group_identifier(str(target_group))
                groups = [_fetch_single_group(access_token, identifier)]
            else:
                groups = _fetch_admin_groups(access_token, user_id)
        except VkApiError as exc:
            logger.warning("VK group fetch error: %s", exc)
            return _popup_response(str(exc), success=False)
        except requests.RequestException as exc:
            logger.exception("VK group fetch failed: %s", exc)
            return _popup_response("Не удалось получить список групп VK", success=False)

        if not groups:
            return _popup_response("VK не нашёл групп, где вы администратор.", success=False)

        for group in groups:
            _save_vk_integration(client, request.user, group, access_token, user_id)

        message = "Группа успешно подключена." if len(groups) == 1 else f"Подключено групп: {len(groups)}."
        return _popup_response(f"{message} Это окно можно закрыть.")


class VkPublishView(APIView):
    """Publishes a post with optional images to VK."""

    permission_classes = [IsTenantOwnerOrEditor]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        client = get_active_client(request.user)

        integration_id = request.data.get("integration_id")
        if not integration_id:
            return Response({"success": False, "error": "Не указана интеграция VK"}, status=status.HTTP_400_BAD_REQUEST)

        integration = get_object_or_404(VkIntegration, id=integration_id, client=client)
        message = (request.data.get("message") or "").strip()
        images = request.FILES.getlist("images")

        if not message and not images:
            return Response(
                {"success": False, "error": "Добавьте текст или изображение для публикации"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            attachments = self._upload_images(integration, images) if images else []
            params = {
                "owner_id": -abs(int(integration.group_id)),
                "from_group": 1,
                "message": message,
            }
            if attachments:
                params["attachments"] = ",".join(attachments)
            vk_response = _vk_api_request(
                "wall.post",
                access_token=integration.access_token,
                params=params,
                http_method="post",
            )
        except (VkApiError, ValueError) as exc:
            logger.warning("VK publish error: %s", exc)
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except requests.RequestException as exc:
            logger.exception("VK publish request failed: %s", exc)
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": "Не удалось отправить данные в VK"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        integration.status = VkIntegration.STATUS_ACTIVE
        integration.last_published_at = timezone.now()
        integration.save(update_fields=["status", "last_published_at"])

        return Response({"success": True, "vk_response": vk_response})

    def _upload_images(self, integration: VkIntegration, files):
        attachments: list[str] = []
        for upload_file in files:
            server_info = _vk_api_request(
                "photos.getWallUploadServer",
                access_token=integration.access_token,
                params={"group_id": integration.group_id},
            )
            upload_url = server_info.get("upload_url")
            if not upload_url:
                raise VkApiError("VK не вернул адрес загрузки изображений")

            upload_file.seek(0)
            try:
                upload_response = requests.post(
                    upload_url,
                    files={"photo": (upload_file.name, upload_file.read(), upload_file.content_type or "image/jpeg")},
                    timeout=VK_TIMEOUT,
                )
                upload_data = upload_response.json()
            except requests.RequestException as exc:
                raise VkApiError("Не удалось загрузить изображение в VK") from exc
            except ValueError as exc:
                raise VkApiError("VK вернул некорректный ответ при загрузке изображения") from exc

            save_response = _vk_api_request(
                "photos.saveWallPhoto",
                access_token=integration.access_token,
                params={
                    "group_id": integration.group_id,
                    "photo": upload_data.get("photo"),
                    "server": upload_data.get("server"),
                    "hash": upload_data.get("hash"),
                },
                http_method="post",
            )
            for item in save_response or []:
                attachments.append(f"photo{item['owner_id']}_{item['id']}")
        return attachments


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


class PostTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for PostType (справочник типов постов)"""

    permission_classes = [IsTenantMember]
    serializer_class = PostTypeSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        # Возвращаем системные типы (client=None) + типы конкретного клиента
        return PostType.objects.filter(
            Q(client__isnull=True) | Q(client=client)
        ).order_by("label")

    def perform_create(self, serializer):
        # Новые типы создаются как системные (доступны всем клиентам)
        serializer.save(client=None)


class PostToneViewSet(viewsets.ModelViewSet):
    """ViewSet for PostTone (справочник тонов постов)"""

    permission_classes = [IsTenantMember]
    serializer_class = PostToneSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        # Возвращаем системные тоны (client=None) + тоны конкретного клиента
        return PostTone.objects.filter(
            Q(client__isnull=True) | Q(client=client)
        ).order_by("label")

    def perform_create(self, serializer):
        # Новые тоны создаются как системные (доступны всем клиентам)
        serializer.save(client=None)


class TgChannelView(APIView):
    """
    Unified endpoint for Telegram channel operations:
    - analyze: Start channel analysis
    - status: Get analysis status
    - validate: Validate channel URL
    
    Usage:
    POST /tg_channel/ with {"action": "analyze", "channel_url": "...", "channel_type": "..."}
    GET /tg_channel/ with {"action": "status", "task_id": "..."}
    POST /tg_channel/ with {"action": "validate", "channel_url": "...", "channel_type": "..."}
    """
    permission_classes = [IsAuthenticated]
    CHANNEL_TYPES = {"telegram", "instagram", "youtube", "vkontakte"}
    SUPPORTED_TYPES = {"telegram"}

    def post(self, request):
        """Handle POST requests for analyze and validate actions"""
        action = request.data.get('action')
        
        if action == 'analyze':
            return self._analyze_channel(request)
        elif action == 'validate':
            return self._validate_channel(request)
        else:
            return Response({
                'success': False,
                'error': f'Unknown action: {action}'
            }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """Handle GET requests for status action"""
        action = request.GET.get('action')
        task_id = request.GET.get('task_id')
        
        if action == 'status' and task_id:
            # For GET requests, we need to pass task_id in query params
            # Create a mock request data object using setattr
            setattr(request, '_data', {'action': 'status', 'task_id': task_id})
            return self._get_analysis_status(request)
        else:
            return Response({
                'success': False,
                'error': f'Unknown action: {action}'
            }, status=status.HTTP_400_BAD_REQUEST)

    def _normalize_channel_type(self, value):
        """Return normalized channel type if valid."""
        if not value:
            return ""
        normalized = str(value).strip().lower()
        return normalized if normalized in self.CHANNEL_TYPES else ""

    def _resolve_channel_config(self, request):
        """Return active client and resolved channel config."""
        client = get_active_client(request.user)
        data = getattr(request, 'data', {}) or {}

        raw_url = (data.get('channel_url') or '').strip()
        raw_type = (data.get('channel_type') or '').strip()

        normalized_type = self._normalize_channel_type(raw_type)
        type_invalid = bool(raw_type and not normalized_type)

        stored_url = (client.ai_analysis_channel_url or '').strip()
        stored_type = self._normalize_channel_type(getattr(client, 'ai_analysis_channel_type', ''))

        channel_url = raw_url or stored_url
        channel_type = normalized_type or stored_type

        updates = {}
        if raw_url and raw_url != stored_url:
            updates['ai_analysis_channel_url'] = raw_url
        if normalized_type and normalized_type != stored_type:
            updates['ai_analysis_channel_type'] = normalized_type

        return client, channel_url, channel_type, type_invalid, updates

    def _persist_channel_preferences(self, client, updates):
        """Save updated channel settings on the client model."""
        if not updates:
            return
        for field, value in updates.items():
            setattr(client, field, value)
        client.save(update_fields=list(updates.keys()))

    def _normalize_identifier(self, channel_url: str, channel_type: str) -> str:
        if channel_type == "telegram":
            return normalize_telegram_channel_identifier(channel_url)
        return (channel_url or "").strip()

    def _analyze_channel(self, request):
        """Start channel analysis"""
        from .permissions import IsTenantOwnerOrEditor
        
        # Check permissions
        if not IsTenantOwnerOrEditor().has_permission(request, self):
            return Response({
                'success': False,
                'error': 'Insufficient permissions'
            }, status=status.HTTP_403_FORBIDDEN)
        
        client, channel_url, channel_type, type_invalid, updates = self._resolve_channel_config(request)

        if type_invalid:
            return Response({
                'success': False,
                'error': f"Некорректный тип канала. Допустимые значения: {', '.join(sorted(self.CHANNEL_TYPES))}"
            }, status=status.HTTP_400_BAD_REQUEST)

        if not channel_url or not channel_type:
            return Response({
                'success': False,
                'error': 'Не указан канал для анализа. Добавьте channel_url и channel_type в запрос или сохраните их в настройках клиента.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if channel_type not in self.SUPPORTED_TYPES:
            return Response({
                'success': False,
                'error': 'Пока поддерживаются только Telegram каналы'
            }, status=status.HTTP_400_BAD_REQUEST)

        normalized_identifier = self._normalize_identifier(channel_url, channel_type)
        if not normalized_identifier:
            return Response({
                'success': False,
                'error': 'Не удалось распознать канал. Проверьте правильность ссылки.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Persist provided settings so the client configuration stays in sync
        self._persist_channel_preferences(client, updates)

        analysis = ChannelAnalysis.objects.create(
            client=client,
            channel_url=channel_url,
            channel_type=channel_type,
            status=ChannelAnalysis.STATUS_PENDING,
            progress=0,
        )

        task = tasks.analyze_channel_task.delay(analysis.id)
        analysis.task_id = task.id
        analysis.save(update_fields=['task_id'])

        return Response({
            'success': True,
            'message': 'Анализ канала запущен',
            'task_id': analysis.task_id,
            'channel_url': channel_url,
            'channel_type': channel_type,
        })

    def _validate_channel(self, request):
        """Validate channel URL"""
        client, channel_url, channel_type, type_invalid, _updates = self._resolve_channel_config(request)

        if type_invalid:
            return Response({
                'valid': False,
                'error': f"Некорректный тип канала. Допустимые значения: {', '.join(sorted(self.CHANNEL_TYPES))}"
            }, status=status.HTTP_400_BAD_REQUEST)

        if not channel_url or not channel_type:
            return Response({
                'valid': False,
                'error': 'channel_url и channel_type обязательны. Заполните канал в настройках клиента или передайте значения в запросе.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if channel_type not in self.SUPPORTED_TYPES:
            return Response({
                'valid': False,
                'error': 'Пока поддерживаются только Telegram каналы'
            }, status=status.HTTP_400_BAD_REQUEST)

        identifier = self._normalize_identifier(channel_url, channel_type)
        if not identifier:
            return Response({
                'valid': False,
                'error': 'Не удалось распознать канал. Проверьте ссылку или @username'
            }, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Add actual validation logic
        # For now, just return success

        return Response({
            'valid': True,
            'message': 'Channel URL is valid',
            'channel_url': channel_url,
            'channel_type': channel_type,
            'normalized_channel': identifier,
        })

    def _get_analysis_status(self, request):
        """Get analysis task status"""
        client = get_active_client(request.user)

        task_id = request.GET.get('task_id') or getattr(request, 'data', {}).get('task_id')
        if not task_id:
            return Response({
                'success': False,
                'error': 'task_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            analysis = ChannelAnalysis.objects.get(client=client, task_id=task_id)
        except ChannelAnalysis.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Анализ с таким task_id не найден'
            }, status=status.HTTP_404_NOT_FOUND)

        payload = {
            'task_id': analysis.task_id,
            'status': analysis.status,
            'progress': analysis.progress,
            'result': analysis.result if analysis.status == ChannelAnalysis.STATUS_COMPLETED else None,
        }

        if analysis.status == ChannelAnalysis.STATUS_FAILED:
            payload['error'] = analysis.error or 'Анализ завершился с ошибкой'

        return Response(payload)


class ChannelAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose stored channel analysis records."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            ChannelAnalysis.objects.filter(client=client)
            .select_related("client")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return ChannelAnalysisListSerializer
        return ChannelAnalysisDetailSerializer

    @action(
        detail=True,
        methods=["post"],
        url_path="merge_audience",
        permission_classes=[IsTenantOwnerOrEditor],
    )
    def merge_audience(self, request, pk=None):
        """Добавить описание ЦА из анализа канала в профиль клиента."""
        client = get_active_client(request.user)
        analysis = self.get_object()

        if analysis.client_id != client.id:
            return Response({"success": False, "error": "Анализ не принадлежит текущему клиенту"}, status=status.HTTP_403_FORBIDDEN)

        if analysis.status != ChannelAnalysis.STATUS_COMPLETED:
            return Response({"success": False, "error": "Анализ ещё не завершён"}, status=status.HTTP_400_BAD_REQUEST)

        result = analysis.result if isinstance(analysis.result, dict) else {}
        profile = result.get("audience_profile")

        def _has_text(value) -> bool:
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (list, tuple)):
                return any(_has_text(item) for item in value)
            if isinstance(value, dict):
                return any(_has_text(item) for item in value.values())
            return bool(value)

        if not isinstance(profile, dict) or not any(_has_text(value) for value in profile.values()):
            return Response(
                {"success": False, "error": "Для этого анализа нет описания целевой аудитории"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_profile = {
            "avatar": client.avatar or "",
            "pains": client.pains or "",
            "desires": client.desires or "",
            "objections": client.objections or "",
        }

        merged_profile = merge_audience_profiles(current_profile, profile)
        for field, value in merged_profile.items():
            setattr(client, field, value)
        client.save(update_fields=["avatar", "pains", "desires", "objections"])

        return Response(
            {
                "success": True,
                "message": "Описание целевой аудитории обновлено в настройках клиента",
                "client_profile": merged_profile,
            }
        )


class SEOKeywordSetViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing and generating SEO keyword sets."""

    permission_classes = [IsTenantMember]
    serializer_class = SEOKeywordSetSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = SEOKeywordSet.objects.filter(client=client).order_by('-created_at')
        group_type = self.request.query_params.get('group_type')
        if group_type:
            queryset = queryset.filter(group_type=group_type)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    @action(detail=False, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate(self, request):
        client = get_active_client(request.user)
        task = tasks.generate_seo_keywords_for_client.delay(client.id)
        return Response({
            'success': True,
            'message': f"Генерация SEO-фраз запущена для клиента: {client.name}",
            'task_id': task.id,
        })
