"""
Celery задачи для еженедельных отчётов по источникам контента.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ..aggregator import fetch_rss_feeds
from ..instagram_client import fetch_instagram_profile, normalize_instagram_username
from ..models import Client, WeeklySourceReport, WeeklySourceBatch
from ..telegram_client import (
    TelegramContentCollector,
    normalize_telegram_channel_identifier,
    run_async_task,
)
from ..youtube_client import fetch_youtube_channel, normalize_youtube_identifier
from .channel_analysis import (
    _prepare_posts_text,
    _get_telegram_credentials,
    _get_youtube_api_key,
    _request_ai_json,
)

logger = logging.getLogger(__name__)


def _new_ai_generator():
    from ..ai_generator import AIContentGenerator

    return AIContentGenerator()


def _filter_last_week(items: List[Dict]) -> List[Dict]:
    """Оставить только записи за последние 7 дней."""
    cutoff = timezone.now() - timedelta(days=7)
    filtered: List[Dict] = []
    for item in items:
        dt = item.get("date")
        if not dt:
            continue
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)
        if dt >= cutoff:
            filtered.append(item)
    return filtered


def _collect_telegram(client: Client, identifier: str) -> Tuple[List[Dict], List[Dict]]:
    api_id, api_hash, session_name = _get_telegram_credentials(client)
    if not api_id or not api_hash:
        raise RuntimeError("Не настроены Telegram API ID/API Hash для анализа каналов")

    collector = TelegramContentCollector(api_id=api_id, api_hash=api_hash, session_name=session_name)

    async def fetch():
        await collector.connect()
        try:
            messages = await collector.get_channel_messages(identifier, limit=60)
            info = await collector.get_channel_info(identifier)
            return info, messages
        finally:
            await collector.disconnect()

    info, messages = run_async_task(fetch())
    posts = _filter_last_week(messages)
    return posts, []


def _collect_instagram(identifier: str) -> Tuple[List[Dict], List[Dict]]:
    profile, posts = fetch_instagram_profile(identifier, limit=60)
    posts_week = _filter_last_week(posts)
    return posts_week, []


def _collect_youtube(client: Client, identifier: str) -> Tuple[List[Dict], List[Dict]]:
    api_key = _get_youtube_api_key(client)
    if not api_key:
        raise RuntimeError("Не настроен YouTube API ключ")

    profile, videos = fetch_youtube_channel(api_key, identifier, max_videos=60)
    videos_week = _filter_last_week(videos)
    return videos_week, []


def _collect_rss(feed_url: str) -> Tuple[List[Dict], List[Dict]]:
    # aggregator already tries to parse published date; ensure to convert to aware datetimes
    items = fetch_rss_feeds([feed_url], keywords=None, limit=80)
    posts: List[Dict] = []
    for item in items:
        date_iso = ((item.get("extra") or {}).get("published_date")) or ((item.get("extra") or {}).get("published"))
        dt = None
        if date_iso:
            try:
                dt = datetime.fromisoformat(str(date_iso).replace("Z", "+00:00"))
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
            except Exception:
                dt = None
        posts.append(
            {
                "id": item.get("url"),
                "title": item.get("title"),
                "text": item.get("description"),
                "url": item.get("url"),
                "date": dt,
            }
        )
    posts_week = _filter_last_week(posts)
    return posts_week, []


def _summarize_posts(source_type: str, source_value: str, posts: List[Dict]) -> str:
    if not posts:
        return "За последнюю неделю контент не найден."

    texts: List[str] = []
    for post in posts[:20]:
        title = post.get("title") or ""
        text = post.get("text") or ""
        combined = title or text
        if not combined:
            combined = text
        snippet = (combined or "")[:240]
        texts.append(f"- {snippet}".strip())

    prompt = f"""Ты аналитик контента. Вот посты из источника ({source_type}) {source_value} за последние 7 дней.
Сделай 1-2 предложения: кто и что делал, и зачем/почему. Без воды, только краткая выжимка.

Посты:
{chr(10).join(texts)}

Короткий вывод:"""

    generator = _new_ai_generator()
    response = generator.get_ai_response(prompt, max_tokens=220, temperature=0.4)
    return response.strip() if response else "Не удалось получить краткий вывод."


def _summarize_post_ideas(posts: List[Dict], audience_avatar: str | None) -> Dict[int, Dict[str, str]]:
    """Сгенерировать краткую мысль и применение для каждого поста (первые 15 шт.)."""
    if not posts:
        return {}

    limited = posts[:15]
    lines = []
    for idx, post in enumerate(limited, start=1):
        title = post.get("title") or ""
        text = post.get("text") or ""
        snippet = (title or text or "")[:500]
        date_iso = post.get("date").isoformat() if post.get("date") else ""
        lines.append(f"{idx}) {date_iso}\n{snippet}")

    avatar_text = (audience_avatar or "").strip()
    prompt = f"""Даны посты. Опиши по каждому:
1) idea — основная мысль поста (1 предложение)
2) action — как использовать этот пост, чтобы привлечь мою аудиторию. Аудитория: "{avatar_text or 'описание отсутствует'}".

Верни JSON:
{{
  "ideas": [
    {{"index": 1, "idea": "...", "action": "..." }},
    ...
  ]
}}

