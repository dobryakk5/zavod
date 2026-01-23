"""
Celery задачи для AI анализа каналов.
"""

import json
import logging
import re
from datetime import datetime
from collections import defaultdict
from statistics import mean
from typing import Dict, List, Optional, Tuple

import requests

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..ai_generator import AIContentGenerator
from ..generation_events import check_generation_limit, record_generation_event
from ..instagram_client import fetch_instagram_profile, normalize_instagram_username
from ..models import ChannelAnalysis, Client, GenerationEvent, ProjectChannelAnalysisRun, ProjectChannelPostStat
from ..telegram_client import (
    TelegramContentCollector,
    normalize_telegram_channel_identifier,
    run_async_task,
)
from ..youtube_client import fetch_youtube_channel, normalize_youtube_identifier

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {"telegram", "instagram", "youtube"}
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


def _get_youtube_api_key(client) -> Optional[str]:
    """Вернуть YouTube API ключ, fallback на настройки приложения."""
    return client.youtube_api_key or getattr(settings, "YOUTUBE_API_KEY", None)


def _prepare_posts_text(
    messages: List[Dict],
    limit: int = 12,
    *,
    max_chars: int = 12000,
    per_post_limit: Optional[int] = None,
) -> str:
    """Сформировать текст из нескольких постов для AI анализа."""
    texts: List[str] = []
    for msg in messages:
        text = (msg.get("text") or "").strip()
        if not text:
            continue
        if per_post_limit and len(text) > per_post_limit:
            text = text[:per_post_limit].rstrip()
        texts.append(text)
        if len(texts) >= limit:
            break
    if not texts:
        return ""
    sample = "\n\n---ПОСТ---\n\n".join(texts)
    if max_chars and len(sample) > max_chars:
        return sample[:max_chars]
    return sample


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


def _split_telegram_message(text: str, max_length: int = 4000) -> List[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= max_length:
        return [normalized]
    parts: List[str] = []
    remaining = normalized
    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break
        split_idx = remaining.rfind("\n", 0, max_length)
        if split_idx <= 0:
            split_idx = max_length
        parts.append(remaining[:split_idx].rstrip())
        remaining = remaining[split_idx:].lstrip()
    return parts


def _send_telegram_message(chat_id: str, text: str) -> None:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
    if not token or not chat_id:
        logger.warning("Telegram notify is skipped (token or chat id missing)")
        return
    for part in _split_telegram_message(text):
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": part},
                timeout=10,
            )
            if response.status_code != 200:
                logger.error("Failed to send Telegram message: %s %s", response.status_code, response.text)
        except Exception as exc:
            logger.error("Error while sending Telegram message: %s", exc, exc_info=True)


