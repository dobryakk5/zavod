from celery import shared_task
import logging
import os
import queue
import random
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from django.core.files import File

from ..models import (
    Post,
    PostImage,
    PostVideo,
    Topic,
    TrendItem,
    ContentTemplate,
    Client,
    SEOKeywordSet,
)
from ..ai_generator import AIContentGenerator

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


def _get_latest_seo_keywords_for_client(client: Client):
    """Возвращает свежие SEO списки по группам для клиента."""
    from ..models import SEOKeywordSet

    latest = {}
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


def _select_seo_keywords_for_posts(keywords: List[str], total_posts: int) -> List[str]:
    """
    Возвращает список ключей для генерации постов.
    Сначала используются все уникальные ключи в случайном порядке, затем остаток добирается случайными повторами.
    """
    if not keywords or total_posts <= 0:
        return []

    cleaned = [kw for kw in keywords if isinstance(kw, str) and kw.strip()]
    if not cleaned:
        return []

    unique_keywords = list(dict.fromkeys([kw.strip() for kw in cleaned]))
    random.shuffle(unique_keywords)

    selected: List[str] = []
    pool = unique_keywords.copy()

    while pool and len(selected) < total_posts:
        selected.append(pool.pop())

    if not unique_keywords:
        return selected

    while len(selected) < total_posts:
        selected.append(random.choice(unique_keywords))

    return selected


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
            "brand": trend.client.name or "",
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


@shared_task
def generate_posts_from_seo_keyword_set(
    seo_keyword_set_id: int,
    template_id: int,
    posts_count: int,
    created_by_id: Optional[int] = None
):
    """Сгенерировать серию постов, используя SEO ключи из SEOKeywordSet."""
    try:
        seo_set = SEOKeywordSet.objects.select_related("client", "topic").get(id=seo_keyword_set_id)
    except SEOKeywordSet.DoesNotExist:
        logger.error("SEOKeywordSet %s не найден для генерации постов", seo_keyword_set_id)
        return {"success": False, "error": "seo_set_not_found"}

    client = seo_set.client
    if not client:
        logger.error("У SEOKeywordSet %s не указан клиент", seo_keyword_set_id)
        return {"success": False, "error": "client_required"}

    try:
        template = ContentTemplate.objects.get(id=template_id, client=client)
    except ContentTemplate.DoesNotExist:
        logger.error(
            "Шаблон %s не найден или не принадлежит клиенту %s",
            template_id,
            client.id
        )
        return {"success": False, "error": "template_not_found"}

    keywords = seo_set.get_flat_keywords()
    if not keywords:
        logger.error("SEOKeywordSet %s не содержит ключевых фраз", seo_keyword_set_id)
        return {"success": False, "error": "no_keywords"}

    try:
        total_posts = max(1, int(posts_count))
    except (TypeError, ValueError):
        total_posts = len(keywords)

    selected_keywords = _select_seo_keywords_for_posts(keywords, total_posts)
    if not selected_keywords:
        logger.error("Не удалось выбрать ключи для генерации постов (SEOKeywordSet %s)", seo_keyword_set_id)
        return {"success": False, "error": "selection_failed"}

    template_config = {
        "tone": template.tone,
        "length": template.length,
        "language": template.language,
        "type": template.type,
        "seo_prompt_template": template.seo_prompt_template,
        "trend_prompt_template": template.trend_prompt_template,
        "prompt_type": "seo",
        "additional_instructions": template.additional_instructions,
        "include_hashtags": template.include_hashtags,
        "max_hashtags": template.max_hashtags,
        "brand": client.name or "",
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
    }

    topic_name = ""
    if seo_set.topic and seo_set.topic.name:
        topic_name = seo_set.topic.name
    elif client.name:
        topic_name = client.name

    try:
        generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора: %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    group_name = seo_set.group_type or "seo_keywords"
    created_posts = 0
    errors: List[Dict[str, str]] = []

    for index, keyword in enumerate(selected_keywords, start=1):
        per_post_keywords = {
            group_name: [keyword]
        }
        logger.info(
            "[SEO %s] Генерация поста %s/%s по ключу '%s'",
            seo_keyword_set_id,
            index,
            total_posts,
            keyword
        )

        result = generator.generate_post_text(
            trend_title=f"SEO keyword: {keyword}",
            trend_description=f"Generated from SEO Keyword Set #{seo_keyword_set_id}",
            trend_url="",
            topic_name=topic_name or client.slug,
            template_config=template_config,
            seo_keywords=per_post_keywords
        )

        if not result or not result.get("success"):
            error_message = (result or {}).get("error", "Неизвестная ошибка AI")
            logger.error(
                "[SEO %s] Ошибка генерации поста по ключу '%s': %s",
                seo_keyword_set_id,
                keyword,
                error_message
            )
            errors.append({"index": index, "keyword": keyword, "error": error_message})
            continue

        hashtags = result.get("hashtags", [])
        tags = []
        if isinstance(hashtags, list):
            tags.extend(hashtags)
        if keyword:
            tags.append(keyword)
        tags.append("seo")

        # Удаляем дубликаты, сохраняя порядок
        seen = set()
        deduped_tags = []
        for tag in tags:
            if isinstance(tag, str):
                normalized = tag.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    deduped_tags.append(normalized)

        Post.objects.create(
            client=client,
            title=result["title"],
            text=result["text"],
            status="draft",
            tags=deduped_tags,
            source_links=[],
            generated_by="seo-keywords",
            created_by_id=created_by_id
        )
        created_posts += 1

    logger.info(
        "Генерация постов из SEOKeywordSet %s завершена: %s/%s успешно",
        seo_keyword_set_id,
        created_posts,
        total_posts
    )

    return {
        "success": created_posts > 0,
        "created": created_posts,
        "requested": total_posts,
        "errors": errors,
    }


