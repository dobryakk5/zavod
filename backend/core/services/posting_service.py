import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from ..models import Connection, PostJob, Schedule
from ..social_publishers import InstagramPublisher, YouTubePublisher
from .connection_service import ConnectionService

logger = logging.getLogger(__name__)


def update_post_status_after_publish(post):
    """
    Обновляет статус поста после успешной публикации.

    - Если все Schedule поста опубликованы (status='published'), то пост становится 'published'
    - Если есть хотя бы один опубликованный Schedule, но есть и другие, статус остается 'scheduled'
    """
    all_schedules = Schedule.objects.filter(post=post)

    if not all_schedules.exists():
        logger.warning("Нет Schedule для поста %s, не обновляем статус", post.id)
        return

    published_count = all_schedules.filter(status="published").count()
    total_count = all_schedules.count()

    if published_count == total_count:
        if post.status != "published":
            post.status = "published"
            post.save()
            logger.info("Пост %s обновлен на статус 'published' (%s/%s)", post.id, published_count, total_count)
    elif published_count > 0:
        if post.status not in ["published", "scheduled"]:
            post.status = "scheduled"
            post.save()
            logger.info("Пост %s обновлен на статус 'scheduled' (%s/%s)", post.id, published_count, total_count)


class PostingService:
    """Публикация контента в соцсети через Connection + PostJob."""

    def __init__(self) -> None:
        self.connection_service = ConnectionService()

    def publish_instagram(self, schedule: Schedule, assets: Dict[str, Any]) -> Dict[str, Any]:
        provider = "instagram"
        connection = self._get_connection(schedule, provider)
        payload = {
            "caption": assets.get("text") or "",
            "image_url": assets.get("image_url"),
            "video_url": assets.get("video_url"),
        }
        job = self._create_job(schedule, provider=provider, connection=connection, payload=payload)

        if not connection:
            error_msg = "Instagram Connection не найден для расписания"
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)
            return {"success": False, "error": error_msg}

        ig_account_id = (
            connection.account_id
            or (connection.metadata or {}).get("instagram_business_account_id")
            or (connection.metadata or {}).get("instagram_account_id")
            or (connection.metadata or {}).get("ig_user_id")
        )
        if not ig_account_id:
            error_msg = "Не указан instagram business account id в Connection"
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)
            return {"success": False, "error": error_msg}

        media_url, use_video = self._select_media(payload)
        if not media_url:
            error_msg = (
                "Для Instagram нужен публичный URL изображения или видео. "
                "Убедитесь, что MEDIA_URL доступен извне или настроен PUBLIC_MEDIA_BASE_URL/WAGTAILADMIN_BASE_URL."
            )
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)
            return {"success": False, "error": error_msg}

        self._start_job(job)
        publisher = InstagramPublisher(
            access_token=connection.access_token,
            business_account_id=str(ig_account_id),
        )

        result = publisher.publish_post(
            caption=payload["caption"],
            image_url=None if use_video else media_url,
            video_url=media_url if use_video else None,
        )

        if result.get("success"):
            media_id = str(result.get("media_id", ""))
            permalink = result.get("url", "") or ""
            self._succeed_job(job, remote_id=media_id, remote_url=permalink)
            self._success_schedule(schedule, f"Опубликовано в Instagram", media_id, permalink)
            update_post_status_after_publish(schedule.post)
        else:
            error_msg = result.get("error", "Instagram публикация завершилась с ошибкой")
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)

        return result

    def publish_youtube(self, schedule: Schedule, assets: Dict[str, Any]) -> Dict[str, Any]:
        provider = "youtube"
        connection = self._get_connection(schedule, provider)
        video_path = assets.get("video_path")
        if not video_path:
            error_msg = "Для публикации на YouTube требуется видеофайл"
            job = self._create_job(schedule, provider=provider, connection=connection, payload=assets)
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)
            return {"success": False, "error": error_msg}

        job = self._create_job(
            schedule,
            provider=provider,
            connection=connection,
            payload={
                "video_path": video_path,
                "title": assets.get("title"),
                "description": assets.get("text"),
            },
        )

        if not connection:
            error_msg = "YouTube Connection не найден для расписания"
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)
            return {"success": False, "error": error_msg}

        self._start_job(job)
        metadata = connection.metadata or {}
        client_id = metadata.get("client_id") or getattr(settings, "YOUTUBE_CLIENT_ID", None)
        client_secret = metadata.get("client_secret") or getattr(settings, "YOUTUBE_CLIENT_SECRET", None)
        token_uri = metadata.get("token_uri") or getattr(settings, "YOUTUBE_TOKEN_URI", None) or "https://oauth2.googleapis.com/token"
        privacy_status = metadata.get("privacy_status") or "public"

        publisher = YouTubePublisher(
            access_token=connection.access_token,
            refresh_token=connection.refresh_token or None,
            client_id=client_id,
            client_secret=client_secret,
            token_uri=token_uri,
        )

        description = (assets.get("text") or "").strip()[:5000]
        title = (assets.get("title") or getattr(schedule.post, "title", "") or "Видео").strip() or "Видео"

        result = publisher.publish_video(
            video_path=video_path,
            title=title,
            description=description,
            privacy_status=privacy_status,
        )

        if result.get("success"):
            video_id = str(result.get("video_id", ""))
            url = result.get("url", "") or ""
            self._succeed_job(job, remote_id=video_id, remote_url=url)
            self._success_schedule(schedule, "Опубликовано на YouTube", video_id, url)

            new_token = result.get("access_token")
            new_expiry = result.get("access_token_expires_at")
            fields_to_update = []
            if new_token and new_token != connection.access_token:
                connection.access_token = new_token
                fields_to_update.append("access_token")
            if new_expiry:
                connection.expires_at = new_expiry
                fields_to_update.append("expires_at")
            if fields_to_update:
                connection.save(update_fields=fields_to_update + ["updated_at"])

            update_post_status_after_publish(schedule.post)
        else:
            error_msg = result.get("error", "YouTube публикация завершилась с ошибкой")
            self._fail_job(job, error_msg)
            self._fail_schedule(schedule, error_msg)

        return result

    # Helpers
    def _get_connection(self, schedule: Schedule, provider: str) -> Optional[Connection]:
        connection = self.connection_service.get_connection_for_schedule(schedule, provider=provider)
        if connection and connection.provider != provider:
            logger.warning(
                "Connection %s provider mismatch for schedule %s: %s != %s",
                connection.id,
                schedule.id,
                connection.provider,
                provider,
            )
            return None
        return connection

    def _create_job(self, schedule: Schedule, *, provider: str, connection: Optional[Connection], payload: Dict[str, Any]) -> PostJob:
        return PostJob.objects.create(
            client=schedule.client,
            provider=provider,
            connection=connection,
            schedule=schedule,
            payload=payload or {},
        )

    def _start_job(self, job: PostJob) -> None:
        job.status = "processing"
        job.attempts += 1
        job.started_at = timezone.now()
        job.save(update_fields=["status", "attempts", "started_at", "updated_at"])

    def _succeed_job(self, job: PostJob, remote_id: str = "", remote_url: str = "") -> None:
        job.status = "succeeded"
        if remote_id:
            job.remote_id = remote_id
        if remote_url:
            job.remote_url = remote_url
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "remote_id", "remote_url", "finished_at", "updated_at"])

    def _fail_job(self, job: PostJob, error_msg: str) -> None:
        job.status = "failed"
        job.last_error = error_msg or job.last_error
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "last_error", "finished_at", "updated_at"])

    def _fail_schedule(self, schedule: Schedule, error_msg: str) -> None:
        schedule.status = "failed"
        schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
        schedule.save(update_fields=["status", "log"])
        logger.error("%s | schedule %s", error_msg, schedule.id)

    def _success_schedule(self, schedule: Schedule, message: str, external_id: str = "", remote_url: str = "") -> None:
        schedule.status = "published"
        if external_id:
            schedule.external_id = external_id
        suffix = f": {remote_url}" if remote_url else ""
        schedule.log = (schedule.log or "") + f"\n[SUCCESS] {message}{suffix}"
        schedule.save(update_fields=["status", "external_id", "log"])

    def _select_media(self, payload: Dict[str, Any]) -> tuple[Optional[str], bool]:
        video_url = payload.get("video_url")
        image_url = payload.get("image_url")
        if video_url:
            return video_url, True
        if image_url:
            return image_url, False
        return None, False
