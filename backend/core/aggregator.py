"""
Модуль для агрегации контента из внешних источников.
Собирает тренды из Google Trends и новости из Google News RSS.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def fetch_google_trends(keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить текущие тренды из Google Trends для заданных ключевых слов.

    Args:
        keywords: Список ключевых слов для поиска
        limit: Максимальное количество трендов (по умолчанию 5)

    Returns:
        Список словарей с данными трендов:
        {
            'title': str,
            'description': str,
            'url': str,
            'relevance_score': int,
            'extra': dict
        }
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl='ru-RU', tz=360)

        results = []

        # Получить связанные запросы для каждого ключевого слова
        for keyword in keywords[:3]:  # Ограничим количество запросов
            try:
                # Построить запрос для interest over time
                pytrends.build_payload([keyword], cat=0, timeframe='now 7-d', geo='', gprop='')

                # Получить связанные запросы
                related_queries = pytrends.related_queries()

                if keyword in related_queries:
                    top_queries = related_queries[keyword].get('top')

                    if top_queries is not None and not top_queries.empty:
                        for idx, row in top_queries.head(limit).iterrows():
                            query = row['query']
                            value = int(row['value'])

                            results.append({
                                'title': f"{query} (связано с '{keyword}')",
                                'description': f"Популярный поисковый запрос, связанный с темой '{keyword}'",
                                'url': f"https://trends.google.com/trends/explore?q={query}",
                                'relevance_score': value,
                                'extra': {
                                    'keyword': keyword,
                                    'query': query,
                                    'value': value,
                                    'type': 'related_query'
                                }
                            })

                # Также получить rising queries (растущие запросы)
                rising_queries = related_queries[keyword].get('rising')

                if rising_queries is not None and not rising_queries.empty:
                    for idx, row in rising_queries.head(3).iterrows():
                        query = row['query']
                        value = row['value']

                        # Value может быть "Breakout" или числом
                        score = 1000 if value == "Breakout" else int(value) if isinstance(value, (int, float)) else 500

                        results.append({
                            'title': f"🔥 {query} (растущий тренд для '{keyword}')",
                            'description': f"Быстро растущий поисковый запрос по теме '{keyword}'",
                            'url': f"https://trends.google.com/trends/explore?q={query}",
                            'relevance_score': score,
                            'extra': {
                                'keyword': keyword,
                                'query': query,
                                'value': str(value),
                                'type': 'rising_query'
                            }
                        })

            except Exception as e:
                logger.warning(f"Ошибка при получении трендов для '{keyword}': {e}")
                continue

        # Сортировать по relevance_score и вернуть топ результатов
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]

    except ImportError:
        logger.error("pytrends не установлен. Установите: pip install pytrends")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении Google Trends: {e}")
        return []


def fetch_google_news_rss(keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить новости из Google News RSS для заданных ключевых слов.

    Args:
        keywords: Список ключевых слов для поиска
        limit: Максимальное количество новостей (по умолчанию 5)

    Returns:
        Список словарей с данными новостей:
        {
            'title': str,
            'description': str,
            'url': str,
            'relevance_score': int,
            'extra': dict
        }
    """
    try:
        import feedparser
        import requests
        from urllib.parse import quote

        results = []

        for keyword in keywords[:3]:  # Ограничим количество запросов
            try:
                # Google News RSS URL
                # https://news.google.com/rss/search?q=ключевое+слово&hl=ru&gl=RU&ceid=RU:ru
                encoded_keyword = quote(keyword)
                rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ru&gl=RU&ceid=RU:ru"

                logger.info(f"Получение новостей для '{keyword}' из Google News RSS")

                # Получить RSS feed
                feed = feedparser.parse(rss_url)

                # Обработать записи
                for entry in feed.entries[:limit]:
                    title = entry.get('title', 'Без названия')
                    link = entry.get('link', '')
                    description = entry.get('summary', '')
                    published = entry.get('published', '')
                    source = entry.get('source', {}).get('title', 'Неизвестный источник')

                    # Попытаться распарсить дату
                    published_date = None
                    if published:
                        try:
                            from email.utils import parsedate_to_datetime
                            published_date = parsedate_to_datetime(published)
                        except:
                            pass

                    # Рассчитать relevance_score на основе свежести (более свежие = выше score)
                    relevance_score = 50  # базовый score
                    if published_date:
                        age_hours = (datetime.now(published_date.tzinfo) - published_date).total_seconds() / 3600
                        # Более свежие новости получают больше баллов
                        if age_hours < 24:
                            relevance_score = 100
                        elif age_hours < 48:
                            relevance_score = 80
                        elif age_hours < 72:
                            relevance_score = 60

                    results.append({
                        'title': title,
                        'description': description,
                        'url': link,
                        'relevance_score': relevance_score,
                        'extra': {
                            'keyword': keyword,
                            'source': source,
                            'published': published,
                            'published_date': published_date.isoformat() if published_date else None,
                        }
                    })

            except Exception as e:
                logger.warning(f"Ошибка при получении новостей для '{keyword}': {e}")
                continue

        # Сортировать по relevance_score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]

    except ImportError as e:
        logger.error(f"Необходимая библиотека не установлена: {e}. Установите: pip install feedparser")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении Google News RSS: {e}")
        return []