Посты:
{chr(10).join(lines)}
"""
    generator = _new_ai_generator()
    data = _request_ai_json(
        prompt,
        max_tokens=600,
        temperature=0.4,
        generator=generator,
        context="краткие идеи по постам",
        analysis=None,
    )
    if not isinstance(data, dict):
        return {}
    ideas_list = data.get("ideas") or []
    mapping: Dict[int, Dict[str, str]] = {}
    for item in ideas_list:
        try:
            idx = int(item.get("index"))
        except Exception:
            continue
        idea_text = str(item.get("idea") or "").strip()
        action_text = str(item.get("action") or "").strip()
        if idx > 0 and (idea_text or action_text):
            mapping[idx - 1] = {"idea": idea_text, "action": action_text}
    return mapping


def _prepare_sources(client: Client) -> List[Tuple[str, str]]:
    sources: List[Tuple[str, str]] = []
    sources.extend([("telegram", ch) for ch in client.get_telegram_source_channels_list()])
    sources.extend([("instagram", acc) for acc in client.get_instagram_source_accounts_list()])
    sources.extend([("youtube", ch) for ch in client.get_youtube_source_channels_list()])
    sources.extend([("rss", url) for url in client.get_rss_source_feeds_list()])
    return [(stype, val) for stype, val in sources if val]


@shared_task
def run_weekly_sources_for_client(client_id: int, batch_id: int | None = None) -> Dict:
    """Создать отчёты по всем доступным источникам клиента и запустить сбор."""
    client = Client.objects.get(pk=client_id)
    week_start = timezone.now().date() - timedelta(days=timezone.now().weekday())
    sources = _prepare_sources(client)

    if batch_id:
        batch = WeeklySourceBatch.objects.get(pk=batch_id)
        batch.week_start = week_start
        batch.status = WeeklySourceReport.STATUS_PENDING
        batch.save(update_fields=["week_start", "status", "updated_at"])
    else:
        batch = WeeklySourceBatch.objects.create(
            client=client,
            week_start=week_start,
            status=WeeklySourceReport.STATUS_PENDING,
        )

    scheduled = 0
    batch.status = WeeklySourceReport.STATUS_IN_PROGRESS
    batch.save(update_fields=["status", "updated_at"])

    for source_type, raw_value in sources:
        value = raw_value
        if source_type == "telegram":
            value = normalize_telegram_channel_identifier(raw_value)
        elif source_type == "instagram":
            value = normalize_instagram_username(raw_value)
        elif source_type == "youtube":
            value = normalize_youtube_identifier(raw_value)

        if not value:
            continue

        report = WeeklySourceReport.objects.create(
            client=client,
            batch=batch,
            source_type=source_type,
            source_value=value,
            week_start=week_start,
            status=WeeklySourceReport.STATUS_PENDING,
        )
        process_weekly_source.delay(report.id)
        scheduled += 1

    if scheduled == 0:
        batch.status = WeeklySourceReport.STATUS_FAILED
        batch.save(update_fields=["status", "updated_at"])

    return {"scheduled": scheduled, "week_start": str(week_start), "batch_id": batch.id}


@shared_task
def process_weekly_source(report_id: int) -> None:
    """Собрать посты за неделю, отправить в AI и сохранить отчёт."""
    try:
        report = WeeklySourceReport.objects.select_related("client").get(id=report_id)
    except WeeklySourceReport.DoesNotExist:
        logger.error("WeeklySourceReport %s не найден", report_id)
        return

    if report.status in {WeeklySourceReport.STATUS_COMPLETED, WeeklySourceReport.STATUS_IN_PROGRESS}:
        return

    report.status = WeeklySourceReport.STATUS_IN_PROGRESS
    report.error = ""
    report.save(update_fields=["status", "error", "updated_at"])

    try:
        source_type = report.source_type
        source_value = report.source_value
        if source_type == "telegram":
            posts, _links = _collect_telegram(report.client, source_value)
        elif source_type == "instagram":
            posts, _links = _collect_instagram(source_value)
        elif source_type == "youtube":
            posts, _links = _collect_youtube(report.client, source_value)
        elif source_type == "rss":
            posts, _links = _collect_rss(source_value)
        else:
            raise ValueError(f"Источник {source_type} пока не поддерживается")

        ideas = _summarize_post_ideas(posts, report.client.avatar)
        links = []
        for idx, post in enumerate(posts):
            text_value = (post.get("text") or post.get("title") or "") or ""
            idea_payload = ideas.get(idx, {})
            links.append(
                {
                    "title": post.get("title") or post.get("text", "")[:120] or "Пост",
                    "url": post.get("url", ""),
                    "date": post.get("date").isoformat() if post.get("date") else None,
                    "text_length": len(text_value),
                    "duration_seconds": post.get("duration_seconds") or 0,
                    "idea": idea_payload.get("idea", ""),
                    "action": idea_payload.get("action", ""),
                }
            )

        summary = _summarize_posts(source_type, source_value, posts)

        report.summary = summary
        report.links = links
        report.status = WeeklySourceReport.STATUS_COMPLETED
        report.save(update_fields=["summary", "links", "status", "updated_at"])
        _maybe_update_batch(report)
    except Exception as exc:
        logger.error("Ошибка при обработке WeeklySourceReport %s: %s", report_id, exc, exc_info=True)
        report.status = WeeklySourceReport.STATUS_FAILED
        report.error = str(exc)
        report.save(update_fields=["status", "error", "updated_at"])
        _maybe_update_batch(report, failed=True)


def _maybe_update_batch(report: WeeklySourceReport, failed: bool = False) -> None:
    """Обновить статус подборки, если все отчёты завершены или есть ошибка."""
    batch = report.batch
    if not batch:
        return
    reports_qs = batch.reports.all()
    statuses = {r.status for r in reports_qs}
    if WeeklySourceReport.STATUS_IN_PROGRESS in statuses or WeeklySourceReport.STATUS_PENDING in statuses:
        # Есть ещё работающие — не завершаем
        return
    if failed or WeeklySourceReport.STATUS_FAILED in statuses:
        batch.status = WeeklySourceReport.STATUS_FAILED
    else:
        batch.status = WeeklySourceReport.STATUS_COMPLETED
    batch.save(update_fields=["status", "updated_at"])
