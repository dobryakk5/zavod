from celery import shared_task
import logging
import os
import queue
import random
import json
import shutil
import subprocess
import threading
import tempfile
import uuid
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, List, Optional, Tuple, Set
from zoneinfo import ZoneInfo

from django.core.files import File
from django.db.models import F
from django.db.utils import ProgrammingError
from django.utils import timezone

from ..models import (
    Post,
    PostImage,
    PostVideo,
    Topic,
    TrendItem,
    ContentTemplate,
    Client,
    SEOKeywordSet,
    Schedule,
    SocialAccount,
    WordstatResult,
)
from ..ai_generator import AIContentGenerator, merge_video_prompt_with_additional
from ..system_settings import get_image_generation_method
from ..video_postprocessing import (
    apply_text_overlays_to_video,
    build_overlay_scenes_from_post,
)
from ..photo_postprocessing import apply_text_overlay_to_image

logger = logging.getLogger(__name__)

CUSTOM_POST_AI_MODEL = "tngtech/deepseek-r1t-chimera:free"

WEEKDAY_LABELS = [
    "понедельник",
    "вторник",
    "среду",
    "четверг",
    "пятницу",
    "субботу",
    "воскресенье",
]

MAX_WEEKLY_POSTS = 21
TIE_BREAKER_DAY_ORDER = [0, 2, 4, 1, 3, 5, 6]
DEFAULT_TEMPLATE_LENGTH = 1200


def _configure_custom_generator_model(generator: AIContentGenerator) -> None:
    """
    Custom-flow: посты должны генерироваться строго через заданную модель,
    без fallback на другие модели.
    """
    generator.model = CUSTOM_POST_AI_MODEL
    generator.post_model = CUSTOM_POST_AI_MODEL
    generator.fallback_model = CUSTOM_POST_AI_MODEL


def _get_client_timezone(client: Client):
    tz_name = client.timezone or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning("Unknown timezone '%s', falling back to UTC", tz_name)
        return dt_timezone.utc


def _get_next_week_start_local(client: Client):
    client_tz = _get_client_timezone(client)
    now_local = timezone.now().astimezone(client_tz)
    days_until_next_week = (7 - now_local.weekday()) % 7
    if days_until_next_week == 0:
        days_until_next_week = 7
    start_local = (now_local + timedelta(days=days_until_next_week)).replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start_local


def _collect_existing_weekdays(client: Client, template: ContentTemplate, week_start_local) -> Set[int]:
    client_tz = _get_client_timezone(client)
    week_start_utc = week_start_local.astimezone(dt_timezone.utc)
    week_end_utc = week_start_utc + timedelta(days=7)
    template_tag = f"template:{template.id}"
    week_tag = f"plan-week:{week_start_local.date().isoformat()}"

    blocked: Set[int] = set()

    schedules_qs = Schedule.objects.filter(
        client=client,
        scheduled_at__gte=week_start_utc,
        scheduled_at__lt=week_end_utc,
        post__tags__contains=[template_tag],
    )
    for schedule in schedules_qs:
        local_dt = schedule.scheduled_at.astimezone(client_tz)
        blocked.add(local_dt.weekday())

    planned_posts = Post.objects.filter(client=client, tags__contains=[template_tag])
    planned_posts = planned_posts.filter(tags__contains=[week_tag])
    for post in planned_posts:
        planned_dt = None
        for tag in post.tags:
            if isinstance(tag, str) and tag.startswith("planned-at:"):
                raw_value = tag.split("planned-at:", 1)[1]
                try:
                    planned_dt = datetime.fromisoformat(raw_value)
                except ValueError:
                    planned_dt = None
                break
        if planned_dt:
            blocked.add(planned_dt.astimezone(client_tz).weekday())

    return blocked


def _collect_week_day_load(client: Client, week_start_local) -> Dict[int, int]:
    """Подсчитать количество уже запланированных публикаций по дням целевой недели."""
    client_tz = _get_client_timezone(client)
    week_start_utc = week_start_local.astimezone(dt_timezone.utc)
    week_end_utc = week_start_utc + timedelta(days=7)

    counts: Dict[int, int] = defaultdict(int)
    schedules_qs = Schedule.objects.filter(
        client=client,
        scheduled_at__gte=week_start_utc,
        scheduled_at__lt=week_end_utc,
    )
    for schedule in schedules_qs:
        local_dt = schedule.scheduled_at.astimezone(client_tz)
        counts[local_dt.weekday()] += 1

    return counts


def _build_weekly_slots(
    start_local,
    total_count: int,
    blocked_days: Optional[Set[int]] = None,
    weekday_counts: Optional[Dict[int, int]] = None,
) -> List[Tuple[Any, int]]:
    if total_count <= 0:
        return []

    per_day_usage: Dict[int, int] = defaultdict(int)
    permanent_blocked = set(blocked_days or set())
    slots: List[Tuple[Any, int]] = []
    counts: Dict[int, int] = defaultdict(int)

    if weekday_counts:
        for day_index, value in weekday_counts.items():
            try:
                day_key = int(day_index)
            except (TypeError, ValueError):
                continue
            counts[day_key] = value

    def _tie_breaker(day: int) -> int:
        try:
            return TIE_BREAKER_DAY_ORDER.index(day)
        except ValueError:
            return len(TIE_BREAKER_DAY_ORDER) + day

    for _ in range(total_count):
        ordered_days = sorted(
            range(7),
            key=lambda day: (counts[day], _tie_breaker(day)),
        )
        available_days = [day for day in ordered_days if day not in permanent_blocked]
        day_offset = available_days[0] if available_days else ordered_days[0]

        in_day_index = per_day_usage[day_offset]
        scheduled_local = start_local + timedelta(days=day_offset, hours=in_day_index * 2)
        slots.append((scheduled_local, day_offset))
        per_day_usage[day_offset] = in_day_index + 1
        counts[day_offset] += 1

    return slots


def _apply_wordstat_refinement(
    generator: AIContentGenerator,
    base_result: Dict[str, Any],
    phrases: List[str],
    language: str,
    log_prefix: str,
) -> Dict[str, Any]:
    def _transliterate_ru_to_lat(src: str) -> str:
        mapping = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
            "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
            "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
            "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
            "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        }
        return "".join(mapping.get(ch, mapping.get(ch.lower(), ch)) for ch in src)

    def _replace_insensitive(text: str, needle: str, replacement: str) -> Tuple[str, bool]:
        if not needle:
            return text, False
        match = re.search(re.escape(needle), text, re.IGNORECASE)
        if not match:
            return text, False
        start, end = match.span()
        return text[:start] + replacement + text[end:], True

    def _ensure_exact_phrases(text: str, phrases_list: List[str]) -> str:
        """Гарантировать, что точные фразы присутствуют в тексте (с заменой регистровых вариантов)."""
        updated = text or ""
        for phrase in phrases_list:
            if not phrase:
                continue
            if phrase in updated:
                continue
            # 1) Пробуем заменить совпадение по регистру
            updated, replaced = _replace_insensitive(updated, phrase, phrase)
            if replaced:
                continue
            # 2) Пробуем по транслитерации (ru->lat), чтобы заменить SMM -> смм
            translit = _transliterate_ru_to_lat(phrase.lower())
            if translit and translit != phrase.lower():
                updated, replaced = _replace_insensitive(updated, translit, phrase)
                if replaced:
                    continue
            # если ничего похожего не нашли, добавляем компактно в конец
            if updated and not updated.endswith("\n"):
                updated += "\n"
            updated += f"{phrase}"
        return updated

    cleaned_phrases: List[str] = []
    for phrase in phrases or []:
        if not isinstance(phrase, str):
            continue
        normalized = phrase.strip()
        if normalized and normalized not in cleaned_phrases:
            cleaned_phrases.append(normalized)

    if not cleaned_phrases or not base_result or not base_result.get("text"):
        if cleaned_phrases:
            base_result["wordstat_phrases_used"] = cleaned_phrases
            if not base_result.get("text"):
                base_result["text"] = f"Черновик: добавьте в текст фразы Wordstat: {', '.join(cleaned_phrases)}."
                logger.warning("[%s] Пустой текст после генерации; добавлен черновик с Wordstat-фразами", log_prefix)
        return base_result

    text_lower = (base_result.get("text") or "").lower()
    missing = [phrase for phrase in cleaned_phrases if phrase.lower() not in text_lower]
    if not missing:
        base_result["wordstat_phrases_used"] = cleaned_phrases
        return base_result

    try:
        refined = generator.refine_text_with_wordstat(
            title=base_result.get("title") or "",
            text=base_result.get("text") or "",
            phrases=cleaned_phrases,
            language=language or "ru",
        )
    except Exception as exc:
        logger.warning("[%s] Ошибка доработки текста под Wordstat: %s", log_prefix, exc)
        return base_result

    if refined and refined.get("success") and refined.get("text"):
        if refined.get("title"):
            base_result["title"] = refined.get("title") or base_result.get("title", "")
        base_result["text"] = refined.get("text") or base_result.get("text", "")
        base_result["wordstat_phrases_used"] = refined.get("wordstat_phrases_used") or cleaned_phrases
        logger.info("[%s] Текст дополнен Wordstat-фразами", log_prefix)
    else:
        base_result["wordstat_phrases_used"] = cleaned_phrases
        if missing:
            suffix = f"\n\nКлючевые фразы: {', '.join(cleaned_phrases)}."
            base_result["text"] = (base_result.get("text") or "").strip() + suffix

    # Финальная проверка: точные фразы должны быть в тексте (без замены на латиницу/регистр).
    if cleaned_phrases:
        base_result["text"] = _ensure_exact_phrases(base_result.get("text") or "", cleaned_phrases)
        base_result["wordstat_phrases_used"] = cleaned_phrases

    return base_result