def fetch_rss_feeds(feed_urls: List[str], keywords: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить новости из RSS/Atom фидов.

    Args:
        feed_urls: Список URL RSS/Atom фидов
        keywords: Опциональный список ключевых слов для фильтрации (если None, возвращаются все)
        limit: Максимальное количество новостей с каждого фида

    Returns:
        Список словарей с данными новостей
    """
    try:
        import feedparser
        from datetime import datetime
        from email.utils import parsedate_to_datetime

        results = []

        for feed_url in feed_urls:
            try:
                logger.info(f"Получение RSS фида: {feed_url}")
                feed = feedparser.parse(feed_url)

                for entry in feed.entries[:limit * 2]:  # Берём больше для фильтрации
                    title = entry.get('title', 'Без названия')
                    link = entry.get('link', '')
                    description = entry.get('summary', entry.get('description', ''))
                    published = entry.get('published', entry.get('updated', ''))

                    # Фильтрация по ключевым словам (если указаны)
                    if keywords:
                        text_to_search = (title + ' ' + description).lower()
                        if not any(kw.lower() in text_to_search for kw in keywords):
                            continue

                    # Попытаться распарсить дату
                    published_date = None
                    if published:
                        try:
                            published_date = parsedate_to_datetime(published)
                        except:
                            pass

                    # Рассчитать relevance_score на основе свежести
                    relevance_score = 50
                    if published_date:
                        age_hours = (datetime.now(published_date.tzinfo) - published_date).total_seconds() / 3600
                        if age_hours < 24:
                            relevance_score = 100
                        elif age_hours < 48:
                            relevance_score = 80
                        elif age_hours < 72:
                            relevance_score = 60

                    results.append({
                        'title': title,
                        'description': description,
                        'url': link,
                        'relevance_score': relevance_score,
                        'extra': {
                            'feed_url': feed_url,
                            'published': published,
                            'published_date': published_date.isoformat() if published_date else None,
                        }
                    })

                    if len(results) >= limit * len(feed_urls):
                        break

            except Exception as e:
                logger.warning(f"Ошибка при получении RSS фида '{feed_url}': {e}")
                continue

        # Сортировать по relevance_score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]

    except ImportError as e:
        logger.error(f"feedparser не установлен: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении RSS фидов: {e}")
        return []


def fetch_youtube_videos(api_key: str, channel_ids: List[str], keywords: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить последние видео из YouTube каналов.

    Args:
        api_key: YouTube Data API v3 ключ
        channel_ids: Список ID каналов или handles (например, UC_x5XG1OV2P6uZZ5FSM9Ttw или @channel_handle)
        keywords: Опциональный список ключевых слов для фильтрации
        limit: Максимальное количество видео с каждого канала

    Returns:
        Список словарей с данными видео
    """
    try:
        import requests
        from datetime import datetime
        from urllib.parse import quote

        if not api_key:
            logger.error("YouTube API ключ не предоставлен")
            return []

        results = []

        for channel_id in channel_ids:
            try:
                # Если channel_id начинается с @, нужно сначала получить реальный ID
                if channel_id.startswith('@'):
                    # Поиск канала по handle
                    search_url = "https://www.googleapis.com/youtube/v3/search"
                    search_params = {
                        'key': api_key,
                        'q': channel_id,
                        'type': 'channel',
                        'part': 'snippet',
                        'maxResults': 1
                    }
                    search_response = requests.get(search_url, params=search_params)
                    search_response.raise_for_status()
                    search_data = search_response.json()

                    if not search_data.get('items'):
                        logger.warning(f"Канал {channel_id} не найден")
                        continue

                    channel_id = search_data['items'][0]['snippet']['channelId']

                # Получить последние видео канала
                logger.info(f"Получение видео из YouTube канала: {channel_id}")

                search_url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    'key': api_key,
                    'channelId': channel_id,
                    'part': 'snippet',
                    'order': 'date',
                    'type': 'video',
                    'maxResults': limit * 2  # Берём больше для фильтрации
                }

                response = requests.get(search_url, params=params)
                response.raise_for_status()
                data = response.json()

                for item in data.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']

                    title = snippet.get('title', 'Без названия')
                    description = snippet.get('description', '')
                    published = snippet.get('publishedAt', '')
                    thumbnail = snippet.get('thumbnails', {}).get('high', {}).get('url', '')

                    # Фильтрация по ключевым словам
                    if keywords:
                        text_to_search = (title + ' ' + description).lower()
                        if not any(kw.lower() in text_to_search for kw in keywords):
                            continue

                    # Получить статистику видео (просмотры, лайки)
                    stats_url = "https://www.googleapis.com/youtube/v3/videos"
                    stats_params = {
                        'key': api_key,
                        'id': video_id,
                        'part': 'statistics'
                    }
                    stats_response = requests.get(stats_url, params=stats_params)
                    stats_data = stats_response.json()

                    view_count = 0
                    like_count = 0
                    if stats_data.get('items'):
                        statistics = stats_data['items'][0].get('statistics', {})
                        view_count = int(statistics.get('viewCount', 0))
                        like_count = int(statistics.get('likeCount', 0))

                    # Рассчитать relevance_score на основе просмотров и свежести
                    relevance_score = min(view_count // 100, 1000)  # Макс 1000

                    # Добавить бонус за свежесть
                    if published:
                        try:
                            published_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                            age_hours = (datetime.now(published_date.tzinfo) - published_date).total_seconds() / 3600
                            if age_hours < 24:
                                relevance_score += 200
                            elif age_hours < 48:
                                relevance_score += 100
                        except:
                            pass

                    results.append({
                        'title': title,
                        'description': description,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'relevance_score': relevance_score,
                        'extra': {
                            'video_id': video_id,
                            'channel_id': channel_id,
                            'published': published,
                            'thumbnail': thumbnail,
                            'view_count': view_count,
                            'like_count': like_count,
                        }
                    })

                    if len(results) >= limit * len(channel_ids):
                        break

            except Exception as e:
                logger.warning(f"Ошибка при получении видео из канала '{channel_id}': {e}")
                continue

        # Сортировать по relevance_score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]

    except ImportError as e:
        logger.error(f"requests не установлен: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении YouTube видео: {e}")
        return []


def fetch_instagram_posts(access_token: str, usernames: List[str], keywords: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить последние посты из Instagram аккаунтов через Graph API.

    ВНИМАНИЕ: Для работы требуется Instagram Business или Creator аккаунт
    и access_token с правами instagram_basic, instagram_content_publish.

    Args:
        access_token: Instagram Graph API токен доступа
        usernames: Список Instagram аккаунтов (usernames)
        keywords: Опциональный список ключевых слов для фильтрации
        limit: Максимальное количество постов с каждого аккаунта

    Returns:
        Список словарей с данными постов
    """
    try:
        import requests

        if not access_token:
            logger.error("Instagram access token не предоставлен")
            return []

        results = []

        # Примечание: Instagram Graph API требует бизнес-аккаунты
        # Этот код является заглушкой и требует дополнительной настройки
        logger.warning("Instagram API интеграция требует настройки бизнес-аккаунта и разрешений")
        logger.warning("Функция fetch_instagram_posts является заглушкой и требует доработки")

        # TODO: Реализовать полноценную интеграцию с Instagram Graph API
        # Документация: https://developers.facebook.com/docs/instagram-api/

        return results

    except Exception as e:
        logger.error(f"Ошибка при получении Instagram постов: {e}")
        return []


def fetch_vkontakte_posts(access_token: str, group_ids: List[str], keywords: List[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Получить последние посты из VK групп через VK API.

    Args:
        access_token: VK API токен доступа
        group_ids: Список ID групп или коротких имен (например: apiclub, thecode)
        keywords: Опциональный список ключевых слов для фильтрации
        limit: Максимальное количество постов с каждой группы

    Returns:
        Список словарей с данными постов
    """
    try:
        import requests
        from datetime import datetime

        if not access_token:
            logger.error("VKontakte access token не предоставлен")
            return []

        results = []
        api_version = "5.131"

        for group_id in group_ids:
            try:
                # Получить посты со стены группы
                logger.info(f"Получение постов из VK группы: {group_id}")

                url = "https://api.vk.com/method/wall.get"
                params = {
                    'access_token': access_token,
                    'v': api_version,
                    'domain': group_id,  # Можно использовать короткое имя или ID
                    'count': limit * 2,  # Берём больше для фильтрации
                    'filter': 'owner'  # Только посты владельца (не репосты)
                }

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                if 'error' in data:
                    logger.error(f"VK API ошибка для группы {group_id}: {data['error'].get('error_msg')}")
                    continue

                items = data.get('response', {}).get('items', [])

                for item in items:
                    post_id = item.get('id')
                    owner_id = item.get('owner_id')
                    text = item.get('text', '')
                    date = item.get('date', 0)
                    likes = item.get('likes', {}).get('count', 0)
                    reposts = item.get('reposts', {}).get('count', 0)
                    views = item.get('views', {}).get('count', 0)
                    comments = item.get('comments', {}).get('count', 0)

                    # Фильтрация по ключевым словам
                    if keywords:
                        if not any(kw.lower() in text.lower() for kw in keywords):
                            continue

                    # Получить URL поста
                    post_url = f"https://vk.com/wall{owner_id}_{post_id}"

                    # Рассчитать relevance_score на основе взаимодействий
                    relevance_score = likes + reposts * 3 + comments * 2 + (views // 100 if views else 0)

                    # Добавить бонус за свежесть
                    if date:
                        try:
                            post_date = datetime.fromtimestamp(date)
                            now = datetime.now()
                            age_hours = (now - post_date).total_seconds() / 3600
                            if age_hours < 24:
                                relevance_score += 100
                            elif age_hours < 48:
                                relevance_score += 50
                        except:
                            pass

                    # Обрезать текст для title
                    title = text[:200] if len(text) > 200 else text
                    if not title:
                        title = f"Пост от {group_id}"

                    results.append({
                        'title': title,
                        'description': text,
                        'url': post_url,
                        'relevance_score': relevance_score,
                        'extra': {
                            'group_id': group_id,
                            'post_id': post_id,
                            'owner_id': owner_id,
                            'date': datetime.fromtimestamp(date).isoformat() if date else None,
                            'likes': likes,
                            'reposts': reposts,
                            'views': views,
                            'comments': comments,
                        }
                    })

                    if len(results) >= limit * len(group_ids):
                        break

            except Exception as e:
                logger.warning(f"Ошибка при получении постов из VK группы '{group_id}': {e}")
                continue

        # Сортировать по relevance_score
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]

    except ImportError as e:
        logger.error(f"requests не установлен: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении VK постов: {e}")
        return []


def deduplicate_trends(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Удалить дубликаты из списка трендов по URL.

    Args:
        trends: Список трендов

    Returns:
        Список уникальных трендов
    """
    seen_urls = set()
    unique_trends = []

    for trend in trends:
        url = trend.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_trends.append(trend)
        elif not url:
            # Если нет URL, всё равно добавляем (может быть полезным)
            unique_trends.append(trend)

    return unique_trends
