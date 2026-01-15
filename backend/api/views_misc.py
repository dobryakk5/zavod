from __future__ import annotations

# NOTE: This module is kept for backward-compatible imports and gradual refactors.

from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core import tasks
from core.generation_events import record_generation_event
from core.models import ContentTemplate, GenerationEvent, Schedule, SocialAccount, Story, Topic, TrendItem
from core.services.posting_service import update_post_status_after_publish
from core.social_accounts import sync_client_default_telegram_account

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers import (
    ContentTemplateSerializer,
    ScheduleSerializer,
    SocialAccountSerializer,
    StoryDetailSerializer,
    StorySerializer,
    TopicDetailSerializer,
    TopicSerializer,
    TrendItemDetailSerializer,
    TrendItemSerializer,
)
from .utils import enforce_generation_limit, get_active_client
from .views_accounts import (
    ClientExpertBooksView,
    GenerationEventSummaryView,
    ClientInfoView,
    ClientSettingsView,
    ClientSummaryView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    TelegramAuthView,
)  # noqa: F401
from .views_integrations import (
    ChannelAnalysisViewSet,
    ProjectChannelAnalysisRunView,
    ProjectChannelAnalysisRunViewSet,
    VkCallbackView,
    VkConnectView,
    VkIntegrationViewSet,
    VkPublishView,
    WeeklySourceBatchViewSet,
    WeeklySourceReportViewSet,
    WeeklySourceRunView,
)  # noqa: F401
from .views_posts import PostsListView, PostToneViewSet, PostTypeViewSet, PostViewSet  # noqa: F401
from .views_products import (
    ClientProductViewSet,
    MindMapViewSet,
    MindNodePositionView,
    MindNodePropertyViewSet,
    ProductTypeViewSet,
)  # noqa: F401
from .views_seo import (
    ArticleViewSet,
    SEOKeywordSetViewSet,
    WordstatClusterViewSet,
    WordstatQueryViewSet,
    WordstatResultViewSet,
)  # noqa: F401
from .views_social import DzenRSSFeedView, TgChannelView, _ensure_rss_account_for_client  # noqa: F401

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

        limit_response = enforce_generation_limit(topic.client, GenerationEvent.EVENT_POST)
        if limit_response:
            return limit_response

        # Call existing Celery task
        task = tasks.generate_posts_for_topic.delay(topic.id)

        record_generation_event(
            topic.client,
            GenerationEvent.EVENT_POST,
            meta={"source": "topic", "topic_id": topic.id},
        )

        return Response({
            'success': True,
            'message': f'Post generation started for topic: {topic.name}',
            'task_id': task.id
        })

    @action(detail=True, methods=['post'], permission_classes=[IsTenantOwnerOrEditor])
    def generate_seo(self, request, pk=None):
        """Generate SEO keywords for the topic's client"""
        topic = self.get_object()

        limit_response = enforce_generation_limit(topic.client, GenerationEvent.EVENT_SEO_GROUP)
        if limit_response:
            return limit_response

        # Trigger client-level SEO generation (deduplicated per client)
        task = tasks.generate_seo_keywords_for_client.delay(topic.client_id)

        record_generation_event(
            topic.client,
            GenerationEvent.EVENT_SEO_GROUP,
            meta={"source": "topic", "topic_id": topic.id},
        )

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

        limit_response = enforce_generation_limit(trend.client, GenerationEvent.EVENT_POST)
        if limit_response:
            return limit_response

        # Call existing Celery task
        task = tasks.generate_post_from_trend.delay(trend.id)

        record_generation_event(
            trend.client,
            GenerationEvent.EVENT_POST,
            meta={"source": "trend", "trend_id": trend.id},
        )

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

        limit_response = enforce_generation_limit(story.client, GenerationEvent.EVENT_POST)
        if limit_response:
            return limit_response

        # Call existing Celery task
        task = tasks.generate_posts_from_story.delay(story.id)

        record_generation_event(
            story.client,
            GenerationEvent.EVENT_POST,
            meta={"source": "story", "story_id": story.id},
        )

        return Response({
            'success': True,
            'message': f'Generating posts from story: {story.title}',
            'task_id': task.id
        })



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