@shared_task
def generate_posts_with_videos_from_seo_keyword_set(
    seo_keyword_set_id: int,
    template_id: int,
    posts_count: int,
    videos_per_post: int = 1,
    created_by_id: Optional[int] = None
):
    """
    Сгенерировать серию постов и создать видео для них.

    Логика работы:
    - Тексты постов генерируются последовательно (один поток), созданные посты сразу попадают в очередь
    - Отдельный видео-поток начинает работу как только появляется первый пост, обрабатывая по одному посту за раз
    - Для каждого поста видео генерируются и дожидаются результата синхронно (по 2 на пост), при таймаутах выполняются повторные попытки
    - Возврат происходит только после того, как обработаны все посты и очередь видео пуста
    """
    # ===== Валидация и подготовка =====
    try:
        seo_set = SEOKeywordSet.objects.select_related("client", "topic").get(id=seo_keyword_set_id)
    except SEOKeywordSet.DoesNotExist:
        logger.error("SEOKeywordSet %s не найден для генерации постов с видео", seo_keyword_set_id)
        return {"success": False, "error": "seo_set_not_found"}

    client = seo_set.client
    if not client:
        logger.error("У SEOKeywordSet %s отсутствует клиент", seo_keyword_set_id)
        return {"success": False, "error": "client_required"}

    try:
        template = ContentTemplate.objects.get(id=template_id, client=client)
    except ContentTemplate.DoesNotExist:
        logger.error(
            "Шаблон %s не найден или не принадлежит клиенту %s",
            template_id,
            client.id
        )
        return {"success": False, "error": "template_not_found"}

    keywords = seo_set.get_flat_keywords()
    if not keywords:
        logger.error("SEOKeywordSet %s не содержит ключевых фраз", seo_keyword_set_id)
        return {"success": False, "error": "no_keywords"}

    try:
        total_posts = max(1, int(posts_count))
    except (TypeError, ValueError):
        total_posts = len(keywords)
    total_posts = max(1, min(99, total_posts))

    try:
        videos_per_post_int = max(1, int(videos_per_post))
    except (TypeError, ValueError):
        videos_per_post_int = 1
    videos_per_post_int = max(1, min(5, videos_per_post_int))

    selected_keywords = _select_seo_keywords_for_posts(keywords, total_posts)
    if not selected_keywords:
        return {"success": False, "error": "selection_failed"}

    template_config = {
        "tone": template.tone,
        "length": template.length,
        "language": template.language,
        "type": template.type,
        "seo_prompt_template": template.seo_prompt_template,
        "trend_prompt_template": template.trend_prompt_template,
        "prompt_type": "seo",
        "additional_instructions": template.additional_instructions,
        "include_hashtags": template.include_hashtags,
        "max_hashtags": template.max_hashtags,
        "brand": client.name or "",
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
    }

    topic_name = ""
    if seo_set.topic and seo_set.topic.name:
        topic_name = seo_set.topic.name
    elif client.name:
        topic_name = client.name

    try:
        generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора (SEO+видео): %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    def _dedupe_tags(values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if isinstance(value, str):
                normalized = value.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    result.append(normalized)
        return result

    # ===== Создание постов + отдельный поток для синхронной генерации видео =====
    logger.info(
        "[SEO %s] Старт пакетной генерации: %s постов, %s видео на пост",
        seo_keyword_set_id,
        total_posts,
        videos_per_post_int
    )

    created_posts_list: List[Post] = []
    post_errors: List[Dict[str, str]] = []
    video_errors: List[Dict[str, Any]] = []
    video_saved = 0
    video_attempts = 0

    post_queue: "queue.Queue[int]" = queue.Queue()
    text_generation_done = threading.Event()

    video_method = (os.getenv("SEO_VIDEO_METHOD") or "veo").lower()
    video_options: Dict[str, Any] = {}
    bot_username = os.getenv("VEO_BOT_USERNAME")
    if bot_username:
        video_options["bot_username"] = bot_username
    session_path = (
        os.getenv("VEO_SESSION_PATH")
        or os.getenv("VEO_SESSION_FILE")
        or os.getenv("TELEGRAM_SESSION_PATH")
    )
    if session_path:
        video_options["session_path"] = session_path
    session_name = os.getenv("VEO_SESSION_NAME")
    if session_name:
        video_options["session_name"] = session_name
    max_attempts_per_video = max(1, int(os.getenv("VEO_VIDEO_MAX_ATTEMPTS", "3")))

    def _video_worker():
        nonlocal video_saved, video_attempts
        try:
            video_prompt_generator = AIContentGenerator()
        except ValueError as exc:
            logger.error("[SEO %s] Невозможно запустить видео-поток: %s", seo_keyword_set_id, exc)
            text_generation_done.wait()
            return

        while True:
            try:
                post_id = post_queue.get(timeout=2)
            except queue.Empty:
                if text_generation_done.is_set():
                    break
                continue

            try:
                post_obj = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                post_queue.task_done()
                continue

            try:
                logger.info("[SEO %s] Видео-поток обрабатывает пост %s", seo_keyword_set_id, post_obj.id)
                stats = _generate_videos_for_single_post(
                    post=post_obj,
                    videos_per_post=videos_per_post_int,
                    prompt_generator=video_prompt_generator,
                    language=template.language,
                    video_method=video_method,
                    video_options=video_options,
                    max_attempts=max_attempts_per_video,
                    log_prefix=f"SEO {seo_keyword_set_id}"
                )
                video_saved += stats["saved"]
                video_attempts += stats["attempts"]
                video_errors.extend(stats["errors"])
                if stats["saved"] == videos_per_post_int:
                    logger.info(
                        "[SEO %s] Пост %s полностью обработан видео-потоком",
                        seo_keyword_set_id,
                        post_obj.id
                    )
            except Exception as exc:
                logger.error(
                    "[SEO %s] Непредвиденная ошибка видео-потока для поста %s: %s",
                    seo_keyword_set_id,
                    post_id,
                    exc,
                    exc_info=True
                )
                video_errors.append({
                    "post_id": post_id,
                    "video_index": None,
                    "error": str(exc),
                    "prompt_start": "",
                })
            finally:
                post_queue.task_done()

    video_thread = threading.Thread(
        target=_video_worker,
        name=f"seo-{seo_keyword_set_id}-video-worker",
        daemon=True
    )
    video_thread.start()

    try:
        for index, keyword in enumerate(selected_keywords, start=1):
            per_post_keywords = {seo_set.group_type or "seo_keywords": [keyword]}
            logger.info(
                "[SEO %s] Генерация текста поста %s/%s по ключу '%s'",
                seo_keyword_set_id,
                index,
                total_posts,
                keyword
            )

            post_result = generator.generate_post_text(
                trend_title=f"SEO keyword: {keyword}",
                trend_description=f"Generated from SEO Keyword Set #{seo_keyword_set_id}",
                trend_url="",
                topic_name=topic_name or client.slug,
                template_config=template_config,
                seo_keywords=per_post_keywords
            )

            if not post_result or not post_result.get("success"):
                error_message = (post_result or {}).get("error", "Не удалось сгенерировать пост")
                logger.error(
                    "[SEO %s] Ошибка генерации поста по ключу '%s': %s",
                    seo_keyword_set_id,
                    keyword,
                    error_message
                )
                post_errors.append({"keyword": keyword, "error": error_message})
                continue

            hashtags = post_result.get("hashtags", [])
            tags = []
            if isinstance(hashtags, list):
                tags.extend(hashtags)
            if keyword:
                tags.append(keyword)
            tags.extend(["seo", "video"])
            tags = _dedupe_tags(tags)

            try:
                post = Post.objects.create(
                    client=client,
                    title=(post_result.get("title") or keyword or "SEO post")[:255],
                    text=post_result.get("text") or "",
                    status="draft",
                    tags=tags,
                    source_links=[],
                    generated_by="seo-keywords-video",
                    created_by_id=created_by_id
                )
                created_posts_list.append(post)
                logger.info(
                    "[SEO %s] Пост %s создан (ID=%s): %s",
                    seo_keyword_set_id,
                    index,
                    post.id,
                    post.title[:50]
                )
                post_queue.put(post.id)

            except Exception as exc:
                logger.error("Не удалось сохранить пост для SEO %s: %s", seo_keyword_set_id, exc, exc_info=True)
                post_errors.append({"keyword": keyword, "error": str(exc)})
                continue

    finally:
        text_generation_done.set()
        post_queue.join()
        video_thread.join()

    created_posts = len(created_posts_list)
    logger.info(
        "[SEO %s] Завершено: создано %s/%s постов, сохранено %s/%s видео",
        seo_keyword_set_id,
        created_posts,
        total_posts,
        video_saved,
        video_attempts
    )

    # Объединяем результаты
    return {
        "success": created_posts > 0,
        "created_posts": created_posts,
        "requested_posts": total_posts,
        "videos_per_post": videos_per_post_int,
        "videos_saved": video_saved,
        "video_attempts": video_attempts,
        "post_errors": post_errors,
        "video_errors": video_errors,
        "post_ids": [post.id for post in created_posts_list],
    }


def _generate_videos_for_single_post(
    post: Post,
    videos_per_post: int,
    prompt_generator: AIContentGenerator,
    language: str,
    video_method: str,
    video_options: Dict[str, Any],
    max_attempts: int,
    log_prefix: str = "Videos"
) -> Dict[str, Any]:
    """
    Синхронно сгенерировать указанное количество видео для одного поста.
    """
    stats = {
        "saved": 0,
        "attempts": 0,
        "errors": [],
    }
    videos_per_post = max(1, int(videos_per_post))
    max_attempts = max(1, int(max_attempts))

    video_prompt = prompt_generator.generate_video_prompt(
        post_title=post.title or "",
        post_text=post.text or "",
        language=language
    )
    if not video_prompt:
        video_prompt = _build_text_video_prompt(post)

    prompts: Dict[int, str] = {}
    for video_idx in range(1, videos_per_post + 1):
        prompt_to_use = video_prompt
        if videos_per_post > 1:
            prompt_to_use = (
                f"{video_prompt}\nVariation #{video_idx}: distinct cinematic take, camera work and pacing."
            )
        prompts[video_idx] = prompt_to_use

    video_state: Dict[int, Dict[str, Any]] = {
        idx: {"attempts": 0, "success": False}
        for idx in prompts
    }
    pending = set(prompts.keys())

    def _run_video_generation(prompt_text: str) -> Dict[str, Any]:
        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return {"success": False, "error": str(exc), "cleanup_paths": []}
        return generator.generate_video_from_text(
            prompt=prompt_text,
            method=video_method,
            **video_options
        )

    while pending:
        batch = [idx for idx in pending if video_state[idx]["attempts"] < max_attempts]
        if not batch:
            break

        max_workers = len(batch)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}
            for idx in batch:
                video_state[idx]["attempts"] += 1
                attempt_no = video_state[idx]["attempts"]
                logger.info(
                    "[%s] Генерация видео %s/%s для поста %s (параллельная попытка %s/%s)",
                    log_prefix,
                    idx,
                    videos_per_post,
                    post.id,
                    attempt_no,
                    max_attempts
                )
                future = executor.submit(_run_video_generation, prompts[idx])
                future_map[future] = (idx, attempt_no)

            for future in as_completed(future_map):
                idx, attempt_no = future_map[future]
                stats["attempts"] += 1
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"success": False, "error": str(exc), "cleanup_paths": []}
                cleanup_paths = result.get("cleanup_paths") or []
                video_path = result.get("video_path")

                if result.get("success") and video_path and os.path.exists(video_path):
                    try:
                        filename = f"post_{post.id}_{uuid.uuid4().hex[:8]}.mp4"
                        with open(video_path, "rb") as video_file:
                            post_video = PostVideo(
                                post=post,
                                order=post.videos.count(),
                                caption=(prompts[idx] or post.title or "")[:255],
                            )
                            post_video.video.save(filename, File(video_file), save=True)
                        stats["saved"] += 1
                        video_state[idx]["success"] = True
                        pending.discard(idx)
                        logger.info(
                            "[%s] Видео %s/%s для поста %s сохранено",
                            log_prefix,
                            idx,
                            videos_per_post,
                            post.id
                        )
                    except Exception as exc:
                        logger.error(
                            "[%s] Ошибка сохранения видео для поста %s: %s",
                            log_prefix,
                            post.id,
                            exc,
                            exc_info=True
                        )
                        stats["errors"].append({
                            "post_id": post.id,
                            "video_index": idx,
                            "error": str(exc),
                            "prompt_start": (prompts[idx] or "")[:120],
                        })
                    finally:
                        if os.path.exists(video_path):
                            try:
                                os.remove(video_path)
                            except OSError:
                                pass
                        for extra_path in cleanup_paths:
                            if extra_path and os.path.exists(extra_path):
                                try:
                                    os.remove(extra_path)
                                except OSError:
                                    pass
                else:
                    error_message = result.get("error") or "Видео не получено"
                    logger.warning(
                        "[%s] Неудачная генерация видео %s/%s для поста %s: %s",
                        log_prefix,
                        idx,
                        videos_per_post,
                        post.id,
                        error_message
                    )
                    for extra_path in cleanup_paths:
                        if extra_path and os.path.exists(extra_path):
                            try:
                                os.remove(extra_path)
                            except OSError:
                                pass

                    if video_state[idx]["attempts"] >= max_attempts:
                        stats["errors"].append({
                            "post_id": post.id,
                            "video_index": idx,
                            "error": f"video_failed_after_{max_attempts}_attempts",
                            "prompt_start": (prompts[idx] or "")[:120],
                        })
                        logger.error(
                            "[%s] Не удалось получить видео %s/%s для поста %s",
                            log_prefix,
                            idx,
                            videos_per_post,
                            post.id
                        )
                        pending.discard(idx)

    return stats

    return stats


