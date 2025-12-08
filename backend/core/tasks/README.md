# Core Tasks Module

Этот модуль содержит все Celery задачи для Content Factory (Zavod).

## Структура

Задачи разбиты на 5 логических модулей:

### 1. **publishing.py** (201 строк, 2 задачи)
Публикация контента в социальные сети:
- `process_due_schedules()` - находит и запускает публикации по расписанию
- `publish_schedule()` - публикует пост в соцсеть (Telegram, Instagram, YouTube)

### 2. **aggregation.py** (1092 строк, 12 задач)
Сбор трендов и контента из различных источников:
- `discover_trends_for_topic()` - Google Trends + Google News
- `discover_telegram_trends_for_topic()` - Telegram каналы
- `discover_rss_trends_for_topic()` - RSS фиды
- `discover_youtube_trends_for_topic()` - YouTube каналы
- `discover_instagram_trends_for_topic()` - Instagram аккаунты
- `discover_vkontakte_trends_for_topic()` - VK группы
- `discover_google_trends_only()` - только Google Trends
- `discover_news_from_all_sources()` - все источники новостей
- `discover_content_for_topic()` - **основная задача**, использует настройки топика
- `discover_trends_for_topic_with_telegram()` - (deprecated)
- `discover_trends_for_all_active_topics()` - запуск для всех активных тем
- `analyze_telegram_channel_task()` - AI анализ канала для профиля аудитории

### 3. **generation.py** (798 строк, 7 задач)
Генерация контента с помощью AI:
- `generate_post_from_trend()` - генерация поста из тренда
- `generate_posts_for_topic()` - генерация постов для всех трендов темы
- `generate_image_for_post()` - генерация изображения для поста
- `generate_video_from_image()` - генерация видео из изображения или текста
- `generate_story_from_trend()` - генерация истории (мини-сериала)
- `generate_posts_from_story()` - генерация постов из эпизодов истории
- `regenerate_post_text()` - регенерация текста поста

### 4. **seo.py** (225 строк, 2 задачи)
Генерация SEO ключевых слов:
- `generate_seo_keywords_for_client()` - генерация SEO фраз для клиента
- `generate_seo_keywords_for_topic()` - (deprecated) переадресует на клиента

### 5. **scheduling.py** (97 строк, 1 задача)
Автоматическое планирование публикаций:
- `auto_schedule_story_posts()` - создание расписания для постов истории

## Использование

Все задачи экспортируются через `__init__.py` для обратной совместимости:

```python
# Прямой импорт из подмодулей (рекомендуется)
from core.tasks.publishing import publish_schedule
from core.tasks.generation import generate_post_from_trend

# Или через главный модуль (для совместимости)
from core.tasks import publish_schedule, generate_post_from_trend
```

## Преимущества структуры

✅ **Удобство разработки** - легко найти нужную задачу
✅ **Тестирование** - можно тестировать модули отдельно
✅ **Производительность** - быстрее загрузка и импорты
✅ **Масштабируемость** - проще добавлять новые задачи
✅ **Читаемость** - вместо 2358 строк в одном файле, ~200-1000 строк в каждом модуле
✅ **Разделение ответственности** - каждый модуль отвечает за свою область

## Миграция

Старый файл `tasks.py` сохранён как `tasks.py.backup` и может быть удалён после проверки работоспособности новой структуры.
