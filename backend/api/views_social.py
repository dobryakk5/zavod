from __future__ import annotations

import html
import mimetypes
from email.utils import format_datetime

from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.html import linebreaks
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core import tasks
from core.models import ChannelAnalysis, Client, Post
from core.social_accounts import ensure_rss_zen_account
from core.social_publishers import build_absolute_media_url
from core.telegram_client import normalize_telegram_channel_identifier
from core.instagram_client import normalize_instagram_username
from core.youtube_client import normalize_youtube_identifier

from .utils import get_active_client


def _absolute_media_url(raw_url: str, request) -> str | None:
    """
    Resolve a media URL to an absolute URL, falling back to the current request host.
    """
    if not raw_url:
        return None

    url = build_absolute_media_url(raw_url)
    if url:
        return url

    try:
        return request.build_absolute_uri(raw_url)
    except Exception:
        return None


def _get_primary_image_info(post: Post, request):
    """
    Return dict with absolute URL, mime type and length for the first image, or None.
    """
    primary = post.get_primary_image()
    if not primary or not getattr(primary, "image", None):
        return None

    try:
        raw_url = primary.image.url
    except ValueError:
        return None

    image_url = _absolute_media_url(raw_url, request)
    if not image_url:
        return None

    mime_type, _ = mimetypes.guess_type(raw_url)
    try:
        length = primary.image.size
    except (OSError, ValueError):
        length = None

    return {
        "url": image_url,
        "type": mime_type or "image/jpeg",
        "length": length,
        "alt": primary.alt_text or post.title or "",
    }


def _format_pub_date(dt):
    if not dt:
        return ""
    try:
        return format_datetime(timezone.localtime(dt))
    except Exception:
        return timezone.localtime(dt).strftime("%a, %d %b %Y %H:%M:%S %z")


def _ensure_rss_account_for_client(client: Client, request) -> Client.social_accounts.rel.related_model | None:  # type: ignore
    try:
        feed_url = request.build_absolute_uri(reverse("rss-feed", args=[client.slug]))
    except Exception:
        feed_url = None
    return ensure_rss_zen_account(client, feed_url)


def _build_post_description(post: Post, request):
    image_info = _get_primary_image_info(post, request)
    parts: list[str] = []

    if image_info:
        parts.append(f'<p><img src="{image_info["url"]}" alt="{html.escape(image_info["alt"])}" /></p>')

    body = (post.text or "").strip()
    if body:
        parts.append(str(linebreaks(body)))

    description_html = "\n".join(parts)
    # Ensure CDATA is not prematurely closed
    safe_description = description_html.replace("]]>", "]]]]><![CDATA[>")
    return safe_description, image_info


