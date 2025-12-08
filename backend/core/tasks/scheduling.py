from celery import shared_task
import logging

from ..models import Post, Schedule

logger = logging.getLogger(__name__)


@shared_task
def auto_schedule_story_posts(story_id: int, posts_per_day: int, start_date: str, social_account_ids: list):
    """
    Автоматическое создание расписания для всех постов истории.

    Args:
        story_id: ID истории (Story)
        posts_per_day: Количество постов в день
        start_date: Дата начала публикации (формат: YYYY-MM-DD)
        social_account_ids: Список ID соц. аккаунтов (SocialAccount)

    Returns:
        Количество созданных Schedule записей
    """
    from ..models import Story, SocialAccount
    from datetime import datetime, timedelta

    try:
        story = Story.objects.select_related('client').get(id=story_id)
        posts = Post.objects.filter(story=story).order_by('episode_number')

        if not posts.exists():
            logger.error(f"Нет постов для истории {story_id}")
            return 0

        # Парсим дату начала
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            # Устанавливаем время на 10:00 по умолчанию
            start_datetime = start_datetime.replace(hour=10, minute=0, second=0)
        except ValueError:
            logger.error(f"Неверный формат даты: {start_date}. Ожидается YYYY-MM-DD")
            return 0

        # Получаем соц. аккаунты
        social_accounts = SocialAccount.objects.filter(id__in=social_account_ids, client=story.client)

        if not social_accounts.exists():
            logger.error(f"Не найдены соц. аккаунты с ID: {social_account_ids}")
            return 0

        logger.info(f"Создание автоматического расписания для истории: {story.title}")
        logger.info(f"  Постов: {posts.count()}, по {posts_per_day} в день, начало: {start_datetime}")
        logger.info(f"  Соц. аккаунты: {', '.join([sa.name for sa in social_accounts])}")

        created_count = 0
        current_datetime = start_datetime

        # Интервал между постами в течение дня (в часах)
        hours_between_posts = 24 // posts_per_day if posts_per_day > 0 else 24

        post_index = 0
        for post in posts:
            for social_account in social_accounts:
                # Создаем Schedule
                schedule = Schedule.objects.create(
                    client=story.client,
                    post=post,
                    social_account=social_account,
                    scheduled_at=current_datetime,
                    status="pending"
                )

                logger.info(f"  Создано расписание: {post.title[:40]} → {social_account.name} на {current_datetime}")
                created_count += 1

            # Переход к следующему времени публикации
            post_index += 1
            if post_index % posts_per_day == 0:
                # Переход на следующий день
                current_datetime = current_datetime + timedelta(days=1)
                current_datetime = current_datetime.replace(hour=10, minute=0)
            else:
                # Следующий пост в тот же день
                current_datetime = current_datetime + timedelta(hours=hours_between_posts)

        logger.info(f"Создано {created_count} записей расписания для истории {story.title}")

        # Обновляем статус постов на 'scheduled'
        posts.update(status='scheduled')

        return created_count

    except Story.DoesNotExist:
        logger.error(f"История {story_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка создания расписания для истории {story_id}: {e}", exc_info=True)
        return 0
