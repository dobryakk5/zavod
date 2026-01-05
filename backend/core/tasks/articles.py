from __future__ import annotations

import json
import logging

from celery import shared_task
from django.db import transaction

from core.ai_generator import AIContentGenerator
from core.models import Article, ArticleBlock, WordstatResult
from core.services.article_blocks import get_system_block_prompt_template, sync_blocks_from_seo_blocks

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    if value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _parse_ai_json_object(raw_response: str):
    if not raw_response:
        return None
    candidates: list[str] = []
    cleaned = _strip_code_fences(raw_response)
    if cleaned:
        candidates.append(cleaned)
    if raw_response.strip() and raw_response.strip() not in candidates:
        candidates.append(raw_response.strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _format_context(article: Article) -> str:
    parts: list[str] = []
    if article.selected_why_now:
        parts.append("Почему ищет сейчас:")
        parts.extend([f"- {item}" for item in article.selected_why_now])
    if article.selected_solution:
        parts.append("К какому решению ведём:")
        parts.extend([f"- {item}" for item in article.selected_solution])
    return "\n".join(parts).strip()


def _format_product_context(article: Article) -> str:
    parts: list[str] = []
    if article.lead_product_name:
        parts.append(f"Lead: {article.lead_product_name}")
    if article.tripwire_product_name:
        parts.append(f"Tripwire: {article.tripwire_product_name}")
    return "\n".join(parts).strip()


def _build_prompt(article: Article, block: ArticleBlock) -> tuple[str, list[str]]:
    h2_title = (block.h2_title or block.subquery or "").strip()
    subquery = (block.subquery or "").strip()
    intent = (block.micro_intent or "").strip()
    key_points = (block.key_points or "").strip()

    keywords = [str(k).strip() for k in (block.keywords or []) if str(k).strip()][:2]
    if not keywords:
        keywords = [article.wordstat]
    wordstat2 = ", ".join(keywords)

    variables = {
        "main_query": article.wordstat,
        "audience": (article.client.avatar or article.audience or "").strip(),
        "context": _format_context(article),
        "h2_title": h2_title,
        "subquery": subquery,
        "intent": intent,
        "key_points": key_points,
        "product_context": _format_product_context(article),
        "wordstat2": wordstat2,
        "keywords": wordstat2,
    }

    base_template = get_system_block_prompt_template(block.block_key).strip()
    if not base_template:
        base_template = "Контекст статьи: {{context}}\n\nЗадача: Напиши блок по теме {{main_query}}."
    correction = (block.prompt_template or "").strip()
    if correction:
        template = f"{base_template}\n\nКорректировка (учти при написании):\n{correction}"
    else:
        template = base_template

    prompt_used = template
    for key, value in variables.items():
        prompt_used = prompt_used.replace(f"{{{{{key}}}}}", value)

    if block.block_key not in {"Закрывающее утверждение"}:
        prompt_used = (
            prompt_used
            + "\n\nSEO требования:\n"
            + f"- Используй 1–2 ключа: {', '.join(keywords)}\n"
            + "- Держи фокус: 1 подзапрос = 1 смысл, не смешивай интенты.\n"
        )

    return prompt_used, keywords


def _generate_block_content(article: Article, block: ArticleBlock) -> ArticleBlock:
    try:
        generator = AIContentGenerator()
    except Exception:
        block.status = "failed"
        block.save(update_fields=["status", "updated_at"])
        raise

    prompt_used, keywords = _build_prompt(article, block)
    block.prompt_used = prompt_used

    ai_text = generator.get_ai_response(prompt_used, max_tokens=850, temperature=0.35)
    if not ai_text:
        block.status = "failed"
        block.save(update_fields=["prompt_used", "status", "updated_at"])
        raise RuntimeError("Не удалось сгенерировать блок")

    block.content = ai_text.strip()
    block.status = "ready"
    block.regeneration_count = (block.regeneration_count or 0) + 1
    block.save(update_fields=["prompt_used", "content", "status", "regeneration_count", "updated_at"])
    return block


@shared_task
def generate_article_blueprint_task(article_id: int) -> dict:
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        logger.warning("Article %s not found for blueprint generation", article_id)
        return {"error": "article_not_found"}

    favorite_rows = (
        WordstatResult.objects.filter(query__client=article.client, result_type="favorite")
        .order_by("-count", "phrase")
        .values("phrase", "count")
    )
    favorites: list[dict[str, object]] = []
    seen_fav: set[str] = set()
    for row in favorite_rows:
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        key = phrase.lower()
        if key in seen_fav:
            continue
        seen_fav.add(key)
        favorites.append({"phrase": phrase, "count": int(row.get("count") or 0)})
        if len(favorites) >= 60:
            break

    block_titles = [
        "Вступление",
        "Блок «Почему проблема возникает»",
        "Блок «Типичные ошибки»",
        "Блок «Правильная логика / система»",
        "Блок «Пошаговая модель»",
        "Блок «Пример / кейс / сценарий»",
        "Блок «Что делать дальше»",
        "Мягкий переход к продукту:",
    ]

    allowed_keyword_map = {
        str(item["phrase"]).strip().lower(): str(item["phrase"]).strip()
        for item in favorites
        if item.get("phrase")
    }

    def _normalize_keywords(raw_value):
        keywords: list[str] = []
        if isinstance(raw_value, list):
            for item in raw_value:
                candidate = str(item).strip()
                if not candidate:
                    continue
                canonical = allowed_keyword_map.get(candidate.lower())
                if canonical and canonical not in keywords:
                    keywords.append(canonical)
                if len(keywords) >= 2:
                    break
        if not keywords:
            first_phrase = str(favorites[0].get("phrase") or "").strip() if favorites else ""
            keywords = [first_phrase] if first_phrase else [article.wordstat]
        return keywords

    level3: dict[str, dict[str, object]] = {}
    try:
        generator = AIContentGenerator()
        prompt = f"""
Сделай УРОВЕНЬ 3 SEO-логики для структуры статьи по запросу: "{article.wordstat}".

Условия для КАЖДОГО блока:
- придумай 1 H2 заголовок (4–12 слов, без кавычек)
- придумай 1 подзапрос (конкретный пользовательский вопрос)
- выбери 1–2 ключа СТРОГО из Wordstat избранного ниже (используй поле phrase) → wordstat2
- сформулируй 1 интент (какую когнитивную задачу закрывает блок)
- выпиши 3–6 ключевых смыслов (key_points)

Wordstat избранное (ключи для выбора):
{json.dumps(favorites, ensure_ascii=False)}

Блоки (используй названия как есть):
{json.dumps(block_titles, ensure_ascii=False)}

Верни строго JSON:
{{
  "blocks": [
    {{
      "block": "<одно из названий блока выше>",
      "h2_title": "<H2 заголовок>",
      "subquery": "<подзапрос>",
      "wordstat2": ["<ключ1>", "<ключ2>"],
      "intent": "<интент>",
      "key_points": ["<смысл 1>", "<смысл 2>", "<смысл 3>"]
    }}
  ]
}}

НЕ пиши контент статьи, только эти поля.
"""
        ai_raw = generator.get_ai_response(
            prompt,
            max_tokens=1200,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        parsed = _parse_ai_json_object(ai_raw or "")
        blocks = parsed.get("blocks") if isinstance(parsed, dict) else None
        if isinstance(blocks, list):
            for item in blocks:
                if not isinstance(item, dict):
                    continue
                block = str(item.get("block") or "").strip()
                if block not in block_titles:
                    continue
                h2_title = str(item.get("h2_title") or item.get("subquery_h2") or "").strip()
                subquery = str(item.get("subquery") or "").strip()
                if not h2_title and subquery:
                    h2_title = subquery
                micro_intent = str(item.get("intent") or item.get("micro_intent") or "").strip()
                raw_wordstat2 = item.get("wordstat2") or item.get("keywords")
                keywords = _normalize_keywords(raw_wordstat2)
                raw_key_points = item.get("key_points")
                key_points = []
                if isinstance(raw_key_points, list):
                    key_points = [str(point).strip() for point in raw_key_points if str(point).strip()][:6]
                elif isinstance(raw_key_points, str) and raw_key_points.strip():
                    key_points = [raw_key_points.strip()]
                level3[block] = {
                    "h2_title": h2_title,
                    "subquery": subquery,
                    "keywords": keywords,
                    "micro_intent": micro_intent,
                    "key_points": key_points,
                }
    except Exception:
        logger.exception("Failed to generate level3 SEO structure for article %s", article.id)

    with transaction.atomic():
        article.seo_blocks = level3
        if article.status == "draft":
            article.status = "options_ready"
        article.save(update_fields=["seo_blocks", "status", "updated_at"])
        sync_blocks_from_seo_blocks(article)

    return {"article_id": article.id}


@shared_task
def generate_article_block_task(article_id: int, block_id: int) -> dict:
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        logger.warning("Article %s not found for block generation", article_id)
        return {"error": "article_not_found"}

    try:
        block = ArticleBlock.objects.get(id=block_id, article=article)
    except ArticleBlock.DoesNotExist:
        logger.warning("Article block %s not found for article %s", block_id, article_id)
        return {"error": "block_not_found"}

    try:
        _generate_block_content(article, block)
    except Exception as exc:
        logger.exception("Failed to generate block %s for article %s: %s", block_id, article_id, exc)
        return {"error": "generation_failed", "block_id": block_id}

    return {"article_id": article.id, "block_id": block.id}


@shared_task
def generate_article_blocks_task(article_id: int) -> dict:
    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        logger.warning("Article %s not found for blocks generation", article_id)
        return {"error": "article_not_found"}

    blocks = ArticleBlock.objects.filter(article=article).order_by("order", "id")
    generated: list[int] = []
    for block in blocks:
        if block.content and block.content.strip():
            continue
        try:
            _generate_block_content(article, block)
            generated.append(block.id)
        except Exception as exc:
            logger.exception("Failed to generate block %s in phase 2: %s", block.id, exc)

    return {"article_id": article.id, "generated_blocks": generated}
