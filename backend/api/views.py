from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from core.models import (
    Client,
    ContentTemplate,
    Post,
    Schedule,
    SocialAccount,
    Story,
    Topic,
    TrendItem,
)
from core import tasks

from .permissions import CanGenerateVideo, IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ClientSettingsSerializer,
    ClientSummarySerializer,
    ContentTemplateSerializer,
    PostDetailSerializer,
    PostSerializer,
    ScheduleSerializer,
    SocialAccountSerializer,
    StoryDetailSerializer,
    StorySerializer,
    TopicDetailSerializer,
    TopicSerializer,
    TrendItemDetailSerializer,
    TrendItemSerializer,
)
from .utils import get_active_client

User = get_user_model()

COOKIE_SECURE = not settings.DEBUG
COOKIE_SAMESITE = getattr(settings, "JWT_COOKIE_SAMESITE", "Lax")
COOKIE_MAX_AGE = int(getattr(settings, "JWT_COOKIE_MAX_AGE", 60 * 60))  # 1 hour for access token
REFRESH_COOKIE_MAX_AGE = int(getattr(settings, "JWT_REFRESH_COOKIE_MAX_AGE", 60 * 60 * 24 * 7))


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

    def get(self, request):
        """Check if user is authenticated"""
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        user_data = {
            "user": {
                "telegramId": str(request.user.id),
                "firstName": request.user.first_name or request.user.username,
                "lastName": request.user.last_name,
                "username": request.user.username,
                "photoUrl": None,
                "authDate": str(request.user.date_joined),
                "isDev": getattr(request.user, 'is_dev_user', False)
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
        return (
            Schedule.objects.filter(client=client)
            .select_related("post", "social_account")
            .order_by("scheduled_at")
        )


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
        Model choices: pollinations, nanobanana, huggingface, flux2
        """
        post = self.get_object()
        model = request.data.get('model', 'pollinations')

        # Call existing Celery task
        task = tasks.generate_image_for_post.delay(post.id, model)

        return Response({
            'success': True,
            'message': f'Image generation started with model: {model}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[CanGenerateVideo, IsTenantOwnerOrEditor])
    def generate_video(self, request, pk=None):
        """
        Generate video from post image.
        Only available in DEBUG mode or for zavod client.
        """
        post = self.get_object()

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

        if source == 'image' and not post.image:
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
        """Generate SEO keywords for this topic"""
        topic = self.get_object()

        # Call existing Celery task
        task = tasks.generate_seo_keywords_for_topic.delay(topic.id)

        return Response({
            'success': True,
            'message': f'SEO keyword generation started for topic: {topic.name}',
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
        return ContentTemplate.objects.filter(client=client).order_by('-created_at')

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
        return Schedule.objects.filter(client=client).select_related(
            'post', 'social_account'
        ).order_by('scheduled_at')

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
        return SocialAccount.objects.filter(client=client).order_by('platform', 'name')

    def perform_create(self, serializer):
        client = get_active_client(self.request.user)
        serializer.save(client=client)


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
