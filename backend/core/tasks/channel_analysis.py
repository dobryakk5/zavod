"""
Celery задачи для AI анализа каналов.
"""

import json
import logging
import re
from collections import defaultdict
from statistics import mean
from typing import Dict, List, Optional, Tuple

import requests

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..ai_generator import AIContentGenerator
from ..models import ChannelAnalysis
from ..telegram_client import (
    TelegramContentCollector,
    normalize_telegram_channel_identifier,
    run_async_task,
)

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {"telegram"}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_ALERT_CHAT_ID = "7852511755"


def _update_analysis(analysis: ChannelAnalysis, **fields) -> None:
    """Сохранить изменения состояния анализа."""
    for attr, value in fields.items():
        setattr(analysis, attr, value)
    update_fields = list(fields.keys())
    if "updated_at" not in update_fields:
        update_fields.append("updated_at")
    analysis.save(update_fields=update_fields)


def _get_telegram_credentials(client) -> Tuple[str, str, str]:
    """Вернуть api_id, api_hash и имя сессии."""
    api_id = client.telegram_api_id or getattr(settings, "TELEGRAM_API_ID", None)
    api_hash = client.telegram_api_hash or getattr(settings, "TELEGRAM_API_HASH", None)

    if client.telegram_api_id and client.telegram_api_hash:
        session_name = f"session_collector_client_{client.id}"
    else:
        session_name = "session_collector_client_3"

    return api_id, api_hash, session_name


def _prepare_posts_text(messages: List[Dict], limit: int = 12) -> str:
    """Сформировать текст из нескольких постов для AI анализа."""
    texts = [msg.get("text", "").strip() for msg in messages if msg.get("text")]
    if not texts:
        return ""
    sample = "\n\n---ПОСТ---\n\n".join(texts[:limit])
    return sample[:12000]


def _parse_ai_json_payload(raw_response: Optional[str]) -> Tuple[Optional[Dict], Optional[str]]:
    if not raw_response:
        return None, "empty response"

    text = raw_response.strip()
    if not text:
        return None, "empty response"

    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    payload = json_match.group(0) if json_match else text
    try:
        return json.loads(payload), None
    except json.JSONDecodeError as exc:
        preview = payload[:400].replace("\n", " ")
        return None, f"{exc}: {preview}"


