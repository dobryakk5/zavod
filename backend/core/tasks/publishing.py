from celery import shared_task
from django.utils import timezone
import logging

from ..models import Schedule, SocialAccount
from ..social_publishers import build_absolute_media_url
from ..services.posting_service import PostingService, update_post_status_after_publish
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


@shared_task
def process_due_schedules():
    """
    Ищет все записи Schedule со временем <= сейчас и статусом pending
    и запускает для них таску publish_schedule.
    """
    now = timezone.now()
    due_ids = list(
        Schedule.objects
        .filter(status="pending", scheduled_at__lte=now)
        .values_list("id", flat=True)
    )
    logger.info("Beat tick process_due_schedules: now=%s due=%s", now.isoformat(), len(due_ids))
    scheduled = 0

    for schedule_id in due_ids:
        updated = Schedule.objects.filter(id=schedule_id, status="pending").update(status="in_progress")
        if not updated:
            continue
        try:
            publish_schedule.delay(schedule_id)
        except Exception:
            Schedule.objects.filter(id=schedule_id).update(status="pending")
            logger.warning("Failed to enqueue schedule %s", schedule_id, exc_info=True)
            continue
        scheduled += 1

    logger.info("Beat tick process_due_schedules done: enqueued=%s", scheduled)
    return scheduled


@shared_task
def publish_schedule(schedule_id: int):
    """
    Публикация поста в соцсеть согласно Schedule.
    Поддерживаемые платформы: Telegram, Instagram, YouTube, RSS Дзен.
    """
    from django.conf import settings

    try:
        schedule = (
            Schedule.objects.select_related("post", "social_account", "connection", "client")
            .get(id=schedule_id)
        )

        schedule.status = "in_progress"
        schedule.save(update_fields=["status"])

        post = schedule.post
        social_account = getattr(schedule, "social_account", None)
        client = schedule.client
        if social_account is None and not schedule.connection_id:
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

        posting_service = PostingService()
        provider = schedule.connection.provider if schedule.connection_id else social_account.platform
        logger.info(f"Публикация поста '{post.title}' в {provider}")

        # Telegram публикация
        if provider == "telegram":
            if social_account is None:
                error_msg = "Telegram social_account не указан для расписания"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save(update_fields=["status", "log"])
                return

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
                update_post_status_after_publish(post)
            else:
                schedule.status = "failed"
                error_msg = result.get('error', 'Unknown error')
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                logger.error(f"Ошибка публикации в Telegram: {error_msg}")

        # Instagram публикация
        elif provider == "instagram":
            posting_service.publish_instagram(schedule, assets)

        # YouTube публикация
        elif provider == "youtube":
            posting_service.publish_youtube(schedule, assets)

        # RSS Дзен — посты забираются из ленты автоматически, сразу считаем опубликованным
        elif provider == "rss_zen":
            if social_account is None:
                error_msg = "SocialAccount для RSS Дзена не найден"
                logger.error(error_msg)
                schedule.status = "failed"
                schedule.log = (schedule.log or "") + f"\n[ERROR] {error_msg}"
                schedule.save(update_fields=["status", "log"])
                return
            feed_url = (social_account.access_token or "").strip()
            schedule.status = "published"
            schedule.external_id = feed_url
            log_msg = "\n[SUCCESS] Отмечено для RSS Дзена (берётся из RSS ленты)"
            if feed_url:
                log_msg += f"\nFeed: {feed_url}"
            schedule.log = (schedule.log or "") + log_msg
            update_post_status_after_publish(post)

        else:
            logger.error(f"Неизвестная платформа: {provider}")
            schedule.status = "failed"
            schedule.log = (schedule.log or "") + f"\n[ERROR] Неизвестная платформа: {provider}"

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
