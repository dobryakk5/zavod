from __future__ import annotations

import re
from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import (
    Article,
    ArticleBlock,
    ChannelAnalysis,
    Client,
    ClientProduct,
    Chain,
    ChainCondition,
    ChainEdge,
    ChainNode,
    ProductType,
    ContentTemplate,
    Connection,
    MindEdge,
    MindMap,
    MindNode,
    MindNodePosition,
    MindNodeProperty,
    KbFolder,
    KbDocument,
    KbDocumentVersion,
    KbComment,
    KbTag,
    KbDocumentTag,
    KbDocumentShare,
    Post,
    PostImage,
    PostTone,
    PostType,
    PostVideo,
    Schedule,
    SEOKeywordSet,
    ProjectSemanticSet,
    SocialAccount,
    Story,
    TelegramTask,
    Topic,
    TrendItem,
    VkIntegration,
    WebsiteScan,
    WebsiteScanPage,
    WordstatQuery,
    WordstatResult,
    WordstatCluster,
    WeeklySourceReport,
    WeeklySourceBatch,
    WeeklySalesPlan,
    WeeklyContentStrategy,
    ProjectChannelAnalysisRun,
    SemanticCluster,
    SemanticGroup,
    SemanticPhrase,
)
from core.services.product_type_templates import is_system_product_type_name
from core.telegram_client import normalize_telegram_channel_identifier
from core.social_accounts import ensure_telegram_account_metadata
from core.social_accounts import sync_client_default_telegram_account

User = get_user_model()


class PostSerializer(serializers.ModelSerializer):
    platforms = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True)
    has_images = serializers.SerializerMethodField()
    has_videos = serializers.SerializerMethodField()
    next_scheduled_at = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "hook_title",
            "status",
            "created_at",
            "platforms",
            "template_name",
            "has_images",
            "has_videos",
            "next_scheduled_at",
        ]

    def get_platforms(self, obj: Post) -> list[str]:
        schedules = obj.schedules.all()
        platforms = set()
        for schedule in schedules:
            if schedule.connection_id:
                platforms.add(schedule.connection.provider)
            elif schedule.social_account_id:
                platforms.add(schedule.social_account.platform)
        return sorted(platforms)

    def get_has_images(self, obj: Post) -> bool:
        annotated_count = getattr(obj, "images_count", None)
        if annotated_count is not None:
            return annotated_count > 0
        return obj.images.exists()

    def get_has_videos(self, obj: Post) -> bool:
        annotated_count = getattr(obj, "videos_count", None)
        if annotated_count is not None:
            return annotated_count > 0
        return obj.videos.exists()

    def get_next_scheduled_at(self, obj: Post):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("schedules")
        schedules = prefetched if prefetched is not None else obj.schedules.all()
        scheduled_dates = [item.scheduled_at for item in schedules if getattr(item, "scheduled_at", None)]
        if not scheduled_dates:
            return None
        return min(scheduled_dates)


class ScheduleSerializer(serializers.ModelSerializer):
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())
    social_account = serializers.PrimaryKeyRelatedField(queryset=SocialAccount.objects.all(), required=False, allow_null=True)
    connection = serializers.PrimaryKeyRelatedField(queryset=Connection.objects.all(), required=False, allow_null=True)
    platform = serializers.SerializerMethodField()
    post_title = serializers.CharField(source="post.title", read_only=True)
    social_account_name = serializers.CharField(source="social_account.name", read_only=True)
    connection_name = serializers.CharField(source="connection.name", read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id",
            "post",
            "post_title",
            "social_account",
            "social_account_name",
            "connection",
            "connection_name",
            "platform",
            "scheduled_at",
            "status",
        ]
        read_only_fields = ["platform", "post_title", "social_account_name", "connection_name", "status"]

    def validate(self, attrs):
        """
        Ensure that post and social account belong to the active client.
        """
        client = self.context.get("client")

        post = attrs.get("post") or getattr(self.instance, "post", None)
        social_account = attrs.get("social_account") or getattr(self.instance, "social_account", None)
        connection = attrs.get("connection") or getattr(self.instance, "connection", None)

        if client:
            if post and post.client_id != client.id:
                raise serializers.ValidationError("Пост не принадлежит текущему клиенту")
            if social_account and social_account.client_id != client.id:
                raise serializers.ValidationError("Аккаунт не принадлежит текущему клиенту")
            if connection and connection.client_id != client.id:
                raise serializers.ValidationError("Подключение не принадлежит текущему клиенту")

        if post and social_account and post.client_id != social_account.client_id:
            raise serializers.ValidationError("Пост и аккаунт должны принадлежать одному клиенту")
        if connection and post and connection.client_id != post.client_id:
            raise serializers.ValidationError("Пост и подключение должны принадлежать одному клиенту")
        if connection and social_account and connection.provider != social_account.platform:
            raise serializers.ValidationError("Платформа SocialAccount и Connection должны совпадать")
        if not social_account and not connection:
            raise serializers.ValidationError("Нужно указать social_account или connection для публикации")

        return attrs

    def get_platform(self, obj: Schedule) -> Optional[str]:
        if obj.connection_id:
            return obj.connection.provider
        if obj.social_account_id:
            return obj.social_account.platform
        return None


class TelegramTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramTask
        fields = [
            "id",
            "tg_name",
            "message_text",
            "received_at",
            "rating",
        ]

class PlatformCountSerializer(serializers.Serializer):
    platform = serializers.CharField()
    count = serializers.IntegerField()


class ClientSummarySerializer(serializers.Serializer):
    total_posts = serializers.IntegerField()
    posts_scheduled = serializers.IntegerField()
    posts_published = serializers.IntegerField()
    by_platform = PlatformCountSerializer(many=True)


# ============================================================================
# DETAILED SERIALIZERS FOR CRUD OPERATIONS
# ============================================================================


class PostImageSerializer(serializers.ModelSerializer):
    width = serializers.SerializerMethodField()
    height = serializers.SerializerMethodField()

    def _get_image_dimension(self, obj, attr: str):
        """
        Safely return image dimension without raising if the file is missing.
        """
        image = getattr(obj, "image", None)
        if not image or not getattr(image, "name", None):
            return None
        try:
            if not image.storage.exists(image.name):
                return None
            return getattr(image, attr)
        except (OSError, ValueError):
            return None

    def get_width(self, obj):
        return self._get_image_dimension(obj, "width")

    def get_height(self, obj):
        return self._get_image_dimension(obj, "height")

    class Meta:
        model = PostImage
        fields = ["id", "image", "alt_text", "order", "created_at", "updated_at", "width", "height"]
        read_only_fields = ["id", "image", "alt_text", "order", "created_at", "updated_at", "width", "height"]


class PostVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostVideo
        fields = ["id", "video", "caption", "order", "created_at", "updated_at"]
        read_only_fields = ["id", "video", "caption", "order", "created_at", "updated_at"]


class PostDetailSerializer(serializers.ModelSerializer):
    """Detailed post serializer with all fields for create/update/retrieve."""

    images = PostImageSerializer(many=True, read_only=True)
    videos = PostVideoSerializer(many=True, read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)
    template_type = serializers.CharField(source="template.type", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "hook_title",
            "text",
            "status",
            "tags",
            "source_links",
            "wordstat_phrases_used",
            "publish_text",
            "publish_image",
            "publish_video",
            "story",
            "episode_number",
            "generated_by",
            "regeneration_count",
            "created_at",
            "updated_at",
            "template",
            "template_name",
            "template_type",
            "images",
            "videos",
        ]
        read_only_fields = [
            "id",
            "generated_by",
            "regeneration_count",
            "created_at",
            "updated_at",
            "images",
            "videos",
            "template_name",
            "template_type",
            "wordstat_phrases_used",
        ]


class TopicSerializer(serializers.ModelSerializer):
    """Topic serializer for list/create operations."""

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "keywords",
            "is_active",
            "use_google_trends",
            "use_telegram",
            "use_rss",
            "use_youtube",
            "use_instagram",
            "use_vkontakte",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TopicDetailSerializer(serializers.ModelSerializer):
    """Detailed topic serializer with enabled sources."""

    enabled_sources = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            "id",
            "name",
            "keywords",
            "is_active",
            "use_google_trends",
            "use_telegram",
            "use_rss",
            "use_youtube",
            "use_instagram",
            "use_vkontakte",
            "enabled_sources",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_enabled_sources(self, obj: Topic) -> list[str]:
        return obj.get_enabled_sources()


class TrendItemSerializer(serializers.ModelSerializer):
    """Trend item serializer for list operations."""

    topic_name = serializers.CharField(source="topic.name", read_only=True)
    used_for_post_title = serializers.CharField(
        source="used_for_post.title", read_only=True, allow_null=True
    )

    class Meta:
        model = TrendItem
        fields = [
            "id",
            "topic",
            "topic_name",
            "source",
            "title",
            "description",
            "url",
            "relevance_score",
            "used_for_post",
            "used_for_post_title",
            "discovered_at",
        ]
        read_only_fields = ["id", "discovered_at"]


class TrendItemDetailSerializer(serializers.ModelSerializer):
    """Detailed trend item serializer."""

    topic_name = serializers.CharField(source="topic.name", read_only=True)

    class Meta:
        model = TrendItem
        fields = [
            "id",
            "topic",
            "topic_name",
            "source",
            "title",
            "description",
            "url",
            "relevance_score",
            "extra",
            "used_for_post",
            "discovered_at",
        ]
        read_only_fields = ["id", "discovered_at"]


