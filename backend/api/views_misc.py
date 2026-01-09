from __future__ import annotations

# NOTE: This module is kept for backward-compatible imports and gradual refactors.

import base64
import hashlib
import hmac
import html
import json
import logging
import mimetypes
import secrets
import string
from datetime import datetime, timedelta
from email.utils import format_datetime
from typing import List
from urllib.parse import parse_qsl, urlencode

import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F, Q, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import linebreaks
from rest_framework import generics, status, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from config.celery import app as celery_app

from core.audience_profiles import merge_audience_profiles
from core.ai_generator import AIContentGenerator
from core.ai_generator_seo import cluster_wordstat_phrases, normalize_phrase
from core.services.article_blocks import get_system_block_prompt_template, sync_blocks_from_seo_blocks
from core.models import (
    Article,
    ArticleBlock,
    Client,
    ClientProduct,
    ProductType,
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
    WeeklySourceReport,
    WeeklySourceBatch,
    SEOKeywordSet,
    VkIntegration,
    WordstatQuery,
    WordstatResult,
    WordstatCluster,
)
from core import tasks
from core.telegram_client import normalize_telegram_channel_identifier
from core.social_accounts import (
    ensure_rss_zen_account,
    sync_client_default_telegram_account,
)
from core.system_settings import get_image_generation_model, get_image_generation_method
from core.instagram_client import normalize_instagram_username
from core.youtube_client import normalize_youtube_identifier
from core.wordstat import WordstatError, get_wordstat_client
from core.services.posting_service import update_post_status_after_publish

from .authentication import CookieJWTAuthentication
from .permissions import CanGenerateVideo, IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ArticleListSerializer,
    ArticleSerializer,
    ArticleBlockSerializer,
    ChannelAnalysisDetailSerializer,
    ChannelAnalysisListSerializer,
    ClientProductSerializer,
    ProductTypeSerializer,
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
    WeeklySourceReportSerializer,
    WeeklySourceBatchSerializer,
    WeeklySourceBatchListSerializer,
    WordstatQuerySerializer,
    WordstatResultSerializer,
    WordstatClusterSerializer,
)
from .utils import get_active_client

User = get_user_model()

# ViewSets extracted into smaller modules (keep re-exports for urls.py imports).
from .views_products import (  # noqa: E402
    ClientProductViewSet,
    MindMapViewSet,
    MindNodePositionView,
    MindNodePropertyViewSet,
    ProductTypeViewSet,
)
from .views_posts import PostsListView, PostToneViewSet, PostTypeViewSet, PostViewSet  # noqa: E402
from .views_social import DzenRSSFeedView, TgChannelView, _ensure_rss_account_for_client  # noqa: E402

COOKIE_SECURE = not settings.DEBUG
COOKIE_SAMESITE = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
COOKIE_MAX_AGE = int(getattr(settings, "JWT_COOKIE_MAX_AGE", 60 * 60))  # 1 hour for access token
REFRESH_COOKIE_MAX_AGE = int(getattr(settings, "JWT_REFRESH_COOKIE_MAX_AGE", 60 * 60 * 24 * 7))
VK_SCOPE = "wall photos groups"
VK_TIMEOUT = 15
VK_ID_AUTHORIZE_URL = "https://id.vk.ru/authorize"
VK_ID_TOKEN_URL = "https://id.vk.ru/oauth2/auth"

logger = logging.getLogger(__name__)


class VkApiError(Exception):
    """Raised when VK API responds with an error."""

    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


def _missing_vk_settings() -> list[str]:
    missing: list[str] = []
    if not getattr(settings, "VK_CLIENT_ID", ""):
        missing.append("VK_CLIENT_ID")
    if not getattr(settings, "VK_REDIRECT_URI", ""):
        missing.append("VK_REDIRECT_URI")
    return missing


def _popup_response(message: str, *, success: bool = True, title: str = "VK интеграция"):
    """
    Returns a minimal plain-text page (no scripts) per VK ID redirect_uri requirements.
    """
    status_value = "Успех" if success else "Ошибка"
    content = f"{title}: {status_value}\n\n{message}\n\nОкно можно закрыть."
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    response["Referrer-Policy"] = "no-referrer"
    return response


def _generate_vk_state(length: int = 36) -> str:
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _generate_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def _vk_id_token_request(payload: dict) -> dict:
    try:
        response = requests.post(VK_ID_TOKEN_URL, data=payload, timeout=VK_TIMEOUT)
        data = response.json()
    except requests.RequestException as exc:
        raise VkApiError("Не удалось связаться с VK ID") from exc
    except ValueError as exc:
        raise VkApiError("VK ID вернул некорректный ответ") from exc

    if "error" in data:
        message = data.get("error_description") or data.get("error") or "Ошибка VK ID"
        raise VkApiError(message, data)
    return data


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


def _save_vk_integration(
    client: Client,
    owner,
    group_data: dict,
    access_token: str,
    user_id: int | None,
    token_meta: dict | None = None,
):
    group_id = int(group_data.get("id"))
    integration, _created = VkIntegration.objects.get_or_create(
        client=client,
        group_id=group_id,
        defaults={
            "owner": owner,
            "group_name": group_data.get("name", ""),
            "screen_name": group_data.get("screen_name", ""),
        },
    )

    extra = integration.extra or {}
    extra.update({
        "type": group_data.get("type"),
        "members_count": group_data.get("members_count"),
    })

    token_meta = token_meta or {}
    if token_meta.get("refresh_token"):
        extra["refresh_token"] = token_meta["refresh_token"]
    if token_meta.get("device_id"):
        extra["device_id"] = token_meta["device_id"]
    if token_meta.get("id_token"):
        extra["id_token"] = token_meta["id_token"]
    if token_meta.get("scope"):
        extra["scope"] = token_meta["scope"]

    expires_in = token_meta.get("expires_in")
    if expires_in:
        try:
            expires_seconds = int(expires_in)
            if expires_seconds > 0:
                expires_at = timezone.now() + timedelta(seconds=expires_seconds)
                extra["access_token_expires_at"] = expires_at.isoformat()
        except (TypeError, ValueError):
            pass

    integration.owner = owner
    integration.group_name = group_data.get("name", "")
    integration.screen_name = group_data.get("screen_name", "")
    integration.access_token = access_token
    integration.user_id = user_id
    integration.status = VkIntegration.STATUS_ACTIVE
    integration.extra = extra
    integration.save(
        update_fields=[
            "owner",
            "group_name",
            "screen_name",
            "access_token",
            "user_id",
            "status",
            "extra",
            "updated_at",
        ]
    )