def _select_wordstat_phrases(client: Client, limit: int = 2) -> List[str]:
    """Выбрать избранные фразы Wordstat для клиента по приоритету.

    Приоритет рассчитывается как count / (10 * used), где used=0.01 если ещё не
    использовали фразу. Берём top-N по приоритету без дубликатов.
    """
    if not client or limit <= 0:
        return []

    def _calculate_priority(entries: List[Tuple[float, str]]) -> List[str]:
        ordered: List[str] = []
        for _, phrase in sorted(entries, key=lambda x: x[0], reverse=True):
            if phrase not in ordered:
                ordered.append(phrase)
            if len(ordered) >= limit:
                break
        return ordered

    phrases: List[str] = []
    priorities: List[tuple[float, str]] = []

    try:
        qs = (
            WordstatResult.objects.filter(query__client=client, result_type="favorite")
            .values_list("phrase", "count", "used_in_post")
            .order_by("-query__created_at", "-count", "phrase")
        )
        for phrase, count, used in qs.iterator():
            phrase_clean = (phrase or "").strip()
            if not phrase_clean or phrase_clean in phrases:
                continue
            used_value = 0.01 if not used else float(used)
            count_value = float(count or 0)
            priority = count_value / (10 * used_value) if count_value > 0 else 0.0
            priorities.append((priority, phrase_clean))

        phrases = _calculate_priority(priorities)
    except ProgrammingError as exc:
        logger.warning(
            "Не удалось использовать used_in_post для Wordstat (возможно, не применена миграция): %s",
            exc,
        )
        try:
            fallback_qs = (
                WordstatResult.objects.filter(query__client=client, result_type="favorite")
                .values_list("phrase", "count")
                .order_by("-query__created_at", "-count", "phrase")
            )
            for phrase, count in fallback_qs.iterator():
                phrase_clean = (phrase or "").strip()
                if not phrase_clean or phrase_clean in phrases:
                    continue
                count_value = float(count or 0)
                priority = count_value / 0.1 if count_value > 0 else 0.0  # assume used=0.01
                priorities.append((priority, phrase_clean))
            phrases = _calculate_priority(priorities)
        except Exception as inner_exc:
            logger.warning(
                "Резервный расчёт Wordstat-фраз также не удался для клиента %s: %s",
                getattr(client, "id", None),
                inner_exc,
            )
            return []
    except Exception as exc:
        logger.warning("Не удалось получить избранные Wordstat-фразы для клиента %s: %s", getattr(client, "id", None), exc)
        return []

    return phrases


def _increment_wordstat_usage(
    client: Client,
    phrases: Optional[List[str]],
    previous_phrases: Optional[List[str]] = None,
    had_existing_text: bool = False,
) -> None:
    """
    Увеличить счётчик использования Wordstat-фраз при создании/обновлении поста.

    had_existing_text=True – инкрементируем только новые фразы, чтобы не считать
    повторное сохранение одного и того же поста.
    """
    if not client or not phrases:
        return

    new_set = {p.strip() for p in phrases if isinstance(p, str) and p.strip()}
    if not new_set:
        return

    prev_set = {p.strip() for p in previous_phrases or [] if isinstance(p, str) and p.strip()}
    increment_set = new_set - prev_set if had_existing_text else new_set
    if not increment_set:
        return

    try:
        WordstatResult.objects.filter(query__client=client, phrase__in=increment_set).update(
            used_in_post=F("used_in_post") + 1
        )
    except Exception as exc:
        logger.warning(
            "Не удалось увеличить счётчик использования Wordstat для клиента %s: %s",
            getattr(client, "id", None),
            exc,
        )


def _build_template_config(template: ContentTemplate, client: Client, prompt_type: str = "trend") -> Dict[str, Any]:
    return {
        "tone": template.tone,
        "length": template.length,
        "language": template.language,
        "seo_prompt_template": template.seo_prompt_template,
        "trend_prompt_template": template.trend_prompt_template,
        "prompt_type": prompt_type,
        "additional_instructions": template.additional_instructions,
        "include_hashtags": template.include_hashtags,
        "max_hashtags": template.max_hashtags,
        "type": getattr(template, "type", ""),
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
        "brand": client.get_brand_display_name(),
        "books": client.expert_books or "",
        "video_prompt": client.get_video_prompt_template(),
    }


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
            try:
                template = ContentTemplate.get_for_client_or_system(trend.client, template_id)
            except ContentTemplate.DoesNotExist:
                logger.error(f"Шаблон контента с ID {template_id} не найден для клиента {trend.client_id}")
                return None
        else:
            template = ContentTemplate.get_default_for_client(trend.client)

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
            "brand": trend.client.get_brand_display_name() if trend.client else "",
            "avatar": trend.client.avatar or "",
            "pains": trend.client.pains or "",
            "desires": trend.client.desires or "",
            "objections": trend.client.objections or "",
            "books": trend.client.expert_books or "",
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
        wordstat_phrases = _select_wordstat_phrases(trend.client)

        # Сгенерировать контент
        result = generator.generate_post_text(
            trend_title=trend.title,
            trend_description=trend.description or "",
            trend_url=trend.url or "",
            topic_name=trend.topic.name,
            template_config=template_config,
            seo_keywords=seo_keywords,
            wordstat_phrases=wordstat_phrases,
        )

        if not result.get('success'):
            logger.error(f"Ошибка генерации контента: {result.get('error')}")
            return None

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=getattr(template, "language", "ru"),
            log_prefix="trend",
        )

        # Создать Post
        post_title = result['title']
        post_text = result['text']
        hook_title = result.get('hook_title', '')
        hashtags = result.get('hashtags', [])
        wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []

        # Собрать теги (только хэштеги от AI, без мета-информации)
        tags = hashtags.copy()

        # Создать пост со статусом draft
        post = Post.objects.create(
            client=trend.client,
            template=template,
            title=post_title,
            hook_title=hook_title,
            text=post_text,
            status="draft",  # Требует модерации
            tags=tags,
            source_links=[trend.url] if trend.url else [],
            generated_by="openrouter-deepseek",
            wordstat_phrases_used=wordstat_phrases_used,
            # created_by будет None - автоматическая генерация
        )
        _increment_wordstat_usage(trend.client, wordstat_phrases_used)

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
        template = ContentTemplate.get_for_client_or_system(client, template_id)
    except ContentTemplate.DoesNotExist:
        logger.error(
            "Шаблон %s не найден или недоступен клиенту %s",
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
        "brand": client.get_brand_display_name(),
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
        "books": client.expert_books or "",
    }

    topic_name = ""
    if seo_set.topic and seo_set.topic.name:
        topic_name = seo_set.topic.name
    elif client.name:
        topic_name = client.name
    wordstat_phrases = _select_wordstat_phrases(client)

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
            seo_keywords=per_post_keywords,
            wordstat_phrases=wordstat_phrases,
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

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=getattr(template, "language", "ru"),
            log_prefix="seo-text",
        )

        hashtags = result.get("hashtags", [])
        tags = []
        if isinstance(hashtags, list):
            tags.extend(hashtags)
        if keyword:
            tags.append(keyword)
        tags.append("seo")
        wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []

        # Удаляем дубликаты, сохраняя порядок
        seen = set()
        deduped_tags = []
        for tag in tags:
            if isinstance(tag, str):
                normalized = tag.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    deduped_tags.append(normalized)

        hook_title = result.get("hook_title", "")
        post = Post.objects.create(
            client=client,
            template=template,
            title=result["title"],
            hook_title=hook_title,
            text=result["text"],
            status="draft",
            tags=deduped_tags,
            source_links=[],
            generated_by="seo-keywords",
            created_by_id=created_by_id,
            wordstat_phrases_used=wordstat_phrases_used,
        )
        _increment_wordstat_usage(client, wordstat_phrases_used)
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
def generate_posts_from_custom_task(
    client_id: int,
    template_id: int,
    posts_count: int,
    task: str,
    created_by_id: Optional[int] = None,
):
    """Сгенерировать серию постов по произвольной задаче (freeform)."""
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        logger.error("Client %s не найден для custom генератора", client_id)
        return {"success": False, "error": "client_not_found"}

    task_text = (task or "").strip()
    if not task_text:
        logger.error("Пустая задача для custom генератора (client=%s)", client_id)
        return {"success": False, "error": "task_required"}

    try:
        template = ContentTemplate.get_for_client_or_system(client, template_id)
    except ContentTemplate.DoesNotExist:
        logger.error(
            "Шаблон %s не найден или недоступен клиенту %s (custom генератор)",
            template_id,
            client_id,
        )
        return {"success": False, "error": "template_not_found"}

    try:
        total_posts = max(1, int(posts_count))
    except (TypeError, ValueError):
        total_posts = 1
    total_posts = max(1, min(99, total_posts))

    template_config = {
        "tone": template.tone,
        "length": template.length,
        "language": template.language,
        "type": template.type,
        "seo_prompt_template": template.seo_prompt_template,
        "trend_prompt_template": template.trend_prompt_template,
        "prompt_type": "trend",
        "additional_instructions": template.additional_instructions,
        "include_hashtags": template.include_hashtags,
        "max_hashtags": template.max_hashtags,
        "brand": client.get_brand_display_name(),
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
        "books": client.expert_books or "",
    }

    topic_name = client.name or client.slug
    wordstat_phrases = _select_wordstat_phrases(client)

    try:
        generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора (custom): %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    _configure_custom_generator_model(generator)

    created_posts = 0
    errors: List[Dict[str, str]] = []

    for index in range(1, total_posts + 1):
        logger.info(
            "[CUSTOM %s] Генерация поста %s/%s по задаче",
            client_id,
            index,
            total_posts,
        )

        trend_description = (
            f"ЗАДАЧА:\n{task_text}\n\n"
            f"Сгенерируй уникальный вариант №{index} из {total_posts}. "
            "Не повторяй структуру и формулировки прошлых вариантов."
        )

        result = generator.generate_post_text(
            trend_title=task_text,
            trend_description=trend_description,
            trend_url="",
            topic_name=topic_name,
            template_config=template_config,
            seo_keywords=None,
            wordstat_phrases=wordstat_phrases,
        )

        if not result or not result.get("success"):
            error_message = (result or {}).get("error", "Неизвестная ошибка AI")
            logger.error("[CUSTOM %s] Ошибка генерации: %s", client_id, error_message)
            errors.append({"index": str(index), "error": str(error_message)})
            continue

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=getattr(template, "language", "ru"),
            log_prefix="custom-text",
        )

        hashtags = result.get("hashtags", [])
        tags = []
        if isinstance(hashtags, list):
            tags.extend(hashtags)
        tags.append("custom")
        wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []

        seen = set()
        deduped_tags = []
        for tag in tags:
            if isinstance(tag, str):
                normalized = tag.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    deduped_tags.append(normalized)

        hook_title = result.get("hook_title", "")
        Post.objects.create(
            client=client,
            template=template,
            title=result["title"],
            hook_title=hook_title,
            text=result["text"],
            status="draft",
            tags=deduped_tags,
            source_links=[],
            generated_by="custom-generator",
            created_by_id=created_by_id,
            wordstat_phrases_used=wordstat_phrases_used,
        )
        _increment_wordstat_usage(client, wordstat_phrases_used)
        created_posts += 1

    logger.info(
        "Custom генерация постов для client %s завершена: %s/%s успешно",
        client_id,
        created_posts,
        total_posts,
    )

    return {
        "success": created_posts > 0,
        "created": created_posts,
        "requested": total_posts,
        "errors": errors,
    }


