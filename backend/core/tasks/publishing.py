from celery import shared_task
from django.utils import timezone
import logging

from ..models import Schedule
from ..social_publishers import (
    InstagramPublisher,
    YouTubePublisher,
    build_absolute_media_url,
)
from ..telegram_client import TelegramPublisher, run_async_task

logger = logging.getLogger(__name__)


def _compose_post_text(post) -> str:
    """Собрать текст для публикации, добавив заголовок перед основным текстом."""
    if not getattr(post, "publish_text", False):
        return ""

    parts = []

    title = (getattr(post, "title", "") or "").strip()
    if title:
        parts.append(title)

    body = (getattr(post, "text", "") or "").strip()
    if body:
        parts.append(body)

    return "\n\n".join(parts)


def _prepare_media_assets(post):
    """
    Собирает пути и публичные URL для медиа, учитывая флаги публикации.
    """
    text = _compose_post_text(post)
    image_path = image_url = video_path = video_url = None

    if getattr(post, "publish_image", False):
        primary_image = post.get_primary_image()
        if primary_image and primary_image.image:
            image_path = getattr(primary_image.image, "path", None)
            image_url = build_absolute_media_url(getattr(primary_image.image, "url", ""))

    if getattr(post, "publish_video", False):
        primary_video = post.get_primary_video()
        if primary_video and primary_video.video:
            video_path = getattr(primary_video.video, "path", None)
            video_url = build_absolute_media_url(getattr(primary_video.video, "url", ""))

    return {
        "text": text,
        "image_path": image_path,
        "image_url": image_url,
        "video_path": video_path,
        "video_url": video_url,
    }


def _update_post_status_after_publish(post):
    """
    Обновляет статус поста после успешной публикации.

    Логика:
    - Если все Schedule поста опубликованы (status='published'), то пост становится 'published'
    - Если есть хотя бы один опубликованный Schedule, но есть и другие, статус остается 'scheduled'
    """
    # Получаем все Schedule для этого поста
    all_schedules = Schedule.objects.filter(post=post)

    if not all_schedules.exists():
        logger.warning(f"Нет Schedule для поста {post.id}, не обновляем статус")
        return

    # Проверяем статусы всех Schedule
    published_count = all_schedules.filter(status='published').count()
    total_count = all_schedules.count()

    if published_count == total_count:
        # Все Schedule опубликованы
        if post.status != 'published':
            post.status = 'published'
            post.save()
            logger.info(f"Пост {post.id} обновлен на статус 'published' - все Schedule опубликованы ({published_count}/{total_count})")
    elif published_count > 0:
        # Есть опубликованные, но не все
        if post.status not in ['published', 'scheduled']:
            post.status = 'scheduled'
            post.save()
            logger.info(f"Пост {post.id} обновлен на статус 'scheduled' - частично опубликован ({published_count}/{total_count})")


@shared_task
def process_due_schedules():
    """
    Ищет все записи Schedule со временем <= сейчас и статусом pending
    и запускает для них таску publish_schedule.
    """
    now = timezone.now()
    qs = (
        Schedule.objects
        .select_related("post", "social_account", "client")
        .filter(status="pending", scheduled_at__lte=now)
    )

    for schedule in qs:
        publish_schedule.delay(schedule.id)