def _generate_videos_batch(posts: List[Post], videos_per_post: int = 1, language: str = "en") -> Dict[str, Any]:
    """
    Общая функция для генерации видео для списка постов синхронно (по одному посту за раз).
    """
    if not posts:
        logger.warning("Не переданы посты для генерации видео")
        return {"success": False, "error": "no_posts"}

    try:
        videos_per_post_int = max(1, min(5, int(videos_per_post)))
    except (TypeError, ValueError):
        videos_per_post_int = 1

    logger.info(
        "[Videos] Синхронная генерация видео для %s постов (по %s видео на пост)",
        len(posts),
        videos_per_post_int
    )

    try:
        prompt_generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора: %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    video_method = (
        os.getenv("SEO_VIDEO_METHOD")
        or os.getenv("VIDEO_GENERATOR_METHOD")
        or "veo"
    ).lower()
    video_options: Dict[str, Any] = {}
    bot_username = os.getenv("VEO_BOT_USERNAME")
    if bot_username:
        video_options["bot_username"] = bot_username
    session_path = (
        os.getenv("VEO_SESSION_PATH")
        or os.getenv("VEO_SESSION_FILE")
        or os.getenv("TELEGRAM_SESSION_PATH")
    )
    if session_path:
        video_options["session_path"] = session_path
    session_name = os.getenv("VEO_SESSION_NAME")
    if session_name:
        video_options["session_name"] = session_name
    try:
        max_attempts = int(os.getenv("VEO_VIDEO_MAX_ATTEMPTS", "3"))
    except ValueError:
        max_attempts = 3

    processed_posts = 0
    video_saved = 0
    video_attempts = 0
    video_errors: List[Dict[str, Any]] = []

    for post in posts:
        processed_posts += 1
        log_prefix = f"Videos Post {post.id}"
        stats = _generate_videos_for_single_post(
            post=post,
            videos_per_post=videos_per_post_int,
            prompt_generator=prompt_generator,
            language=language,
            video_method=video_method,
            video_options=video_options,
            max_attempts=max_attempts,
            log_prefix=log_prefix
        )
        video_saved += stats["saved"]
        video_attempts += stats["attempts"]
        video_errors.extend(stats["errors"])

    logger.info(
        "[Videos] Завершено: обработано %s постов, сохранено %s/%s видео",
        processed_posts,
        video_saved,
        video_attempts
    )

    return {
        "success": video_saved > 0,
        "processed_posts": processed_posts,
        "videos_per_post": videos_per_post_int,
        "videos_saved": video_saved,
        "video_attempts": video_attempts,
        "video_errors": video_errors,
        "post_ids": [post.id for post in posts],
    }


