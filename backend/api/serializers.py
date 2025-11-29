from __future__ import annotations

from rest_framework import serializers

from core.models import Post, Schedule


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
