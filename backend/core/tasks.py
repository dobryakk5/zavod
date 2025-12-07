from celery import shared_task
from django.utils import timezone
import logging
import json
import os
from typing import Optional, Dict

from .models import Schedule, Topic, TrendItem, Post, ContentTemplate, SEOKeywordSet, Client
from .aggregator import (
    fetch_google_trends,
    fetch_google_news_rss,
    fetch_rss_feeds,
    fetch_youtube_videos,
    fetch_instagram_posts,
    fetch_vkontakte_posts,
    deduplicate_trends
)
from .ai_generator import AIContentGenerator
from .telegram_client import TelegramContentCollector, TelegramPublisher, run_async_task

logger = logging.getLogger(__name__)


def _build_text_video_prompt(post: Post) -> str:
    """Собрать описание для генерации видео по тексту."""
    base_text = (post.text or "").strip()
    if len(base_text) > 800:
        base_text = base_text[:800] + "..."

    topic_name = ""
    raw_topic = getattr(post, "topic", None)
    if raw_topic:
        topic_name = getattr(raw_topic, "name", str(raw_topic))
    elif getattr(post, "story_id", None):
        try:
            story = post.story
        except Exception:
            story = None
        if story and story.trend_item and story.trend_item.topic:
            topic_name = story.trend_item.topic.name

    if not topic_name:
        source_trends = getattr(post, "source_trends", None)
        trend = None
        if source_trends is not None:
            try:
                trend = source_trends.select_related("topic").first()
            except Exception:
                trend = source_trends.first()
        if trend and trend.topic:
            topic_name = trend.topic.name

    if not topic_name and post.client:
        topic_name = post.client.name

    parts = [
        "Create a dynamic short-form social media video (vertical 9:16).",
        "Add cinematic motion and modern transitions.",
        f"Title: {post.title}".strip(),
    ]
    if topic_name:
        parts.append(f"Business/topic: {topic_name}")
    if base_text:
        parts.append(f"Script idea:\n{base_text}")

    return "\n".join(parts)


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
    from .models import Schedule
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

            if post.publish_image and post.image:
                image_path = post.image.path
            if post.publish_video and post.video:
                video_path = post.video.path

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


@shared_task
def discover_trends_for_topic(topic_id: int):
    """
    Найти тренды и новости для заданной темы.

    1. Получает тему из базы данных
    2. Собирает данные из Google Trends
    3. Собирает новости из Google News RSS
    4. Сохраняет топ-5 результатов в базу данных

    Args:
        topic_id: ID темы (Topic)

    Returns:
        Количество найденных и сохранённых трендов
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        logger.info(f"Начинаем поиск трендов для темы: {topic.name} (клиент: {topic.client.name})")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        if not keywords:
            logger.warning(f"Нет ключевых слов для темы {topic.name}")
            return 0

        logger.info(f"Ключевые слова: {keywords}")

        # Собираем тренды из Google Trends
        logger.info("Получаем данные из Google Trends...")
        google_trends = fetch_google_trends(keywords, limit=5)
        logger.info(f"Найдено {len(google_trends)} трендов из Google Trends")

        # Собираем новости из Google News RSS
        logger.info("Получаем новости из Google News RSS...")
        google_news = fetch_google_news_rss(keywords, limit=5)
        logger.info(f"Найдено {len(google_news)} новостей из Google News")

        # Объединяем и дедуплицируем
        all_trends = google_trends + google_news
        unique_trends = deduplicate_trends(all_trends)

        # Сортируем по relevance_score и берём топ-5
        unique_trends.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_trends = unique_trends[:5]

        logger.info(f"После дедупликации и фильтрации: {len(top_trends)} уникальных трендов")

        # Сохраняем в базу данных
        created_count = 0
        for trend_data in top_trends:
            # Проверяем, не существует ли уже такой тренд (по URL)
            url = trend_data.get('url', '')

            # Определяем источник
            if 'google_trends' in trend_data.get('extra', {}).get('type', ''):
                source = 'google_trends'
            elif trend_data.get('extra', {}).get('source'):
                source = 'google_news_rss'
            else:
                # Попробуем определить по URL
                if 'trends.google.com' in url:
                    source = 'google_trends'
                elif 'news.google.com' in url or url:
                    source = 'google_news_rss'
                else:
                    source = 'manual'

            # Проверяем дубликаты по URL (если URL есть)
            if url:
                existing = TrendItem.objects.filter(
                    topic=topic,
                    url=url
                ).first()

                if existing:
                    logger.debug(f"Тренд уже существует: {trend_data['title'][:50]}")
                    continue

            # Создаём новый TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=topic.client,
                source=source,
                title=trend_data['title'],
                description=trend_data.get('description', ''),
                url=url,
                relevance_score=trend_data.get('relevance_score', 0),
                extra=trend_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создан тренд: {trend_item.title[:60]}")

        logger.info(f"Успешно создано {created_count} новых трендов для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске трендов для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_trends_for_all_active_topics():
    """
    Найти тренды для всех активных тем.
    Запускается периодически по расписанию (например, каждый день).

    Returns:
        Количество обработанных тем
    """
    active_topics = Topic.objects.filter(is_active=True)

    logger.info(f"Запуск поиска трендов для {active_topics.count()} активных тем")

    for topic in active_topics:
        discover_trends_for_topic.delay(topic.id)

    return active_topics.count()


@shared_task
def _get_latest_seo_keywords_for_client(client: Client) -> Dict[str, list]:
    """Возвращает свежие SEO списки по группам для клиента."""
    latest: Dict[str, list] = {}
    completed_sets = SEOKeywordSet.objects.filter(
        client=client,
        status='completed'
    ).order_by('-created_at')

    for seo_set in completed_sets:
        if seo_set.group_type:
            if seo_set.group_type not in latest and seo_set.keywords_list:
                latest[seo_set.group_type] = seo_set.keywords_list
                continue

        if seo_set.keyword_groups:
            for group_name, keywords in seo_set.keyword_groups.items():
                if group_name not in latest and isinstance(keywords, list) and keywords:
                    latest[group_name] = keywords

        if len(latest) >= len(SEOKeywordSet.GROUP_TYPE_CHOICES):
            break

    return latest


def _create_seo_records_for_generation(client: Client) -> Dict[str, SEOKeywordSet]:
    """
    Создать (или пересоздать) SEOKeywordSet записи для каждой группы перед генерацией.
    """
    SEOKeywordSet.objects.filter(
        client=client,
        status__in=['pending', 'generating']
    ).update(status='failed', error_log='Superseded by new SEO generation')

    records = {}
    for group_type, _ in SEOKeywordSet.GROUP_TYPE_CHOICES:
        records[group_type] = SEOKeywordSet.objects.create(
            client=client,
            status='generating',
            group_type=group_type
        )
    return records


def generate_post_from_trend(trend_item_id: int, template_id: int = None):
    """
    Сгенерировать пост из тренда используя AI.

    Args:
        trend_item_id: ID тренда (TrendItem)
        template_id: ID шаблона контента (ContentTemplate). Если None, используется default для клиента

    Returns:
        ID созданного поста или None при ошибке
    """
    try:
        # Получить TrendItem
        trend = TrendItem.objects.select_related('topic', 'client').get(id=trend_item_id)

        # Проверить, не использован ли уже этот тренд
        if trend.used_for_post:
            logger.warning(f"Тренд {trend.id} уже использован для поста {trend.used_for_post.id}")
            return None

        logger.info(f"Генерация поста из тренда: {trend.title[:50]} (клиент: {trend.client.name})")

        # Получить шаблон контента
        if template_id:
            template = ContentTemplate.objects.get(id=template_id, client=trend.client)
        else:
            # Использовать default шаблон для клиента
            template = ContentTemplate.objects.filter(
                client=trend.client,
                is_default=True
            ).first()

            if not template:
                # Если нет default шаблона, взять любой первый
                template = ContentTemplate.objects.filter(client=trend.client).first()

            if not template:
                logger.error(f"Нет шаблонов контента для клиента {trend.client.name}")
                return None

        logger.info(f"Используется шаблон: {template.name}")

        # Подготовить конфигурацию для AI генератора
        template_config = {
            "tone": template.tone,
            "length": template.length,
            "language": template.language,
            "seo_prompt_template": template.seo_prompt_template,
            "trend_prompt_template": template.trend_prompt_template,
            "prompt_type": "trend",
            "additional_instructions": template.additional_instructions,
            "include_hashtags": template.include_hashtags,
            "max_hashtags": template.max_hashtags,
            # Данные по типу поста и целевой аудитории клиента
            "type": getattr(template, "type", "selling"),
            "avatar": trend.client.avatar or "",
            "pains": trend.client.pains or "",
            "desires": trend.client.desires or "",
            "objections": trend.client.objections or "",
        }

        # Создать AI генератор
        try:
            generator = AIContentGenerator()
        except ValueError as e:
            logger.error(f"Ошибка инициализации AI генератора: {e}")
            logger.error("Убедитесь, что OPENROUTER_API_KEY установлен в переменных окружения")
            return None

        # Получить SEO-ключи для клиента (если есть)
        seo_keywords = _get_latest_seo_keywords_for_client(trend.client)
        if seo_keywords:
            logger.info(
                f"Используются SEO-ключи групп {list(seo_keywords.keys())} "
                f"для клиента {trend.client.name}"
            )
        else:
            logger.info("SEO-ключи не найдены для клиента, генерация без SEO-оптимизации")

        # Сгенерировать контент
        result = generator.generate_post_text(
            trend_title=trend.title,
            trend_description=trend.description or "",
            trend_url=trend.url or "",
            topic_name=trend.topic.name,
            template_config=template_config,
            seo_keywords=seo_keywords
        )

        if not result.get('success'):
            logger.error(f"Ошибка генерации контента: {result.get('error')}")
            return None

        # Создать Post
        post_title = result['title']
        post_text = result['text']
        hashtags = result.get('hashtags', [])

        # Собрать теги (только хэштеги от AI, без мета-информации)
        tags = hashtags.copy()

        # Создать пост со статусом draft
        post = Post.objects.create(
            client=trend.client,
            title=post_title,
            text=post_text,
            status="draft",  # Требует модерации
            tags=tags,
            source_links=[trend.url] if trend.url else [],
            generated_by="openrouter-deepseek",
            # created_by будет None - автоматическая генерация
        )

        # Связать тренд с постом
        trend.used_for_post = post
        trend.save()

        logger.info(f"Успешно создан пост ID={post.id} из тренда ID={trend.id}")
        logger.info(f"Заголовок: {post_title[:60]}")

        return post.id

    except TrendItem.DoesNotExist:
        logger.error(f"Тренд с ID {trend_item_id} не найден")
        return None
    except ContentTemplate.DoesNotExist:
        logger.error(f"Шаблон контента с ID {template_id} не найден")
        return None
    except Exception as e:
        logger.error(f"Ошибка при генерации поста из тренда {trend_item_id}: {e}", exc_info=True)
        return None


@shared_task
def generate_posts_for_topic(topic_id: int, template_id: int = None, limit: int = None):
    """
    Сгенерировать посты для всех неиспользованных трендов темы.

    Args:
        topic_id: ID темы (Topic)
        template_id: ID шаблона контента (если None, используется default)
        limit: Максимальное количество постов для генерации (если None, генерировать все)

    Returns:
        Количество запущенных задач генерации
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        logger.info(f"Генерация постов для темы: {topic.name} (клиент: {topic.client.name})")

        # Найти все неиспользованные тренды
        unused_trends = TrendItem.objects.filter(
            topic=topic,
            used_for_post__isnull=True
        ).order_by('-relevance_score', '-discovered_at')

        if limit:
            unused_trends = unused_trends[:limit]

        count = unused_trends.count()
        logger.info(f"Найдено {count} неиспользованных трендов")

        # Запустить задачи генерации для каждого тренда
        generated_count = 0
        for trend in unused_trends:
            generate_post_from_trend.delay(trend.id, template_id)
            generated_count += 1

        logger.info(f"Запущено {generated_count} задач генерации постов для темы '{topic.name}'")
        return generated_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при генерации постов для темы {topic_id}: {e}", exc_info=True)
        return 0


