from __future__ import annotations

from typing import Any

from django.utils import timezone

from .models import Client, GenerationEvent

DEFAULT_TRIAL_LIMIT = 3
WORDSTAT_TRIAL_LIMIT = 20

EVENT_LABELS: dict[str, str] = {
    GenerationEvent.EVENT_POST: "Пост",
    GenerationEvent.EVENT_ARTICLE_WRITE: "Статья: написать",
    GenerationEvent.EVENT_ARTICLE_EVALUATE: "Статья: оценить",
    GenerationEvent.EVENT_CHANNEL_ANALYSIS: "Аналитика канала",
    GenerationEvent.EVENT_WEBSITE_ANALYSIS: "Аналитика сайта",
    GenerationEvent.EVENT_WEEKLY_COLLECTION: "Подборка",
    GenerationEvent.EVENT_SEO_GROUP: "SEO группы",
    GenerationEvent.EVENT_WORDSTAT_QUERY: "Wordstat",
    GenerationEvent.EVENT_GOOGLE_QUERY: "Google запросы",
    GenerationEvent.EVENT_PRODUCT: "Продукт",
    GenerationEvent.EVENT_PRODUCT_MAP: "Карта продуктов",
    GenerationEvent.EVENT_BOOK_SEARCH: "Книги",
    GenerationEvent.EVENT_BOOK_SEMANTICS: "Семантика по книгам",
}

EVENT_TYPE_LIST = list(EVENT_LABELS.keys())


def is_trial_client(client: Client) -> bool:
    now = timezone.now()
    plan = getattr(client, "plan", None)
    if plan and getattr(plan, "code", "") == "trial":
        return True
    if not client.plan_id:
        return True
    if not client.plan_expires_at or client.plan_expires_at <= now:
        return True
    return False


def get_trial_limit(event_type: str) -> int:
    if event_type == GenerationEvent.EVENT_WORDSTAT_QUERY:
        return WORDSTAT_TRIAL_LIMIT
    return DEFAULT_TRIAL_LIMIT


def check_generation_limit(client: Client, event_type: str) -> dict[str, int] | None:
    if not is_trial_client(client):
        return None
    limit = get_trial_limit(event_type)
    used = GenerationEvent.objects.filter(client=client, event_type=event_type).count()
    if used >= limit:
        return {"used": used, "limit": limit}
    return None


def build_limit_error_payload(event_type: str, used: int, limit: int) -> dict[str, Any]:
    label = EVENT_LABELS.get(event_type, event_type)
    return {
        "error": f"Лимит ознакомительного тарифа для «{label}» исчерпан ({used}/{limit}).",
        "event_type": event_type,
        "used": used,
        "limit": limit,
    }


def record_generation_event(client: Client, event_type: str, meta: dict[str, Any] | None = None) -> GenerationEvent:
    return GenerationEvent.objects.create(
        client=client,
        event_type=event_type,
        meta=meta or {},
    )