@shared_task
def generate_videos_for_posts(post_ids: List[int], videos_per_post: int = 1):
    """Сгенерировать указанное количество видео для существующих постов."""

    if not post_ids:
        logger.warning("Не переданы посты для генерации видео")
        return {"success": False, "error": "no_posts"}

    normalized_ids: List[int] = []
    seen_ids = set()
    for raw_id in post_ids:
        try:
            post_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        normalized_ids.append(post_id)

    if not normalized_ids:
        logger.warning("После нормализации не осталось ни одного ID поста: %s", post_ids)
        return {"success": False, "error": "no_valid_posts"}

    posts_qs = Post.objects.filter(id__in=normalized_ids).select_related("client")
    posts_map = {post.id: post for post in posts_qs}
    ordered_posts = [posts_map[pk] for pk in normalized_ids if pk in posts_map]

    if not ordered_posts:
        logger.warning("Не удалось найти посты для генерации видео: %s", normalized_ids)
        return {"success": False, "error": "posts_not_found"}

    # Используем общую функцию для генерации видео
    return _generate_videos_batch(ordered_posts, videos_per_post)


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

        # Шаг 3: Сохранить изображение среди PostImage
        try:
            with open(temp_image_path, 'rb') as f:
                post_image = PostImage(
                    post=post,
                    order=post.images.count(),
                )
                post_image.image.save(image_filename, File(f), save=True)

            logger.info(f"Изображение успешно сохранено в пост {post.id}: {post_image.image.url}")
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

        primary_image = post.get_primary_image()

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
            if not primary_image or not primary_image.image:
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
                image_path=primary_image.image.path,
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

        with open(video_temp_path, "rb") as video_file:
            post_video = PostVideo(
                post=post,
                order=post.videos.count(),
            )
            post_video.caption = (post.title or "")[:255]
            post_video.video.save(video_filename, File(video_file), save=True)

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
    from ..models import Story

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
    from ..models import Story

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
            "brand": story.client.name or "",
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
                "brand": post.client.name or "",
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
                "brand": post.client.name or "",
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