def _collect_client_topics_and_keywords(client: Client):
    topics = Topic.objects.filter(client=client).order_by('name')
    topic_names = []
    raw_keywords = []

    for topic in topics:
        if topic.name:
            topic_names.append(topic.name)
        if topic.keywords:
            for kw in topic.keywords:
                if isinstance(kw, str):
                    trimmed = kw.strip()
                    if trimmed:
                        raw_keywords.append(trimmed)

    seen = set()
    deduped_keywords = []
    for kw in raw_keywords:
        if kw not in seen:
            deduped_keywords.append(kw)
            seen.add(kw)

    if not deduped_keywords and topic_names:
        deduped_keywords = topic_names.copy()

    return topic_names, deduped_keywords


def _generate_seo_keywords_for_client_instance(client: Client, language: str = "ru"):
    logger.info(f"Генерация SEO-фраз для клиента: {client.name}")

    seo_records = _create_seo_records_for_generation(client)

    try:
        generator = AIContentGenerator()
    except ValueError as e:
        logger.error(f"Ошибка инициализации AI генератора: {e}")
        logger.error("Убедитесь, что OPENROUTER_API_KEY установлен в переменных окружения")
        for record in seo_records.values():
            record.status = 'failed'
            record.error_log = f"AI initialization error: {str(e)}"
            record.save()
        return None

    topic_names, keywords_list = _collect_client_topics_and_keywords(client)
    topic_context = ", ".join(topic_names) if topic_names else client.name
    prompt_text = (
        f"Client: {client.name}, Topics: {topic_names or '[]'}, "
        f"Keywords: {keywords_list or '[]'}, Language: {language}"
    )

    def mark_record_success(group_type: str, keywords: list):
        record = seo_records.get(group_type)
        if not record:
            return
        record.keywords_list = keywords
        record.keyword_groups = {group_type: keywords}
        record.status = 'completed'
        record.error_log = ""
        record.prompt_used = prompt_text
        record.ai_model = generator.model
        record.topic = None
        record.save()

    result = generator.generate_seo_keywords(
        topic_name=topic_context,
        keywords=keywords_list,
        language=language,
        brand=client.name,
        avatar=client.avatar or "",
        pains=client.pains or "",
        desires=client.desires or "",
        objections=client.objections or "",
        on_group_generated=lambda group, data: mark_record_success(group, data)
    )

    if not result.get('success'):
        error_message = result.get('error', 'Unknown error')
        logger.error(f"Ошибка генерации SEO-фраз: {error_message}")
        for record in seo_records.values():
            if record.status == 'completed':
                continue
            record.status = 'failed'
            record.error_log = error_message
            record.prompt_used = prompt_text
            record.ai_model = generator.model
            record.keywords_list = []
            record.keyword_groups = {}
            record.save()
        return None

    keyword_groups = result.get('keyword_groups', {})

    completed_ids = []
    for group_type, record in seo_records.items():
        if record.status == 'completed':
            completed_ids.append(record.id)
            continue

        keywords = keyword_groups.get(group_type, [])
        if keywords:
            mark_record_success(group_type, keywords)
            completed_ids.append(seo_records[group_type].id)
        else:
            record.status = 'failed'
            record.error_log = f"Group '{group_type}' not returned by AI"
            record.prompt_used = prompt_text
            record.ai_model = generator.model
            record.keywords_list = []
            record.keyword_groups = {}
            record.save()

    logger.info(
        f"Успешно сгенерированы SEO-фразы для клиента '{client.name}' "
        f"(группы: {list(keyword_groups.keys())})"
    )

    total_keywords = sum(len(keywords or []) for keywords in keyword_groups.values())
    logger.info(f"Всего ключей: {total_keywords}")

    return completed_ids


