from __future__ import annotations

from rest_framework import serializers

from core.models import (
    ChannelAnalysis,
    Client,
    ContentTemplate,
    Post,
    PostImage,
    PostTone,
    PostType,
    PostVideo,
    Schedule,
    SEOKeywordSet,
    SocialAccount,
    Story,
    Topic,
    TrendItem,
    VkIntegration,
)
from core.telegram_client import normalize_telegram_channel_identifier
from core.social_accounts import ensure_telegram_account_metadata
from core.social_accounts import sync_client_default_telegram_account


class PostSerializer(serializers.ModelSerializer):
    platforms = serializers.SerializerMethodField()
    template_name = serializers.CharField(source="template.name", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "title", "hook_title", "status", "created_at", "platforms", "template_name"]

    def get_platforms(self, obj: Post) -> list[str]:
        schedules = obj.schedules.all()
        return sorted({schedule.social_account.platform for schedule in schedules})


class ScheduleSerializer(serializers.ModelSerializer):
    post = serializers.PrimaryKeyRelatedField(queryset=Post.objects.all())
    social_account = serializers.PrimaryKeyRelatedField(queryset=SocialAccount.objects.all())
    platform = serializers.CharField(source="social_account.platform", read_only=True)
    post_title = serializers.CharField(source="post.title", read_only=True)
    social_account_name = serializers.CharField(source="social_account.name", read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id",
            "post",
            "post_title",
            "social_account",
            "social_account_name",
            "platform",
            "scheduled_at",
            "status",
        ]
        read_only_fields = ["platform", "post_title", "social_account_name", "status"]

    def validate(self, attrs):
        """
        Ensure that post and social account belong to the active client.
        """
        client = self.context.get("client")

        post = attrs.get("post") or getattr(self.instance, "post", None)
        social_account = attrs.get("social_account") or getattr(self.instance, "social_account", None)

        if client:
            if post and post.client_id != client.id:
                raise serializers.ValidationError("Пост не принадлежит текущему клиенту")
            if social_account and social_account.client_id != client.id:
                raise serializers.ValidationError("Аккаунт не принадлежит текущему клиенту")

        if post and social_account and post.client_id != social_account.client_id:
            raise serializers.ValidationError("Пост и аккаунт должны принадлежать одному клиенту")

        return attrs


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

    def get_width(self, obj):
        return obj.image.width if obj.image else None

    def get_height(self, obj):
        return obj.image.height if obj.image else None

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


class ContentTemplateSerializer(serializers.ModelSerializer):
    """
    Content template serializer.
    Type and tone are now editable to allow custom values.
    Length and language remain read-only after creation.
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
            "length",  # Keep readonly for now
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
            "access_token": {"write_only": True},
            "refresh_token": {"write_only": True},
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
            "timezone",
            "avatar",
            "pains",
            "desires",
            "objections",
            "expert_books",
            "telegram_client_channel",
            "ai_analysis_channel_url",
            "ai_analysis_channel_type",
            "telegram_source_channels",
            "rss_source_feeds",
            "youtube_source_channels",
            "instagram_source_accounts",
            "vkontakte_source_groups",
            "last_image_generation_at",
            "last_video_generation_at",
        ]
        read_only_fields = ["slug", "last_image_generation_at", "last_video_generation_at"]  # slug is readonly

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
                return value.strip()
            if isinstance(value, list):
                parts = [clean_text(item) for item in value]
                return "\n".join(part for part in parts if part)
            if isinstance(value, dict):
                parts = [clean_text(item) for item in value.values()]
                return "\n".join(part for part in parts if part)
            if value is None:
                return ""
            return str(value).strip()

        client = getattr(obj, "client", None)
        client_profile = {
            "avatar": clean_text(getattr(client, "avatar", "")) if client else "",
            "pains": clean_text(getattr(client, "pains", "")) if client else "",
            "desires": clean_text(getattr(client, "desires", "")) if client else "",
            "objections": clean_text(getattr(client, "objections", "")) if client else "",
        }

        normalized_profile = {}
        if isinstance(profile, dict):
            for key in ("avatar", "pains", "desires", "objections"):
                normalized_profile[key] = clean_text(profile.get(key)) or client_profile[key]
        else:
            normalized_profile = client_profile

        normalized["audience_profile"] = normalized_profile

        return normalized
