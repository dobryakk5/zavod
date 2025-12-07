from __future__ import annotations

from rest_framework import serializers

from core.models import (
    Client,
    ContentTemplate,
    Post,
    PostTone,
    PostType,
    Schedule,
    SEOKeywordSet,
    SocialAccount,
    Story,
    Topic,
    TrendItem,
)


class PostSerializer(serializers.ModelSerializer):
    platforms = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "title", "status", "created_at", "platforms"]

    def get_platforms(self, obj: Post) -> list[str]:
        schedules = obj.schedules.all()
        return sorted({schedule.social_account.platform for schedule in schedules})


class ScheduleSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="social_account.platform")
    post_title = serializers.CharField(source="post.title")

    class Meta:
        model = Schedule
        fields = ["id", "platform", "post_title", "scheduled_at", "status"]


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


class PostDetailSerializer(serializers.ModelSerializer):
    """Detailed post serializer with all fields for create/update/retrieve."""

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "text",
            "image",
            "video",
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
        ]
        read_only_fields = [
            "id",
            "generated_by",
            "regeneration_count",
            "created_at",
            "updated_at",
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


class ClientSettingsSerializer(serializers.ModelSerializer):
    """
    Client settings serializer.
    Excludes 'id' and 'name' fields - they cannot be edited by users.
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
            "telegram_api_id",
            "telegram_api_hash",
            "telegram_source_channels",
            "rss_source_feeds",
            "youtube_api_key",
            "youtube_source_channels",
            "instagram_access_token",
            "instagram_source_accounts",
            "vkontakte_access_token",
            "vkontakte_source_groups",
        ]
        read_only_fields = ["slug"]  # slug is readonly



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