def _format_metric(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _format_delta(value: int | None) -> str:
    if value is None:
        return ""
    sign = "+" if value >= 0 else ""
    return f"{sign}{int(value):,}".replace(",", " ")


def _format_metric_with_delta(value: int | None, delta: int | None) -> str:
    base = _format_metric(value)
    if delta is None:
        return base
    return f"{base} ({_format_delta(delta)})"


def _resolve_client_timezone(client: Client):
    try:
        return ZoneInfo(client.timezone or "")
    except ZoneInfoNotFoundError:
        return timezone.get_default_timezone()


def _build_project_channel_message(
    client: Client,
    run: ProjectChannelAnalysisRun,
    channels: List[Dict],
    previous_subscribers: Dict[Tuple[int, str, str], int],
) -> str:
    tz = _resolve_client_timezone(client)
    generated_at = timezone.localtime(run.created_at, tz)
    header = f"📊 Аналитика каналов проекта — {client.name}\n{generated_at:%Y-%m-%d %H:%M}"

    lines: List[str] = [header]
    if not channels:
        lines.append("Нет данных для анализа.")
        return "\n".join(lines)

    for channel in channels:
        channel_type = channel.get("channel_type") or "unknown"
        channel_identifier = channel.get("channel_identifier") or ""
        summary = channel.get("summary") or {}
        totals = channel.get("totals") or {}
        delta = channel.get("delta") or {}

        channel_name = summary.get("channel_name") or channel_identifier or channel.get("channel_url") or "Без названия"
        subscribers = summary.get("subscribers")
        prev_run_id = channel.get("previous_run_id")
        prev_subs = previous_subscribers.get((prev_run_id, channel_type, channel_identifier))
        delta_subs = None if prev_subs is None else int(subscribers or 0) - int(prev_subs)

        lines.append("")
        lines.append(f"• {channel_name} ({channel_type})")
        if channel.get("channel_url"):
            lines.append(str(channel.get("channel_url")))

        subs_line = f"Подписчики: {_format_metric(subscribers)}"
        if delta_subs is not None:
            subs_line += f" ({_format_delta(delta_subs)})"
        lines.append(subs_line)

        lines.append("Просмотры: " + _format_metric_with_delta(totals.get("views"), delta.get("views")))
        lines.append("Реакции: " + _format_metric_with_delta(totals.get("reactions"), delta.get("reactions")))
        lines.append("Комментарии: " + _format_metric_with_delta(totals.get("comments"), delta.get("comments")))

    return "\n".join(lines)


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

    channel_label = "канала"
    if analysis and analysis.channel_type == "telegram":
        channel_label = "Telegram канала"
    elif analysis and analysis.channel_type == "instagram":
        channel_label = "Instagram аккаунта"
    elif analysis and analysis.channel_type == "youtube":
        channel_label = "YouTube канала"

    prompt = f"""Проанализируй последние 20 постов из {channel_label} и определи профиль целевой аудитории.

Эти посты обращены к аудитории. Определи:
1) avatar — собирательный образ целевой аудитории
2) pains — основные боли и проблемы
3) desires — желания и цели
4) objections — страхи и возражения, мешающие купить или попробовать

Пиши ответы одним абзацем без списков и без пустых строк.

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


def _extract_author_influence_analysis(
    messages: List[Dict],
    analysis: Optional[ChannelAnalysis] = None,
) -> Dict:
    """Получить анализ ценностей и стиля влияния автора."""
    def build_prompt(posts_text: str) -> str:
        return f"""SYSTEM ROLE:
You are an AI marketing analyst specializing in behavioral pattern analysis,
influence modeling, and value-based marketing.
You do NOT perform psychological diagnostics or personality typing.

INPUT:
A set of the latest Telegram posts from a single channel author (20-30 posts).
Treat the content as a behavioral trace, not as answers to a questionnaire.

POSTS:
{posts_text}

GOAL:
Produce a marketing-oriented profile that helps:
- increase ad integration conversion
- adapt offers to the author
- reduce partnership and integration risks

IMPORTANT CONSTRAINTS:
- Do NOT assign personality types or diagnoses
- Do NOT reference psychological tests (Hogan, Big5, Enneagram, etc.)
- All conclusions must be phrased as hypotheses and observable patterns
- Focus ONLY on marketing, sales, and influence

---

ANALYSIS TASKS:

1. Identify dominant VALUE DRIVERS reflected in the content
   (e.g. control, status, autonomy, knowledge, usefulness, freedom, meaning).

2. Describe the AUTHOR'S INFLUENCE STYLE in communication:
   - logic vs emotion vs authority
   - dominant vs cooperative
   - teaching, leading, confronting, supporting

3. Describe the NORMAL BEHAVIORAL PATTERN:
   - how the author positions themselves
   - how they argue
   - how they influence their audience

4. Identify POTENTIAL RISKS under stress or disagreement:
   - criticism patterns
   - rigidity
   - devaluation
   - resistance to control or instructions

5. Form a MOTIVATIONAL PATTERN HYPOTHESIS
   (describe 1-2 dominant motivational tendencies, not a "type").

6. Translate all findings into CLEAR MARKETING RECOMMENDATIONS.

---

OUTPUT FORMAT (STRICT, RUSSIAN HEADINGS ONLY):

### 1. Краткий обзор автора (5-7 предложений)
Краткое и нейтральное описание того, как автор действует и влияет.

### 2. Ключевые драйверы ценностей
Перечень 4-6 драйверов по силе влияния.
Для каждого:
- Название драйвера
- Доказательства из контента
- Как использовать в маркетинговой коммуникации

### 3. Стиль влияния и коммуникации
Буллеты:
- метод убеждения
- тон
- отношение к аудитории
- позиция в контенте (эксперт / лидер / партнер / челленджер)

### 4. Риски партнерства и интеграций
Список конкретных рисков с пояснениями.
Пример:
- Риск: сопротивление жестким скриптам
- Почему: частые акценты на автономии и личном суждении

### 5. Playbook взаимодействия в маркетинге
**Лучший подход:**
- угол атаки
- фрейминг сообщения
- тон
- стиль CTA

**Избегать:**
- типы сообщений
- обещания
- формулировки, которые вероятнее не сработают

### 6. Резюме для принятия решений
3-5 буллетов:
- Подходит ли автор для интеграций?
- Какие продукты лучше всего подходят?
- Как максимизировать конверсию?

---

FINAL CHECK:
If any conclusion is weakly supported by the text, mark it explicitly as
"low confidence hypothesis".

OUTPUT LANGUAGE:
- Produce the final report in Russian.
- Preserve marketing terminology in a professional business style.

OUTPUT FORMAT:
Return ONLY valid JSON. Do NOT use markdown, headings, or extra text.
Schema:
{{
  "short_overview": "5-7 sentences",
  "core_value_drivers": [
    {{
      "driver": "Название драйвера",
      "evidence": "Доказательства из контента",
      "marketing_use": "Как использовать в коммуникации"
    }}
  ],
  "influence_style": {{
    "persuasion_method": "logic/emotion/authority mix",
    "tone": "тон общения",
    "audience_relationship": "роль и дистанция",
    "content_posture": "эксперт/лидер/партнер/челленджер"
  }},
  "risk_signals": [
    {{
      "risk": "Короткая формулировка риска",
      "why": "Почему это риск по тексту"
    }}
  ],
  "marketing_playbook": {{
    "best_approach": {{
      "angle": "угол атаки",
      "message_framing": "фрейминг сообщения",
      "tone": "тон",
      "cta_style": "стиль CTA"
    }},
    "avoid": {{
      "message_types": "тип сообщений",
      "promises": "обещания",
      "wording_styles": "формулировки"
    }}
  }},
  "executive_summary": [
    "буллет 1",
    "буллет 2"
  ]
}}
"""
    generator = AIContentGenerator()

    attempts = [
        {"limit": 30},
        {"limit": 20},
    ]

    for attempt in attempts:
        posts_text = _prepare_posts_text(
            messages,
            limit=attempt["limit"],
            max_chars=0,
        )
        if not posts_text:
            continue
        prompt = build_prompt(posts_text)
        data = _request_ai_json(
            prompt,
            max_tokens=2200,
            temperature=0.4,
            generator=generator,
            context="при анализе ценностей и стиля влияния автора",
            analysis=analysis,
        )
        if isinstance(data, dict):
            return data

    _notify_ai_failure("при анализе ценностей и стиля влияния автора", ["empty response"], analysis)
    return {}


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


def _summarize_posts(messages: List[Dict], *, audience_size: Optional[int] = None) -> Dict[str, float]:
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
        reactions_count = int(msg.get("reactions") or 0)
        comments_count = int(msg.get("comments") or 0)
        if audience_size and audience_size > 0:
            engagement_rates.append(((reactions_count + comments_count) / audience_size) * 100)
        elif views_count > 0:
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
        if audience_size and audience_size > 0:
            engagement = round(((reactions_count + comments) / audience_size) * 100, 2)
        elif views_count:
            engagement = round((forwards / views_count) * 100, 2)
        else:
            engagement = 0.0
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
    _update_analysis(analysis, progress=25)

    if not messages:
        raise RuntimeError("Не удалось получить посты из канала. Проверьте доступность канала и Telegram сессию.")

    stats = _summarize_posts(messages)
    _update_analysis(analysis, progress=50)
    schedule = _build_schedule(messages)
    insights = _extract_ai_topics(messages, analysis)
    audience_profile = _extract_audience_profile(messages, analysis)
    author_influence_analysis = _extract_author_influence_analysis(messages, analysis)
    _update_analysis(analysis, progress=75)

    channel_title = (channel_info or {}).get("title") or channel_identifier
    subscribers = int((channel_info or {}).get("subscribers") or 0)

    _update_analysis(analysis, progress=90)

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
        "author_influence_analysis": author_influence_analysis,
    }


def _analyze_instagram_channel(analysis: ChannelAnalysis) -> Dict:
    """Выполнить сбор и анализ Instagram аккаунта."""
    username = normalize_instagram_username(analysis.channel_url)
    if not username:
        raise ValueError("Не удалось распознать Instagram аккаунт из ссылки")

    profile, posts = fetch_instagram_profile(username, limit=50)
    _update_analysis(analysis, progress=25)

    if not posts:
        raise RuntimeError("Не удалось получить посты из Instagram аккаунта.")

    subscribers = int(profile.get("followers_count") or 0)
    stats = _summarize_posts(posts, audience_size=subscribers or None)
    _update_analysis(analysis, progress=50)

    schedule = _build_schedule(posts)
    insights = _extract_ai_topics(posts, analysis)
    audience_profile = _extract_audience_profile(posts, analysis)
    author_influence_analysis = _extract_author_influence_analysis(posts, analysis)
    _update_analysis(analysis, progress=75)

    channel_title = profile.get("full_name") or profile.get("username") or username
    profile_url = f"https://www.instagram.com/{profile.get('username') or username}/"

    _update_analysis(analysis, progress=90)

    return {
        "channel_name": channel_title,
        "channel_username": profile.get("username") or username,
        "profile_url": profile_url,
        "bio": profile.get("biography") or "",
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
        "author_influence_analysis": author_influence_analysis,
    }


def _analyze_youtube_channel(analysis: ChannelAnalysis) -> Dict:
    """Выполнить сбор и анализ YouTube канала."""
    client = analysis.client
    api_key = _get_youtube_api_key(client)
    if not api_key:
        raise RuntimeError("Не настроен YouTube API ключ для анализа каналов")

    identifier = normalize_youtube_identifier(analysis.channel_url)
    if not identifier:
        raise ValueError("Не удалось распознать YouTube канал из URL")

    profile, videos = fetch_youtube_channel(api_key, identifier, max_videos=50)
    _update_analysis(analysis, progress=25)

    if not videos:
        raise RuntimeError("Не удалось получить видео из YouTube канала.")

    subscribers = int(profile.get("subscriber_count") or 0)
    stats = _summarize_posts(videos, audience_size=subscribers or None)
    _update_analysis(analysis, progress=50)

    schedule = _build_schedule(videos)
    insights = _extract_ai_topics(videos, analysis)
    audience_profile = _extract_audience_profile(videos, analysis)
    author_influence_analysis = _extract_author_influence_analysis(videos, analysis)
    _update_analysis(analysis, progress=75)

    channel_title = profile.get("title") or identifier
    channel_username = profile.get("custom_url") or ""
    profile_url = ""
    if channel_username:
        profile_url = f"https://www.youtube.com/{channel_username.lstrip('/')}"
    elif profile.get("channel_id"):
        profile_url = f"https://www.youtube.com/channel/{profile.get('channel_id')}"

    _update_analysis(analysis, progress=90)

    return {
        "channel_name": channel_title,
        "channel_username": channel_username,
        "profile_url": profile_url,
        "bio": profile.get("description") or "",
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
        "author_influence_analysis": author_influence_analysis,
    }


def _update_project_run(run: ProjectChannelAnalysisRun, **fields) -> None:
    """Сохранить изменения состояния анализа проекта."""
    for attr, value in fields.items():
        setattr(run, attr, value)
    update_fields = list(fields.keys())
    if "updated_at" not in update_fields:
        update_fields.append("updated_at")
    run.save(update_fields=update_fields)


def _coerce_datetime(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _format_datetime(value) -> Optional[str]:
    dt = _coerce_datetime(value)
    return dt.isoformat() if dt else None


def _extract_post_title(post: Dict) -> str:
    text = (post.get("title") or post.get("text") or "").strip()
    if not text:
        return ""
    return text.split("\n")[0][:140]


def _get_previous_project_stats(
    client,
    channel_type: str,
    channel_identifier: str,
    run_id: int,
) -> Tuple[Optional[int], Dict[str, ProjectChannelPostStat], Dict[str, int]]:
    previous_run_id = (
        ProjectChannelPostStat.objects.filter(
            client=client,
            channel_type=channel_type,
            channel_identifier=channel_identifier,
            run__status=ProjectChannelAnalysisRun.STATUS_COMPLETED,
        )
        .exclude(run_id=run_id)
        .order_by("-run__created_at")
        .values_list("run_id", flat=True)
        .first()
    )

    if not previous_run_id:
        return None, {}, {"posts_count": 0, "views": 0, "reactions": 0, "comments": 0}

    previous_stats = list(
        ProjectChannelPostStat.objects.filter(
            run_id=previous_run_id,
            channel_type=channel_type,
            channel_identifier=channel_identifier,
        )
    )
    stats_map = {stat.external_id: stat for stat in previous_stats}
    totals = {
        "posts_count": len(previous_stats),
        "views": sum(stat.views for stat in previous_stats),
        "reactions": sum(stat.reactions for stat in previous_stats),
        "comments": sum(stat.comments for stat in previous_stats),
    }
    return previous_run_id, stats_map, totals


def _collect_project_telegram_data(client, channel_url: str) -> Tuple[str, Dict, List[Dict]]:
    api_id, api_hash, session_name = _get_telegram_credentials(client)
    if not api_id or not api_hash:
        raise RuntimeError("Не настроены Telegram API ID/API Hash для анализа каналов")

    channel_identifier = normalize_telegram_channel_identifier(channel_url)
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
    if not messages:
        raise RuntimeError("Не удалось получить посты из Telegram канала.")

    return channel_identifier, channel_info, messages


def _collect_project_instagram_data(channel_url: str) -> Tuple[str, Dict, List[Dict]]:
    username = normalize_instagram_username(channel_url)
    if not username:
        raise ValueError("Не удалось распознать Instagram аккаунт из ссылки")
    profile, posts = fetch_instagram_profile(username, limit=50)
    if not posts:
        raise RuntimeError("Не удалось получить посты из Instagram аккаунта.")
    return username, profile, posts


def _collect_project_youtube_data(client, channel_url: str) -> Tuple[str, Dict, List[Dict]]:
    api_key = _get_youtube_api_key(client)
    if not api_key:
        raise RuntimeError("Не настроен YouTube API ключ для анализа каналов")
    identifier = normalize_youtube_identifier(channel_url)
    if not identifier:
        raise ValueError("Не удалось распознать YouTube канал из URL")
    profile, videos = fetch_youtube_channel(api_key, identifier, max_videos=50)
    if not videos:
        raise RuntimeError("Не удалось получить видео из YouTube канала.")
    return identifier, profile, videos


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
        if analysis.channel_type == "telegram":
            result = _analyze_telegram_channel(analysis)
        elif analysis.channel_type == "instagram":
            result = _analyze_instagram_channel(analysis)
        elif analysis.channel_type == "youtube":
            result = _analyze_youtube_channel(analysis)
        else:
            raise ValueError("Анализ для этого типа канала пока не поддерживается")

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
            progress=analysis.progress or 0,
            error=str(exc),
        )
        raise


@shared_task(bind=True, max_retries=0)
def analyze_project_channels_task(self, run_id: int):
    """Celery задача для анализа каналов проекта клиента."""
    try:
        run = ProjectChannelAnalysisRun.objects.select_related("client").get(id=run_id)
    except ProjectChannelAnalysisRun.DoesNotExist:
        logger.error("ProjectChannelAnalysisRun %s не найден", run_id)
        return

    if run.status in {ProjectChannelAnalysisRun.STATUS_COMPLETED, ProjectChannelAnalysisRun.STATUS_IN_PROGRESS}:
        return run.result

    _update_project_run(
        run,
        status=ProjectChannelAnalysisRun.STATUS_IN_PROGRESS,
        progress=5,
        error="",
    )

    client = run.client
    channels = [
        ("telegram", client.project_telegram_channel or ""),
        ("instagram", client.project_instagram_channel or ""),
        ("youtube", client.project_youtube_channel or ""),
    ]
    channels = [(ctype, value.strip()) for ctype, value in channels if value and value.strip()]
    if not channels:
        _update_project_run(
            run,
            status=ProjectChannelAnalysisRun.STATUS_FAILED,
            progress=run.progress or 0,
            error="Не указаны каналы проекта для анализа.",
        )
        return

    results: List[Dict] = []
    progress_step = max(1, int(80 / max(1, len(channels))))

    try:
        for index, (channel_type, channel_url) in enumerate(channels, start=1):
            if channel_type == "telegram":
                channel_identifier, channel_info, posts = _collect_project_telegram_data(client, channel_url)
                subscribers = int((channel_info or {}).get("subscribers") or 0)
                stats = _summarize_posts(posts)
                schedule = _build_schedule(posts)
                insights = _extract_ai_topics(posts)
                audience_profile = _extract_audience_profile(posts)
                author_influence_analysis = _extract_author_influence_analysis(posts)
                channel_title = (channel_info or {}).get("title") or channel_identifier
                summary = {
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
                    "author_influence_analysis": author_influence_analysis,
                }
            elif channel_type == "instagram":
                channel_identifier, profile, posts = _collect_project_instagram_data(channel_url)
                subscribers = int(profile.get("followers_count") or 0)
                stats = _summarize_posts(posts, audience_size=subscribers or None)
                schedule = _build_schedule(posts)
                insights = _extract_ai_topics(posts)
                audience_profile = _extract_audience_profile(posts)
                author_influence_analysis = _extract_author_influence_analysis(posts)
                channel_title = profile.get("full_name") or profile.get("username") or channel_identifier
                summary = {
                    "channel_name": channel_title,
                    "channel_username": profile.get("username") or channel_identifier,
                    "profile_url": f"https://www.instagram.com/{profile.get('username') or channel_identifier}/",
                    "bio": profile.get("biography") or "",
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
                    "author_influence_analysis": author_influence_analysis,
                }
            elif channel_type == "youtube":
                channel_identifier, profile, posts = _collect_project_youtube_data(client, channel_url)
                subscribers = int(profile.get("subscriber_count") or 0)
                stats = _summarize_posts(posts, audience_size=subscribers or None)
                schedule = _build_schedule(posts)
                insights = _extract_ai_topics(posts)
                audience_profile = _extract_audience_profile(posts)
                author_influence_analysis = _extract_author_influence_analysis(posts)
                channel_title = profile.get("title") or channel_identifier
                channel_username = profile.get("custom_url") or ""
                profile_url = ""
                if channel_username:
                    profile_url = f"https://www.youtube.com/{channel_username.lstrip('/')}"
                elif profile.get("channel_id"):
                    profile_url = f"https://www.youtube.com/channel/{profile.get('channel_id')}"
                summary = {
                    "channel_name": channel_title,
                    "channel_username": channel_username,
                    "profile_url": profile_url,
                    "bio": profile.get("description") or "",
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
                    "author_influence_analysis": author_influence_analysis,
                }
            else:
                raise ValueError("Анализ для этого типа канала пока не поддерживается")

            ProjectChannelPostStat.objects.filter(
                run=run,
                channel_type=channel_type,
                channel_identifier=channel_identifier,
            ).delete()

            previous_run_id, previous_stats, previous_totals = _get_previous_project_stats(
                client,
                channel_type,
                channel_identifier,
                run.id,
            )

            post_rows: List[ProjectChannelPostStat] = []
            post_outputs: List[Dict] = []
            total_views = 0
            total_reactions = 0
            total_comments = 0

            for post in posts:
                external_id = str(post.get("id") or "").strip()
                if not external_id:
                    continue
                views = int(post.get("views") or 0)
                reactions = int(post.get("reactions") or 0)
                comments = int(post.get("comments") or 0)
                total_views += views
                total_reactions += reactions
                total_comments += comments

                published_at = _coerce_datetime(post.get("date"))
                post_rows.append(
                    ProjectChannelPostStat(
                        run=run,
                        client=client,
                        channel_type=channel_type,
                        channel_identifier=channel_identifier,
                        external_id=external_id,
                        title=_extract_post_title(post),
                        url=str(post.get("url") or ""),
                        published_at=published_at,
                        views=views,
                        reactions=reactions,
                        comments=comments,
                    )
                )

                prev_stat = previous_stats.get(external_id)
                delta_views = views - prev_stat.views if prev_stat else views
                delta_reactions = reactions - prev_stat.reactions if prev_stat else reactions
                delta_comments = comments - prev_stat.comments if prev_stat else comments

                post_outputs.append(
                    {
                        "external_id": external_id,
                        "title": _extract_post_title(post),
                        "url": str(post.get("url") or ""),
                        "published_at": _format_datetime(published_at),
                        "views": views,
                        "reactions": reactions,
                        "comments": comments,
                        "delta_views": delta_views,
                        "delta_reactions": delta_reactions,
                        "delta_comments": delta_comments,
                        "is_new": prev_stat is None,
                    }
                )

            if post_rows:
                ProjectChannelPostStat.objects.bulk_create(post_rows)

            totals = {
                "posts_count": len(post_outputs),
                "views": total_views,
                "reactions": total_reactions,
                "comments": total_comments,
            }
            delta_totals = {
                "posts_count": totals["posts_count"] - previous_totals["posts_count"],
                "views": totals["views"] - previous_totals["views"],
                "reactions": totals["reactions"] - previous_totals["reactions"],
                "comments": totals["comments"] - previous_totals["comments"],
            }

            results.append(
                {
                    "channel_type": channel_type,
                    "channel_url": channel_url,
                    "channel_identifier": channel_identifier,
                    "summary": summary,
                    "totals": totals,
                    "delta": delta_totals,
                    "previous_run_id": previous_run_id,
                    "posts": post_outputs,
                }
            )

            _update_project_run(run, progress=min(90, 5 + progress_step * index))

        _update_project_run(
            run,
            status=ProjectChannelAnalysisRun.STATUS_COMPLETED,
            progress=100,
            result={"channels": results, "generated_at": timezone.now().isoformat()},
            error="",
        )
        return run.result

    except Exception as exc:
        logger.error("Ошибка анализа каналов проекта %s: %s", run.id, exc, exc_info=True)
        _update_project_run(
            run,
            status=ProjectChannelAnalysisRun.STATUS_FAILED,
            progress=run.progress or 0,
            error=str(exc),
        )
        raise


@shared_task
def notify_project_channel_analysis_run(analysis_result, run_id: int):
    """Отправить уведомление в Telegram по результатам анализа каналов проекта."""
    try:
        run = ProjectChannelAnalysisRun.objects.select_related("client").get(id=run_id)
    except ProjectChannelAnalysisRun.DoesNotExist:
        logger.error("ProjectChannelAnalysisRun %s не найден для уведомления", run_id)
        return

    if run.status != ProjectChannelAnalysisRun.STATUS_COMPLETED:
        logger.warning("Project channel analysis %s not completed, skip notify", run_id)
        return

    result = run.result if isinstance(run.result, dict) else {}
    channels = result.get("channels") if isinstance(result.get("channels"), list) else []

    client = run.client
    chat_id = (client.telegram_client_channel or "").strip() or getattr(settings, "TELEGRAM_ALERT_USER_ID", "")
    if not chat_id:
        logger.warning("Telegram chat id is missing for client %s", client.id)
        return

    previous_run_ids = {channel.get("previous_run_id") for channel in channels if channel.get("previous_run_id")}
    previous_runs = ProjectChannelAnalysisRun.objects.filter(
        id__in=previous_run_ids,
        status=ProjectChannelAnalysisRun.STATUS_COMPLETED,
    )
    previous_subscribers: Dict[Tuple[int, str, str], int] = {}
    for previous_run in previous_runs:
        previous_result = previous_run.result if isinstance(previous_run.result, dict) else {}
        previous_channels = previous_result.get("channels") if isinstance(previous_result.get("channels"), list) else []
        for previous_channel in previous_channels:
            channel_type = previous_channel.get("channel_type") or ""
            channel_identifier = previous_channel.get("channel_identifier") or ""
            summary = previous_channel.get("summary") or {}
            subscribers = summary.get("subscribers")
            if subscribers is None:
                continue
            previous_subscribers[(previous_run.id, channel_type, channel_identifier)] = int(subscribers)

    message = _build_project_channel_message(client, run, channels, previous_subscribers)
    _send_telegram_message(chat_id, message)


@shared_task
def schedule_project_channel_analysis_daily():
    """Запустить ежедневный анализ каналов проекта для всех клиентов."""
    clients = Client.objects.filter(
        Q(project_telegram_channel__gt="") |
        Q(project_instagram_channel__gt="") |
        Q(project_youtube_channel__gt="")
    )

    created = 0
    for client in clients:
        limit_info = check_generation_limit(client, GenerationEvent.EVENT_CHANNEL_ANALYSIS)
        if limit_info:
            logger.info(
                "Skip project channel analysis for client %s: limit reached (%s/%s)",
                client.id,
                limit_info["used"],
                limit_info["limit"],
            )
            continue

        has_running = ProjectChannelAnalysisRun.objects.filter(
            client=client,
            status__in=[ProjectChannelAnalysisRun.STATUS_PENDING, ProjectChannelAnalysisRun.STATUS_IN_PROGRESS],
        ).exists()
        if has_running:
            continue

        run = ProjectChannelAnalysisRun.objects.create(
            client=client,
            status=ProjectChannelAnalysisRun.STATUS_PENDING,
        )
        async_result = analyze_project_channels_task.apply_async(
            args=[run.id],
            link=notify_project_channel_analysis_run.s(run.id),
        )
        run.task_id = async_result.id
        run.save(update_fields=["task_id", "updated_at"])
        record_generation_event(client, GenerationEvent.EVENT_CHANNEL_ANALYSIS, meta={"source": "schedule"})
        created += 1

    return created