@shared_task
def generate_seo_keywords_for_client(client_id: int, language: str = "ru"):
    """
    Сгенерировать SEO-подборку ключевых фраз для клиента используя AI.
    """
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        logger.error(f"Клиент с ID {client_id} не найден")
        return None
    except Exception as exc:
        logger.error(f"Ошибка при получении клиента {client_id}: {exc}", exc_info=True)
        return None

    try:
        return _generate_seo_keywords_for_client_instance(client, language)
    except Exception as exc:
        logger.error(f"Ошибка при генерации SEO для клиента {client_id}: {exc}", exc_info=True)
        try:
            seo_sets = SEOKeywordSet.objects.filter(client_id=client_id, status='generating')
            for seo_set in seo_sets:
                seo_set.status = 'failed'
                seo_set.error_log = str(exc)
                seo_set.save()
        except Exception:
            pass
        return None


@shared_task
def generate_seo_keywords_for_topic(topic_id: int, language: str = "ru"):
    """
    [DEPRECATED] Сгенерировать SEO для клиента темы.
    Оставлено для обратной совместимости.
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)
    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return None
    except Exception as exc:
        logger.error(f"Ошибка при получении темы {topic_id}: {exc}", exc_info=True)
        return None

    logger.info(
        f"generate_seo_keywords_for_topic вызван для темы '{topic.name}', переадресация на клиента '{topic.client.name}'"
    )
    return _generate_seo_keywords_for_client_instance(topic.client, language)


@shared_task
def generate_image_for_post(post_id: int, model: str = "pollinations"):
    """
    Сгенерировать изображение для поста используя AI.

    Args:
        post_id: ID поста (Post)
        model: Модель для генерации изображения:
            - "pollinations": Pollinations AI (бесплатный, по умолчанию)
            - "nanobanana": OpenRouter google/gemini-2.5-flash-image
            - "huggingface": HuggingFace with Nebius GPU (FLUX.1-dev)

    Returns:
        True при успехе, False при ошибке
    """
    try:
        # Получить Post
        post = Post.objects.select_related('client').get(id=post_id)

        logger.info(f"Генерация изображения для поста: {post.title} (ID={post.id}) с моделью '{model}'")

        # Проверить, что у поста есть текст
        if not post.text:
            logger.warning(f"Пост {post.id} не имеет текста, невозможно сгенерировать изображение")
            return False

        # Создать AI генератор
        try:
            generator = AIContentGenerator()
        except ValueError as e:
            logger.error(f"Ошибка инициализации AI генератора: {e}")
            logger.error("Убедитесь, что OPENROUTER_API_KEY установлен в переменных окружения")
            return False

        # Шаг 1: Сгенерировать промпт для изображения
        logger.info("Генерация промпта для изображения...")
        image_prompt = generator.generate_image_prompt(
            post_title=post.title,
            post_text=post.text
        )

        if not image_prompt:
            logger.error("Не удалось сгенерировать промпт для изображения")
            return False

        logger.info(f"Промпт для изображения: {image_prompt}")

        # Шаг 2: Сгенерировать изображение
        import os
        from django.conf import settings
        from django.core.files import File
        import uuid

        # Создать уникальное имя файла
        image_filename = f"post_{post.id}_{uuid.uuid4().hex[:8]}.jpg"
        # Путь для временного сохранения
        temp_image_path = os.path.join(settings.MEDIA_ROOT, 'temp', image_filename)

        logger.info(f"Генерация изображения моделью '{model}' и сохранение в {temp_image_path}...")

        result = generator.generate_image(
            prompt=image_prompt,
            output_path=temp_image_path,
            model=model
        )

        if not result.get('success'):
            logger.error(f"Ошибка генерации изображения: {result.get('error')}")
            return False

        # Шаг 3: Сохранить изображение в поле Post.image
        try:
            with open(temp_image_path, 'rb') as f:
                # Сохраняем только имя файла, Django автоматически добавит upload_to путь
                post.image.save(
                    image_filename,
                    File(f),
                    save=True
                )

            logger.info(f"Изображение успешно сохранено в пост {post.id}: {post.image.url}")
            logger.info(f"Использована модель: {result.get('model', model)}")

            # Удалить временный файл
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                logger.info(f"Временный файл удалён: {temp_image_path}")

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения изображения в пост: {e}", exc_info=True)
            # Попытаться удалить временный файл
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
            return False

    except Post.DoesNotExist:
        logger.error(f"Пост с ID {post_id} не найден")
        return False
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения для поста {post_id}: {e}", exc_info=True)
        return False


@shared_task
def generate_video_from_image(post_id: int, method: Optional[str] = None, source: str = "image"):
    """Создать короткое видео для поста (по изображению или тексту)."""
    try:
        post = Post.objects.get(id=post_id)

        from django.core.files import File
        import uuid

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            logger.error("OPENROUTER_API_KEY обязателен для генерации видео: %s", exc)
            return False

        selected_method = (method or os.getenv("VIDEO_GENERATOR_METHOD", "wan")).lower()
        source_type = (source or "image").lower()
        logger.info(
            "Генерация видео для поста %s методом %s (source=%s)",
            post.id,
            selected_method,
            source_type
        )

        video_prompt = None
        if post.text:
            video_prompt = generator.generate_video_prompt(post.title, post.text)
        if video_prompt:
            logger.info("Используем AI-промпт для видео: %s", video_prompt[:120])

        if source_type == "text":
            if not post.text:
                logger.warning("Пост %s не содержит текста – видео по тексту невозможно", post.id)
                return False
            if selected_method != "veo":
                logger.error("Метод %s не поддерживает генерацию по тексту", selected_method)
                return False

            final_prompt = video_prompt or _build_text_video_prompt(post)
            result = generator.generate_video_from_text(
                prompt=final_prompt,
                method=selected_method
            )
        else:
            if not post.image:
                logger.warning("Пост %s не содержит изображения – видео не получится", post.id)
                return False

            default_prompt = (
                f"make this image come alive, cinematic motion, smooth animation. "
                f"Context: {post.title[:120]}"
            )
            negative_prompt = (
                "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, 整体发灰, 最差质量, "
                "低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, 画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, "
                "形态畸形的肢体, 手指融合, 静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
            )

            final_prompt = video_prompt or default_prompt
            if selected_method == "veo":
                final_prompt = (
                    final_prompt +
                    "\nUse the provided post image as the starting frame and animate it with cinematic motion."
                )
            result = generator.generate_video_from_image(
                image_path=post.image.path,
                prompt=final_prompt,
                method=selected_method,
                negative_prompt=negative_prompt
            )

        if not result.get("success"):
            logger.error("Ошибка генерации видео (%s): %s", selected_method, result.get("error"))
            return False

        video_temp_path = result.get("video_path")
        if not video_temp_path or not os.path.exists(video_temp_path):
            logger.error("Видео не найдено после генерации для поста %s", post.id)
            return False

        video_filename = f"post_{post.id}_{uuid.uuid4().hex[:8]}.mp4"

        if post.video:
            post.video.delete(save=False)

        with open(video_temp_path, "rb") as video_file:
            post.video.save(video_filename, File(video_file), save=True)

        for path in set(result.get("cleanup_paths", []) + [video_temp_path]):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

        logger.info("Видео (%s) успешно сохранено в пост %s", result.get("model", selected_method), post.id)
        return True

    except Post.DoesNotExist:
        logger.error(f"Пост с ID {post_id} не найден для генерации видео")
        return False
    except Exception as e:
        logger.error(f"Ошибка при генерации видео для поста {post_id}: {e}", exc_info=True)
        return False


@shared_task
def discover_telegram_trends_for_topic(topic_id: int, limit: int = 100):
    """
    Найти тренды из Telegram каналов для заданной темы.

    Эта задача:
    1. Получает тему из базы данных
    2. Получает клиента и его настройки Telegram
    3. Парсит telegram_source_channels (формат: "@rian_ru, @tjournal, @meduza")
    4. Собирает сообщения из указанных Telegram каналов по ключевым словам
    5. Сохраняет топ-5 самых популярных как TrendItem с источником 'telegram'

    Настройка в админке:
    - Client.telegram_api_id и telegram_api_hash (получить на my.telegram.org)
    - Client.telegram_source_channels: "@rian_ru, @tjournal" (по умолчанию)

    Args:
        topic_id: ID темы (Topic)
        limit: Максимальное количество сообщений для проверки в каждом канале

    Returns:
        Количество найденных и сохранённых трендов
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        client = topic.client

        # Проверяем настройки Telegram
        if not client.telegram_api_id or not client.telegram_api_hash:
            logger.error(f"Telegram API credentials не настроены для клиента {client.name}")
            return 0

        # Парсим список каналов
        channels_list = client.get_telegram_source_channels_list()
        if not channels_list:
            logger.warning(f"Нет Telegram каналов для клиента {client.name}")
            return 0

        logger.info(f"Начинаем поиск в Telegram каналах для темы: {topic.name}")
        logger.info(f"Каналы: {channels_list}")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        if not keywords:
            logger.warning(f"Нет ключевых слов для темы {topic.name}")
            return 0

        logger.info(f"Ключевые слова: {keywords}")

        # Загружаем last_message_ids для каждого канала (для инкрементального сбора)
        from django.conf import settings
        last_ids_file = os.path.join(
            settings.BASE_DIR,
            'telegram_sessions',
            f'last_ids_client_{client.id}.json'
        )

        last_message_ids = {}
        if os.path.exists(last_ids_file):
            try:
                with open(last_ids_file, 'r', encoding='utf-8') as f:
                    last_message_ids = json.load(f)
            except Exception as e:
                logger.warning(f"Не удалось загрузить last_message_ids: {e}")

        # Создаем коллектор контента
        collector = TelegramContentCollector(
            api_id=client.telegram_api_id,
            api_hash=client.telegram_api_hash,
            session_name=f"session_collector_client_{client.id}"
        )

        # Запускаем асинхронный поиск
        async def search_task():
            await collector.connect()
            try:
                results = await collector.search_in_channels(
                    channels=channels_list,
                    keywords=keywords,
                    limit=limit,
                    last_message_ids=last_message_ids
                )
                return results
            finally:
                await collector.disconnect()

        results = run_async_task(search_task())

        # Обрабатываем результаты
        created_count = 0
        all_messages = []

        for channel, messages in results.items():
            for msg_data in messages:
                all_messages.append({
                    'channel': channel,
                    'message': msg_data
                })

                # Обновляем last_message_id для канала
                current_last_id = last_message_ids.get(channel, 0)
                if msg_data['id'] > current_last_id:
                    last_message_ids[channel] = msg_data['id']

        # Сортируем по просмотрам и пересылкам
        all_messages.sort(
            key=lambda x: (x['message']['views'] + x['message']['forwards'] * 2),
            reverse=True
        )

        # Берем топ-5 самых популярных
        top_messages = all_messages[:5]

        # Сохраняем в базу данных
        for item in top_messages:
            msg_data = item['message']
            channel = item['channel']

            # Проверяем дубликаты по URL
            url = msg_data['url']
            existing = TrendItem.objects.filter(topic=topic, url=url).first()

            if existing:
                logger.debug(f"Тренд уже существует: {url}")
                continue

            # Создаём TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=client,
                source='telegram',
                title=msg_data['text'][:500],  # Первые 500 символов как заголовок
                description=msg_data['text'],
                url=url,
                relevance_score=msg_data['views'] + msg_data['forwards'] * 2,
                extra={
                    'channel': channel,
                    'message_id': msg_data['id'],
                    'date': msg_data['date'].isoformat(),
                    'views': msg_data['views'],
                    'forwards': msg_data['forwards'],
                    'has_media': msg_data['has_media'],
                    'media_type': msg_data['media_type'],
                }
            )

            created_count += 1
            logger.info(f"Создан Telegram тренд: {trend_item.title[:60]} (просмотры: {msg_data['views']})")

        # Сохраняем обновленные last_message_ids
        os.makedirs(os.path.dirname(last_ids_file), exist_ok=True)
        with open(last_ids_file, 'w', encoding='utf-8') as f:
            json.dump(last_message_ids, f, ensure_ascii=False, indent=2)

        logger.info(f"Успешно создано {created_count} новых Telegram трендов для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске Telegram трендов для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_rss_trends_for_topic(topic_id: int, limit: int = 5):
    """
    Найти новости из RSS фидов для заданной темы.

    Args:
        topic_id: ID темы (Topic)
        limit: Максимальное количество новостей

    Returns:
        Количество найденных и сохранённых новостей
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        client = topic.client

        # Получить список RSS фидов
        feed_urls = client.get_rss_source_feeds_list()
        if not feed_urls:
            logger.info(f"Нет RSS фидов для клиента {client.name}")
            return 0

        logger.info(f"Начинаем поиск в RSS фидах для темы: {topic.name}")
        logger.info(f"Фиды: {feed_urls}")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        # Собираем новости из RSS фидов
        rss_news = fetch_rss_feeds(feed_urls, keywords, limit)
        logger.info(f"Найдено {len(rss_news)} новостей из RSS фидов")

        # Сохраняем в базу данных
        created_count = 0
        for news_data in rss_news:
            url = news_data.get('url', '')

            # Проверяем дубликаты по URL
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    logger.debug(f"Новость уже существует: {url}")
                    continue

            # Создаём TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=client,
                source='rss_feed',
                title=news_data['title'],
                description=news_data.get('description', ''),
                url=url,
                relevance_score=news_data.get('relevance_score', 0),
                extra=news_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создана новость из RSS: {trend_item.title[:60]}")

        logger.info(f"Успешно создано {created_count} новых RSS новостей для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске RSS новостей для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_youtube_trends_for_topic(topic_id: int, limit: int = 5):
    """
    Найти видео из YouTube каналов для заданной темы.

    Args:
        topic_id: ID темы (Topic)
        limit: Максимальное количество видео

    Returns:
        Количество найденных и сохранённых видео
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        client = topic.client

        # Проверяем настройки YouTube
        if not client.youtube_api_key:
            logger.info(f"YouTube API ключ не настроен для клиента {client.name}")
            return 0

        # Получить список YouTube каналов
        channel_ids = client.get_youtube_source_channels_list()
        if not channel_ids:
            logger.info(f"Нет YouTube каналов для клиента {client.name}")
            return 0

        logger.info(f"Начинаем поиск в YouTube каналах для темы: {topic.name}")
        logger.info(f"Каналы: {channel_ids}")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        # Собираем видео из YouTube
        youtube_videos = fetch_youtube_videos(client.youtube_api_key, channel_ids, keywords, limit)
        logger.info(f"Найдено {len(youtube_videos)} видео из YouTube")

        # Сохраняем в базу данных
        created_count = 0
        for video_data in youtube_videos:
            url = video_data.get('url', '')

            # Проверяем дубликаты по URL
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    logger.debug(f"Видео уже существует: {url}")
                    continue

            # Создаём TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=client,
                source='youtube',
                title=video_data['title'],
                description=video_data.get('description', ''),
                url=url,
                relevance_score=video_data.get('relevance_score', 0),
                extra=video_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создано видео из YouTube: {trend_item.title[:60]} (просмотры: {video_data.get('extra', {}).get('view_count', 0)})")

        logger.info(f"Успешно создано {created_count} новых YouTube видео для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске YouTube видео для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_instagram_trends_for_topic(topic_id: int, limit: int = 5):
    """
    Найти посты из Instagram аккаунтов для заданной темы.

    ВНИМАНИЕ: Требует Instagram Business аккаунт и настроенный access_token.

    Args:
        topic_id: ID темы (Topic)
        limit: Максимальное количество постов

    Returns:
        Количество найденных и сохранённых постов
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        client = topic.client

        # Проверяем настройки Instagram
        if not client.instagram_access_token:
            logger.info(f"Instagram access token не настроен для клиента {client.name}")
            return 0

        # Получить список Instagram аккаунтов
        usernames = client.get_instagram_source_accounts_list()
        if not usernames:
            logger.info(f"Нет Instagram аккаунтов для клиента {client.name}")
            return 0

        logger.info(f"Начинаем поиск в Instagram аккаунтах для темы: {topic.name}")
        logger.info(f"Аккаунты: {usernames}")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        # Собираем посты из Instagram (пока заглушка)
        instagram_posts = fetch_instagram_posts(client.instagram_access_token, usernames, keywords, limit)
        logger.info(f"Найдено {len(instagram_posts)} постов из Instagram")

        # Сохраняем в базу данных
        created_count = 0
        for post_data in instagram_posts:
            url = post_data.get('url', '')

            # Проверяем дубликаты по URL
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    logger.debug(f"Пост уже существует: {url}")
                    continue

            # Создаём TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=client,
                source='instagram',
                title=post_data['title'],
                description=post_data.get('description', ''),
                url=url,
                relevance_score=post_data.get('relevance_score', 0),
                extra=post_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создан пост из Instagram: {trend_item.title[:60]}")

        logger.info(f"Успешно создано {created_count} новых Instagram постов для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске Instagram постов для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_google_trends_only(topic_id: int):
    """
    ДЕЙСТВИЕ 1: Найти тренды только из Google Trends (без новостей).

    Эта задача использует только Google Trends API для поиска трендов.

    Args:
        topic_id: ID темы (Topic)

    Returns:
        Количество найденных трендов
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        logger.info(f"=== ПОИСК ТРЕНДОВ (Google Trends) для темы: {topic.name} ===")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        if not keywords:
            logger.warning(f"Нет ключевых слов для темы {topic.name}")
            return 0

        logger.info(f"Ключевые слова: {keywords}")

        # Собираем тренды из Google Trends
        logger.info("Получаем данные из Google Trends...")
        google_trends = fetch_google_trends(keywords, limit=10)
        logger.info(f"Найдено {len(google_trends)} трендов из Google Trends")

        # Сохраняем в базу данных
        created_count = 0
        for trend_data in google_trends:
            url = trend_data.get('url', '')

            # Проверяем дубликаты по URL
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    logger.debug(f"Тренд уже существует: {trend_data['title'][:50]}")
                    continue

            # Создаём новый TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=topic.client,
                source='google_trends',
                title=trend_data['title'],
                description=trend_data.get('description', ''),
                url=url,
                relevance_score=trend_data.get('relevance_score', 0),
                extra=trend_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создан тренд: {trend_item.title[:60]}")

        logger.info(f"=== РЕЗУЛЬТАТ: Создано {created_count} новых трендов для темы '{topic.name}' ===")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске трендов для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_news_from_all_sources(topic_id: int):
    """
    ДЕЙСТВИЕ 2: Найти новости из всех настроенных источников.

    Эта задача собирает новости из всех источников, настроенных в клиенте:
    - Google News RSS
    - RSS фиды (указанные в настройках)
    - Telegram каналы
    - YouTube каналы
    - Instagram аккаунты

    Args:
        topic_id: ID темы (Topic)

    Returns:
        Общее количество найденных новостей
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        logger.info(f"=== ПОИСК НОВОСТЕЙ (все источники) для темы: {topic.name} ===")

        total_count = 0

        # 1. Google News RSS
        logger.info("Получаем новости из Google News RSS...")
        google_news_count = 0
        keywords = topic.keywords if topic.keywords else [topic.name]
        google_news = fetch_google_news_rss(keywords, limit=5)

        for news_data in google_news:
            url = news_data.get('url', '')
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    continue

            TrendItem.objects.create(
                topic=topic,
                client=topic.client,
                source='google_news_rss',
                title=news_data['title'],
                description=news_data.get('description', ''),
                url=url,
                relevance_score=news_data.get('relevance_score', 0),
                extra=news_data.get('extra', {})
            )
            google_news_count += 1

        logger.info(f"Google News RSS: {google_news_count} новостей")
        total_count += google_news_count

        # 2. RSS фиды
        rss_count = discover_rss_trends_for_topic(topic_id, limit=5)
        logger.info(f"RSS фиды: {rss_count} новостей")
        total_count += rss_count

        # 3. Telegram
        telegram_count = discover_telegram_trends_for_topic(topic_id, limit=5)
        logger.info(f"Telegram: {telegram_count} новостей")
        total_count += telegram_count

        # 4. YouTube
        youtube_count = discover_youtube_trends_for_topic(topic_id, limit=5)
        logger.info(f"YouTube: {youtube_count} новостей")
        total_count += youtube_count

        # 5. Instagram (пока заглушка)
        instagram_count = discover_instagram_trends_for_topic(topic_id, limit=5)
        logger.info(f"Instagram: {instagram_count} новостей")
        total_count += instagram_count

        logger.info(f"=== РЕЗУЛЬТАТ: Всего найдено {total_count} новостей из всех источников ===")
        return total_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске новостей для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_vkontakte_trends_for_topic(topic_id: int, limit: int = 5):
    """
    Найти посты из VKontakte групп для заданной темы.

    Args:
        topic_id: ID темы (Topic)
        limit: Максимальное количество постов

    Returns:
        Количество найденных и сохранённых постов
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        client = topic.client

        # Проверяем настройки VKontakte
        if not client.vkontakte_access_token:
            logger.info(f"VKontakte access token не настроен для клиента {client.name}")
            return 0

        # Получить список VK групп
        group_ids = client.get_vkontakte_source_groups_list()
        if not group_ids:
            logger.info(f"Нет VK групп для клиента {client.name}")
            return 0

        logger.info(f"Начинаем поиск в VK группах для темы: {topic.name}")
        logger.info(f"Группы: {group_ids}")

        # Формируем список ключевых слов
        keywords = topic.keywords if topic.keywords else [topic.name]

        # Собираем посты из VK
        vk_posts = fetch_vkontakte_posts(client.vkontakte_access_token, group_ids, keywords, limit)
        logger.info(f"Найдено {len(vk_posts)} постов из VK")

        # Сохраняем в базу данных
        created_count = 0
        for post_data in vk_posts:
            url = post_data.get('url', '')

            # Проверяем дубликаты по URL
            if url:
                existing = TrendItem.objects.filter(topic=topic, url=url).first()
                if existing:
                    logger.debug(f"Пост уже существует: {url}")
                    continue

            # Создаём TrendItem
            trend_item = TrendItem.objects.create(
                topic=topic,
                client=client,
                source='vkontakte',
                title=post_data['title'],
                description=post_data.get('description', ''),
                url=url,
                relevance_score=post_data.get('relevance_score', 0),
                extra=post_data.get('extra', {})
            )

            created_count += 1
            logger.info(f"Создан пост из VK: {trend_item.title[:60]} (лайки: {post_data.get('extra', {}).get('likes', 0)})")

        logger.info(f"Успешно создано {created_count} новых VK постов для темы '{topic.name}'")
        return created_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске VK постов для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_content_for_topic(topic_id: int):
    """
    ОСНОВНАЯ ЗАДАЧА: Найти контент для темы из выбранных источников.

    Эта задача анализирует настройки топика (use_google_trends, use_telegram и т.д.)
    и запускает соответствующие задачи сбора контента только из включенных источников.

    Args:
        topic_id: ID темы (Topic)

    Returns:
        Общее количество найденного контента
    """
    try:
        topic = Topic.objects.select_related('client').get(id=topic_id)

        if not topic.is_active:
            logger.info(f"Тема '{topic.name}' неактивна, пропускаем")
            return 0

        logger.info(f"=== ПОИСК КОНТЕНТА для темы: {topic.name} ===")

        # Получить список включенных источников
        enabled_sources = topic.get_enabled_sources()

        if not enabled_sources:
            logger.warning(f"Нет включенных источников для темы '{topic.name}'")
            logger.warning("Включите хотя бы один источник в настройках топика")
            return 0

        logger.info(f"Включенные источники: {', '.join(enabled_sources)}")

        total_count = 0

        # 1. Google Trends
        if 'google_trends' in enabled_sources:
            logger.info("Ищем в Google Trends...")
            trends_count = discover_google_trends_only(topic_id)
            logger.info(f"Google Trends: {trends_count} трендов")
            total_count += trends_count

        # 2. Telegram
        if 'telegram' in enabled_sources:
            logger.info("Ищем в Telegram каналах...")
            telegram_count = discover_telegram_trends_for_topic(topic_id, limit=5)
            logger.info(f"Telegram: {telegram_count} новостей")
            total_count += telegram_count

        # 3. RSS
        if 'rss' in enabled_sources:
            logger.info("Ищем в RSS фидах...")
            rss_count = discover_rss_trends_for_topic(topic_id, limit=5)
            logger.info(f"RSS: {rss_count} новостей")
            total_count += rss_count

        # 4. YouTube
        if 'youtube' in enabled_sources:
            logger.info("Ищем в YouTube каналах...")
            youtube_count = discover_youtube_trends_for_topic(topic_id, limit=5)
            logger.info(f"YouTube: {youtube_count} видео")
            total_count += youtube_count

        # 5. Instagram
        if 'instagram' in enabled_sources:
            logger.info("Ищем в Instagram аккаунтах...")
            instagram_count = discover_instagram_trends_for_topic(topic_id, limit=5)
            logger.info(f"Instagram: {instagram_count} постов")
            total_count += instagram_count

        # 6. VKontakte
        if 'vkontakte' in enabled_sources:
            logger.info("Ищем в VK группах...")
            vk_count = discover_vkontakte_trends_for_topic(topic_id, limit=5)
            logger.info(f"VKontakte: {vk_count} постов")
            total_count += vk_count

        logger.info(f"=== РЕЗУЛЬТАТ: Всего найдено {total_count} материалов из {len(enabled_sources)} источников ===")
        return total_count

    except Topic.DoesNotExist:
        logger.error(f"Тема с ID {topic_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при поиске контента для темы {topic_id}: {e}", exc_info=True)
        return 0


@shared_task
def discover_trends_for_topic_with_telegram(topic_id: int):
    """
    УСТАРЕВШАЯ: Найти тренды для темы из всех источников, включая Telegram.

    РЕКОМЕНДУЕТСЯ использовать:
    - discover_content_for_topic() для поиска контента из выбранных источников

    Args:
        topic_id: ID темы (Topic)

    Returns:
        Общее количество найденных трендов
    """
    # Запускаем поиск в Google
    google_count = discover_trends_for_topic(topic_id)

    # Запускаем поиск в Telegram
    telegram_count = discover_telegram_trends_for_topic(topic_id)

    total = google_count + telegram_count
    logger.info(f"Всего найдено трендов для темы {topic_id}: {total} (Google: {google_count}, Telegram: {telegram_count})")

    return total


# ============================================================================
# ЗАДАЧИ ДЛЯ РАБОТЫ С ИСТОРИЯМИ (STORIES)
# ============================================================================

@shared_task
def generate_story_from_trend(trend_item_id: int, episode_count: int = 5, template_id: int = None):
    """
    Генерация истории (мини-сериала) из тренда.

    Args:
        trend_item_id: ID тренда (TrendItem)
        episode_count: Количество эпизодов (по умолчанию 5)
        template_id: ID шаблона контента (ContentTemplate) для постов (опционально)

    Returns:
        ID созданной истории или None при ошибке
    """
    from .models import Story

    try:
        trend = TrendItem.objects.select_related('client', 'topic').get(id=trend_item_id)
        client = trend.client
        topic = trend.topic

        # Валидация количества эпизодов
        if not (2 <= episode_count <= 20):
            logger.error(f"Недопустимое количество эпизодов: {episode_count}. Должно быть от 2 до 20")
            return None

        # Получить шаблон если указан
        template = None
        if template_id:
            try:
                template = ContentTemplate.objects.get(id=template_id, client=client)
            except ContentTemplate.DoesNotExist:
                logger.warning(f"Шаблон {template_id} не найден, продолжаем без шаблона")

        logger.info(f"Генерация истории из тренда: {trend.title[:60]} ({episode_count} эпизодов)")

        # Инициализация AI генератора
        generator = AIContentGenerator()

        # Генерация эпизодов истории
        result = generator.generate_story_episodes(
            trend_title=trend.title,
            trend_description=trend.description,
            topic_name=topic.name,
            episode_count=episode_count,
            client_desires=client.desires or "",
            language="ru"
        )

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            logger.error(f"Ошибка генерации истории: {error}")
            return None

        # Создание истории
        story = Story.objects.create(
            client=client,
            trend_item=trend,
            template=template,
            title=result["title"],
            episodes=result["episodes"],
            episode_count=len(result["episodes"]),
            status="ready",
            generated_by="openrouter-chimera"
        )

        logger.info(f"История успешно создана: {story.title} (ID: {story.id})")
        return story.id

    except TrendItem.DoesNotExist:
        logger.error(f"Тренд {trend_item_id} не найден")
        return None
    except Exception as e:
        logger.error(f"Ошибка создания истории из тренда {trend_item_id}: {e}", exc_info=True)
        return None


@shared_task
def generate_posts_from_story(story_id: int):
    """
    Генерация постов из эпизодов истории.

    Args:
        story_id: ID истории (Story)

    Returns:
        Количество созданных постов
    """
    from .models import Story

    try:
        story = Story.objects.select_related('client', 'trend_item', 'template').get(id=story_id)

        if not story.episodes:
            logger.error(f"История {story_id} не содержит эпизодов")
            return 0

        # Обновляем статус истории
        story.status = "generating_posts"
        story.save()

        logger.info(f"Генерация постов для истории: {story.title} ({len(story.episodes)} эпизодов)")

        # Получаем или создаем конфигурацию шаблона
        if story.template:
            template_config = {
                "tone": story.template.tone,
                "length": story.template.length,
                "language": story.template.language,
                "type": story.template.type,
                "include_hashtags": story.template.include_hashtags,
                "max_hashtags": story.template.max_hashtags,
                "additional_instructions": story.template.additional_instructions,
            }
        else:
            # Дефолтная конфигурация
            template_config = {
                "tone": "friendly",
                "length": "medium",
                "language": "ru",
                "type": "story",
                "include_hashtags": True,
                "max_hashtags": 5,
                "additional_instructions": "",
            }

        # Информация о клиенте
        client_info = {
            "avatar": story.client.avatar or "",
            "pains": story.client.pains or "",
            "desires": story.client.desires or "",
            "objections": story.client.objections or "",
        }

        # Инициализация AI генератора
        generator = AIContentGenerator()

        created_count = 0
        total_episodes = len(story.episodes)

        # Генерируем пост для каждого эпизода
        for episode in story.episodes:
            episode_number = episode["order"]
            episode_title = episode["title"]

            logger.info(f"Генерация поста для эпизода {episode_number}/{total_episodes}: {episode_title[:60]}")

            # Генерация поста
            result = generator.generate_post_from_episode(
                story_title=story.title,
                episode_title=episode_title,
                episode_number=episode_number,
                total_episodes=total_episodes,
                topic_name=story.trend_item.topic.name if story.trend_item else "unknown",
                template_config=template_config,
                client_info=client_info
            )

            if not result.get("success"):
                logger.error(f"Ошибка генерации поста для эпизода {episode_number}: {result.get('error')}")
                continue

            # Создание поста
            post = Post.objects.create(
                client=story.client,
                story=story,
                episode_number=episode_number,
                title=result["title"],
                text=result["text"],
                status="ready",
                tags=result.get("hashtags", []),
                generated_by="openrouter-grok",
                regeneration_count=0
            )

            logger.info(f"Пост создан: {post.title} (ID: {post.id})")
            created_count += 1

        # Обновляем статус истории
        if created_count == total_episodes:
            story.status = "completed"
        else:
            story.status = "ready"  # Возвращаем в ready если не все посты созданы
        story.save()

        logger.info(f"Создано {created_count}/{total_episodes} постов для истории {story.title}")
        return created_count

    except Story.DoesNotExist:
        logger.error(f"История {story_id} не найдена")
        return 0
    except Exception as e:
        logger.error(f"Ошибка генерации постов для истории {story_id}: {e}", exc_info=True)
        return 0


@shared_task
def regenerate_post_text(post_id: int):
    """
    Регенерация текста поста.

    Args:
        post_id: ID поста (Post)

    Returns:
        True если успешно, False при ошибке
    """
    try:
        post = Post.objects.select_related('client', 'story').get(id=post_id)

        logger.info(f"Регенерация текста для поста: {post.title[:60]}")

        # Инициализация AI генератора
        generator = AIContentGenerator()

        # Если пост из истории
        if post.story:
            story = post.story
            episode = next((ep for ep in story.episodes if ep["order"] == post.episode_number), None)

            if not episode:
                logger.error(f"Эпизод {post.episode_number} не найден в истории {story.id}")
                return False

            # Получаем конфигурацию шаблона
            if story.template:
                template_config = {
                    "tone": story.template.tone,
                    "length": story.template.length,
                    "language": story.template.language,
                    "type": story.template.type,
                    "include_hashtags": story.template.include_hashtags,
                    "max_hashtags": story.template.max_hashtags,
                    "additional_instructions": story.template.additional_instructions,
                }
            else:
                template_config = {
                    "tone": "friendly",
                    "length": "medium",
                    "language": "ru",
                    "type": "story",
                    "include_hashtags": True,
                    "max_hashtags": 5,
                    "additional_instructions": "",
                }

            # Информация о клиенте
            client_info = {
                "avatar": post.client.avatar or "",
                "pains": post.client.pains or "",
                "desires": post.client.desires or "",
                "objections": post.client.objections or "",
            }

            # Регенерация из эпизода
            result = generator.generate_post_from_episode(
                story_title=story.title,
                episode_title=episode["title"],
                episode_number=post.episode_number,
                total_episodes=len(story.episodes),
                topic_name=story.trend_item.topic.name if story.trend_item else "unknown",
                template_config=template_config,
                client_info=client_info
            )

        else:
            # Пост из тренда (обычный пост)
            # Получаем исходный тренд
            trend = post.source_trends.first()

            if not trend:
                logger.error(f"Не найден исходный тренд для поста {post.id}")
                return False

            # Получаем шаблон (пока используем дефолтный)
            template_config = {
                "tone": "friendly",
                "length": "medium",
                "language": "ru",
                "type": "selling",
                "include_hashtags": True,
                "max_hashtags": 5,
                "additional_instructions": "",
                "avatar": post.client.avatar or "",
                "pains": post.client.pains or "",
                "desires": post.client.desires or "",
                "objections": post.client.objections or "",
                "seo_prompt_template": "",
                "trend_prompt_template": "",
                "prompt_type": "trend",
            }

            # Регенерация из тренда
            result = generator.generate_post_text(
                trend_title=trend.title,
                trend_description=trend.description,
                trend_url=trend.url or "",
                topic_name=trend.topic.name,
                template_config=template_config
            )

        if not result.get("success"):
            logger.error(f"Ошибка регенерации поста: {result.get('error')}")
            return False

        # Обновляем пост
        post.title = result["title"]
        post.text = result["text"]
        post.tags = result.get("hashtags", [])
        post.regeneration_count += 1
        post.save()

        logger.info(f"Пост успешно регенерирован: {post.title} (регенераций: {post.regeneration_count})")
        return True

    except Post.DoesNotExist:
        logger.error(f"Пост {post_id} не найден")
        return False
    except Exception as e:
        logger.error(f"Ошибка регенерации поста {post_id}: {e}", exc_info=True)
        return False


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
    from .models import Story, SocialAccount
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


@shared_task(bind=True, max_retries=3)
def analyze_telegram_channel_task(self, client_id: int):
    """
    Celery задача для анализа Telegram канала и заполнения профиля аудитории.

    Получает последние 20 постов из Telegram канала клиента,
    анализирует их с помощью AI и заполняет поля:
    - Аватар клиента (avatar)
    - Боли (pains)
    - Хотелки (desires)
    - Возражения/страхи (objections)

    Args:
        client_id: ID клиента

    Returns:
        dict: Результат анализа с заполненными полями
    """
    try:
        from django.conf import settings

        # Получаем клиента
        client = Client.objects.get(id=client_id)
        logger.info(f"Начат анализ Telegram канала для клиента {client.name} (ID: {client_id})")

        # Проверяем наличие необходимых данных
        if not client.telegram_client_channel:
            logger.error(f"У клиента {client_id} не указан telegram_client_channel")
            return {"success": False, "error": "Не указан Telegram канал"}

        # Используем credentials клиента или системные по умолчанию
        api_id = client.telegram_api_id or settings.TELEGRAM_API_ID
        api_hash = client.telegram_api_hash or settings.TELEGRAM_API_HASH

        # Определяем имя сессии: если у клиента свои credentials - используем его сессию,
        # иначе используем общую системную сессию
        if client.telegram_api_id and client.telegram_api_hash:
            session_name = f"session_collector_client_{client_id}"
            logger.info(f"Используются клиентские Telegram API credentials")
        else:
            # Переиспользуем системную сессию (например, клиента 3)
            session_name = "session_collector_client_3"
            logger.info(f"Используются системные Telegram API credentials с переиспользованием сессии")

        if not api_id or not api_hash:
            logger.error(f"Не указаны Telegram API credentials (ни у клиента {client_id}, ни системные)")
            return {"success": False, "error": "Не указаны Telegram API ID и Hash. Получите их на my.telegram.org"}

        # Инициализируем TelegramContentCollector
        collector = TelegramContentCollector(
            api_id=api_id,
            api_hash=api_hash,
            session_name=session_name
        )

        # Получаем последние 20 постов из канала
        logger.info(f"Получение последних 20 постов из канала {client.telegram_client_channel}")

        # Создаем асинхронную функцию для подключения и получения сообщений
        async def get_messages_with_connection():
            try:
                await collector.connect()
                messages = await collector.get_channel_messages(
                    channel_username=client.telegram_client_channel,
                    limit=20
                )
                return messages
            finally:
                await collector.disconnect()

        # Используем run_async_task для запуска асинхронной функции
        messages = run_async_task(get_messages_with_connection())

        if not messages:
            logger.warning(f"Не удалось получить сообщения из канала {client.telegram_client_channel}")
            return {"success": False, "error": "Не удалось получить посты из канала. Проверьте правильность имени канала и API credentials."}

        logger.info(f"Получено {len(messages)} постов из канала")

        # Формируем текст постов для анализа
        posts_text = "\n\n---ПОСТ---\n\n".join([
            msg.get('text', '') for msg in messages if msg.get('text')
        ])

        if not posts_text.strip():
            logger.warning(f"Все посты из канала {client.telegram_client_channel} пустые")
            return {"success": False, "error": "В канале нет текстовых постов для анализа"}

        # Создаем промпт для AI анализа
        analysis_prompt = f"""Проанализируй последние 20 постов из Telegram канала и определи профиль целевой аудитории.

ВАЖНО: Эти посты написаны ДЛЯ целевой аудитории, чтобы продать им что-то.
Тебе нужно определить:
1. **Аватар клиента** - кто эта целевая аудитория (например: "Мама двоих детей, работает удалённо, хочет больше времени для себя")
2. **Боли** - какие проблемы и боли есть у этой аудитории (например: "нет времени на себя, стресс, лишний вес, низкая самооценка")
3. **Хотелки** - что эта аудитория хочет получить, чего они желают (например: "похудеть к лету, научиться танцевать, найти хобби, познакомиться с новыми людьми")
4. **Возражения/страхи** - какие страхи и возражения могут быть у этой аудитории (например: "дорого, нет времени, боюсь выглядеть глупо, не получится")

Посты из канала:
{posts_text}

Верни результат СТРОГО в JSON формате:
{{
  "avatar": "Описание целевой аудитории",
  "pains": "Боли и проблемы аудитории",
  "desires": "Желания и цели аудитории",
  "objections": "Страхи и возражения аудитории"
}}

Важно: возвращай ТОЛЬКО JSON, без дополнительного текста."""

        # Используем AI для анализа (модель берется из системных настроек автоматически)
        generator = AIContentGenerator()

        logger.info(f"Отправка запроса к AI модели {generator.model} для анализа")

        response = generator.get_ai_response(analysis_prompt, max_tokens=2000, temperature=0.5)

        if not response:
            logger.error(f"AI не вернула ответ для клиента {client_id}")
            return {"success": False, "error": "AI не смогла проанализировать посты"}

        logger.info(f"Получен ответ от AI: {response[:200]}...")

        # Парсим JSON ответ
        try:
            # Пытаемся извлечь JSON из ответа (на случай если AI добавила текст вокруг)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group(0)

            analysis_result = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Не удалось распарсить JSON ответ от AI: {e}\nОтвет: {response}")
            return {"success": False, "error": "AI вернула некорректный формат ответа"}

        # Обновляем поля клиента (не затираем старые данные, а добавляем новые)
        def append_or_set_field(current_value: str, new_value: str) -> str:
            """Добавить новое значение к существующему или установить новое."""
            new_value = new_value.strip()
            if not new_value:
                return current_value

            if current_value and current_value.strip():
                # Если поле уже заполнено - добавляем после пустой строки
                return f"{current_value}\n\n-----Определено по данным канала:\n{new_value}"
            else:
                # Если поле пустое - просто устанавливаем новое значение
                return new_value

        client.avatar = append_or_set_field(client.avatar or '', analysis_result.get('avatar', ''))
        client.pains = append_or_set_field(client.pains or '', analysis_result.get('pains', ''))
        client.desires = append_or_set_field(client.desires or '', analysis_result.get('desires', ''))
        client.objections = append_or_set_field(client.objections or '', analysis_result.get('objections', ''))
        client.save()

        logger.info(f"Профиль аудитории успешно обновлен для клиента {client.name}")

        return {
            "success": True,
            "client_id": client_id,
            "avatar": client.avatar,
            "pains": client.pains,
            "desires": client.desires,
            "objections": client.objections
        }

    except Client.DoesNotExist:
        logger.error(f"Клиент {client_id} не найден")
        return {"success": False, "error": "Клиент не найден"}
    except Exception as e:
        logger.error(f"Ошибка анализа Telegram канала для клиента {client_id}: {e}", exc_info=True)
        # Retry задачи при ошибке
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)  # Повторить через 60 секунд
        return {"success": False, "error": str(e)}
