"""
Celery tasks для Content Factory (Zavod).

Этот модуль экспортирует все задачи из подмодулей для обратной совместимости.

Структура:
- publishing.py    - публикация контента в соцсети (2 задачи)
- aggregation.py   - сбор трендов из различных источников (12 задач)
- generation.py    - генерация контента с помощью AI (10 задач)
- seo.py          - генерация SEO ключевых слов (2 задачи)
- scheduling.py    - автоматическое планирование публикаций (1 задача)
"""

# Publishing tasks (2)
from .publishing import (
    process_due_schedules,
    publish_schedule,
)

# Aggregation tasks (12)
from .aggregation import (
    discover_trends_for_topic,
    discover_trends_for_all_active_topics,
    discover_telegram_trends_for_topic,
    discover_rss_trends_for_topic,
    discover_youtube_trends_for_topic,
    discover_instagram_trends_for_topic,
    discover_google_trends_only,
    discover_news_from_all_sources,
    discover_vkontakte_trends_for_topic,
    discover_content_for_topic,
    discover_trends_for_topic_with_telegram,
    analyze_telegram_channel_task,
)

from .channel_analysis import (
    analyze_channel_task,
)
# Generation tasks (10)
from .generation import (
    generate_post_from_trend,
    generate_posts_for_topic,
    generate_posts_from_seo_keyword_set,
    generate_posts_with_videos_from_seo_keyword_set,
    generate_videos_for_posts,
    generate_image_for_post,
    generate_video_from_image,
    generate_story_from_trend,
    generate_posts_from_story,
    regenerate_post_text,
    generate_weekly_posts_from_template,
)

# SEO tasks (2)
from .seo import (
    generate_seo_keywords_for_client,
    generate_seo_keywords_for_topic,
)

# Scheduling tasks (1)
from .scheduling import (
    auto_schedule_story_posts,
)

__all__ = [
    # Publishing (2)
    'process_due_schedules',
    'publish_schedule',

    # Aggregation (12)
    'discover_trends_for_topic',
    'discover_trends_for_all_active_topics',
    'discover_telegram_trends_for_topic',
    'discover_rss_trends_for_topic',
    'discover_youtube_trends_for_topic',
    'discover_instagram_trends_for_topic',
    'discover_google_trends_only',
    'discover_news_from_all_sources',
    'discover_vkontakte_trends_for_topic',
    'discover_content_for_topic',
    'discover_trends_for_topic_with_telegram',
    'analyze_telegram_channel_task',
    'analyze_channel_task',

    # Generation (10)
    'generate_post_from_trend',
    'generate_posts_for_topic',
    'generate_posts_from_seo_keyword_set',
    'generate_posts_with_videos_from_seo_keyword_set',
    'generate_videos_for_posts',
    'generate_image_for_post',
    'generate_video_from_image',
    'generate_story_from_trend',
    'generate_posts_from_story',
    'regenerate_post_text',
    'generate_weekly_posts_from_template',

    # SEO (2)
    'generate_seo_keywords_for_client',
    'generate_seo_keywords_for_topic',

    # Scheduling (1)
    'auto_schedule_story_posts',
]