class StorySerializer(serializers.ModelSerializer):
    """Story serializer for list operations."""

    trend_title = serializers.CharField(source="trend_item.title", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = Story
        fields = [
            "id",
            "title",
            "trend_item",
            "trend_title",
            "template",
            "template_name",
            "episode_count",
            "status",
            "generated_by",
            "created_at",
        ]
        read_only_fields = ["id", "generated_by", "created_at"]


class StoryDetailSerializer(serializers.ModelSerializer):
    """Detailed story serializer with episodes."""

    trend_title = serializers.CharField(source="trend_item.title", read_only=True)
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = Story
        fields = [
            "id",
            "title",
            "trend_item",
            "trend_title",
            "template",
            "template_name",
            "episode_count",
            "episodes",
            "status",
            "generated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "generated_by", "created_at", "updated_at"]


class ArticleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ["id", "wordstat", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = [
            "id",
            "wordstat",
            "wordstat_phrases",
            "status",
            "audience",
            "options_why_now",
            "options_solution",
            "selected_why_now",
            "selected_solution",
            "tripwire_product_id",
            "tripwire_product_name",
            "lead_product_id",
            "lead_product_name",
            "seo_blocks",
            "outline_markdown",
            "result_html",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "wordstat_phrases",
            "status",
            "options_why_now",
            "options_solution",
            "created_at",
            "updated_at",
        ]


class ArticleBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleBlock
        fields = [
            "id",
            "article",
            "order",
            "block_key",
            "h2_title",
            "subquery",
            "micro_intent",
            "keywords",
            "key_points",
            "prompt_template",
            "prompt_is_custom",
            "prompt_used",
            "content",
            "status",
            "regeneration_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "article", "created_at", "updated_at"]


class ContentTemplateSerializer(serializers.ModelSerializer):
    """
    Content template serializer.
    Type and tone are editable to allow custom values.
    Length is stored as a numeric target in symbols; language remains read-only for now.
    """

    is_system = serializers.SerializerMethodField()

    class Meta:
        model = ContentTemplate
        fields = [
            "id",
            "name",
            "type",
            "tone",
            "length",
            "language",
            "seo_prompt_template",
            "trend_prompt_template",
            "additional_instructions",
            "is_default",
            "include_hashtags",
            "max_hashtags",
            "is_system",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "language",  # Keep readonly for now
            "created_at",
            "updated_at",
        ]

    def get_is_system(self, obj):
        return obj.is_system


class SEOKeywordSetSerializer(serializers.ModelSerializer):
    """SEO keyword set serializer."""

    topic_name = serializers.CharField(source="topic.name", read_only=True)
    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = SEOKeywordSet
        fields = [
            "id",
            "client",
            "client_name",
             "group_type",
            "topic",
            "topic_name",
            "status",
            "keywords_list",
            "keyword_groups",
            "ai_model",
            "prompt_used",
            "error_log",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "group_type",
            "topic",
            "status",
            "keywords_list",
            "keyword_groups",
            "ai_model",
            "prompt_used",
            "error_log",
            "created_at",
        ]


class SemanticGroupSerializer(serializers.ModelSerializer):
    """Semantic group serializer."""

    client_name = serializers.CharField(source="client.name", read_only=True)
    clusters_count = serializers.SerializerMethodField()

    class Meta:
        model = SemanticGroup
        fields = [
            "id",
            "client",
            "client_name",
            "parent",
            "name",
            "description",
            "source_books",
            "scope",
            "expected_clusters",
            "status",
            "source",
            "clusters_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "client_name",
            "clusters_count",
            "created_at",
            "updated_at",
        ]

    def get_clusters_count(self, obj: SemanticGroup) -> int:
        annotated = getattr(obj, "clusters_count", None)
        if annotated is not None:
            try:
                return int(annotated)
            except (TypeError, ValueError):
                return 0
        return obj.clusters.count()


class SemanticClusterSerializer(serializers.ModelSerializer):
    """Semantic cluster serializer."""

    phrases_count = serializers.SerializerMethodField()

    class Meta:
        model = SemanticCluster
        fields = [
            "id",
            "client",
            "semantic_group",
            "name",
            "description",
            "main_keyword",
            "intent",
            "user_goal",
            "cta",
            "priority",
            "page_type",
            "url",
            "status",
            "phrases_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "semantic_group",
            "phrases_count",
            "created_at",
            "updated_at",
        ]

    def get_phrases_count(self, obj: SemanticCluster) -> int:
        annotated = getattr(obj, "phrases_count", None)
        if annotated is not None:
            try:
                return int(annotated)
            except (TypeError, ValueError):
                return 0
        return obj.phrases.count()


class SemanticPhraseSerializer(serializers.ModelSerializer):
    """Semantic phrase serializer."""

    phrase = serializers.SerializerMethodField()
    normalized_phrase = serializers.CharField(read_only=True)
    frequency = serializers.IntegerField(source="phrase.frequency", read_only=True)
    wordstat_id = serializers.IntegerField(source="phrase_id", read_only=True)

    def get_phrase(self, obj: SemanticPhrase) -> str | None:
        if getattr(obj, "normalized_phrase", None):
            return obj.normalized_phrase
        if getattr(obj, "phrase", None) and obj.phrase_id:
            return obj.phrase.phrase
        return None

    class Meta:
        model = SemanticPhrase
        fields = [
            "id",
            "client",
            "phrase",
            "raw_phrase",
            "normalized_phrase",
            "comment",
            "type",
            "intent",
            "source",
            "frequency",
            "wordstat_id",
            "competition",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "raw_phrase",
            "normalized_phrase",
            "wordstat_id",
            "created_at",
            "updated_at",
        ]


class ProjectSemanticSetSerializer(serializers.ModelSerializer):
    """Project semantic set serializer."""

    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = ProjectSemanticSet
        fields = [
            "id",
            "client",
            "client_name",
            "source",
            "status",
            "books_text",
            "keywords_list",
            "keyword_groups",
            "ai_model",
            "prompt_used",
            "error_log",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "source",
            "status",
            "books_text",
            "keywords_list",
            "keyword_groups",
            "ai_model",
            "prompt_used",
            "error_log",
            "created_at",
            "updated_at",
        ]


class WordstatResultSerializer(serializers.ModelSerializer):
    cluster_name = serializers.CharField(source="cluster.name", read_only=True)

    class Meta:
        model = WordstatResult
        fields = ["id", "phrase", "count", "result_type", "used_in_post", "cluster", "cluster_name"]
        read_only_fields = ["id", "phrase", "count", "used_in_post", "cluster_name"]


class WordstatClusterSerializer(serializers.ModelSerializer):
    phrases_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = WordstatCluster
        fields = ["id", "name", "is_main", "phrases_count", "created_at"]
        read_only_fields = ["id", "name", "phrases_count", "created_at"]


class WordstatQuerySerializer(serializers.ModelSerializer):
    results = WordstatResultSerializer(many=True, read_only=True)

    class Meta:
        model = WordstatQuery
        fields = [
            "id",
            "client",
            "group_name",
            "phrases",
            "request_phrase",
            "total_count",
            "include_parent",
            "regions",
            "devices",
            "user_login",
            "limit_per_second",
            "daily_limit",
            "daily_limit_remaining",
            "created_at",
            "results",
        ]
        read_only_fields = [
            "id",
            "client",
            "total_count",
            "user_login",
            "limit_per_second",
            "daily_limit",
            "daily_limit_remaining",
            "created_at",
            "results",
        ]


class SocialAccountSerializer(serializers.ModelSerializer):
    """Social account serializer."""

    class Meta:
        model = SocialAccount
        fields = [
            "id",
            "platform",
            "name",
            "access_token",
            "refresh_token",
            "extra",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "access_token": {
                "write_only": True,
                "allow_blank": True,
                "required": False,
                "default": "",
            },
            "refresh_token": {
                "write_only": True,
                "allow_blank": True,
            },
        }

    def _maybe_refresh_telegram(self, instance: SocialAccount, extra_payload):
        if instance.platform != "telegram":
            return

        channel_value = None
        if isinstance(extra_payload, dict):
            raw_channel = extra_payload.get("channel")
            if isinstance(raw_channel, str):
                channel_value = raw_channel

        ensure_telegram_account_metadata(
            instance,
            channel_value=channel_value,
            force_refresh=bool(channel_value),
        )

    def create(self, validated_data):
        extra_payload = validated_data.get("extra")
        instance = super().create(validated_data)
        self._maybe_refresh_telegram(instance, extra_payload)
        return instance

    def update(self, instance, validated_data):
        extra_payload = validated_data.get("extra")
        instance = super().update(instance, validated_data)
        self._maybe_refresh_telegram(instance, extra_payload)
        return instance


class VkIntegrationSerializer(serializers.ModelSerializer):
    """Serializer for VK integrations."""

    owner_name = serializers.SerializerMethodField()
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)

    class Meta:
        model = VkIntegration
        fields = [
            "id",
            "group_id",
            "group_name",
            "screen_name",
            "status",
            "last_published_at",
            "created_at",
            "updated_at",
            "owner_id",
            "owner_name",
            "extra",
        ]
        read_only_fields = fields

    def get_owner_name(self, obj: VkIntegration) -> str:
        full_name = obj.owner.get_full_name()
        return full_name or obj.owner.get_username()


class ClientSettingsSerializer(serializers.ModelSerializer):
    """
    Client settings serializer.
    Excludes 'id' and 'name' fields - they cannot be edited by users.
    Excludes secret fields - they cannot be accessed by frontend.
    """

    class Meta:
        model = Client
        fields = [
            "slug",
            "brand_name",
            "niche",
            "product_service",
            "timezone",
            "avatar",
            "pains",
            "desires",
            "objections",
            "expert_books",
            "telegram_client_channel",
            "ai_analysis_channel_url",
            "ai_analysis_channel_type",
            "project_telegram_channel",
            "project_instagram_channel",
            "project_youtube_channel",
            "telegram_source_channels",
            "rss_source_feeds",
            "youtube_source_channels",
            "instagram_source_accounts",
            "vkontakte_source_groups",
            "last_image_generation_at",
            "last_video_generation_at",
        ]
        read_only_fields = ["slug", "last_image_generation_at", "last_video_generation_at"]  # slug is readonly

    def validate_timezone(self, value: str | None) -> str:
        if value is None:
            return "Europe/Moscow"
        normalized = str(value).strip()
        if not normalized:
            return "Europe/Moscow"
        routing = {
            "Europe/Moscow UTC+3": "Europe/Moscow",
            "UTC+0": "UTC",
            "Europe/Helsinki UTC+2/UTC+3": "Europe/Helsinki",
            "Europe/London UTC+0/UTC+1": "Europe/London",
            "America/New_York UTC-5/UTC-4": "America/New_York",
            "Asia/Tokyo UTC+9": "Asia/Tokyo",
        }
        return routing.get(normalized, normalized)

    def validate_telegram_client_channel(self, value: str | None) -> str:
        if not value:
            return ""
        return normalize_telegram_channel_identifier(str(value))

    def update(self, instance, validated_data):
        channel_provided = "telegram_client_channel" in validated_data
        updated_client = super().update(instance, validated_data)
        if channel_provided:
            sync_client_default_telegram_account(
                updated_client,
                channel_value=validated_data.get("telegram_client_channel"),
            )
        return updated_client



class PostTypeSerializer(serializers.ModelSerializer):
    """Serializer for PostType (справочник типов постов)"""

    class Meta:
        model = PostType
        fields = ["id", "value", "label", "is_default", "created_at"]
        read_only_fields = ["id", "is_default", "created_at"]


class PostToneSerializer(serializers.ModelSerializer):
    """Serializer for PostTone (справочник тонов постов)"""

    class Meta:
        model = PostTone
        fields = ["id", "value", "label", "is_default", "created_at"]
        read_only_fields = ["id", "is_default", "created_at"]


class ChannelAnalysisListSerializer(serializers.ModelSerializer):
    """Short serializer for displaying channel analyses."""

    channel_name = serializers.SerializerMethodField()

    class Meta:
        model = ChannelAnalysis
        fields = [
            "id",
            "channel_url",
            "channel_type",
            "task_id",
            "status",
            "progress",
            "channel_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_channel_name(self, obj: ChannelAnalysis) -> str | None:
        result = obj.result or {}
        if isinstance(result, dict):
            return result.get("channel_name") or None
        return None


class ChannelAnalysisDetailSerializer(ChannelAnalysisListSerializer):
    """Detailed serializer with AI result payload."""

    result = serializers.SerializerMethodField()
    error = serializers.CharField(allow_blank=True)

    class Meta(ChannelAnalysisListSerializer.Meta):
        fields = ChannelAnalysisListSerializer.Meta.fields + ["result", "error"]
        read_only_fields = fields

    def get_result(self, obj: ChannelAnalysis):
        if obj.status != ChannelAnalysis.STATUS_COMPLETED:
            return None

        result = obj.result or {}
        if not isinstance(result, dict):
            return result

        normalized = dict(result)
        normalized["avg_reactions"] = normalized.get("avg_reactions", normalized.get("avg_likes", 0) or 0)
        normalized["avg_comments"] = normalized.get("avg_comments", 0)
        if "avg_likes" in normalized:
            normalized.pop("avg_likes")
        if "avg_reach" in normalized:
            normalized.pop("avg_reach")

        top_posts = normalized.get("top_posts") or []
        normalized_posts = []
        for post in top_posts:
            if not isinstance(post, dict):
                continue
            entry = dict(post)
            entry["reactions"] = entry.get("reactions", entry.get("likes", 0) or 0)
            if "likes" in entry:
                entry.pop("likes")
            normalized_posts.append(entry)
        normalized["top_posts"] = normalized_posts

        profile = normalized.get("audience_profile") or {}

        def clean_text(value):
            if isinstance(value, str):
                collapsed = re.sub(r"[ \t]+", " ", value)
                collapsed = re.sub(r"\n{2,}", "\n", collapsed)
                return collapsed.strip()
            if isinstance(value, list):
                parts = [clean_text(item) for item in value]
                return "\n".join(part for part in parts if part)
            if isinstance(value, dict):
                parts = [clean_text(item) for item in value.values()]
                return "\n".join(part for part in parts if part)
            if value is None:
                return ""
            return str(value).strip()

        normalized_profile = {}
        if isinstance(profile, dict):
            for key in ("avatar", "pains", "desires", "objections"):
                normalized_profile[key] = clean_text(profile.get(key))
        else:
            normalized_profile = {key: "" for key in ("avatar", "pains", "desires", "objections")}

        normalized["audience_profile"] = normalized_profile

        return normalized


class ProjectChannelAnalysisRunListSerializer(serializers.ModelSerializer):
    """Short serializer for project channel analysis runs."""

    class Meta:
        model = ProjectChannelAnalysisRun
        fields = [
            "id",
            "task_id",
            "status",
            "progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProjectChannelAnalysisRunDetailSerializer(ProjectChannelAnalysisRunListSerializer):
    """Detailed serializer for project channel analysis runs with payload."""

    result = serializers.SerializerMethodField()
    error = serializers.CharField(allow_blank=True)

    class Meta(ProjectChannelAnalysisRunListSerializer.Meta):
        fields = ProjectChannelAnalysisRunListSerializer.Meta.fields + ["result", "error"]
        read_only_fields = fields

    def get_result(self, obj: ProjectChannelAnalysisRun):
        if obj.status != ProjectChannelAnalysisRun.STATUS_COMPLETED:
            return None
        return obj.result


class WebsiteScanCreateSerializer(serializers.Serializer):
    base_url = serializers.CharField()
    max_depth = serializers.IntegerField(required=False, min_value=0, max_value=10, default=3)
    max_pages = serializers.IntegerField(required=False, min_value=1, max_value=500, default=100)


class WebsiteScanListSerializer(serializers.ModelSerializer):
    pages_count = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = WebsiteScan
        fields = [
            "id",
            "base_url",
            "status",
            "progress",
            "max_depth",
            "max_pages",
            "pages_total",
            "mind_map_id",
            "error",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "pages_count",
        ]
        read_only_fields = fields


class WebsiteScanDetailSerializer(WebsiteScanListSerializer):
    class Meta(WebsiteScanListSerializer.Meta):
        fields = WebsiteScanListSerializer.Meta.fields + [
            "task_id",
            "robots_url",
            "robots_txt",
            "sitemap_urls",
        ]
        read_only_fields = fields


class WebsiteScanPageSerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = WebsiteScanPage
        fields = [
            "id",
            "url",
            "parent_id",
            "depth",
            "status_code",
            "content_type",
            "title",
            "meta_description",
            "headings",
            "wordstats",
            "cluster_level_1",
            "cluster_level_2",
            "cluster_level_3",
            "cluster_source",
            "can_fetch_all",
            "can_fetch_googlebot",
            "fetched_at",
        ]
        read_only_fields = fields


class WeeklySourceReportSerializer(serializers.ModelSerializer):
    """Serializer for weekly source reports."""

    class Meta:
        model = WeeklySourceReport
        fields = [
            "id",
            "batch_id",
            "source_type",
            "source_value",
            "week_start",
            "status",
            "summary",
            "links",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WeeklySourceBatchSerializer(serializers.ModelSerializer):
    reports = WeeklySourceReportSerializer(many=True, read_only=True)

    class Meta:
        model = WeeklySourceBatch
        fields = [
            "id",
            "week_start",
            "status",
            "created_at",
            "updated_at",
            "reports",
        ]
        read_only_fields = fields


class WeeklySourceBatchListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklySourceBatch
        fields = [
            "id",
            "week_start",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WeeklySalesPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklySalesPlan
        fields = [
            "id",
            "week_start",
            "cold_leads_plan",
            "cold_leads_fact",
            "hot_leads_plan",
            "hot_leads_fact",
            "sales_plan",
            "sales_fact",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class WeeklyContentStrategySerializer(serializers.ModelSerializer):
    def validate_wordstat_cluster_ids(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается список Wordstat-кластеров.")

        cleaned: list[int] = []
        for item in value:
            try:
                cluster_id = int(item)
            except (TypeError, ValueError):
                raise serializers.ValidationError("Некорректный идентификатор Wordstat-кластера.")
            if cluster_id <= 0:
                raise serializers.ValidationError("Некорректный идентификатор Wordstat-кластера.")
            if cluster_id not in cleaned:
                cleaned.append(cluster_id)

        client = self.context.get("client")
        if client and cleaned:
            valid_ids = set(
                WordstatCluster.objects.filter(client=client, is_main=False, id__in=cleaned).values_list("id", flat=True)
            )
            if len(valid_ids) != len(cleaned):
                raise serializers.ValidationError("Некоторые кластеры недоступны для выбора.")

        return cleaned

    class Meta:
        model = WeeklyContentStrategy
        fields = [
            "id",
            "week_start",
            "comment",
            "wordstat_cluster_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ============================================================================
# Mind maps
# ============================================================================


class MindNodePositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MindNodePosition
        fields = ["layout_name", "x", "y"]
        extra_kwargs = {"layout_name": {"required": False, "default": "default"}}


class MindNodePropertySerializer(serializers.ModelSerializer):
    node = serializers.PrimaryKeyRelatedField(queryset=MindNode.objects.all(), write_only=True, required=False)
    node_id = serializers.UUIDField(read_only=True)
    value = serializers.CharField(allow_blank=True)

    class Meta:
        model = MindNodeProperty
        fields = [
            "id",
            "node",
            "node_id",
            "title",
            "value",
            "delta",
            "order_index",
            "meta",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "node_id", "created_at", "updated_at"]
        extra_kwargs = {"node": {"write_only": True}}


class MindNodeSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    map_id = serializers.IntegerField(read_only=True)
    position = MindNodePositionSerializer(read_only=True)
    properties = MindNodePropertySerializer(many=True, read_only=True)

    class Meta:
        model = MindNode
        fields = [
            "id",
            "map_id",
            "text",
            "color",
            "shape",
            "meta",
            "position",
            "created_at",
            "updated_at",
            "properties",
        ]
        read_only_fields = ["map_id", "created_at", "updated_at", "position", "properties"]


class MindEdgeSerializer(serializers.ModelSerializer):
    map_id = serializers.IntegerField(read_only=True)
    from_node_id = serializers.PrimaryKeyRelatedField(
        queryset=MindNode.objects.all(),
        source="from_node",
    )
    to_node_id = serializers.PrimaryKeyRelatedField(
        queryset=MindNode.objects.all(),
        source="to_node",
    )

    class Meta:
        model = MindEdge
        fields = [
            "id",
            "map_id",
            "from_node_id",
            "to_node_id",
            "type",
            "label",
            "meta",
            "created_at",
        ]
        read_only_fields = ["id", "map_id", "created_at"]

    def validate(self, attrs):
        from_node = attrs.get("from_node")
        to_node = attrs.get("to_node")

        if from_node and to_node and from_node.id == to_node.id:
            raise serializers.ValidationError("Связь не может ссылаться на один и тот же узел")

        return attrs


class MindMapSerializer(serializers.ModelSerializer):
    nodes_count = serializers.IntegerField(read_only=True)
    edges_count = serializers.IntegerField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MindMap
        fields = [
            "id",
            "title",
            "description",
            "type",
            "is_public",
            "owner_id",
            "created_at",
            "updated_at",
            "nodes_count",
            "edges_count",
        ]
        read_only_fields = ["id", "type", "owner_id", "created_at", "updated_at", "nodes_count", "edges_count"]


class MindMapDetailSerializer(MindMapSerializer):
    nodes = MindNodeSerializer(many=True, read_only=True)
    edges = MindEdgeSerializer(many=True, read_only=True)

    class Meta(MindMapSerializer.Meta):
        fields = MindMapSerializer.Meta.fields + ["nodes", "edges"]


# ============================================================================
# Knowledge base
# ============================================================================


class KbUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = ["id"]


class KbFolderSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)
    documents_count = serializers.SerializerMethodField()
    subfolders_count = serializers.SerializerMethodField()

    class Meta:
        model = KbFolder
        fields = [
            "id",
            "name",
            "workspace",
            "parent",
            "created_by",
            "created_at",
            "updated_at",
            "position",
            "documents_count",
            "subfolders_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "workspace"]

    def get_documents_count(self, obj):
        return obj.documents.filter(is_archived=False).count()

    def get_subfolders_count(self, obj):
        return obj.subfolders.count()


class KbFolderTreeSerializer(KbFolderSerializer):
    children = serializers.SerializerMethodField()

    class Meta(KbFolderSerializer.Meta):
        fields = KbFolderSerializer.Meta.fields + ["children"]

    def get_children(self, obj):
        children = obj.subfolders.all().order_by("position", "id")
        return KbFolderTreeSerializer(children, many=True, context=self.context).data


class KbTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = KbTag
        fields = ["id", "name", "color", "workspace", "created_at"]
        read_only_fields = ["id", "created_at", "workspace"]


class KbDocumentListSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)
    last_edited_by = KbUserSerializer(read_only=True)
    tags = KbTagSerializer(many=True, read_only=True)
    child_count = serializers.SerializerMethodField()

    class Meta:
        model = KbDocument
        fields = [
            "id",
            "title",
            "icon",
            "cover_image",
            "workspace",
            "folder",
            "parent_document",
            "created_by",
            "last_edited_by",
            "created_at",
            "updated_at",
            "is_published",
            "is_archived",
            "is_template",
            "position",
            "tags",
            "child_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "workspace"]

    def get_child_count(self, obj):
        return obj.child_documents.count()


class KbDocumentDetailSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)
    last_edited_by = KbUserSerializer(read_only=True)
    tags = KbTagSerializer(many=True, read_only=True)
    child_documents = KbDocumentListSerializer(many=True, read_only=True)

    class Meta:
        model = KbDocument
        fields = [
            "id",
            "title",
            "icon",
            "cover_image",
            "content",
            "workspace",
            "folder",
            "parent_document",
            "created_by",
            "last_edited_by",
            "created_at",
            "updated_at",
            "is_published",
            "is_archived",
            "is_template",
            "position",
            "tags",
            "child_documents",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by", "workspace"]

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            instance.last_edited_by = request.user
        return super().update(instance, validated_data)


class KbDocumentVersionSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)

    class Meta:
        model = KbDocumentVersion
        fields = [
            "id",
            "document",
            "content",
            "title",
            "created_by",
            "created_at",
            "version_number",
        ]
        read_only_fields = ["id", "created_at", "version_number", "created_by"]


class KbCommentSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = KbComment
        fields = [
            "id",
            "document",
            "parent_comment",
            "content",
            "block_id",
            "created_by",
            "created_at",
            "updated_at",
            "is_resolved",
            "replies",
            "replies_count",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    def get_replies(self, obj):
        if obj.parent_comment is None:
            replies = obj.replies.all()
            return KbCommentSerializer(replies, many=True, context=self.context).data
        return []

    def get_replies_count(self, obj):
        return obj.replies.count()


class KbDocumentShareSerializer(serializers.ModelSerializer):
    created_by = KbUserSerializer(read_only=True)
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = KbDocumentShare
        fields = [
            "id",
            "document",
            "share_token",
            "permission",
            "password",
            "expires_at",
            "created_by",
            "created_at",
            "is_active",
            "visit_count",
            "share_url",
        ]
        read_only_fields = ["id", "share_token", "created_at", "visit_count", "created_by"]

    def get_share_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/kb/share/{obj.share_token}")
        return f"/kb/share/{obj.share_token}"


class KbDocumentTagSerializer(serializers.ModelSerializer):
    tag = KbTagSerializer(read_only=True)
    tag_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = KbDocumentTag
        fields = ["id", "document", "tag", "tag_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class KbDocumentMoveSerializer(serializers.Serializer):
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    parent_document_id = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.IntegerField(required=False)


class KbDocumentDuplicateSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    include_children = serializers.BooleanField(default=False)


class KbBulkDocumentArchiveSerializer(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
    archive = serializers.BooleanField(default=True)


class ChainSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Chain
        fields = [
            "id",
            "tenant_id",
            "name",
            "description",
            "status",
            "start_node_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance


class ChainNodeSerializer(serializers.ModelSerializer):
    chain_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChainNode
        fields = [
            "id",
            "chain_id",
            "node_type",
            "payload",
            "delay_seconds",
            "pos_x",
            "pos_y",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "chain_id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance


class ChainEdgeSerializer(serializers.ModelSerializer):
    chain_id = serializers.IntegerField(read_only=True)
    source_node_id = serializers.PrimaryKeyRelatedField(
        queryset=ChainNode.objects.all(),
        source="source_node",
    )
    target_node_id = serializers.PrimaryKeyRelatedField(
        queryset=ChainNode.objects.all(),
        source="target_node",
    )

    class Meta:
        model = ChainEdge
        fields = [
            "id",
            "chain_id",
            "source_node_id",
            "source_port_id",
            "target_node_id",
            "priority",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "chain_id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance


class ChainConditionSerializer(serializers.ModelSerializer):
    edge_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChainCondition
        fields = [
            "id",
            "edge_id",
            "condition_type",
            "params",
            "created_at",
        ]
        read_only_fields = ["id", "edge_id", "created_at"]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        return instance


class ClientProductSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(read_only=True)
    product_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductType.objects.all(),
        source="product_type",
        required=False,
        allow_null=True,
    )
    product_type_name = serializers.CharField(source="product_type.name", read_only=True)
    product_type = serializers.SerializerMethodField()

    def get_product_type(self, obj: ClientProduct):
        product_type = getattr(obj, "product_type", None)
        if not product_type:
            return None
        return ProductTypeSerializer(product_type).data

    class Meta:
        model = ClientProduct
        fields = [
            "id",
            "name",
            "product_type_id",
            "product_type_name",
            "product_type",
            "short_description",
            "packages",
            "structure",
            "owner_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_id", "created_at", "updated_at"]


class ProductTypeSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(read_only=True)
    is_deletable = serializers.SerializerMethodField()

    def get_is_deletable(self, obj: ProductType) -> bool:
        return not is_system_product_type_name(getattr(obj, "name", None))

    class Meta:
        model = ProductType
        fields = [
            "id",
            "name",
            "value",
            "goal",
            "requirements_name",
            "requirements_packages",
            "requirements_audience",
            "requirements_transformation",
            "requirements_metrics",
            "requirements_method",
            "requirements_lesson_format",
            "requirements_program_modules",
            "requirements_packaging",
            "owner_id",
            "is_deletable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_id", "is_deletable", "created_at", "updated_at"]
