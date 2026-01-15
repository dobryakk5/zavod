from __future__ import annotations

from core.article_prompt_templates import ARTICLE_BLOCK_PROMPTS
from core.models import Article, ArticleBlock, ArticleBlockPromptTemplate

ARTICLE_BLOCK_TITLES = [
    "Вступление",
    "Блок «Почему проблема возникает»",
    "Блок «Типичные ошибки»",
    "Блок «Правильная логика / система»",
    "Блок «Пошаговая модель»",
    "Блок «Пример / кейс / сценарий»",
    "Блок «Что делать дальше»",
    "Мягкий переход к продукту:",
    "Закрывающее утверждение",
]


def get_system_block_prompt_template(block_key: str) -> str:
    row = ArticleBlockPromptTemplate.objects.filter(block_key=block_key).only("prompt_template").first()
    if row and (row.prompt_template or "").strip():
        return row.prompt_template
    return ARTICLE_BLOCK_PROMPTS.get(block_key, "")


def _normalize_key_points(raw_value: object) -> str:
    if isinstance(raw_value, list):
        items = [str(item).strip() for item in raw_value if str(item).strip()]
        return "\n".join(items)[:1500]
    if isinstance(raw_value, str):
        return raw_value.strip()[:1500]
    return ""


def sync_blocks_from_seo_blocks(article: Article) -> None:
    level3 = article.seo_blocks if isinstance(article.seo_blocks, dict) else {}

    for order, block_key in enumerate(ARTICLE_BLOCK_TITLES, start=1):
        entry = level3.get(block_key) if isinstance(level3, dict) else None
        if not isinstance(entry, dict):
            entry = {}
        h2_title = str(entry.get("h2_title") or entry.get("subquery_h2") or "")[:300]
        subquery = str(entry.get("subquery") or "")[:300]
        if not h2_title and subquery:
            h2_title = subquery[:300]
        micro_intent = str(entry.get("intent") or entry.get("micro_intent") or "")[:300]
        key_points = _normalize_key_points(entry.get("key_points"))
        keywords = entry.get("keywords") if isinstance(entry.get("keywords"), list) else []
        keywords_norm = [str(item).strip() for item in keywords if str(item).strip()]

        block, created = ArticleBlock.objects.get_or_create(
            article=article,
            block_key=block_key,
            defaults={
                "order": order,
                "h2_title": h2_title,
                "subquery": subquery,
                "micro_intent": micro_intent,
                "keywords": keywords_norm,
                "key_points": key_points,
                "prompt_template": "",
                "status": "blueprint_ready"
                if h2_title or subquery or micro_intent or key_points or keywords_norm
                else "draft",
            },
        )
        if created:
            continue

        changed = False
        if block.order != order:
            block.order = order
            changed = True
        if block.h2_title != h2_title:
            block.h2_title = h2_title
            changed = True
        if block.subquery != subquery:
            block.subquery = subquery
            changed = True
        if block.micro_intent != micro_intent:
            block.micro_intent = micro_intent
            changed = True
        if (block.keywords or []) != keywords_norm:
            block.keywords = keywords_norm
            changed = True
        if block.key_points != key_points:
            block.key_points = key_points
            changed = True

        if not block.content.strip() and block.status != "failed":
            desired_status = (
                "blueprint_ready" if h2_title or subquery or micro_intent or key_points or keywords_norm else "draft"
            )
            if block.status != desired_status:
                block.status = desired_status
                changed = True

        if changed:
            block.save(
                update_fields=[
                    "order",
                    "h2_title",
                    "subquery",
                    "micro_intent",
                    "keywords",
                    "key_points",
                    "status",
                    "updated_at",
                ]
            )