class DzenRSSFeedView(APIView):
    """
    Public RSS feed for Yandex Zen consumption.
    """

    permission_classes = [AllowAny]
    authentication_classes: tuple = ()
    allowed_statuses = ("approved", "scheduled", "published")

    def get(self, request, client_slug: str, *args, **kwargs):
        from django.http import HttpResponse

        client = get_object_or_404(Client, slug=client_slug)

        try:
            limit = int(request.GET.get("limit", 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        posts_qs = (
            Post.objects.filter(client=client, status__in=self.allowed_statuses)
            .filter(schedules__social_account__platform="rss_zen")
            .exclude(schedules__status="failed")
            .exclude(text__isnull=True)
            .exclude(text__exact="")
            .prefetch_related("images")
            .order_by("-created_at")
            .distinct()
        )
        posts = list(posts_qs[:limit])

        channel_title = client.get_brand_display_name() or client.name or client.slug
        channel_link = request.build_absolute_uri("/")
        channel_description = f"RSS лента постов {channel_title} для Яндекс Дзена"
        last_build_date = _format_pub_date(posts[0].created_at if posts else timezone.now())

        items_xml: list[str] = []
        for post in posts:
            description_html, image_info = _build_post_description(post, request)
            post_link = request.build_absolute_uri(reverse("public-post", args=[client.slug, post.id]))

            enclosure_xml = ""
            if image_info:
                length_attr = f' length="{image_info["length"]}"' if image_info.get("length") else ""
                enclosure_xml = (
                    f'\n    <enclosure url="{html.escape(image_info["url"])}"'
                    f'{length_attr} type="{html.escape(image_info["type"])}" />'
                )

            items_xml.append(
                f"""    <item>
      <title>{html.escape(post.title)}</title>
      <link>{post_link}</link>
      <guid isPermaLink="false">post-{client.slug}-{post.id}</guid>
      <description><![CDATA[{description_html}]]></description>
      <pubDate>{_format_pub_date(post.created_at)}</pubDate>{enclosure_xml}
    </item>"""
            )

        items_block = "\n".join(items_xml)
        rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{html.escape(channel_title)}</title>
    <link>{channel_link}</link>
    <description>{html.escape(channel_description)}</description>
    <language>ru-RU</language>
    <lastBuildDate>{last_build_date}</lastBuildDate>
{items_block}
  </channel>
</rss>"""

        return HttpResponse(rss, content_type="application/rss+xml; charset=utf-8")


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
    SUPPORTED_TYPES = {"telegram", "instagram", "youtube"}

    def post(self, request):
        """Handle POST requests for analyze and validate actions"""
        action = request.data.get("action")

        if action == "analyze":
            return self._analyze_channel(request)
        if action == "validate":
            return self._validate_channel(request)
        return Response({"success": False, "error": f"Unknown action: {action}"}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """Handle GET requests for status action"""
        action = request.GET.get("action")
        task_id = request.GET.get("task_id")

        if action == "status" and task_id:
            setattr(request, "_data", {"action": "status", "task_id": task_id})
            return self._get_analysis_status(request)
        return Response({"success": False, "error": f"Unknown action: {action}"}, status=status.HTTP_400_BAD_REQUEST)

    def _normalize_channel_type(self, value):
        """Return normalized channel type if valid."""
        if not value:
            return ""
        normalized = str(value).strip().lower()
        return normalized if normalized in self.CHANNEL_TYPES else ""

    def _resolve_channel_config(self, request):
        """Return active client and resolved channel config."""
        client = get_active_client(request.user)
        data = getattr(request, "data", {}) or {}

        raw_url = (data.get("channel_url") or "").strip()
        raw_type = (data.get("channel_type") or "").strip()

        normalized_type = self._normalize_channel_type(raw_type)
        type_invalid = bool(raw_type and not normalized_type)

        stored_url = (client.ai_analysis_channel_url or "").strip()
        stored_type = self._normalize_channel_type(getattr(client, "ai_analysis_channel_type", ""))

        channel_url = raw_url or stored_url
        channel_type = normalized_type or stored_type

        updates = {}
        if raw_url and raw_url != stored_url:
            updates["ai_analysis_channel_url"] = raw_url
        if normalized_type and normalized_type != stored_type:
            updates["ai_analysis_channel_type"] = normalized_type

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
        if channel_type == "instagram":
            return normalize_instagram_username(channel_url)
        if channel_type == "youtube":
            return normalize_youtube_identifier(channel_url)
        return (channel_url or "").strip()

    def _analyze_channel(self, request):
        """Start channel analysis"""
        from .permissions import IsTenantOwnerOrEditor

        if not IsTenantOwnerOrEditor().has_permission(request, self):
            return Response({"success": False, "error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        client, channel_url, channel_type, type_invalid, updates = self._resolve_channel_config(request)

        if type_invalid:
            return Response(
                {
                    "success": False,
                    "error": f"Некорректный тип канала. Допустимые значения: {', '.join(sorted(self.CHANNEL_TYPES))}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not channel_url or not channel_type:
            return Response(
                {
                    "success": False,
                    "error": "Не указан канал для анализа. Добавьте channel_url и channel_type в запрос или сохраните их в настройках клиента.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if channel_type not in self.SUPPORTED_TYPES:
            allowed = ", ".join(sorted(self.SUPPORTED_TYPES))
            return Response({"success": False, "error": f"Пока поддерживаются только: {allowed}"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_identifier = self._normalize_identifier(channel_url, channel_type)
        if not normalized_identifier:
            return Response({"success": False, "error": "Не удалось распознать канал. Проверьте правильность ссылки."}, status=status.HTTP_400_BAD_REQUEST)

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
        analysis.save(update_fields=["task_id"])

        return Response(
            {
                "success": True,
                "message": "Анализ канала запущен",
                "task_id": analysis.task_id,
                "channel_url": channel_url,
                "channel_type": channel_type,
            }
        )

    def _validate_channel(self, request):
        """Validate channel URL"""
        _client, channel_url, channel_type, type_invalid, _updates = self._resolve_channel_config(request)

        if type_invalid:
            return Response(
                {
                    "valid": False,
                    "error": f"Некорректный тип канала. Допустимые значения: {', '.join(sorted(self.CHANNEL_TYPES))}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not channel_url or not channel_type:
            return Response(
                {
                    "valid": False,
                    "error": "channel_url и channel_type обязательны. Заполните канал в настройках клиента или передайте значения в запросе.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if channel_type not in self.SUPPORTED_TYPES:
            allowed = ", ".join(sorted(self.SUPPORTED_TYPES))
            return Response({"valid": False, "error": f"Пока поддерживаются только: {allowed}"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_identifier = self._normalize_identifier(channel_url, channel_type)
        if not normalized_identifier:
            return Response({"valid": False, "error": "Не удалось распознать канал. Проверьте правильность ссылки."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"valid": True, "normalized": normalized_identifier, "channel_type": channel_type})

    def _get_analysis_status(self, request):
        """Get analysis status"""
        client = get_active_client(request.user)
        data = getattr(request, "data", {}) or {}
        task_id = str(data.get("task_id") or "").strip()

        if not task_id:
            return Response({"success": False, "error": "task_id обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            analysis = ChannelAnalysis.objects.get(client=client, task_id=task_id)
        except ChannelAnalysis.DoesNotExist:
            return Response({"success": False, "error": "Анализ с таким task_id не найден"}, status=status.HTTP_404_NOT_FOUND)

        payload = {
            "task_id": analysis.task_id,
            "status": analysis.status,
            "progress": analysis.progress,
            "result": analysis.result if analysis.status == ChannelAnalysis.STATUS_COMPLETED else None,
        }

        if analysis.status == ChannelAnalysis.STATUS_FAILED:
            payload["error"] = analysis.error or "Анализ завершился с ошибкой"

        return Response(payload)