def _send_telegram_alert(message: str) -> None:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    chat_id = getattr(settings, "TELEGRAM_ALERT_USER_ID", "") or DEFAULT_ALERT_CHAT_ID
    if not token or not chat_id:
        logger.warning("Telegram alert is skipped (token or chat id missing)")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message[:4000]},
            timeout=10,
        )
        if response.status_code != 200:
            logger.error("Failed to send Telegram alert: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.error("Error while sending Telegram alert: %s", exc, exc_info=True)


def _notify_ai_failure(context: str, errors: List[str], analysis: Optional[ChannelAnalysis] = None) -> None:
    if not errors:
        return
    analysis_info = ""
    if analysis:
        analysis_info = f" (analysis_id={analysis.id}, channel={analysis.channel_url})"
    message = f"⚠️ AI ошибка {context}{analysis_info}:\n" + "\n".join(errors[:3])
    logger.warning(message)
    _send_telegram_alert(message)


def _request_ai_json(
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    generator: AIContentGenerator,
    context: str,
    analysis: Optional[ChannelAnalysis] = None,
) -> Optional[Dict]:
    errors: List[str] = []

    response = generator.get_ai_response(prompt, max_tokens=max_tokens, temperature=temperature)
    data, error = _parse_ai_json_payload(response)
    if data is not None:
        return data
    if error:
        current_model = (generator.model or "primary").strip() or "primary"
        errors.append(f"{current_model}: {error}")

    fallback_model = (generator.fallback_model or "").strip()
    if fallback_model:
        fallback_response = generator.get_ai_response(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            model=fallback_model,
            allow_fallback=False,
        )
        fallback_data, fallback_error = _parse_ai_json_payload(fallback_response)
        if fallback_data is not None:
            return fallback_data
        if fallback_error:
            errors.append(f"{fallback_model}: {fallback_error}")

    if errors:
        _notify_ai_failure(context, errors, analysis)
    return None


def _extract_ai_topics(messages: List[Dict], analysis: Optional[ChannelAnalysis] = None) -> Dict[str, List[str]]:
    """Получить ключевые слова и темы при помощи AI."""
    empty_response = {"keywords": [], "topics": [], "content_types": []}
    posts_text = _prepare_posts_text(messages)
    if not posts_text:
        return empty_response

    prompt = f"""Ты контент-аналитик. Проанализируй подборку постов из канала и выдели:
1) keywords — до 10 ключевых слов или коротких фраз
2) topics — до 6 тем или рубрик
3) content_types — до 5 форматов контента (например: stories, экспертные посты, разборы, инструкции)

Посты:
{posts_text}

Верни ЧИСТЫЙ JSON вида:
{{
  "keywords": ["keyword1", "keyword2"],
  "topics": ["topic1", "topic2"],
  "content_types": ["format1", "format2"]
}}
"""
    generator = AIContentGenerator()
    data = _request_ai_json(
        prompt,
        max_tokens=800,
        temperature=0.3,
        generator=generator,
        context="при получении ключевых слов",
        analysis=analysis,
    )

    if not isinstance(data, dict):
        return empty_response

    def ensure_list(key: str) -> List[str]:
        value = data.get(key, [])
        if isinstance(value, list):
            return [str(item)[:80] for item in value]
        return []

    return {
        "keywords": ensure_list("keywords"),
        "topics": ensure_list("topics"),
        "content_types": ensure_list("content_types"),
    }


def _extract_audience_profile(messages: List[Dict], analysis: Optional[ChannelAnalysis] = None) -> Dict[str, str]:
    """Получить описание целевой аудитории канала."""
    posts_text = _prepare_posts_text(messages, limit=20)
    if not posts_text:
        return {}

    prompt = f"""Проанализируй последние 20 постов из Telegram канала и определи профиль целевой аудитории.

Эти посты обращены к аудитории. Определи:
1) avatar — собирательный образ целевой аудитории
2) pains — основные боли и проблемы
3) desires — желания и цели
4) objections — страхи и возражения, мешающие купить или попробовать

Посты:
{posts_text}

Ответ верни в JSON:
{{
  "avatar": "кто они",
  "pains": "их проблемы",
  "desires": "их цели",
  "objections": "их страхи"
}}
"""
    generator = AIContentGenerator()
    data = _request_ai_json(
        prompt,
        max_tokens=1200,
        temperature=0.4,
        generator=generator,
        context="при определении профиля аудитории",
        analysis=analysis,
    )

    if not isinstance(data, dict):
        return {}

    def clean(key: str) -> str:
        value = data.get(key)
        if isinstance(value, str):
            return value.strip()
        return ""

    return {
        "avatar": clean("avatar"),
        "pains": clean("pains"),
        "desires": clean("desires"),
        "objections": clean("objections"),
    }


def _build_schedule(messages: List[Dict]) -> List[Dict]:
    """Сформировать расписание публикаций."""
    counter = defaultdict(int)
    current_tz = timezone.get_current_timezone()

    for msg in messages:
        timestamp = msg.get("date")
        if not timestamp:
            continue
        dt = timestamp
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone=timezone.utc)
        dt = dt.astimezone(current_tz)
        day = DAY_NAMES[dt.weekday()]
        counter[(day, dt.hour)] += 1

    sorted_slots = sorted(counter.items(), key=lambda item: item[1], reverse=True)
    return [
        {"day": day, "hour": hour, "posts_count": count}
        for (day, hour), count in sorted_slots[:14]
    ]