@shared_task
def publish_schedule(schedule_id: int):
    """
    Публикация поста в соцсеть согласно Schedule.
    Поддерживаемые платформы: Telegram, Instagram (TODO), YouTube (TODO).
    """
    from ..models import Schedule
    from django.conf import settings

    try:
        schedule = Schedule.objects.select_related("post", "social_account", "client").get(id=schedule_id)

        schedule.status = "in_progress"
        schedule.save(update_fields=["status"])

        post = schedule.post
        social_account = getattr(schedule, "social_account", None)
        client = schedule.client
        if social_account is None:
            desired_url = (schedule.external_id or "").strip()
            account_qs = SocialAccount.objects.filter(client=client, platform="rss_zen")
            if desired_url:
                account_qs = account_qs.filter(access_token=desired_url)
            social_account = account_qs.first()
            if not social_account and desired_url:
                social_account = SocialAccount.objects.create(
                    client=client,
                    platform="rss_zen",
                    name="RSS Дзен",
                    access_token=desired_url,
                    extra={"url": desired_url, "source": "rss_zen"},
                )
            if social_account:
                schedule.social_account = social_account
                schedule.save(update_fields=["social_account"])
            else:
                error_msg = "У расписания не указан социальный аккаунт"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save(update_fields=["status", "log"])
                return
        assets = _prepare_media_assets(post)
        text = assets["text"]

        logger.info(f"Публикация поста '{post.title}' в {social_account.platform}")

        # Telegram публикация
        if social_account.platform == "telegram":
            # Проверяем настройки Telegram
            if not client.telegram_api_id or not client.telegram_api_hash:
                error_msg = f"Telegram API credentials не настроены для клиента {client.name}"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            # Определяем канал для публикации из SocialAccount
            publish_channel = None
            if social_account.extra and 'channel' in social_account.extra:
                publish_channel = social_account.extra['channel']

            if not publish_channel:
                error_msg = f"Telegram канал не указан в SocialAccount (заполните поле 'channel' в extra)"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            # Создаем publisher
            # Используем TELEGRAM_BOT_TOKEN из settings (глобальный токен бота)
            from django.conf import settings
            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

            publisher = TelegramPublisher(
                api_id=client.telegram_api_id,
                api_hash=client.telegram_api_hash,
                session_name=f"session_publisher_client_{client.id}",
                bot_token=bot_token
            )

            image_path = assets["image_path"]
            video_path = assets["video_path"]

            # Проверяем, что есть хоть что-то для публикации
            if not text and not image_path and not video_path:
                error_msg = "Нечего публиковать: все флаги публикации отключены или контент отсутствует"
                logger.warning(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            # Публикуем
            logger.info(f"Публикация в Telegram канал: {publish_channel}")
            logger.info(f"  Текст: {'Да' if text else 'Нет'} ({len(text)} символов)")
            logger.info(f"  Изображение: {'Да' if image_path else 'Нет'}")
            logger.info(f"  Видео: {'Да' if video_path else 'Нет'}")

            async def publish_task():
                await publisher.connect()
                try:
                    result = await publisher.publish_post(
                        channel=publish_channel,
                        text=text,
                        image_path=image_path,
                        video_path=video_path
                    )
                    return result
                finally:
                    await publisher.disconnect()

            result = run_async_task(publish_task())

            if result['success']:
                schedule.status = "published"
                schedule.external_id = str(result.get('message_id', ''))
                log_msg = f"\n[SUCCESS] Опубликовано в Telegram: {result.get('url', '')}"
                schedule.log = (schedule.log or "") + log_msg
                logger.info(f"Пост успешно опубликован в Telegram: {result.get('url', '')}")

                # Обновляем статус поста на published
                _update_post_status_after_publish(post)
            else:
                schedule.status = "failed"
                error_msg = result.get('error', 'Unknown error')
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                logger.error(f"Ошибка публикации в Telegram: {error_msg}")

        # Instagram публикация
        elif social_account.platform == "instagram":
            access_token = (social_account.access_token or "").strip()
            extra = social_account.extra or {}
            ig_account_id = None
            if isinstance(extra, dict):
                ig_account_id = (
                    extra.get("instagram_business_account_id")
                    or extra.get("instagram_account_id")
                    or extra.get("ig_user_id")
                )

            if not access_token:
                error_msg = "Instagram access_token не указан в SocialAccount"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            if not ig_account_id:
                error_msg = "В extra SocialAccount не указан instagram_business_account_id"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            # Instagram требует медиа: используем видео приоритетно, иначе изображение
            media_url = None
            use_video = False
            if assets["video_url"]:
                media_url = assets["video_url"]
                use_video = True
            elif assets["image_url"]:
                media_url = assets["image_url"]

            if not media_url:
                error_msg = (
                    "Для Instagram нужен публичный URL изображения или видео. "
                    "Убедитесь, что MEDIA_URL доступен извне или настройте PUBLIC_MEDIA_BASE_URL/WAGTAILADMIN_BASE_URL."
                )
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            publisher = InstagramPublisher(
                access_token=access_token,
                business_account_id=str(ig_account_id),
            )

            result = publisher.publish_post(
                caption=text,
                image_url=None if use_video else media_url,
                video_url=media_url if use_video else None,
            )

            if result.get("success"):
                schedule.status = "published"
                schedule.external_id = str(result.get("media_id", ""))
                log_msg = f"\n[SUCCESS] Опубликовано в Instagram: {result.get('url', '')}"
                schedule.log = (schedule.log or "") + log_msg
                logger.info(f"Пост успешно опубликован в Instagram: {result.get('url', '')}")
                _update_post_status_after_publish(post)
            else:
                schedule.status = "failed"
                error_msg = result.get("error", "Instagram публикация завершилась с ошибкой")
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                logger.error(f"Ошибка публикации в Instagram: {error_msg}")

        # YouTube публикация
        elif social_account.platform == "youtube":
            video_path = assets["video_path"]
            if not video_path:
                error_msg = "Для публикации на YouTube требуется видеофайл"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            access_token = (social_account.access_token or "").strip()
            refresh_token = (social_account.refresh_token or "").strip() or None
            extra = social_account.extra or {}
            client_id = extra.get("client_id") if isinstance(extra, dict) else None
            client_secret = extra.get("client_secret") if isinstance(extra, dict) else None
            token_uri = extra.get("token_uri") if isinstance(extra, dict) else None
            privacy_status = extra.get("privacy_status") if isinstance(extra, dict) else None

            if not access_token:
                error_msg = "YouTube access_token не указан в SocialAccount"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save()
                return

            publisher = YouTubePublisher(
                access_token=access_token,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri=token_uri or "https://oauth2.googleapis.com/token",
            )

            description = (text or "").strip()[:5000]
            title = (getattr(post, "title", "") or "Видео").strip() or "Видео"

            result = publisher.publish_video(
                video_path=video_path,
                title=title,
                description=description,
                privacy_status=privacy_status or "public",
            )

            if result.get("success"):
                schedule.status = "published"
                schedule.external_id = str(result.get("video_id", ""))
                log_msg = f"\n[SUCCESS] Опубликовано на YouTube: {result.get('url', '')}"
                schedule.log = (schedule.log or "") + log_msg
                logger.info(f"Пост успешно опубликован на YouTube: {result.get('url', '')}")

                new_token = result.get("access_token")
                if new_token and new_token != social_account.access_token:
                    social_account.access_token = new_token
                    social_account.save(update_fields=["access_token"])

                _update_post_status_after_publish(post)
            else:
                schedule.status = "failed"
                error_msg = result.get("error", "YouTube публикация завершилась с ошибкой")
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                logger.error(f"Ошибка публикации на YouTube: {error_msg}")

        # RSS Дзен — посты забираются из ленты автоматически, сразу считаем опубликованным
        elif social_account.platform == "rss_zen":
            feed_url = (social_account.access_token or "").strip()
            schedule.status = "published"
            schedule.external_id = feed_url
            log_msg = "\n[SUCCESS] Отмечено для RSS Дзена (берётся из RSS ленты)"
            if feed_url:
                log_msg += f"\nFeed: {feed_url}"
            schedule.log = (schedule.log or "") + log_msg
            _update_post_status_after_publish(post)

        else:
            logger.error(f"Неизвестная платформа: {social_account.platform}")
            schedule.status = "failed"
            schedule.log = (schedule.log or "") + f"\n[ERROR] Неизвестная платформа: {social_account.platform}"

        schedule.save()

    except Schedule.DoesNotExist:
        logger.error(f"Schedule с ID {schedule_id} не найден")
    except Exception as e:
        logger.error(f"Ошибка при публикации schedule {schedule_id}: {e}", exc_info=True)
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            schedule.status = "failed"
            schedule.log = (schedule.log or "") + f"\n[ERROR] {str(e)}"
            schedule.save()
        except:
            pass
