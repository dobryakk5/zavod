from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.celery import app as celery_app

from core import tasks
from core.models import ContentTemplate, Post, PostImage, PostTone, PostType, PostVideo, Schedule, SocialAccount
from core.system_settings import get_image_generation_model, get_image_generation_method

from .permissions import CanGenerateVideo, IsTenantMember, IsTenantOwnerOrEditor
from .serializers import PostDetailSerializer, PostSerializer, PostToneSerializer, PostTypeSerializer
from .utils import get_active_client

logger = logging.getLogger(__name__)

MAX_WEEKLY_POSTS = 21
MEDIA_GENERATION_COOLDOWN = timedelta(hours=1)


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


class PostsListView(generics.ListAPIView):
    serializer_class = PostSerializer

    def get_queryset(self):
        client = get_active_client(self.request.user)
        queryset = (
            Post.objects.filter(client=client)
            .annotate(
                images_count=Count("images", distinct=True),
                videos_count=Count("videos", distinct=True),
            )
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


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Post CRUD operations and generation actions.
    Reuses existing functions from core.tasks and core.views.
    """

    permission_classes = [IsTenantMember]

    def get_permissions(self):
        """Different permissions for different actions"""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsTenantOwnerOrEditor()]
        return [IsTenantMember()]

    def get_serializer_class(self):
        """Use detailed serializer for retrieve, create, update"""
        if self.action in ["retrieve", "create", "update", "partial_update"]:
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

    @action(detail=True, methods=["post"], permission_classes=[IsTenantOwnerOrEditor])
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
                    "success": False,
                    "error": _format_cooldown_message("изображения", remaining),
                    "cooldown_seconds": int(remaining.total_seconds()),
                    "cooldown_ends_at": cooldown_ends_at,
                    "cooldown_type": "image",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        model_param = (request.data.get("model") or "").lower()

        if not model_param:
            model = get_image_generation_method()
        else:
            alias_map = {
                "nanobanana": "openrouter",
                "pollinations": "openrouter",
                "huggingface": "openrouter",
                "flux2": "openrouter",
                "sora_images": "veo_photo",
                "telegram_bot": "veo_photo",
                "veo": "veo_photo",
                "giga": "giga_photo",
            }
            model = alias_map.get(model_param, model_param)

        allowed_models = {"openrouter", "veo_photo", "giga_photo"}
        if model not in allowed_models:
            return Response(
                {"success": False, "error": f'Unknown image model "{model_param}"'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = tasks.generate_image_for_post.delay(post.id, model=model)
        client.last_image_generation_at = timezone.now()
        client.save(update_fields=["last_image_generation_at"])

        model_names = {
            "openrouter": f"OpenRouter ({get_image_generation_model()})",
            "veo_photo": "VEO (Telegram)",
        }

        return Response(
            {
                "success": True,
                "message": f"Image generation started: {model_names.get(model, model)}",
                "task_id": task.id,
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[CanGenerateVideo, IsTenantOwnerOrEditor])
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
            return Response(
                {
                    "success": False,
                    "error": _format_cooldown_message("видео", remaining),
                    "cooldown_seconds": int(remaining.total_seconds()),
                    "cooldown_ends_at": cooldown_ends_at,
                    "cooldown_type": "video",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        method = (request.data.get("method") or "wan").lower()
        allowed_methods = {"wan", "veo"}
        if method not in allowed_methods:
            return Response({"success": False, "error": f'Unknown video method "{method}"'}, status=status.HTTP_400_BAD_REQUEST)

        source = (request.data.get("source") or "image").lower()
        allowed_sources = {"image", "text"}
        if source not in allowed_sources:
            return Response({"success": False, "error": f'Unknown video source "{source}"'}, status=status.HTTP_400_BAD_REQUEST)

        if source == "image" and not post.images.exists():
            return Response({"success": False, "error": "Post must have an image before generating video"}, status=status.HTTP_400_BAD_REQUEST)

        if source == "text" and not post.text:
            return Response({"success": False, "error": "Post must have text before generating text-based video"}, status=status.HTTP_400_BAD_REQUEST)

        if source == "text" and method != "veo":
            return Response({"success": False, "error": "Text-based video currently supported only via VEO"}, status=status.HTTP_400_BAD_REQUEST)

        task = tasks.generate_video_from_image.delay(post.id, method=method, source=source)
        client.last_video_generation_at = timezone.now()
        client.save(update_fields=["last_video_generation_at"])

        return Response({"success": True, "message": f"Video generation started ({method}/{source})", "task_id": task.id})

    @action(detail=True, methods=["post"], permission_classes=[IsTenantOwnerOrEditor])
    def regenerate_text(self, request, pk=None):
        """Regenerate post text using AI"""
        post = self.get_object()
        task = tasks.regenerate_post_text.delay(post.id)
        return Response({"success": True, "message": "Text regeneration started", "task_id": task.id})

    @action(detail=True, methods=["post"], permission_classes=[IsTenantOwnerOrEditor])
    def quick_publish(self, request, pk=None):
        """
        Quick publish post to a social account without creating schedule.
        Requires social_account_id in request body.
        """
        post = self.get_object()
        social_account_id = request.data.get("social_account_id")

        if not social_account_id:
            return Response({"success": False, "error": "social_account_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        social_account = get_object_or_404(SocialAccount, id=social_account_id)

        if social_account.client != post.client:
            return Response({"success": False, "error": "Social account does not belong to post client"}, status=status.HTTP_403_FORBIDDEN)

        schedule = Schedule.objects.create(
            client=post.client,
            post=post,
            social_account=social_account,
            scheduled_at=timezone.now(),
            status="pending",
        )

        task = tasks.publish_schedule.delay(schedule.id)

        return Response(
            {
                "success": True,
                "message": "Publishing started",
                "schedule_id": schedule.id,
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["post"], url_path="plan-weekly", permission_classes=[IsTenantOwnerOrEditor])
    def plan_weekly(self, request):
        """Запустить генерацию постов на следующую неделю по выбранному шаблону."""

        client = get_active_client(request.user)
        template_id = request.data.get("template_id")
        posts_per_week = request.data.get("posts_per_week")
        social_account_id = request.data.get("social_account_id")

        try:
            template_id_int = int(template_id)
        except (TypeError, ValueError):
            return Response({"error": "Укажите корректный шаблон"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            posts_count = int(posts_per_week)
        except (TypeError, ValueError):
            return Response({"error": "Некорректное количество постов"}, status=status.HTTP_400_BAD_REQUEST)

        if posts_count <= 0 or posts_count > MAX_WEEKLY_POSTS:
            return Response({"error": f"Количество постов должно быть от 1 до {MAX_WEEKLY_POSTS}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            template = ContentTemplate.get_for_client_or_system(client, template_id_int)
        except ContentTemplate.DoesNotExist:
            return Response({"error": "Шаблон недоступен"}, status=status.HTTP_404_NOT_FOUND)

        social_account_id_int = None
        if social_account_id is not None:
            try:
                social_account_id_int = int(social_account_id)
            except (TypeError, ValueError):
                return Response({"error": "Некорректный ID соц. аккаунта"}, status=status.HTTP_400_BAD_REQUEST)

            if not SocialAccount.objects.filter(id=social_account_id_int, client=client).exists():
                return Response({"error": "Соц. аккаунт не найден"}, status=status.HTTP_404_NOT_FOUND)

        task = tasks.generate_weekly_posts_from_template.delay(
            client.id,
            template.id,
            posts_count,
            request.user.id if request.user and request.user.is_authenticated else None,
            social_account_id_int,
        )

        return Response(
            {
                "success": True,
                "message": f"Запущена генерация {posts_count} постов по шаблону «{template.name}»",
                "task_id": task.id,
            }
        )

    @action(detail=False, methods=["get"], url_path="generation-status", permission_classes=[IsTenantMember])
    def generation_status(self, request):
        """Вернуть состояние задачи генерации постов по task_id."""
        task_id = request.query_params.get("task_id")
        if not task_id:
            return Response({"success": False, "error": "task_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            async_result = celery_app.AsyncResult(task_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to fetch generation status for %s: %s", task_id, exc, exc_info=True)
            return Response({"success": False, "error": "Не удалось получить статус задачи"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        state = (async_result.state or "").lower()
        payload = {"success": state == "success", "status": state, "task_id": task_id}

        if state == "success" and isinstance(async_result.result, dict):
            payload["result"] = async_result.result
        elif state in ("failure", "revoked"):
            error_info = getattr(async_result, "info", None)
            payload["error"] = str(error_info) if error_info else "Задача завершилась с ошибкой"

        return Response(payload)

    @action(detail=True, methods=["delete"], permission_classes=[IsTenantOwnerOrEditor])
    def delete_image(self, request, pk=None):
        """
        Delete a specific image from the post.
        Requires image_id in query parameters.
        """
        post = self.get_object()
        image_id = request.query_params.get("image_id")

        if not image_id:
            return Response({"success": False, "error": "image_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            image_id_int = int(image_id)
        except (TypeError, ValueError):
            return Response({"success": False, "error": "image_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            image = PostImage.objects.get(id=image_id_int, post=post)
        except PostImage.DoesNotExist:
            return Response({"success": False, "error": "Image not found or does not belong to this post"}, status=status.HTTP_404_NOT_FOUND)

        if image.image:
            image.image.delete(save=False)
        image.delete()

        return Response({"success": True, "message": "Image deleted successfully"})

    @action(detail=True, methods=["delete"], permission_classes=[IsTenantOwnerOrEditor])
    def delete_video(self, request, pk=None):
        """
        Delete a specific video from the post.
        Requires video_id in query parameters.
        """
        post = self.get_object()
        video_id = request.query_params.get("video_id")

        if not video_id:
            return Response({"success": False, "error": "video_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            video_id_int = int(video_id)
        except (TypeError, ValueError):
            return Response({"success": False, "error": "video_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            video = PostVideo.objects.get(id=video_id_int, post=post)
        except PostVideo.DoesNotExist:
            return Response({"success": False, "error": "Video not found or does not belong to this post"}, status=status.HTTP_404_NOT_FOUND)

        if video.video:
            video.video.delete(save=False)
        video.delete()

        return Response({"success": True, "message": "Video deleted successfully"})


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
        return PostType.objects.filter(Q(client__isnull=True) | Q(client=client)).order_by("label")

    def perform_create(self, serializer):
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
        return PostTone.objects.filter(Q(client__isnull=True) | Q(client=client)).order_by("label")

    def perform_create(self, serializer):
        serializer.save(client=None)