def _summarize_posts(messages: List[Dict]) -> Dict[str, float]:
    """Рассчитать метрики просмотров и вовлеченности."""
    views = [int(msg.get("views") or 0) for msg in messages if msg.get("views") is not None]
    avg_views = int(mean(views)) if views else 0

    reactions_values = [int(msg.get("reactions") or 0) for msg in messages]
    comments_values = [int(msg.get("comments") or 0) for msg in messages]
    avg_reactions = int(mean(reactions_values)) if reactions_values else 0
    avg_comments = int(mean(comments_values)) if comments_values else 0

    engagement_rates = []
    for msg in messages:
        views_count = int(msg.get("views") or 0)
        forwards = int(msg.get("forwards") or 0)
        if views_count > 0:
            engagement_rates.append((forwards / views_count) * 100)
    avg_engagement = round(mean(engagement_rates), 2) if engagement_rates else 0.0

    sorted_posts = sorted(messages, key=lambda m: int(m.get("views") or 0), reverse=True)[:5]
    top_posts = []
    for msg in sorted_posts:
        text = (msg.get("text") or "").strip()
        title = text.split("\n")[0][:140] if text else f"Пост #{msg.get('id')}"
        views_count = int(msg.get("views") or 0)
        forwards = int(msg.get("forwards") or 0)
        reactions_count = int(msg.get("reactions") or 0)
        comments = int(msg.get("comments") or 0)
        engagement = round((forwards / views_count) * 100, 2) if views_count else 0.0
        top_posts.append({
            "title": title if title else f"Пост #{msg.get('id')}",
            "views": views_count,
            "engagement": engagement,
            "reactions": reactions_count,
            "comments": comments,
            "url": msg.get("url"),
        })

    return {
        "avg_views": avg_views,
        "avg_engagement": avg_engagement,
        "avg_reactions": avg_reactions,
        "avg_comments": avg_comments,
        "top_posts": top_posts,
    }


def _analyze_telegram_channel(analysis: ChannelAnalysis) -> Dict:
    """Выполнить сбор и анализ Telegram канала."""
    client = analysis.client
    api_id, api_hash, session_name = _get_telegram_credentials(client)
    if not api_id or not api_hash:
        raise RuntimeError("Не настроены Telegram API ID/API Hash для анализа каналов")

    channel_identifier = normalize_telegram_channel_identifier(analysis.channel_url)
    if not channel_identifier:
        raise ValueError("Не удалось распознать Telegram канал из URL")

    collector = TelegramContentCollector(api_id=api_id, api_hash=api_hash, session_name=session_name)

    async def fetch_data():
        await collector.connect()
        try:
            info = await collector.get_channel_info(channel_identifier)
            messages = await collector.get_channel_messages(channel_identifier, limit=50)
            return info, messages
        finally:
            await collector.disconnect()

    channel_info, messages = run_async_task(fetch_data())
    _update_analysis(analysis, progress=40)

    if not messages:
        raise RuntimeError("Не удалось получить посты из канала. Проверьте доступность канала и Telegram сессию.")

    stats = _summarize_posts(messages)
    _update_analysis(analysis, progress=70)
    schedule = _build_schedule(messages)
    insights = _extract_ai_topics(messages, analysis)
    audience_profile = _extract_audience_profile(messages, analysis)
    _update_analysis(analysis, progress=90)

    channel_title = (channel_info or {}).get("title") or channel_identifier
    subscribers = int((channel_info or {}).get("subscribers") or 0)

    return {
        "channel_name": channel_title,
        "subscribers": subscribers,
        "avg_views": stats["avg_views"],
        "avg_engagement": stats["avg_engagement"],
        "avg_reactions": stats["avg_reactions"],
        "avg_comments": stats["avg_comments"],
        "top_posts": stats["top_posts"],
        "keywords": insights["keywords"],
        "topics": insights["topics"],
        "content_types": insights["content_types"],
        "posting_schedule": schedule,
        "audience_profile": audience_profile,
    }


@shared_task(bind=True, max_retries=0)
def analyze_channel_task(self, analysis_id: int):
    """Celery задача для анализа канала."""
    try:
        analysis = ChannelAnalysis.objects.select_related("client").get(id=analysis_id)
    except ChannelAnalysis.DoesNotExist:
        logger.error("ChannelAnalysis %s не найден", analysis_id)
        return

    if analysis.status in {ChannelAnalysis.STATUS_COMPLETED, ChannelAnalysis.STATUS_IN_PROGRESS}:
        return analysis.result

    _update_analysis(
        analysis,
        status=ChannelAnalysis.STATUS_IN_PROGRESS,
        progress=10,
        error="",
    )

    try:
        if analysis.channel_type not in SUPPORTED_TYPES:
            raise ValueError("Анализ для этого типа канала пока не поддерживается")

        result = _analyze_telegram_channel(analysis)

        _update_analysis(
            analysis,
            status=ChannelAnalysis.STATUS_COMPLETED,
            progress=100,
            result=result,
            error="",
        )
        return result

    except Exception as exc:
        logger.error("Ошибка анализа канала %s: %s", analysis.id, exc, exc_info=True)
        _update_analysis(
            analysis,
            status=ChannelAnalysis.STATUS_FAILED,
            progress=100,
            error=str(exc),
        )
        raise