def _extract_three_scene_briefs_from_text(
    title: str,
    text: str,
    hook_title: str = "",
) -> List[str]:
    briefs: List[str] = []
    normalized_title = str(title or "").strip()
    if normalized_title:
        briefs.append(normalized_title)

    normalized_hook = str(hook_title or "").strip()
    if normalized_hook:
        briefs.append(normalized_hook)

    body = str(text or "")
    lines = [line.strip() for line in re.split(r"[\\r\\n]+", body) if line.strip()]
    if not lines:
        sentences = [s.strip() for s in re.split(r"[.!?]+", body) if s.strip()]
        lines = sentences

    for line in lines:
        if len(briefs) >= 3:
            break
        if line not in briefs:
            briefs.append(line)

    while len(briefs) < 3:
        briefs.append(normalized_title or "Сцена")

    return briefs[:3]


def _extract_three_scene_briefs(post: Post) -> List[str]:
    return _extract_three_scene_briefs_from_text(
        title=str(getattr(post, "title", "") or ""),
        text=str(getattr(post, "text", "") or ""),
        hook_title=str(getattr(post, "hook_title", "") or ""),
    )


def _concat_three_videos_to_one(video_paths: List[str]) -> Dict[str, Any]:
    """
    Склеить 3 видео в один ролик (без аудио), с приведением к вертикальному формату.
    """
    if len(video_paths) != 3:
        return {"success": False, "error": "expected_3_videos", "video_path": None, "cleanup_paths": []}
    for path in video_paths:
        if not path or not os.path.exists(path):
            return {"success": False, "error": "missing_scene_video", "video_path": None, "cleanup_paths": []}

    if not shutil.which("ffmpeg"):
        return {"success": False, "error": "ffmpeg_not_found", "video_path": None, "cleanup_paths": []}

    fd, output_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    target_w = int(os.getenv("CUSTOM_VIDEO_WIDTH", "720"))
    target_h = int(os.getenv("CUSTOM_VIDEO_HEIGHT", "1280"))

    def _scene_filter(idx: int) -> str:
        return (
            f"[{idx}:v]"
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1"
            f"[v{idx}]"
        )

    filter_complex = (
        f"{_scene_filter(0)};"
        f"{_scene_filter(1)};"
        f"{_scene_filter(2)};"
        f"[v0][v1][v2]concat=n=3:v=1:a=0[v]"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_paths[0],
        "-i",
        video_paths[1],
        "-i",
        video_paths[2],
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-preset",
        os.getenv("CUSTOM_VIDEO_PRESET", "veryfast"),
        "-crf",
        os.getenv("CUSTOM_VIDEO_CRF", "23"),
        output_path,
    ]

    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass
        return {
            "success": False,
            "error": f"ffmpeg_concat_failed: {(exc.stderr or exc.stdout or str(exc))[:400]}",
            "video_path": None,
            "cleanup_paths": [],
        }

    return {"success": True, "video_path": output_path, "cleanup_paths": [output_path]}


