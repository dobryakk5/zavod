from celery import shared_task
import logging
import json
import os
import re

from ..models import Topic, TrendItem, Client
from ..aggregator import (
    fetch_google_trends,
    fetch_google_news_rss,
    fetch_rss_feeds,
    fetch_youtube_videos,
    fetch_instagram_posts,
    fetch_vkontakte_posts,
    deduplicate_trends
)
from ..telegram_client import TelegramContentCollector, run_async_task
from ..ai_generator import AIContentGenerator

logger = logging.getLogger(__name__)


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