def _refresh_vk_access_token_if_needed(integration: VkIntegration) -> None:
    extra = integration.extra or {}
    refresh_token = extra.get("refresh_token")
    device_id = extra.get("device_id")
    expires_at_raw = extra.get("access_token_expires_at")

    if not refresh_token or not device_id:
        return

    expires_at = None
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
        except (TypeError, ValueError):
            expires_at = None

    if expires_at and (expires_at - timezone.now()) > timedelta(seconds=60):
        return

    refresh_payload = {
        "client_id": settings.VK_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "device_id": device_id,
        "state": _generate_vk_state(32),
    }
    token_data = _vk_id_token_request(refresh_payload)

    new_expires_in = token_data.get("expires_in")
    if new_expires_in:
        try:
            expires_seconds = int(new_expires_in)
            if expires_seconds > 0:
                expires_at = timezone.now() + timedelta(seconds=expires_seconds)
                extra["access_token_expires_at"] = expires_at.isoformat()
        except (TypeError, ValueError):
            pass

    extra["refresh_token"] = token_data.get("refresh_token") or refresh_token
    extra["device_id"] = device_id
    if token_data.get("scope"):
        extra["scope"] = token_data["scope"]
    if token_data.get("id_token"):
        extra["id_token"] = token_data["id_token"]

    integration.access_token = token_data.get("access_token") or integration.access_token
    integration.extra = extra
    integration.save(update_fields=["access_token", "extra", "updated_at"])


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
        return (
            Post.objects.filter(client=client)
            .annotate(
                images_count=Count("images", distinct=True),
                videos_count=Count("videos", distinct=True),
            )
            .prefetch_related("schedules__social_account")
            .order_by("-created_at")
        )

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

    @action(
        detail=False,
        methods=['get'],
        url_path='generation-status',
        permission_classes=[IsTenantMember],
    )
    def generation_status(self, request):
        """Вернуть состояние задачи генерации постов по task_id."""
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {'success': False, 'error': 'task_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            async_result = celery_app.AsyncResult(task_id)
        except Exception as exc:  # pragma: no cover - защита от неожиданных ошибок окружения
            logger.warning("Failed to fetch generation status for %s: %s", task_id, exc, exc_info=True)
            return Response(
                {'success': False, 'error': 'Не удалось получить статус задачи'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        state = (async_result.state or "").lower()
        payload = {
            'success': state == 'success',
            'status': state,
            'task_id': task_id,
        }

        if state == 'success' and isinstance(async_result.result, dict):
            payload['result'] = async_result.result
        elif state in ('failure', 'revoked'):
            error_info = getattr(async_result, 'info', None)
            payload['error'] = str(error_info) if error_info else 'Задача завершилась с ошибкой'

        return Response(payload)

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


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    if value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _parse_ai_json_object(raw_response: str):
    if not raw_response:
        return None
    candidates: list[str] = []
    cleaned = _strip_code_fences(raw_response)
    if cleaned:
        candidates.append(cleaned)
    if raw_response.strip() and raw_response.strip() not in candidates:
        candidates.append(raw_response.strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _parse_optional_positive_int(value):
    if value in (None, "", 0):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _build_article_outline(
    wordstat: str,
    why_now: list[str],
    solution: list[str],
    *,
    lead_product_name: str = "",
    tripwire_product_name: str = "",
    level3: dict | None = None,
) -> str:
    safe_wordstat = (wordstat or "").strip()
    why_now_items = [str(item).strip() for item in (why_now or []) if str(item).strip()]
    solution_items = [str(item).strip() for item in (solution or []) if str(item).strip()]

    lines: list[str] = []
    lines.append(f"# {safe_wordstat}")
    lines.append("")
    lines.append("SEO-H1 (чётко по запросу)")
    lines.append("")
    lines.append("## Вступление:")
    lines.append("")
    lines.append("### боль")
    if why_now_items:
        for item in why_now_items:
            lines.append(f"- {item}")
    else:
        lines.append("- (какая боль/срочность у пользователя)")
    lines.append("")
    lines.append("### узнавание")
    lines.append("- (как пользователь узнаёт себя в ситуации)")
    lines.append("- (признаки/симптомы, по которым он понимает, что это про него)")
    lines.append("")
    lines.append("### обещание")
    if solution_items:
        for item in solution_items:
            lines.append(f"- {item}")
    else:
        lines.append("- (к какому решению/логике подводим)")
    lines.append("")

    def _append_level3(block_title: str, answer_hint: str) -> bool:
        if not isinstance(level3, dict):
            return False
        entry = level3.get(block_title)
        if not isinstance(entry, dict):
            return False
        h2_title = str(entry.get("h2_title") or entry.get("subquery_h2") or "").strip()
        subquery = str(entry.get("subquery") or "").strip()
        if h2_title:
            lines.append(f"## {h2_title}")
        elif subquery:
            lines.append(f"## {subquery}")
        keywords = entry.get("keywords") if isinstance(entry.get("keywords"), list) else []
        keyword_values = [str(item).strip() for item in keywords if str(item).strip()]
        if keyword_values:
            lines.append(f"- ключи: {', '.join(keyword_values)}")
        if subquery:
            lines.append(f"- подзапрос: {subquery}")
        micro_intent = str(entry.get("intent") or entry.get("micro_intent") or "").strip()
        if micro_intent:
            lines.append(f"- интент: {micro_intent}")
        raw_key_points = entry.get("key_points")
        if isinstance(raw_key_points, list):
            key_points = [str(item).strip() for item in raw_key_points if str(item).strip()]
            if key_points:
                lines.append(f"- ключевые смыслы: {', '.join(key_points)}")
        elif isinstance(raw_key_points, str) and raw_key_points.strip():
            lines.append(f"- ключевые смыслы: {raw_key_points.strip()}")
        lines.append(f"- ответ: {answer_hint}")
        return True

    def _append_level3_placeholder(answer_hint: str):
        lines.append("## (H2 заголовок)")
        lines.append("- подзапрос: (конкретный вопрос пользователя)")
        lines.append("- ключи: (1–2 ключа из Wordstat избранного)")
        lines.append("- интент: (какой когнитивный запрос закрываем)")
        lines.append("- ключевые смыслы: (3–6 пунктов)")
        lines.append(f"- ответ: {answer_hint}")

    lines.append("## Блок «Почему проблема возникает»")
    if not _append_level3("Блок «Почему проблема возникает»", "(причины/механика проблемы: от простого к сложному)"):
        _append_level3_placeholder("(причины/механика проблемы: от простого к сложному)")
    lines.append("")
    lines.append("## Блок «Типичные ошибки»")
    if not _append_level3("Блок «Типичные ошибки»", "(что обычно делают неправильно и почему не работает)"):
        _append_level3_placeholder("(что обычно делают неправильно и почему не работает)")
    lines.append("")
    lines.append("## Блок «Правильная логика / система»")
    if not _append_level3("Блок «Правильная логика / система»", "(правильный принцип/система мышления)"):
        _append_level3_placeholder("(правильный принцип/система мышления)")
    lines.append("")
    lines.append("## Блок «Пошаговая модель»")
    if not _append_level3("Блок «Пошаговая модель»", "(какие шаги и в каком порядке)"):
        _append_level3_placeholder("(какие шаги и в каком порядке)")
    lines.append("- Шаг 1: (что сделать)")
    lines.append("- Шаг 2: (что сделать)")
    lines.append("- Шаг 3: (что сделать)")
    lines.append("")
    lines.append("## Блок «Пример / кейс / сценарий»")
    if not _append_level3("Блок «Пример / кейс / сценарий»", "(короткий сценарий применения шагов)"):
        _append_level3_placeholder("(короткий сценарий применения шагов)")
    lines.append("")
    lines.append("## Блок «Что делать дальше»")
    if not _append_level3("Блок «Что делать дальше»", "(варианты следующего шага и когда нужен специалист/инструмент)"):
        _append_level3_placeholder("(варианты следующего шага и когда нужен специалист/инструмент)")
    lines.append("- (варианты следующего шага)")
    lines.append("- (когда стоит обратиться к специалисту/инструменту)")
    lines.append("")
    lines.append("## Мягкий переход к продукту:")
    if not _append_level3("Мягкий переход к продукту:", "(как связать решение с продуктом без давления)"):
        _append_level3_placeholder("(как связать решение с продуктом без давления)")
    if lead_product_name.strip():
        lines.append(f"- Lead: {lead_product_name.strip()}")
    if tripwire_product_name.strip():
        lines.append(f"- Tripwire: {tripwire_product_name.strip()}")
    lines.append("- (мягко связать решение с продуктом/услугой без давления)")
    lines.append("")

    lines.append("## Закрывающее утверждение")
    lines.append("- (2–3 предложения: ясность, структура, без CTA)")
    lines.append("")
    return "\n".join(lines)


class ArticleViewSet(viewsets.ModelViewSet):
    """Статьи (скелеты) по Wordstat запросам."""

    permission_classes = [IsTenantMember]
    http_method_names = ["get", "post", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return Article.objects.filter(client=client).order_by("-created_at")

    def get_permissions(self):
        if self.action in {
            "start",
            "generate_context",
            "save_choices",
            "save_seo_blocks",
            "generate_seo_blocks",
            "generate_blocks",
            "update_outline",
            "update_wordstat",
            "update_audience",
            "generate_outline",
            "blocks_update",
            "blocks_generate",
        }:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        return ArticleSerializer

    def _get_block_queryset(self, article: Article):
        return ArticleBlock.objects.filter(article=article).order_by("order", "id")

    def _get_system_block_prompt_template(self, block_key: str) -> str:
        """
        Системный промпт для блока (общий для всех клиентов/статей).
        Редактируется в Django Admin в модели ArticleBlockPromptTemplate.
        """
        return get_system_block_prompt_template(block_key)

    def _sync_blocks_from_seo_blocks(self, article: Article):
        sync_blocks_from_seo_blocks(article)

    def _generate_context_options(self, article: Article, force: bool = False):
        has_options = bool(article.options_why_now) and bool(article.options_solution)
        if has_options and not force:
            if article.status in {"draft", "failed"}:
                article.status = "options_ready"
                article.save(update_fields=["status", "updated_at"])
            return True, None, None

        try:
            generator = AIContentGenerator()
        except Exception:
            article.status = "failed"
            article.save(update_fields=["status", "updated_at"])
            return False, "AI генератор не настроен (нет ключа/доступа)", status.HTTP_503_SERVICE_UNAVAILABLE

        prompt = f"""
Ты помощник редактора. По поисковому запросу (Wordstat) нужно сгенерировать варианты для двух списков.

Запрос: "{article.wordstat}"

1) Почему пользователь это ищет именно сейчас?
2) К какому решению его можно подвести?

Требования:
- Верни строго JSON-объект.
- Ключи: "why_now" и "solution".
- Значения: массивы строк (каждая строка 4-12 слов), по 6-10 вариантов.
- Не пиши статьи и объяснения, только варианты.
"""

        ai_raw = generator.get_ai_response(
            prompt,
            max_tokens=700,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        parsed = _parse_ai_json_object(ai_raw or "")
        why_now = parsed.get("why_now") if isinstance(parsed, dict) else None
        solution = parsed.get("solution") if isinstance(parsed, dict) else None

        if not isinstance(why_now, list) or not isinstance(solution, list):
            article.status = "failed"
            article.save(update_fields=["status", "updated_at"])
            return False, "Не удалось получить варианты от AI", status.HTTP_502_BAD_GATEWAY

        article.options_why_now = [str(item).strip() for item in why_now if str(item).strip()]
        article.options_solution = [str(item).strip() for item in solution if str(item).strip()]
        if article.status in {"draft", "failed"}:
            article.status = "options_ready"
        article.save(update_fields=["options_why_now", "options_solution", "status", "updated_at"])

        return True, None, None

    @action(detail=True, methods=["get"])
    def blocks(self, request, pk=None):
        article = self.get_object()
        self._sync_blocks_from_seo_blocks(article)
        serializer = ArticleBlockSerializer(self._get_block_queryset(article), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def blocks_update(self, request, pk=None):
        article = self.get_object()
        block_id = request.data.get("block_id")
        try:
            block_id_int = int(str(block_id))
        except (TypeError, ValueError):
            return Response({"error": "block_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        block = get_object_or_404(ArticleBlock, id=block_id_int, article=article)

        if "h2_title" in request.data:
            block.h2_title = str(request.data.get("h2_title") or "")[:300]
        if "subquery" in request.data:
            block.subquery = str(request.data.get("subquery") or "")[:300]
        if "micro_intent" in request.data or "intent" in request.data:
            block.micro_intent = str(request.data.get("micro_intent") or request.data.get("intent") or "")[:300]
        if "keywords" in request.data:
            raw_keywords = request.data.get("keywords")
            if isinstance(raw_keywords, list):
                block.keywords = [str(item).strip() for item in raw_keywords if str(item).strip()][:2]
            else:
                return Response({"error": "keywords должен быть массивом"}, status=status.HTTP_400_BAD_REQUEST)
        if "key_points" in request.data:
            raw_key_points = request.data.get("key_points")
            if isinstance(raw_key_points, list):
                block.key_points = "\n".join([str(item).strip() for item in raw_key_points if str(item).strip()])[:1500]
            else:
                block.key_points = str(raw_key_points or "")[:1500]
        if "prompt_is_custom" in request.data:
            block.prompt_is_custom = bool(request.data.get("prompt_is_custom"))
        if "content" in request.data:
            block.content = str(request.data.get("content") or "")
        if "prompt_template" in request.data:
            block.prompt_template = str(request.data.get("prompt_template") or "")

        if block.content.strip():
            block.status = "ready"
        elif block.status != "failed":
            block.status = "blueprint_ready"

        block.save(
            update_fields=[
                "h2_title",
                "subquery",
                "micro_intent",
                "keywords",
                "key_points",
                "prompt_template",
                "prompt_is_custom",
                "content",
                "status",
                "updated_at",
            ]
        )
        serializer = ArticleBlockSerializer(block)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def blocks_generate(self, request, pk=None):
        article = self.get_object()
        block_id = request.data.get("block_id")
        try:
            block_id_int = int(str(block_id))
        except (TypeError, ValueError):
            return Response({"error": "block_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(ArticleBlock, id=block_id_int, article=article)

        task = tasks.generate_article_block_task.delay(article.id, block_id_int)
        return Response(
            {
                "success": True,
                "message": "Генерация блока запущена",
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["post"])
    def start(self, request):
        client = get_active_client(request.user)
        raw_phrase = request.data.get("phrase") or request.data.get("wordstat") or ""
        phrase = str(raw_phrase).strip()
        if not phrase:
            return Response({"error": "Укажите Wordstat фразу"}, status=status.HTTP_400_BAD_REQUEST)

        article = Article.objects.create(
            client=client,
            wordstat=phrase[:500],
            status="draft",
            created_by=request.user,
        )
        self._sync_blocks_from_seo_blocks(article)

        ok, error, status_code = self._generate_context_options(article)
        if not ok:
            return Response({"error": error}, status=status_code)

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_context(self, request, pk=None):
        article = self.get_object()
        raw_force = request.data.get("force")
        force = False
        if isinstance(raw_force, bool):
            force = raw_force
        elif raw_force is not None:
            force = str(raw_force).strip().lower() in {"1", "true", "yes", "y", "on"}

        ok, error, status_code = self._generate_context_options(article, force=force)
        if not ok:
            return Response({"error": error}, status=status_code)

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def save_choices(self, request, pk=None):
        article = self.get_object()
        selected_why_now = request.data.get("selected_why_now") or request.data.get("why_now") or []
        selected_solution = request.data.get("selected_solution") or request.data.get("solution") or []
        lead_product_id = request.data.get("lead_product_id")
        lead_product_name = request.data.get("lead_product_name") or ""
        tripwire_product_id = request.data.get("tripwire_product_id")
        tripwire_product_name = request.data.get("tripwire_product_name") or ""

        if not isinstance(selected_why_now, list) or not isinstance(selected_solution, list):
            return Response(
                {"error": "selected_why_now и selected_solution должны быть массивами строк"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.selected_why_now = [str(item).strip() for item in selected_why_now if str(item).strip()]
        article.selected_solution = [str(item).strip() for item in selected_solution if str(item).strip()]
        article.lead_product_id = _parse_optional_positive_int(lead_product_id)
        article.lead_product_name = str(lead_product_name)[:255]
        article.tripwire_product_id = _parse_optional_positive_int(tripwire_product_id)
        article.tripwire_product_name = str(tripwire_product_name)[:255]

        if article.status == "draft":
            article.status = "options_ready"

        article.save(
            update_fields=[
                "selected_why_now",
                "selected_solution",
                "lead_product_id",
                "lead_product_name",
                "tripwire_product_id",
                "tripwire_product_name",
                "status",
                "updated_at",
            ]
        )

        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_wordstat(self, request, pk=None):
        article = self.get_object()
        raw_wordstat = request.data.get("wordstat") or request.data.get("phrase") or ""
        wordstat = str(raw_wordstat).strip()
        if not wordstat:
            return Response({"error": "Укажите wordstat"}, status=status.HTTP_400_BAD_REQUEST)

        article.wordstat = wordstat[:500]
        raw_audience = request.data.get("audience")
        if raw_audience is not None:
            article.audience = str(raw_audience or "")

        if article.outline_markdown:
            lines = (article.outline_markdown or "").splitlines()
            if lines:
                first = lines[0].strip()
                if first.startswith("#"):
                    lines[0] = f"# {article.wordstat}"
                    article.outline_markdown = "\n".join(lines)

        article.save(update_fields=["wordstat", "audience", "outline_markdown", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_audience(self, request, pk=None):
        article = self.get_object()
        raw = request.data.get("audience")
        if raw is None:
            return Response({"error": "audience обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        article.audience = str(raw or "")
        article.save(update_fields=["audience", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_outline(self, request, pk=None):
        article = self.get_object()
        outline = request.data.get("outline_markdown")
        if outline is None:
            return Response({"error": "outline_markdown обязателен"}, status=status.HTTP_400_BAD_REQUEST)
        article.outline_markdown = str(outline)
        # Status is updated only by the blueprint generator.
        article.save(update_fields=["outline_markdown", "updated_at"])
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def save_seo_blocks(self, request, pk=None):
        article = self.get_object()
        raw = request.data.get("seo_blocks")
        if not isinstance(raw, dict):
            return Response({"error": "seo_blocks должен быть объектом"}, status=status.HTTP_400_BAD_REQUEST)
        article.seo_blocks = raw
        article.save(update_fields=["seo_blocks", "updated_at"])
        self._sync_blocks_from_seo_blocks(article)
        serializer = self.get_serializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_seo_blocks(self, request, pk=None):
        article = self.get_object()
        task = tasks.generate_article_blueprint_task.delay(article.id)
        return Response(
            {
                "success": True,
                "message": "Генерация blueprint запущена",
                "task_id": task.id,
            }
        )

    @action(detail=True, methods=["post"])
    def generate_blocks(self, request, pk=None):
        article = self.get_object()
        task = tasks.generate_article_blocks_task.delay(article.id)
        return Response(
            {
                "success": True,
                "message": "Генерация всех блоков запущена",
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["get"], url_path="generation-status")
    def generation_status(self, request):
        """Вернуть состояние задачи генерации статьи по task_id."""
        task_id = request.query_params.get("task_id")
        if not task_id:
            return Response({"success": False, "error": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            async_result = celery_app.AsyncResult(task_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to fetch generation status for %s: %s", task_id, exc, exc_info=True)
            return Response(
                {"success": False, "error": "Не удалось получить статус задачи"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        state = (async_result.state or "").lower()
        payload = {"success": state == "success", "status": state, "task_id": task_id}

        if state == "success" and isinstance(async_result.result, dict):
            payload["result"] = async_result.result
        elif state in ("failure", "revoked"):
            error_info = getattr(async_result, "info", None)
            payload["error"] = str(error_info) if error_info else "Задача завершилась с ошибкой"

        return Response(payload)

    @action(detail=True, methods=["post"])
    def generate_outline(self, request, pk=None):
        article = self.get_object()
        selected_why_now = request.data.get("selected_why_now") or request.data.get("why_now") or []
        selected_solution = request.data.get("selected_solution") or request.data.get("solution") or []
        lead_product_id = request.data.get("lead_product_id")
        lead_product_name = request.data.get("lead_product_name") or ""
        tripwire_product_id = request.data.get("tripwire_product_id")
        tripwire_product_name = request.data.get("tripwire_product_name") or ""

        if not isinstance(selected_why_now, list) or not isinstance(selected_solution, list):
            return Response(
                {"error": "selected_why_now и selected_solution должны быть массивами строк"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        article.selected_why_now = [str(item).strip() for item in selected_why_now if str(item).strip()]
        article.selected_solution = [str(item).strip() for item in selected_solution if str(item).strip()]
        article.lead_product_id = _parse_optional_positive_int(lead_product_id)
        article.lead_product_name = str(lead_product_name)[:255]
        article.tripwire_product_id = _parse_optional_positive_int(tripwire_product_id)
        article.tripwire_product_name = str(tripwire_product_name)[:255]

        block_titles = [
            "Вступление",
            "Блок «Почему проблема возникает»",
            "Блок «Типичные ошибки»",
            "Блок «Правильная логика / система»",
            "Блок «Пошаговая модель»",
            "Блок «Пример / кейс / сценарий»",
            "Блок «Что делать дальше»",
            "Мягкий переход к продукту:",
        ]

        level3 = article.seo_blocks if isinstance(article.seo_blocks, dict) else {}
        if not level3:
            try:
                response = self.generate_seo_blocks(request, pk=pk)
                if isinstance(response.data, dict) and isinstance(response.data.get("seo_blocks"), dict):
                    level3 = response.data.get("seo_blocks")  # type: ignore[assignment]
            except Exception:
                logger.exception("Failed to auto-generate seo blocks for article %s", article.id)

        filtered_level3: dict[str, dict[str, object]] = {}
        if isinstance(level3, dict):
            for key, value in level3.items():
                if key in block_titles and isinstance(value, dict):
                    filtered_level3[key] = value
        article.seo_blocks = filtered_level3
        self._sync_blocks_from_seo_blocks(article)

        article.outline_markdown = _build_article_outline(
            article.wordstat,
            article.selected_why_now,
            article.selected_solution,
            lead_product_name=article.lead_product_name,
            tripwire_product_name=article.tripwire_product_name,
            level3=article.seo_blocks,
        )
        article.status = "outline_ready"
        article.save(
            update_fields=[
                "selected_why_now",
                "selected_solution",
                "lead_product_id",
                "lead_product_name",
                "tripwire_product_id",
                "tripwire_product_name",
                "seo_blocks",
                "outline_markdown",
                "status",
                "updated_at",
            ]
        )

        serializer = self.get_serializer(article)
        return Response(serializer.data)


class ContentTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ContentTemplate CRUD operations.
    Language stays read-only; other fields (type, tone, length) are editable.
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
            "post", "social_account", "connection"
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

        connection = getattr(schedule, "connection", None)
        provider = connection.provider if connection else None
        social_account = getattr(schedule, "social_account", None)
        if social_account is None:
            client = schedule.client
            if provider and provider != "rss_zen":
                # Используем connection-only расписание
                pass
            else:
                social_account = _ensure_rss_account_for_client(client, request)
                if social_account:
                    schedule.social_account = social_account
                    schedule.save(update_fields=["social_account"])
                else:
                    return Response(
                        {"success": False, "error": "У расписания не указан социальный аккаунт"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # RSS Дзен — помечаем опубликованным сразу
        if social_account.platform == "rss_zen":
            feed_url = (social_account.access_token or "").strip()
            schedule.scheduled_at = timezone.now()
            schedule.status = "published"
            schedule.external_id = feed_url
            log_msg = "\n[SUCCESS] Отмечено для RSS Дзена (берётся из RSS ленты)"
            if feed_url:
                log_msg += f"\nFeed: {feed_url}"
            schedule.log = (schedule.log or "") + log_msg
            schedule.save(update_fields=["scheduled_at", "status", "external_id", "log"])
            update_post_status_after_publish(schedule.post)
            return Response({
                'success': True,
                'message': 'Опубликовано в RSS Дзене',
                'status': schedule.status,
            })

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
        _ensure_rss_account_for_client(client, self.request)
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
    """Starts VK ID OAuth PKCE flow and redirects user to VK."""

    permission_classes = [IsTenantOwnerOrEditor]

    def get(self, request):
        # Ensure current user has an active client (raises if not)
        get_active_client(request.user)

        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK ID OAuth не настроен. Укажите переменные "
                f"{', '.join(missing)} на сервере."
            )
            return _popup_response(msg, success=False)

        state = _generate_vk_state()
        code_verifier, code_challenge = _generate_pkce_pair()
        request.session["vk_oauth_state"] = state
        request.session["vk_code_verifier"] = code_verifier
        target_group = request.query_params.get("group_id")
        if target_group:
            request.session["vk_target_group"] = target_group
        request.session.modified = True

        params = {
            "client_id": settings.VK_CLIENT_ID,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "scope": VK_SCOPE,
            "response_type": "code",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{VK_ID_AUTHORIZE_URL}?" + urlencode(params)
        return redirect(auth_url)


class VkCallbackView(APIView):
    """Handles VK ID callback, exchanges code for tokens and saves integrations."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        missing = _missing_vk_settings()
        if missing:
            msg = (
                "VK ID OAuth не настроен. Обратитесь к администратору: "
                f"{', '.join(missing)}"
            )
            return _popup_response(msg, success=False)

        payload_raw = request.GET.get("payload")
        payload_data: dict = {}
        if payload_raw:
            try:
                payload_data = json.loads(payload_raw)
            except ValueError:
                return _popup_response("Некорректный payload авторизации VK ID", success=False)

        provided_state = payload_data.get("state") or request.GET.get("state")
        saved_state = request.session.pop("vk_oauth_state", None)
        if not provided_state or provided_state != saved_state:
            return _popup_response("Некорректный ответ авторизации VK ID (state mismatch)", success=False)

        code_verifier = request.session.pop("vk_code_verifier", None)
        if not code_verifier:
            return _popup_response("Не удалось подтвердить PKCE для VK ID", success=False)

        code = payload_data.get("code") or request.GET.get("code")
        device_id = payload_data.get("device_id") or request.GET.get("device_id")
        if not code:
            error_description = request.GET.get("error_description") or "VK не вернул код авторизации"
            return _popup_response(error_description, success=False)
        if not device_id:
            return _popup_response("VK ID не вернул device_id", success=False)

        try:
            client = get_active_client(request.user)
        except PermissionDenied:
            return _popup_response("Пользователь не привязан к клиенту", success=False)

        token_params = {
            "client_id": settings.VK_CLIENT_ID,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
            "device_id": device_id,
            "code": code,
            "redirect_uri": settings.VK_REDIRECT_URI,
            "state": provided_state,
        }
        try:
            token_data = _vk_id_token_request(token_params)
        except VkApiError as exc:
            logger.warning("VK ID token exchange failed: %s", exc)
            return _popup_response(f"Ошибка VK ID OAuth: {exc}", success=False)

        access_token = token_data.get("access_token")
        user_id = token_data.get("user_id")
        if not access_token:
            return _popup_response("VK ID не вернул access_token", success=False)

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

        token_meta = {
            "refresh_token": token_data.get("refresh_token"),
            "id_token": token_data.get("id_token"),
            "expires_in": token_data.get("expires_in"),
            "scope": token_data.get("scope"),
            "device_id": device_id,
        }
        for group in groups:
            _save_vk_integration(client, request.user, group, access_token, user_id, token_meta)

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
            _refresh_vk_access_token_if_needed(integration)
        except VkApiError as exc:
            integration.status = VkIntegration.STATUS_ERROR
            integration.save(update_fields=["status"])
            return Response(
                {"success": False, "error": f"Не удалось обновить токен VK ID: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
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


class ChannelAnalysisViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    """Expose stored channel analysis records."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_permissions(self):
        if self.action == "destroy":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

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


class WeeklySourceReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only доступ к еженедельным отчетам по источникам."""

    permission_classes = [IsTenantMember]
    serializer_class = WeeklySourceReportSerializer
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WeeklySourceReport.objects.filter(client=client)
            .order_by("-week_start", "source_type", "-created_at")
        )


class WeeklySourceRunView(APIView):
    """Запуск еженедельной аналитики по всем источникам клиента."""

    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
        batch = WeeklySourceBatch.objects.create(
            client=client,
            week_start=week_start,
            status=WeeklySourceReport.STATUS_PENDING,
        )
        task = tasks.run_weekly_sources_for_client.delay(client.id, batch.id)
        return Response(
            {
                "success": True,
                "task_id": task.id,
                "week_start": str(week_start),
                "batch_id": batch.id,
            }
        )


class WeeklySourceBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """Подборки по неделям."""

    permission_classes = [IsTenantMember]
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return WeeklySourceBatch.objects.filter(client=client).order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "list":
            return WeeklySourceBatchListSerializer
        return WeeklySourceBatchSerializer


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


def _parse_int_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    result = []
    for part in parts:
        try:
            number = int(str(part).strip())
        except (ValueError, TypeError):
            continue
        result.append(number)
    return result


def _parse_str_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    result = []
    for part in parts:
        part_str = str(part).strip()
        if part_str:
            result.append(part_str)
    return result


def _parse_phrases(value):
    """Вернуть уникальный список фраз из списка или многострочной строки."""
    if value is None:
        return []
    phrases: list[str] = []
    seen: set[str] = set()

    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value).replace("\r", "\n").split("\n")

    for raw in raw_items:
        if raw is None:
            continue
        for part in str(raw).replace("\r", "\n").split("\n"):
            phrase = part.strip()
            if phrase and phrase not in seen:
                seen.add(phrase)
                phrases.append(phrase)
    return phrases


def _collect_wordstat_data(
    ws_client,
    phrases: list[str],
    regions: list[int],
    devices: list[str],
    include_parent: bool,
):
    aggregated: dict[tuple[str, str], int] = {}
    total_count = 0
    responses: list[dict[str, object]] = []

    for phrase_value in phrases:
        try:
            api_response = ws_client.fetch_top_requests(
                phrase=phrase_value,
                regions=regions or None,
                devices=devices or None,
                include_parent=include_parent,
            )
        except WordstatError as exc:
            raise WordstatError(f"{phrase_value}: {exc}") from exc

        responses.append({"phrase": phrase_value, "response": api_response})
        total_count += int(api_response.get("totalCount") or 0)

        for item in api_response.get("topRequests") or []:
            phrase_text = str(item.get("phrase") or "").strip()
            if not phrase_text:
                continue
            key = (phrase_text, "top_request")
            aggregated[key] = aggregated.get(key, 0) + int(item.get("count") or 0)

        for item in api_response.get("associations") or []:
            phrase_text = str(item.get("phrase") or "").strip()
            if not phrase_text:
                continue
            key = (phrase_text, "association")
            aggregated[key] = aggregated.get(key, 0) + int(item.get("count") or 0)

    return aggregated, total_count, responses


class WordstatQueryViewSet(viewsets.ModelViewSet):
    """Получение и сохранение Wordstat-результатов для клиента."""

    permission_classes = [IsTenantMember]
    serializer_class = WordstatQuerySerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in {"create", "append_phrases", "partial_update", "destroy"}:
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WordstatQuery.objects.filter(client=client)
            .prefetch_related(
                Prefetch("results", queryset=WordstatResult.objects.order_by("-count", "phrase"))
            )
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        client_obj = get_active_client(request.user)
        phrase = (request.data.get("phrase") or "").strip()
        group_raw = request.data.get("group") or request.data.get("phrases")
        phrases = _parse_phrases(group_raw)

        if phrase:
            if phrase not in phrases:
                phrases.insert(0, phrase)
        if not phrases:
            return Response(
                {"error": "Введите фразу или группу фраз для запроса Wordstat"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        regions = _parse_int_list(request.data.get("regions"))
        devices = _parse_str_list(request.data.get("devices"))
        include_parent_raw = request.data.get("include_parent", False)
        include_parent = str(include_parent_raw).lower() in {"1", "true", "yes", "on"}

        try:
            ws_client = get_wordstat_client()
            user_info = ws_client.fetch_user_info()
            aggregated, total_count, responses = _collect_wordstat_data(
                ws_client=ws_client,
                phrases=phrases,
                regions=regions,
                devices=devices,
                include_parent=include_parent,
            )
        except WordstatError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wordstat request failed")
            return Response(
                {"error": "Не удалось получить данные Wordstat"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        user_info_data = user_info.get("userInfo") if isinstance(user_info, dict) else {}
        request_phrase_value = phrase or phrases[0]
        if len(phrases) > 1:
            request_phrase_value = f"{phrases[0]} (+{len(phrases) - 1})"
        request_phrase_value = request_phrase_value[:255]
        group_name = (request.data.get("group_name") or "").strip() or request_phrase_value
        group_name = group_name[:255]
        raw_response_data = (
            responses[0]["response"] if len(responses) == 1 else {"group_phrases": phrases, "responses": responses}
        )
        query = WordstatQuery.objects.create(
            client=client_obj,
            group_name=group_name,
            phrases=phrases,
            request_phrase=request_phrase_value,
            total_count=total_count,
            include_parent=include_parent,
            regions=regions,
            devices=devices,
            user_login=user_info_data.get("login", ""),
            limit_per_second=user_info_data.get("limitPerSecond"),
            daily_limit=user_info_data.get("dailyLimit"),
            daily_limit_remaining=user_info_data.get("dailyLimitRemaining"),
            raw_response=raw_response_data,
        )

        results_to_create = []
        for (phrase_text, result_type), count in sorted(
            aggregated.items(), key=lambda item: (-item[1], item[0][0])
        ):
            results_to_create.append(
                WordstatResult(
                    query=query,
                    phrase=phrase_text,
                    count=int(count or 0),
                    result_type=result_type,
                )
            )

        if results_to_create:
            WordstatResult.objects.bulk_create(results_to_create)

        serializer = self.get_serializer(query)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        query: WordstatQuery = self.get_object()
        group_name = (request.data.get("group_name") or "").strip()[:255]
        query.group_name = group_name
        query.save(update_fields=["group_name"])
        serializer = self.get_serializer(query)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="append")
    def append_phrases(self, request, pk=None):
        """Добавить новые фразы в существующую группу Wordstat и объединить результаты."""
        query: WordstatQuery = self.get_object()
        new_phrases_raw = request.data.get("phrases") or request.data.get("group")
        new_phrases = _parse_phrases(new_phrases_raw)

        if not new_phrases:
            return Response({"error": "Введите фразы для запроса Wordstat"}, status=status.HTTP_400_BAD_REQUEST)

        existing_phrases = query.phrases or []
        existing_set = {p.strip() for p in existing_phrases if p}
        to_fetch = [p for p in new_phrases if p not in existing_set]

        if not to_fetch:
            return Response({"error": "Новых фраз не найдено"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ws_client = get_wordstat_client()
            user_info = ws_client.fetch_user_info()
            aggregated, total_count, responses = _collect_wordstat_data(
                ws_client=ws_client,
                phrases=to_fetch,
                regions=query.regions or [],
                devices=query.devices or [],
                include_parent=query.include_parent,
            )
        except WordstatError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Wordstat append request failed")
            return Response(
                {"error": "Не удалось получить данные Wordstat"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Обновляем агрегированные результаты: либо увеличиваем счетчик, либо создаем новые строки.
        existing_results = WordstatResult.objects.filter(query=query)
        result_map = {(r.phrase, r.result_type): r for r in existing_results}
        to_update: list[WordstatResult] = []
        to_create: list[WordstatResult] = []

        for (phrase_text, result_type), count in aggregated.items():
            found = result_map.get((phrase_text, result_type))
            if found:
                found.count = int(found.count) + int(count or 0)
                to_update.append(found)
            else:
                to_create.append(
                    WordstatResult(
                        query=query,
                        phrase=phrase_text,
                        count=int(count or 0),
                        result_type=result_type,
                    )
                )

        if to_create:
            WordstatResult.objects.bulk_create(to_create)
        if to_update:
            WordstatResult.objects.bulk_update(to_update, ["count"])

        # Обновляем метаданные запроса
        updated_phrases = existing_phrases + to_fetch
        label = updated_phrases[0]
        if len(updated_phrases) > 1:
            label = f"{label} (+{len(updated_phrases) - 1})"
        label = label[:255]

        existing_raw = query.raw_response or {}
        if isinstance(existing_raw, dict) and "responses" in existing_raw:
            combined_responses = list(existing_raw.get("responses") or [])
        else:
            base_response = existing_raw if isinstance(existing_raw, dict) else {}
            base_phrase = query.request_phrase or (existing_phrases[0] if existing_phrases else "")
            combined_responses = []
            if base_response:
                combined_responses.append({"phrase": base_phrase, "response": base_response})

        combined_responses.extend(responses)
        raw_response_data = {"group_phrases": updated_phrases, "responses": combined_responses}

        query.phrases = updated_phrases
        query.request_phrase = label
        query.total_count = int(query.total_count) + total_count
        query.user_login = (user_info.get("userInfo") or {}).get("login", query.user_login)
        query.limit_per_second = (user_info.get("userInfo") or {}).get("limitPerSecond", query.limit_per_second)
        query.daily_limit = (user_info.get("userInfo") or {}).get("dailyLimit", query.daily_limit)
        query.daily_limit_remaining = (user_info.get("userInfo") or {}).get("dailyLimitRemaining", query.daily_limit_remaining)
        query.raw_response = raw_response_data
        query.save(
            update_fields=[
                "phrases",
                "request_phrase",
                "total_count",
                "user_login",
                "limit_per_second",
                "daily_limit",
                "daily_limit_remaining",
                "raw_response",
            ]
        )

        query = self.get_queryset().get(pk=query.pk)
        serializer = self.get_serializer(query)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WordstatClusterViewSet(viewsets.ReadOnlyModelViewSet):
    """Список кластеров Wordstat для клиента."""

    permission_classes = [IsTenantMember]
    serializer_class = WordstatClusterSerializer
    pagination_class = None

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return (
            WordstatCluster.objects.filter(client=client)
            .annotate(phrases_count=Count("results", filter=Q(results__result_type="favorite")))
            .order_by("name", "id")
        )


class WordstatResultViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Обновление отдельных строк Wordstat (например, смена метки)."""

    permission_classes = [IsTenantOwnerOrEditor]
    serializer_class = WordstatResultSerializer
    http_method_names = ["patch", "put", "post", "head", "options"]

    def get_queryset(self):
        client = get_active_client(self.request.user)
        return WordstatResult.objects.filter(query__client=client)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)

        if "cluster" in data:
            client = get_active_client(request.user)
            raw_cluster = data.get("cluster")
            if raw_cluster in (None, "", "null"):
                data["cluster"] = None
            else:
                try:
                    cluster_id = int(raw_cluster)
                except (TypeError, ValueError):
                    return Response({"error": "Некорректный кластер"}, status=status.HTTP_400_BAD_REQUEST)
                if not WordstatCluster.objects.filter(client=client, id=cluster_id).exists():
                    return Response({"error": "Кластер не найден"}, status=status.HTTP_400_BAD_REQUEST)
                data["cluster"] = cluster_id

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="cluster-favorites")
    def cluster_favorites(self, request):
        client = get_active_client(request.user)
        favorites = list(
            WordstatResult.objects.filter(query__client=client, result_type="favorite")
        )
        if not favorites:
            return Response({"error": "Нет избранных фраз для кластеризации"}, status=status.HTTP_400_BAD_REQUEST)

        existing_clusters = list(
            WordstatCluster.objects.filter(client=client).order_by("name", "id")
        )
        existing_names = [cluster.name for cluster in existing_clusters]

        unclustered_rows = [item for item in favorites if item.phrase and not item.cluster_id]
        phrases = [item.phrase for item in unclustered_rows if item.phrase]

        if not phrases:
            clusters = (
                WordstatCluster.objects.filter(client=client)
                .annotate(phrases_count=Count("results", filter=Q(results__result_type="favorite")))
                .order_by("name", "id")
            )
            serializer = WordstatClusterSerializer(clusters, many=True)
            return Response(
                {
                    "success": True,
                    "message": "Нет фраз без кластера",
                    "clusters": serializer.data,
                }
            )

        clustering_result = cluster_wordstat_phrases(phrases, existing_clusters=existing_names)
        if not clustering_result.get("success"):
            return Response(
                {"error": "Не удалось кластеризовать фразы", "details": clustering_result.get("error")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        phrase_to_cluster = clustering_result.get("phrase_to_cluster")
        if not isinstance(phrase_to_cluster, dict):
            phrase_to_cluster = {}

        clusters_payload = clustering_result.get("clusters")
        if not isinstance(clusters_payload, list):
            clusters_payload = []

        cluster_names: list[str] = []
        for cluster in clusters_payload:
            if not isinstance(cluster, dict):
                continue
            name = str(cluster.get("name") or "").strip()
            if name and name not in cluster_names:
                cluster_names.append(name)

        with transaction.atomic():
            clusters_by_name: dict[str, WordstatCluster] = {c.name: c for c in existing_clusters}
            for name in cluster_names:
                if name in clusters_by_name:
                    continue
                clusters_by_name[name] = WordstatCluster.objects.create(
                    client=client,
                    name=name[:255],
                )

            to_update: list[WordstatResult] = []
            for row in unclustered_rows:
                normalized = normalize_phrase(row.phrase)
                cluster_name = phrase_to_cluster.get(normalized)
                if not cluster_name:
                    continue
                cluster = clusters_by_name.get(cluster_name)
                if not cluster:
                    continue
                row.cluster = cluster
                to_update.append(row)

            if to_update:
                WordstatResult.objects.bulk_update(to_update, ["cluster"])

        clusters = (
            WordstatCluster.objects.filter(client=client)
            .annotate(phrases_count=Count("results", filter=Q(results__result_type="favorite")))
            .order_by("name", "id")
        )
        serializer = WordstatClusterSerializer(clusters, many=True)
        return Response({"success": True, "clusters": serializer.data})