def _strip_code_fences(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\s*```$", "", text)
    return text.strip()


def _parse_json_object(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    raw = _strip_code_fences(value)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _generate_custom_video_scenarios(
    generator: AIContentGenerator,
    post_title: str,
    post_text: str,
    videos_count: int,
) -> List[List[str]]:
    """
    Вернуть список сценариев, каждый сценарий = 3 сцены (3 промпта) для VEO.
    ВАЖНО: без доп. системных/клиентских инструкций — только базовый промпт.
    """
    normalized_title = (post_title or "").strip()
    normalized_text = (post_text or "").strip()

    prompt = f"""
You are a director and scriptwriter for short vertical videos (9:16).
Based on the post below, create EXACTLY {videos_count} different VIDEO SCRIPTS.
Each video script MUST have EXACTLY 3 scenes.

Return STRICT JSON (no markdown), schema:
{{
  "videos": [
    {{
      "scenes": [
        "Scene 1 prompt (English, 1-2 sentences)",
        "Scene 2 prompt (English, 1-2 sentences)",
        "Scene 3 prompt (English, 1-2 sentences)"
      ]
    }}
  ]
}}

Rules for every scene prompt:
- English language
- Vertical 9:16, cinematic, realistic, dynamic camera motion
- NO TITLES / NO ON-SCREEN TEXT / NO SUBTITLES / NO CAPTIONS / NO OVERLAYS / NO WATERMARKS / NO LOGOS
- If there is any dialogue/voiceover, it MUST be in Russian (no English speech)
- Keep each scene prompt under 350 characters
- Videos must be noticeably different from each other (different angles, locations, pacing)

Post:
Title: {normalized_title}
Text: {normalized_text[:1200]}
""".strip()

    response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=1200,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    parsed = _parse_json_object(response)
    videos = (parsed or {}).get("videos")
    scenarios: List[List[str]] = []
    if isinstance(videos, list):
        for item in videos:
            if not isinstance(item, dict):
                continue
            scenes = item.get("scenes")
            if not isinstance(scenes, list):
                continue
            cleaned = []
            for scene in scenes:
                if not isinstance(scene, str):
                    continue
                scene_text = scene.strip()
                if scene_text:
                    cleaned.append(scene_text)
            if len(cleaned) == 3:
                scenarios.append(cleaned)

    if len(scenarios) >= videos_count:
        return scenarios[:videos_count]

    fallback_briefs = _extract_three_scene_briefs_from_text(
        title=normalized_title,
        text=normalized_text,
        hook_title="",
    )
    while len(scenarios) < videos_count:
        variant = [
            (
                f"{fallback_briefs[0]}. Vertical 9:16, cinematic, realistic, dynamic camera motion. "
                "NO TITLES / NO ON-SCREEN TEXT / NO SUBTITLES / NO CAPTIONS. "
                "If dialogue/voiceover appears, it MUST be in Russian."
            ),
            (
                f"{fallback_briefs[1]}. Vertical 9:16, cinematic, realistic, dynamic camera motion. "
                "NO TITLES / NO ON-SCREEN TEXT / NO SUBTITLES / NO CAPTIONS. "
                "If dialogue/voiceover appears, it MUST be in Russian."
            ),
            (
                f"{fallback_briefs[2]}. Vertical 9:16, cinematic, realistic, dynamic camera motion. "
                "NO TITLES / NO ON-SCREEN TEXT / NO SUBTITLES / NO CAPTIONS. "
                "If dialogue/voiceover appears, it MUST be in Russian."
            ),
        ]
        scenarios.append(variant)

    return scenarios[:videos_count]


def _generate_three_scene_videos_for_single_post(
    post: Post,
    videos_per_post: int,
    prompt_generator: AIContentGenerator,
    language: str,
    video_method: str,
    video_options: Dict[str, Any],
    max_attempts: int,
    log_prefix: str = "CustomVideos",
    source_title: Optional[str] = None,
    source_text: Optional[str] = None,
    source_hook_title: Optional[str] = None,
) -> Dict[str, Any]:
    stats = {
        "saved": 0,
        "attempts": 0,
        "errors": [],
    }
    try:
        videos_per_post_int = max(1, min(5, int(videos_per_post)))
    except (TypeError, ValueError):
        videos_per_post_int = 1

    requested_method = (video_method or "veo").strip().lower() or "veo"
    if requested_method != "veo":
        logger.warning(
            "[%s] Метод %s не поддерживается для 3-сценного custom видео; использую veo",
            log_prefix,
            requested_method,
        )
        requested_method = "veo"

    max_attempts = max(1, min(2, int(max_attempts)))
    parallel_scenes = 2 if requested_method == "veo" else 1

    base_title = (source_title if source_title is not None else (post.title or "")).strip()
    base_text = (source_text if source_text is not None else (post.text or "")).strip()
    scenarios = _generate_custom_video_scenarios(
        generator=prompt_generator,
        post_title=base_title,
        post_text=base_text,
        videos_count=videos_per_post_int,
    )

    def _cleanup(paths: List[str]):
        for path in paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _generate_scene_clip(scene_idx: int, prompt_text: str) -> Dict[str, Any]:
        prompt_text = (prompt_text or "").strip()
        if not prompt_text:
            return {
                "success": False,
                "scene_idx": scene_idx,
                "error": "empty_prompt",
                "video_path": None,
                "attempts": 0,
                "cleanup_paths": [],
            }

        attempts = 0
        cleanup_paths: List[str] = []
        last_error = None

        for attempt_no in range(1, max_attempts + 1):
            attempts += 1
            try:
                generator = AIContentGenerator()
            except ValueError as exc:
                last_error = str(exc)
                break

            logger.info(
                "[%s] Пост %s: видео сцена %s/3 (попытка %s/%s)",
                log_prefix,
                post.id,
                scene_idx,
                attempt_no,
                max_attempts,
            )
            result = generator.generate_video_from_text(
                prompt=prompt_text,
                method=requested_method,
                **video_options,
            )
            cleanup_paths.extend(result.get("cleanup_paths") or [])

            video_path = result.get("video_path")
            if result.get("success") and video_path and os.path.exists(video_path):
                return {
                    "success": True,
                    "scene_idx": scene_idx,
                    "error": None,
                    "video_path": video_path,
                    "attempts": attempts,
                    "cleanup_paths": cleanup_paths,
                }
            last_error = result.get("error") or "video_generation_failed"

        return {
            "success": False,
            "scene_idx": scene_idx,
            "error": last_error or "video_generation_failed",
            "video_path": None,
            "attempts": attempts,
            "cleanup_paths": cleanup_paths,
        }

    for video_idx in range(1, videos_per_post_int + 1):
        scenes_for_video = scenarios[video_idx - 1] if len(scenarios) >= video_idx else None
        if not scenes_for_video or len(scenes_for_video) != 3:
            stats["errors"].append(
                {
                    "post_id": post.id,
                    "video_index": video_idx,
                    "error": "scenario_missing",
                    "prompt_start": (base_title or "")[:120],
                }
            )
            continue

        clip_paths: List[str] = ["", "", ""]
        cleanup_paths: List[str] = []
        clip_errors: List[str] = []

        max_workers = min(parallel_scenes, 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_generate_scene_clip, scene_idx, prompt_text): scene_idx
                for scene_idx, prompt_text in enumerate(scenes_for_video, start=1)
            }

            for future in as_completed(futures):
                try:
                    scene_result = future.result()
                except Exception as exc:
                    scene_idx = futures[future]
                    scene_result = {
                        "success": False,
                        "scene_idx": scene_idx,
                        "error": str(exc),
                        "video_path": None,
                        "attempts": 0,
                        "cleanup_paths": [],
                    }

                stats["attempts"] += int(scene_result.get("attempts") or 0)
                cleanup_paths.extend(scene_result.get("cleanup_paths") or [])

                scene_idx = int(scene_result.get("scene_idx") or 0)
                if not scene_result.get("success"):
                    clip_errors.append(f"scene_{scene_idx}_failed:{scene_result.get('error') or 'failed'}")
                    continue

                video_path = scene_result.get("video_path")
                if video_path and os.path.exists(video_path) and 1 <= scene_idx <= 3:
                    clip_paths[scene_idx - 1] = video_path
                else:
                    clip_errors.append(f"scene_{scene_idx}_failed:missing_video_path")

        if not all(clip_paths):
            _cleanup([p for p in clip_paths if p] + cleanup_paths)
            stats["errors"].append(
                {
                    "post_id": post.id,
                    "video_index": video_idx,
                    "error": ";".join(clip_errors) or "scene_generation_failed",
                    "prompt_start": (base_title or "")[:120],
                }
            )
            continue

        concat_result = _concat_three_videos_to_one(clip_paths)
        if not concat_result.get("success"):
            _cleanup(clip_paths + cleanup_paths + (concat_result.get("cleanup_paths") or []))
            stats["errors"].append(
                {
                    "post_id": post.id,
                    "video_index": video_idx,
                    "error": concat_result.get("error") or "concat_failed",
                    "prompt_start": (base_title or "")[:120],
                }
            )
            continue

        final_path = concat_result["video_path"]
        try:
            filename = f"post_{post.id}_{uuid.uuid4().hex[:8]}.mp4"
            with open(final_path, "rb") as video_file:
                post_video = PostVideo(
                    post=post,
                    order=post.videos.count(),
                    caption=(post.title or "")[:255],
                )
                post_video.video.save(filename, File(video_file), save=True)
            stats["saved"] += 1
        except Exception as exc:
            stats["errors"].append(
                {
                    "post_id": post.id,
                    "video_index": video_idx,
                    "error": str(exc),
                    "prompt_start": (base_title or "")[:120],
                }
            )
        finally:
            _cleanup(clip_paths + cleanup_paths + [final_path] + (concat_result.get("cleanup_paths") or []))

    return stats


@shared_task(queue="media")
def generate_posts_with_videos_from_custom_task(
    client_id: int,
    template_id: int,
    posts_count: int,
    task: str,
    videos_per_post: int,
    created_by_id: Optional[int] = None,
):
    """Сгенерировать серию постов по задаче и создать видео (каждое видео из 3 сцен)."""
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        logger.error("Client %s не найден для custom+video генератора", client_id)
        return {"success": False, "error": "client_not_found"}

    task_text = (task or "").strip()
    if not task_text:
        return {"success": False, "error": "task_required"}

    try:
        template = ContentTemplate.get_for_client_or_system(client, template_id)
    except ContentTemplate.DoesNotExist:
        return {"success": False, "error": "template_not_found"}

    try:
        total_posts = max(1, int(posts_count))
    except (TypeError, ValueError):
        total_posts = 1
    total_posts = max(1, min(99, total_posts))

    try:
        videos_per_post_int = max(1, min(5, int(videos_per_post)))
    except (TypeError, ValueError):
        videos_per_post_int = 1

    template_config = {
        "tone": template.tone,
        "length": template.length,
        "language": template.language,
        "type": template.type,
        "seo_prompt_template": template.seo_prompt_template,
        "trend_prompt_template": template.trend_prompt_template,
        "prompt_type": "trend",
        "additional_instructions": template.additional_instructions,
        "include_hashtags": template.include_hashtags,
        "max_hashtags": template.max_hashtags,
        "brand": client.get_brand_display_name(),
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
        "books": client.expert_books or "",
    }

    topic_name = client.name or client.slug
    wordstat_phrases = _select_wordstat_phrases(client)

    try:
        generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора (custom+video): %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    _configure_custom_generator_model(generator)

    created_posts: List[Post] = []
    errors: List[Dict[str, str]] = []

    for index in range(1, total_posts + 1):
        trend_description = (
            f"ЗАДАЧА:\n{task_text}\n\n"
            f"Сгенерируй уникальный вариант №{index} из {total_posts}. "
            "Не повторяй структуру и формулировки прошлых вариантов."
        )

        result = generator.generate_post_text(
            trend_title=task_text,
            trend_description=trend_description,
            trend_url="",
            topic_name=topic_name,
            template_config=template_config,
            seo_keywords=None,
            wordstat_phrases=wordstat_phrases,
        )

        if not result or not result.get("success"):
            error_message = (result or {}).get("error", "Неизвестная ошибка AI")
            errors.append({"index": str(index), "error": str(error_message)})
            continue

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=getattr(template, "language", "ru"),
            log_prefix="custom-video-text",
        )

        hashtags = result.get("hashtags", [])
        tags = []
        if isinstance(hashtags, list):
            tags.extend(hashtags)
        tags.extend(["custom", "video"])

        seen = set()
        deduped_tags = []
        for tag in tags:
            if isinstance(tag, str):
                normalized = tag.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    deduped_tags.append(normalized)

        wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []
        hook_title = result.get("hook_title", "")
        post = Post.objects.create(
            client=client,
            template=template,
            title=result["title"],
            hook_title=hook_title,
            text=result["text"],
            status="draft",
            tags=deduped_tags,
            source_links=[],
            generated_by="custom-generator",
            created_by_id=created_by_id,
            wordstat_phrases_used=wordstat_phrases_used,
        )
        _increment_wordstat_usage(client, wordstat_phrases_used)
        created_posts.append(post)

    if not created_posts:
        return {
            "success": False,
            "created_posts": [],
            "requested": total_posts,
            "errors": errors,
        }

    try:
        prompt_generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора (custom+video prompt): %s", exc)
        return {
            "success": True,
            "created_posts": [p.id for p in created_posts],
            "requested": total_posts,
            "errors": errors,
            "videos": {"success": False, "error": "ai_generator_error"},
        }

    _configure_custom_generator_model(prompt_generator)

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
    # Для custom multi-prompt (3 сцены) режим /video может "подвисать" при параллельных запросах.
    # В best-effort режиме, если меню не ответило, всё равно отправляем промпт (часто бот уже в VEO режиме).
    video_options.setdefault("mode_selection", "best_effort")
    max_attempts_per_scene = max(1, int(os.getenv("VEO_VIDEO_MAX_ATTEMPTS", "2")))

    video_saved = 0
    video_attempts = 0
    video_errors: List[Dict[str, Any]] = []

    for post in created_posts:
        stats = _generate_three_scene_videos_for_single_post(
            post=post,
            videos_per_post=videos_per_post_int,
            prompt_generator=prompt_generator,
            language=getattr(template, "language", "ru"),
            video_method=video_method,
            video_options=video_options,
            max_attempts=max_attempts_per_scene,
            log_prefix=f"CUSTOM {client_id}",
        )
        video_saved += stats["saved"]
        video_attempts += stats["attempts"]
        video_errors.extend(stats["errors"])

    return {
        "success": True,
        "created_posts": [p.id for p in created_posts],
        "requested": total_posts,
        "errors": errors,
        "videos": {
            "videos_per_post": videos_per_post_int,
            "saved": video_saved,
            "attempts": video_attempts,
            "errors": video_errors,
        },
    }


@shared_task(queue="media")
def generate_videos_from_trend_item_description(
    trend_item_id: int,
    videos_per_post: int = 1,
    created_by_id: Optional[int] = None,
    force_new_post: bool = False,
):
    """Сгенерировать видео (3 сцены) по description тренда и сохранить в связанном посте."""
    try:
        trend = TrendItem.objects.select_related("client", "used_for_post", "topic").get(id=trend_item_id)
    except TrendItem.DoesNotExist:
        logger.error("TrendItem %s не найден для custom gen видео", trend_item_id)
        return {"success": False, "error": "trend_not_found"}

    client = trend.client
    if not client:
        return {"success": False, "error": "client_required"}

    source_title = (trend.title or "").strip()
    source_text = (trend.description or "").strip()
    if not source_title and not source_text:
        return {"success": False, "error": "no_source_text"}

    previous_post_id = getattr(trend, "used_for_post_id", None)
    post = None if force_new_post else trend.used_for_post
    created_post = False
    if not post:
        template = ContentTemplate.get_default_for_client(client)

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

        topic_name = ""
        try:
            topic_name = (trend.topic.name or "").strip()
        except Exception:
            topic_name = ""
        if not topic_name:
            topic_name = client.name or client.slug

        template_config = {
            "tone": getattr(template, "tone", "professional"),
            "length": getattr(template, "length", 1200),
            "language": getattr(template, "language", "ru"),
            "type": getattr(template, "type", "selling"),
            "seo_prompt_template": getattr(template, "seo_prompt_template", ""),
            "trend_prompt_template": getattr(template, "trend_prompt_template", ""),
            "prompt_type": "trend",
            "additional_instructions": getattr(template, "additional_instructions", ""),
            "include_hashtags": getattr(template, "include_hashtags", True),
            "max_hashtags": getattr(template, "max_hashtags", 5),
            "brand": client.get_brand_display_name(),
            "avatar": client.avatar or "",
            "pains": client.pains or "",
            "desires": client.desires or "",
            "objections": client.objections or "",
            "books": client.expert_books or "",
        }

        seo_keywords = _get_latest_seo_keywords_for_client(client)
        wordstat_phrases = _select_wordstat_phrases(client)

        post_title = (source_title or "Trend")[:255]
        post_text = source_text or source_title or ""
        hook_title = ""
        tags = ["trend", "custom", "video"]
        wordstat_phrases_used: List[str] = []

        try:
            post_generator = AIContentGenerator()
        except ValueError as exc:
            logger.warning("AI генератор недоступен (trend->post), создаю placeholder пост: %s", exc)
        else:
            result = post_generator.generate_post_text(
                trend_title=source_title or "Trend",
                trend_description=source_text or source_title or "Trend description",
                trend_url=trend.url or "",
                topic_name=topic_name,
                template_config=template_config,
                seo_keywords=seo_keywords,
                wordstat_phrases=wordstat_phrases,
            )
            if result and result.get("success"):
                result = _apply_wordstat_refinement(
                    generator=post_generator,
                    base_result=result,
                    phrases=wordstat_phrases,
                    language=getattr(template, "language", "ru"),
                    log_prefix="trend-custom-video",
                )

                post_title = (result.get("title") or post_title)[:255]
                hook_title = result.get("hook_title") or ""
                post_text = result.get("text") or post_text
                hashtags = result.get("hashtags") or []
                tags = []
                if isinstance(hashtags, list):
                    tags.extend([t for t in hashtags if isinstance(t, str)])
                tags.extend(["trend", "custom", "video"])
                tags = _dedupe_tags(tags)
                wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []
            else:
                logger.warning(
                    "Не удалось сгенерировать текст поста из тренда %s для custom video: %s",
                    trend_item_id,
                    (result or {}).get("error", "post_generation_failed"),
                )

        try:
            post = Post.objects.create(
                client=client,
                template=template,
                title=post_title,
                hook_title=hook_title,
                text=post_text,
                status="draft",
                tags=tags,
                source_links=[trend.url] if trend.url else [],
                generated_by="trenditem-custom-video",
                created_by_id=created_by_id,
                wordstat_phrases_used=wordstat_phrases_used,
            )
            if wordstat_phrases_used:
                _increment_wordstat_usage(client, wordstat_phrases_used)
        except Exception as exc:
            logger.error("Не удалось сохранить пост из тренда %s: %s", trend_item_id, exc, exc_info=True)
            return {"success": False, "error": "post_save_failed"}

        trend.used_for_post = post
        trend.save(update_fields=["used_for_post"])
        created_post = True

    try:
        prompt_generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Ошибка инициализации AI генератора (trend video): %s", exc)
        return {"success": True, "post_id": post.id, "created_post": created_post, "videos": {"success": False}}

    try:
        videos_per_post_int = max(1, min(5, int(videos_per_post)))
    except (TypeError, ValueError):
        videos_per_post_int = 1

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
    max_attempts_per_scene = max(1, int(os.getenv("VEO_VIDEO_MAX_ATTEMPTS", "2")))

    stats = _generate_three_scene_videos_for_single_post(
        post=post,
        videos_per_post=videos_per_post_int,
        prompt_generator=prompt_generator,
        language=getattr(getattr(post, "template", None), "language", "ru"),
        video_method=video_method,
        video_options=video_options,
        max_attempts=max_attempts_per_scene,
        log_prefix=f"TREND {trend_item_id}",
        source_title=source_title or (post.title or ""),
        source_text=source_text or (post.text or ""),
        source_hook_title="",
    )

    return {
        "success": True,
        "trend_item_id": trend_item_id,
        "post_id": post.id,
        "previous_post_id": previous_post_id,
        "created_post": created_post,
        "videos_per_post": videos_per_post_int,
        "saved": stats["saved"],
        "attempts": stats["attempts"],
        "errors": stats["errors"],
    }


@shared_task(queue="media")
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
        template = ContentTemplate.get_for_client_or_system(client, template_id)
    except ContentTemplate.DoesNotExist:
        logger.error(
            "Шаблон %s не найден или недоступен клиенту %s",
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
        "brand": client.get_brand_display_name(),
        "avatar": client.avatar or "",
        "pains": client.pains or "",
        "desires": client.desires or "",
        "objections": client.objections or "",
        "books": client.expert_books or "",
    }

    topic_name = ""
    if seo_set.topic and seo_set.topic.name:
        topic_name = seo_set.topic.name
    elif client.name:
        topic_name = client.name
    wordstat_phrases = _select_wordstat_phrases(client)

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
    max_attempts_per_video = max(1, int(os.getenv("VEO_VIDEO_MAX_ATTEMPTS", "2")))

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
                seo_keywords=per_post_keywords,
                wordstat_phrases=wordstat_phrases,
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

            post_result = _apply_wordstat_refinement(
                generator=generator,
                base_result=post_result,
                phrases=wordstat_phrases,
                language=getattr(template, "language", "ru"),
                log_prefix="seo-video",
            )

            hashtags = post_result.get("hashtags", [])
            tags = []
            if isinstance(hashtags, list):
                tags.extend(hashtags)
            if keyword:
                tags.append(keyword)
            tags.extend(["seo", "video"])
            tags = _dedupe_tags(tags)
            wordstat_phrases_used = post_result.get("wordstat_phrases_used") or wordstat_phrases or []

            try:
                hook_title = post_result.get("hook_title", "")
                post = Post.objects.create(
                    client=client,
                    template=template,
                    title=(post_result.get("title") or keyword or "SEO post")[:255],
                    hook_title=hook_title,
                    text=post_result.get("text") or "",
                    status="draft",
                    tags=tags,
                    source_links=[],
                    generated_by="seo-keywords-video",
                    created_by_id=created_by_id,
                    wordstat_phrases_used=wordstat_phrases_used,
                )
                _increment_wordstat_usage(client, wordstat_phrases_used)
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


@shared_task
def generate_weekly_posts_from_template(
    client_id: int,
    template_id: int,
    posts_per_week: int,
    created_by_id: Optional[int] = None,
    social_account_id: Optional[int] = None,
):
    """Запуск автоматической генерации постов на следующую неделю."""

    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        logger.error("Client %s not found for weekly generation", client_id)
        return {"success": False, "error": "client_not_found"}

    try:
        template = ContentTemplate.get_for_client_or_system(client, template_id)
    except ContentTemplate.DoesNotExist:
        logger.error("Template %s unavailable for client %s", template_id, client_id)
        return {"success": False, "error": "template_not_found"}

    try:
        posts_count = int(posts_per_week)
    except (TypeError, ValueError):
        return {"success": False, "error": "invalid_posts_count"}

    posts_count = max(1, min(MAX_WEEKLY_POSTS, posts_count))

    social_account = None
    if social_account_id:
        try:
            social_account = SocialAccount.objects.get(id=social_account_id, client=client)
        except SocialAccount.DoesNotExist:
            logger.error(
                "Social account %s not found for client %s",
                social_account_id,
                client_id,
            )
            return {"success": False, "error": "social_account_not_found"}
    else:
        social_account = SocialAccount.objects.filter(client=client).order_by("id").first()

    start_local = _get_next_week_start_local(client)
    blocked_days = _collect_existing_weekdays(client, template, start_local)
    weekday_counts = _collect_week_day_load(client, start_local)
    slots = _build_weekly_slots(start_local, posts_count, blocked_days, weekday_counts)
    if not slots:
        return {"success": False, "error": "no_slots"}

    try:
        generator = AIContentGenerator()
    except ValueError as exc:
        logger.error("Failed to init AI generator for weekly posts: %s", exc)
        return {"success": False, "error": "ai_generator_error"}

    template_config = _build_template_config(template, client, prompt_type="trend")
    created_posts: List[int] = []
    scheduled_times: List[str] = []
    errors: List[Dict[str, Any]] = []
    reservations: List[Dict[str, Any]] = []
    wordstat_phrases = _select_wordstat_phrases(client)

    logger.info(
        "Weekly plan: client=%s template=%s posts=%s social_account=%s",
        client.slug,
        template.name,
        posts_count,
        getattr(social_account, "id", None),
    )

    week_tag = f"plan-week:{start_local.date().isoformat()}"

    for index, (local_dt, day_offset) in enumerate(slots, start=1):
        weekday_label = WEEKDAY_LABELS[day_offset]
        trend_title = f"{template.name}: пост на {weekday_label}"
        brand_display = client.get_brand_display_name() or "бренда"
        trend_description = (
            "Подготовь {post_type} пост для {brand} на {weekday} следующей недели. "
            "Используй боли и желания аудитории, избегай ссылок и новостных поводов."
        ).format(
            post_type=template.type or "контентный",
            brand=brand_display,
            weekday=weekday_label,
        )

        planned_at_tag = f"planned-at:{local_dt.isoformat()}"
        base_tags = [
            "auto-week",
            f"template:{template.id}",
            f"weekday:{weekday_label}",
            week_tag,
            planned_at_tag,
        ]
        try:
            placeholder_post = Post.objects.create(
                client=client,
                template=template,
                title=trend_title,
                hook_title="",
                text="",
                status="draft",
                tags=base_tags,
                source_links=[],
                generated_by="weekly-plan",
                created_by_id=created_by_id,
                wordstat_phrases_used=wordstat_phrases,
            )
        except Exception as exc:
            logger.error(
                "Не удалось зарезервировать слот %s для weekly-plan (template=%s): %s",
                index,
                template.id,
                exc,
                exc_info=True,
            )
            errors.append({"index": index, "error": "reservation_failed"})
            continue

        reservations.append({
            "index": index,
            "local_dt": local_dt,
            "day_offset": day_offset,
            "weekday_label": weekday_label,
            "trend_title": trend_title,
            "trend_description": trend_description,
            "post": placeholder_post,
        })

    for reservation in reservations:
        index = reservation["index"]
        local_dt = reservation["local_dt"]
        weekday_label = reservation["weekday_label"]
        trend_title = reservation["trend_title"]
        trend_description = reservation["trend_description"]
        post = reservation["post"]

        try:
            result = generator.generate_post_text(
                trend_title=trend_title,
                trend_description=trend_description,
                trend_url="",
                topic_name=client.name or template.name,
                template_config=template_config,
                seo_keywords=None,
                wordstat_phrases=wordstat_phrases,
            )
        except Exception as exc:
            logger.error("Weekly generator crashed: %s", exc, exc_info=True)
            errors.append({"index": index, "error": "generator_error"})
            try:
                post.delete()
            except Exception:
                pass
            continue

        if not result or not result.get("success"):
            error_message = (result or {}).get("error", "generation_failed")
            logger.error(
                "Weekly generation failed (template=%s, index=%s): %s",
                template.id,
                index,
                error_message,
            )
            errors.append({"index": index, "error": error_message})
            try:
                post.delete()
            except Exception:
                pass
            continue

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=getattr(template, "language", "ru"),
            log_prefix="weekly",
        )

        hashtags = result.get("hashtags", [])
        tags: List[str] = []
        if isinstance(post.tags, list):
            tags.extend([tag for tag in post.tags if isinstance(tag, str)])
        if isinstance(hashtags, list):
            tags.extend([tag for tag in hashtags if isinstance(tag, str)])

        seen = set()
        deduped: List[str] = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
            normalized = tag.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)

        hook_title = result.get("hook_title", "")
        previous_wordstat_phrases = list(post.wordstat_phrases_used or [])
        had_text_before = bool(post.text and str(post.text).strip())
        post.title = result["title"]
        post.hook_title = hook_title
        post.text = result["text"]
        post.tags = deduped
        post.source_links = []
        post.generated_by = "weekly-plan"
        post.created_by_id = created_by_id
        post.wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []
        try:
            post.save(
                update_fields=[
                    "title",
                    "hook_title",
                    "text",
                    "tags",
                    "source_links",
                    "generated_by",
                    "created_by",
                    "wordstat_phrases_used",
                    "updated_at",
                ]
            )
            _increment_wordstat_usage(
                client,
                post.wordstat_phrases_used,
                previous_phrases=previous_wordstat_phrases,
                had_existing_text=had_text_before,
            )
        except Exception as exc:
            logger.error(
                "Не удалось обновить пост %s после генерации weekly-plan: %s",
                getattr(post, "id", None),
                exc,
                exc_info=True,
            )
            errors.append({"index": index, "error": "post_save_failed"})
            try:
                post.delete()
            except Exception:
                pass
            continue

        scheduled_at = local_dt.astimezone(dt_timezone.utc)
        if social_account:
            Schedule.objects.create(
                client=client,
                post=post,
                social_account=social_account,
                scheduled_at=scheduled_at,
                status="pending",
            )
            post.status = "scheduled"
            post.save(update_fields=["status"])

        scheduled_times.append(local_dt.isoformat())

        created_posts.append(post.id)

    logger.info(
        "Weekly plan finished: template=%s created=%s errors=%s",
        template.id,
        len(created_posts),
        len(errors),
    )

    return {
        "success": bool(created_posts),
        "created_posts": created_posts,
        "requested": posts_count,
        "errors": errors,
        "scheduled_at": scheduled_times,
        "social_account_id": getattr(social_account, "id", None),
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
    max_attempts = max(1, min(2, int(max_attempts)))

    extra_instructions = ""
    base_instructions = None
    if getattr(post, "client_id", None):
        try:
            extra_instructions = (post.client.get_video_prompt_template() or "").strip()
            base_instructions = post.client.get_base_video_prompt_instructions()
        except Client.DoesNotExist:
            extra_instructions = ""
            base_instructions = None

    video_prompt_body = prompt_generator.generate_video_prompt(
        post_title=post.title or "",
        post_text=post.text or "",
        language=language,
        extra_instructions=extra_instructions,
        base_instructions=base_instructions,
    )
    if not video_prompt_body:
        video_prompt_body = _build_text_video_prompt(post)

    prompts: Dict[int, str] = {}
    for video_idx in range(1, videos_per_post + 1):
        prompt_to_use = video_prompt_body
        if videos_per_post > 1:
            prompt_to_use = (
                f"{video_prompt_body}\nVariation #{video_idx}: distinct cinematic take, camera work and pacing."
            )
        prompts[video_idx] = merge_video_prompt_with_additional(prompt_to_use, extra_instructions)

    video_state: Dict[int, Dict[str, Any]] = {
        idx: {"attempts": 0, "success": False}
        for idx in prompts
    }
    pending = set(prompts.keys())
    normalized_method = (video_method or "").strip().lower()
    parallel_limit = 2 if normalized_method == "veo" else None

    def _cleanup_temp_files(main_path: Optional[str], extra_paths: List[str]):
        if main_path and os.path.exists(main_path):
            try:
                os.remove(main_path)
            except OSError:
                pass
        for temp_path in extra_paths:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _process_generation_result(idx: int, attempt_no: int, result: Dict[str, Any]):
        stats["attempts"] += 1
        cleanup_paths = result.get("cleanup_paths") or []
        video_path = result.get("video_path")
        try:
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
        finally:
            _cleanup_temp_files(video_path, cleanup_paths)

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
        if parallel_limit is not None:
            max_workers = min(max_workers, parallel_limit)
        run_in_parallel = len(batch) > 1 and max_workers > 1
        if run_in_parallel:
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
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"success": False, "error": str(exc), "cleanup_paths": []}
                    _process_generation_result(idx, attempt_no, result)
        else:
            for idx in batch:
                video_state[idx]["attempts"] += 1
                attempt_no = video_state[idx]["attempts"]
                logger.info(
                    "[%s] Генерация видео %s/%s для поста %s (последовательная попытка %s/%s)",
                    log_prefix,
                    idx,
                    videos_per_post,
                    post.id,
                    attempt_no,
                    max_attempts
                )
                try:
                    result = _run_video_generation(prompts[idx])
                except Exception as exc:
                    result = {"success": False, "error": str(exc), "cleanup_paths": []}
                _process_generation_result(idx, attempt_no, result)

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


@shared_task(queue="media")
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


@shared_task(queue="media")
def generate_image_for_post(post_id: int, model: Optional[str] = None):
    """
    Сгенерировать изображение для поста используя AI.

    Args:
        post_id: ID поста (Post)
        model: Явно указанный метод генерации (openrouter, veo_photo, giga_photo)

    Returns:
        True при успехе, False при ошибке
    """
    try:
        # Получить Post
        post = Post.objects.select_related('client').get(id=post_id)

        alias_map = {
            "nanobanana": "openrouter",
            "pollinations": "openrouter",
            "huggingface": "openrouter",
            "flux2": "openrouter",
            "sora_images": "veo_photo",
            "telegram_bot": "veo_photo",
            "veo": "veo_photo",
            "giga": "giga_photo",
            "gigachat": "giga_photo",
        }

        def _normalize_method(raw_value: Optional[str]) -> str:
            value = (raw_value or "").strip().lower()
            return alias_map.get(value, value)

        provided_method = _normalize_method(model)
        generation_method = provided_method or _normalize_method(get_image_generation_method())
        allowed_methods = {"openrouter", "veo_photo", "giga_photo"}
        if generation_method not in allowed_methods:
            fallback = _normalize_method(get_image_generation_method()) or "openrouter"
            if fallback not in allowed_methods:
                fallback = "openrouter"
            logger.warning(
                "Unknown image generation method '%s' (requested='%s'), falling back to '%s'",
                generation_method,
                (model or "").strip(),
                fallback,
            )
            generation_method = fallback

        logger.info(f"Генерация изображения для поста: {post.title} (ID={post.id}) методом '{generation_method}'")

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
        os.makedirs(os.path.dirname(temp_image_path), exist_ok=True)

        logger.info(f"Генерация изображения методом '{generation_method}' и сохранение в {temp_image_path}...")

        cleanup_paths: Set[str] = set()
        result: Dict[str, Any] = {}
        final_image_path: Optional[str] = None

        def _run_image_generation() -> Dict[str, Any]:
            attempts = 0
            last_result: Dict[str, Any] = {}
            while attempts < 2:
                attempts += 1
                if generation_method == "veo_photo":
                    from ..foto_video_gen import generate_image_from_telegram_bot

                    bot_username = "syntxaibot"
                    session_name = "telegram_sessions/session_collector_client_3"

                    result_local = generate_image_from_telegram_bot(
                        prompt=image_prompt,
                        bot_username=bot_username,
                        session_name=session_name,
                        timeout=os.getenv("IMAGE_BOT_TIMEOUT") or os.getenv("VEO_TIMEOUT") or 300,
                        api_id=os.getenv("TELEGRAM_API_ID"),
                        api_hash=os.getenv("TELEGRAM_API_HASH")
                    )
                else:
                    model_for_generator_local = "openrouter" if generation_method == "openrouter" else generation_method
                    result_local = generator.generate_image(
                        prompt=image_prompt,
                        output_path=temp_image_path,
                        model=model_for_generator_local
                    )
                last_result = result_local
                if result_local.get("success"):
                    return result_local
                logger.warning(
                    "Попытка генерации изображения %s/%s завершилась ошибкой: %s",
                    attempts,
                    2,
                    result_local.get("error")
                )
                if attempts >= 2:
                    break
                # Очистка перед повтором
                for path in cleanup_paths:
                    if path and os.path.exists(path):
                        os.remove(path)
                cleanup_paths.clear()

            return last_result

        result = _run_image_generation()
        if generation_method == "veo_photo":
            final_image_path = result.get("image_path")
            cleanup_paths.update(result.get("cleanup_paths") or [])
        else:
            final_image_path = temp_image_path
            cleanup_paths.add(temp_image_path)

        if not result.get('success'):
            logger.error(f"Ошибка генерации изображения: {result.get('error')}")
            # Очистить файлы даже при ошибке
            for path in cleanup_paths:
                if path and os.path.exists(path):
                    os.remove(path)
            return False

        if not final_image_path or not os.path.exists(final_image_path):
            logger.error("Не найден сгенерированный файл изображения (model=%s)", generation_method)
            for path in cleanup_paths:
                if path and os.path.exists(path):
                    os.remove(path)
            return False

        cleanup_paths.add(final_image_path)

        # Шаг 2.5: Нанести hook_title на изображение, если он есть
        processed_image_path = final_image_path
        if post.hook_title and post.hook_title.strip():
            logger.info(f"Нанесение hook_title на изображение: '{post.hook_title}'")
            overlay_result = apply_text_overlay_to_image(
                input_image_path=final_image_path,
                text=post.hook_title.strip(),
            )
            if overlay_result.get("success") and overlay_result.get("image_path"):
                processed_image_path = overlay_result["image_path"]
                cleanup_paths.add(processed_image_path)
                word_used = overlay_result.get("word_used", "")
                logger.info(f"Hook_title нанесен на изображение, использовано слово: '{word_used}'")
            else:
                logger.warning(f"Не удалось нанести hook_title на изображение: {overlay_result.get('error')}")

        # Шаг 3: Сохранить изображение среди PostImage
        try:
            with open(processed_image_path, 'rb') as f:
                post_image = PostImage(
                    post=post,
                    order=post.images.count(),
                )
                post_image.image.save(image_filename, File(f), save=True)

            logger.info(f"Изображение успешно сохранено в пост {post.id}: {post_image.image.url}")
            logger.info(f"Использован метод генерации: {generation_method}, модель: {result.get('model', generation_method)}")

            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения изображения в пост: {e}", exc_info=True)
            return False
        finally:
            for path in cleanup_paths:
                if not path:
                    continue
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info("Удалён временный файл: %s", path)
                except OSError:
                    pass

    except Post.DoesNotExist:
        logger.error(f"Пост с ID {post_id} не найден")
        return False
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения для поста {post_id}: {e}", exc_info=True)
        return False


@shared_task(queue="media")
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

        client_instructions = ""
        base_instructions = None
        if getattr(post, "client_id", None):
            try:
                client_instructions = (post.client.get_video_prompt_template() or "").strip()
                base_instructions = post.client.get_base_video_prompt_instructions()
            except Client.DoesNotExist:
                client_instructions = ""
                base_instructions = None

        video_prompt = None
        if post.text:
            video_prompt = generator.generate_video_prompt(
                post.title,
                post.text,
                extra_instructions=client_instructions,
                base_instructions=base_instructions,
            )
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

            base_prompt_body = video_prompt or _build_text_video_prompt(post)
            final_prompt = merge_video_prompt_with_additional(base_prompt_body, client_instructions)
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

            base_prompt_body = video_prompt or default_prompt
            if selected_method == "veo":
                base_prompt_body = (
                    base_prompt_body +
                    "\nUse the provided post image as the starting frame and animate it with cinematic motion."
                )
            final_prompt = merge_video_prompt_with_additional(base_prompt_body, client_instructions)
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

        temp_video_paths: List[str] = [video_temp_path]
        final_video_path = video_temp_path

        overlay_scenes = build_overlay_scenes_from_post(
            post.title,
            post.text,
        )
        if overlay_scenes:
            overlay_result = apply_text_overlays_to_video(video_temp_path, overlay_scenes)
            if overlay_result.get("success") and overlay_result.get("video_path"):
                final_video_path = overlay_result["video_path"]
                temp_video_paths.append(final_video_path)
                logger.info(
                    "Добавлены титры к видео поста %s (использовано %s сцен)",
                    post.id,
                    len(overlay_scenes),
                )
            else:
                logger.warning(
                    "Не удалось добавить титры к видео поста %s: %s",
                    post.id,
                    overlay_result.get("error") or "неизвестная ошибка",
                )
        else:
            logger.info("Пост %s не содержит текста для титров, пропускаем наложение", post.id)

        video_filename = f"post_{post.id}_{uuid.uuid4().hex[:8]}.mp4"

        with open(final_video_path, "rb") as video_file:
            post_video = PostVideo(
                post=post,
                order=post.videos.count(),
            )
            post_video.caption = (post.title or "")[:255]
            post_video.video.save(video_filename, File(video_file), save=True)

        existing_cleanup = set(result.get("cleanup_paths") or [])
        cleanup_candidates = existing_cleanup | {path for path in temp_video_paths if path}
        for path in cleanup_candidates:
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
                template = ContentTemplate.get_for_client_or_system(client, template_id)
            except ContentTemplate.DoesNotExist:
                logger.warning(f"Шаблон {template_id} не найден для клиента {client.id}, продолжаем без шаблона")

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
                "length": DEFAULT_TEMPLATE_LENGTH,
                "language": "ru",
                "type": "story",
                "include_hashtags": True,
                "max_hashtags": 5,
                "additional_instructions": "",
            }

        # Информация о клиенте
        client_info = {
            "brand": story.client.get_brand_display_name() if story.client else "",
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
            hook_title = result.get("hook_title", "")
            post = Post.objects.create(
                client=story.client,
                template=story.template,
                story=story,
                episode_number=episode_number,
                title=result["title"],
                hook_title=hook_title,
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

        generator = AIContentGenerator()
        existing_tags = post.tags if isinstance(post.tags, list) else []
        generated_by = (post.generated_by or "").lower()
        has_seo_tag = any(isinstance(tag, str) and tag.lower() == "seo" for tag in existing_tags)
        is_seo_post = bool(not post.story and (has_seo_tag or generated_by in {"seo-keywords", "seo_keywords"}))
        seo_keyword_used: Optional[str] = None
        use_seo_generation = False
        wordstat_phrases = _select_wordstat_phrases(post.client)
        previous_wordstat_phrases = list(post.wordstat_phrases_used or [])
        had_text_before = bool(post.text and str(post.text).strip())

        # Если пост из истории
        if post.story:
            story = post.story
            episode = next((ep for ep in story.episodes if ep["order"] == post.episode_number), None)

            if not episode:
                logger.error(f"Эпизод {post.episode_number} не найден в истории {story.id}")
                return False

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
                    "length": DEFAULT_TEMPLATE_LENGTH,
                    "language": "ru",
                    "type": "story",
                    "include_hashtags": True,
                    "max_hashtags": 5,
                    "additional_instructions": "",
                }

            client_info = {
                "brand": post.client.get_brand_display_name() if post.client else "",
                "avatar": post.client.avatar or "",
                "pains": post.client.pains or "",
                "desires": post.client.desires or "",
                "objections": post.client.objections or "",
            }

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
            template_for_post = post.template
            if not template_for_post and post.client:
                template_for_post = ContentTemplate.get_default_for_client(post.client)

            def _template_config_with_fallback(prompt_type: str):
                if template_for_post:
                    return _build_template_config(template_for_post, post.client, prompt_type=prompt_type)
                return {
                    "tone": "friendly",
                    "length": DEFAULT_TEMPLATE_LENGTH,
                    "language": "ru",
                    "type": "selling",
                    "include_hashtags": True,
                    "max_hashtags": 5,
                    "additional_instructions": "",
                    "brand": post.client.get_brand_display_name() if post.client else "",
                    "avatar": post.client.avatar or "",
                    "pains": post.client.pains or "",
                    "desires": post.client.desires or "",
                    "objections": post.client.objections or "",
                    "books": post.client.expert_books or "",
                    "seo_prompt_template": "",
                    "trend_prompt_template": "",
                    "prompt_type": prompt_type,
                }

            trend = None
            try:
                trend = post.source_trends.select_related("topic").first()
            except Exception:
                trend = post.source_trends.first()

            should_use_seo = bool(is_seo_post or not trend)

            if should_use_seo:
                use_seo_generation = True
                keywords_map = _get_latest_seo_keywords_for_client(post.client)
                keywords_pool: List[str] = []
                if keywords_map:
                    primary_keywords = keywords_map.get("seo_keywords") or []
                    keywords_pool.extend(primary_keywords)
                    if not keywords_pool:
                        for group_keywords in keywords_map.values():
                            if isinstance(group_keywords, list):
                                keywords_pool.extend(group_keywords)
                cleaned_keywords = [kw.strip() for kw in keywords_pool if isinstance(kw, str) and kw.strip()]

                if cleaned_keywords:
                    seo_keyword_used = random.choice(cleaned_keywords)
                    logger.info(
                        "Регенерация SEO поста %s по ключу '%s'",
                        post.id,
                        seo_keyword_used,
                    )
                    template_config = _template_config_with_fallback("seo")
                    topic_name = post.client.name or post.client.slug or "business"
                    result = generator.generate_post_text(
                        trend_title=f"SEO keyword: {seo_keyword_used}",
                        trend_description=f"Regenerated from SEO keywords for post {post.id}",
                        trend_url="",
                        topic_name=topic_name,
                        template_config=template_config,
                        seo_keywords={"seo_keywords": [seo_keyword_used]},
                        wordstat_phrases=wordstat_phrases,
                    )
                else:
                    logger.warning(
                        "SEO ключевые фразы не найдены для клиента %s при регенерации поста %s, fallback на обычную генерацию",
                        post.client_id,
                        post.id,
                    )
                    use_seo_generation = False
                    template_config = _template_config_with_fallback("trend")
                    topic_name = (
                        (trend.topic.name if trend and trend.topic else None)
                        or post.client.name
                        or post.client.slug
                        or "business"
                    )
                    trend_title = trend.title if trend else (post.title or "Контент-план")
                    trend_description = trend.description if trend else (post.text or "")
                    seo_keywords = _get_latest_seo_keywords_for_client(post.client)
                    result = generator.generate_post_text(
                        trend_title=trend_title,
                        trend_description=trend_description,
                        trend_url=trend.url if trend else "",
                        topic_name=topic_name,
                        template_config=template_config,
                        seo_keywords=seo_keywords or None,
                        wordstat_phrases=wordstat_phrases,
                    )
            else:
                template_config = _template_config_with_fallback("trend")
                topic_name = trend.topic.name if trend.topic else (post.client.name or post.client.slug or "business")
                seo_keywords = _get_latest_seo_keywords_for_client(post.client)
                result = generator.generate_post_text(
                    trend_title=trend.title,
                    trend_description=trend.description,
                    trend_url=trend.url or "",
                    topic_name=topic_name,
                    template_config=template_config,
                    seo_keywords=seo_keywords or None,
                    wordstat_phrases=wordstat_phrases,
                )

        if not result.get("success"):
            logger.error(f"Ошибка регенерации поста: {result.get('error')}")
            return False

        result = _apply_wordstat_refinement(
            generator=generator,
            base_result=result,
            phrases=wordstat_phrases,
            language=template_config.get("language") if isinstance(template_config, dict) else "ru",
            log_prefix="regenerate",
        )

        # Обновляем пост
        post.title = result["title"]
        post.hook_title = result.get("hook_title", "")
        post.text = result["text"]

        raw_hashtags = result.get("hashtags", [])
        tags_payload: List[str] = []
        if isinstance(raw_hashtags, list):
            tags_payload.extend(raw_hashtags)
        if use_seo_generation:
            if seo_keyword_used:
                tags_payload.append(seo_keyword_used)
            tags_payload.append("seo")

        cleaned_tags: List[str] = []
        seen_tags: Set[str] = set()
        for tag in tags_payload:
            if isinstance(tag, str):
                normalized = tag.strip()
                if normalized and normalized not in seen_tags:
                    seen_tags.add(normalized)
                    cleaned_tags.append(normalized)

        post.tags = cleaned_tags
        post.regeneration_count += 1
        post.wordstat_phrases_used = result.get("wordstat_phrases_used") or wordstat_phrases or []
        post.save(update_fields=["title", "hook_title", "text", "tags", "regeneration_count", "wordstat_phrases_used", "updated_at"])
        _increment_wordstat_usage(
            post.client,
            post.wordstat_phrases_used,
            previous_phrases=previous_wordstat_phrases,
            had_existing_text=had_text_before,
        )

        logger.info(f"Пост успешно регенерирован: {post.title} (регенераций: {post.regeneration_count})")
        return True

    except Post.DoesNotExist:
        logger.error(f"Пост {post_id} не найден")
        return False
    except Exception as e:
        logger.error(f"Ошибка регенерации поста {post_id}: {e}", exc_info=True)
        return False
