from celery import shared_task
from django.utils import timezone
import logging

from ..models import Schedule
from ..telegram_client import TelegramPublisher, run_async_task

logger = logging.getLogger(__name__)


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
        schedule.save()

        post = schedule.post
        social_account = schedule.social_account
        client = schedule.client

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
            # Если в SocialAccount есть access_token, используем его как bot_token
            bot_token = social_account.access_token if social_account.access_token else None

            publisher = TelegramPublisher(
                api_id=client.telegram_api_id,
                api_hash=client.telegram_api_hash,
                session_name=f"session_publisher_client_{client.id}",
                bot_token=bot_token
            )

            # Подготавливаем данные для публикации с учетом флагов
            text = post.text if post.publish_text else ""
            image_path = None
            video_path = None

            if post.publish_image:
                primary_image = post.get_primary_image()
                if primary_image and primary_image.image:
                    image_path = primary_image.image.path
            if post.publish_video:
                primary_video = post.get_primary_video()
                if primary_video and primary_video.video:
                    video_path = primary_video.video.path

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

        # Instagram публикация (TODO)
        elif social_account.platform == "instagram":
            logger.warning("Instagram публикация пока не реализована")
            schedule.status = "failed"
            schedule.log = (schedule.log or "") + "\n[ERROR] Instagram публикация не реализована"

        # YouTube публикация (TODO)
        elif social_account.platform == "youtube":
            logger.warning("YouTube публикация пока не реализована")
            schedule.status = "failed"
            schedule.log = (schedule.log or "") + "\n[ERROR] YouTube публикация не реализована"

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
