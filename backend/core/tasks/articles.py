from __future__ import annotations

import json
import logging
import re
from string import Template

from celery import shared_task
from django.db import transaction

from core.article_prompt_codes import (
    ARTICLE_BLOCK_PROMPT_CODES,
    ARTICLE_BLUEPRINT_DETAILS_CODE,
    ARTICLE_BLUEPRINT_OUTLINE_CODE,
)
from core.models import Article, ArticleBlock, WordstatResult
from core.prompt_settings import render_generator_prompt
from core.services.article_blocks import ARTICLE_BLOCK_TITLES, get_system_block_prompt_template, sync_blocks_from_seo_blocks

logger = logging.getLogger(__name__)


def _new_ai_generator():
    from core.ai_generator import AIContentGenerator

    return AIContentGenerator()


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    if value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _escape_newlines_in_strings(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                continue
            if ch == '"':
                result.append(ch)
                in_string = False
                continue
            if ch == "\n":
                result.append("\\n")
                continue
            if ch == "\r":
                result.append("\\r")
                continue
            result.append(ch)
        else:
            result.append(ch)
            if ch == '"':
                in_string = True
                escaped = False
    return "".join(result)


_FINAL_ANSWER_PATTERNS = [
    r"<answer>\s*",
    r"Ответ:\s*",
    r"Итак,\s*",
    r"Финальный ответ:\s*",
    r"```json\s*",
    r"^\s*\{",
]


def _extract_final_answer(text: str) -> str:
    if not text:
        return ""
    if "<answer>" in text.lower():
        match = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL | re.IGNORECASE)
        if match:
            return (match.group(1) or "").strip()
        start = re.search(r"<answer>\s*", text, re.DOTALL | re.IGNORECASE)
        if start:
            return text[start.end() :].strip()
    for pattern in _FINAL_ANSWER_PATTERNS:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            return text[match.start() :].strip()
    return ""


def _normalize_inline_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _parse_ai_json_object(raw_response: str):
    if not raw_response:
        return None
    from core.ai_generator_content import _parse_ai_json_response

    parsed, _, _ = _parse_ai_json_response(raw_response)
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


def _format_why_now_options(article: Article) -> list[str]:
    items = article.options_why_now if isinstance(article.options_why_now, list) else []
    return [str(item).strip() for item in items if str(item).strip()]


def _format_selected_solution(article: Article) -> list[str]:
    items = article.selected_solution if isinstance(article.selected_solution, list) else []
    return [str(item).strip() for item in items if str(item).strip()]


def _format_product_context(article: Article) -> str:
    parts: list[str] = []
    if article.lead_product_name:
        parts.append(f"Lead: {article.lead_product_name}")
    if article.tripwire_product_name:
        parts.append(f"Tripwire: {article.tripwire_product_name}")
    return "\n".join(parts).strip()


def _render_inline_template(template: str, variables: dict[str, str]) -> str:
    if not template:
        return ""
    normalized = template.replace("{{", "${").replace("}}", "}")
    try:
        return Template(normalized).safe_substitute(**variables)
    except ValueError:
        return template


def _build_prompt(article: Article, block: ArticleBlock) -> tuple[str, list[str]]:
    h2_title = (block.h2_title or block.subquery or "").strip()
    subquery = (block.subquery or "").strip()
    intent = (block.micro_intent or "").strip()
    key_points = (block.key_points or "").strip()

    keywords = [str(k).strip() for k in (block.keywords or []) if str(k).strip()]
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

    prompt_code = ARTICLE_BLOCK_PROMPT_CODES.get(block.block_key)
    base_prompt = ""
    if prompt_code:
        base_prompt = render_generator_prompt(prompt_code, **variables)

    if not base_prompt:
        fallback_template = get_system_block_prompt_template(block.block_key).strip()
        if fallback_template:
            base_prompt = _render_inline_template(fallback_template, variables)

    if not base_prompt:
        base_prompt = _render_inline_template(
            "Контекст статьи: ${context}\n\nЗадача: Напиши блок по теме ${main_query}.",
            variables,
        )

    correction = (block.prompt_template or "").strip()
    if correction:
        correction_text = _render_inline_template(correction, variables)
        template = f"{base_prompt}\n\nКорректировка (учти при написании):\n{correction_text}"
    else:
        template = base_prompt

    prompt_used = template

    if block.block_key not in {"Закрывающее утверждение"}:
        prompt_used = (
            prompt_used
            + "\n\nSEO требования:\n"
            + f"- Используй ключевые фразы из списка (старайся включить все): {', '.join(keywords)}\n"
            + "- Держи фокус: 1 подзапрос = 1 смысл, не смешивай интенты.\n"
        )

    return prompt_used, keywords


def _generate_block_content(article: Article, block: ArticleBlock) -> ArticleBlock:
    ai_raw = ""
    ai_raw = ""
    try:
        generator = _new_ai_generator()
    except Exception:
        block.status = "failed"
        block.save(update_fields=["status", "updated_at"])
        raise

    prompt_used, keywords = _build_prompt(article, block)

    post_model = (generator.post_model or generator.model).strip() or None
    model_name = (post_model or generator.model or "").strip().lower()
    is_deepseek = "deepseek" in model_name
    json_instruction = ""
    response_format = None
    plugins = None
    if is_deepseek:
        json_instruction = """

Верни ответ строго JSON внутри тегов <answer>...</answer>:
<answer>
{
  "content": "<текст блока>"
}
</answer>

Никаких пояснений, только JSON.
""".strip()
        response_format = {"type": "json_object"}
        plugins = [{"id": "response-healing"}]

    prompt_used_final = f"{prompt_used}\n\n{json_instruction}" if json_instruction else prompt_used
    block.prompt_used = prompt_used_final

    ai_text = generator.get_ai_response(
        prompt_used_final,
        max_tokens=850,
        temperature=0.35,
        model=post_model,
        stream=is_deepseek,
        timeout_seconds=300.0 if is_deepseek else 60.0,
        response_format=response_format,
        plugins=plugins,
        retry_without_format=False if is_deepseek else True,
    )
    if is_deepseek and ai_text:
        candidate = _extract_final_answer(ai_text)
        parsed = _parse_ai_json_object(candidate or "")
        if isinstance(parsed, dict):
            content_value = parsed.get("content") or parsed.get("text") or parsed.get("result")
            if isinstance(content_value, str) and content_value.strip():
                ai_text = content_value
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

    logger.info("Blueprint favorites count=%s for article %s", len(favorites), article.id)

    block_titles = list(ARTICLE_BLOCK_TITLES)
    block_labels = [
        "вступление",
        "почему проблема",
        "типичные ошибки",
        "правильная логика",
        "пошаговая модель",
        "пример/кейс",
        "что делать дальше",
        "мягкий переход к продукту",
        "закрывающее утверждение",
    ]
    if len(block_labels) != len(block_titles):
        block_labels = [title for title in block_titles]

    block_id_map = {idx + 1: title for idx, title in enumerate(block_titles)}

    allowed_keyword_map = {
        str(item["phrase"]).strip().lower(): str(item["phrase"]).strip()
        for item in favorites
        if item.get("phrase")
    }

    def _normalize_phrase_list(items) -> list[str]:
        phrases: list[str] = []
        seen: set[str] = set()
        if not isinstance(items, list):
            items = [items]
        for item in items:
            candidate = str(item or "").strip()
            if not candidate:
                continue
            canonical = allowed_keyword_map.get(candidate.lower(), candidate)
            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            phrases.append(canonical)
        return phrases

    stopwords = {
        "и",
        "в",
        "на",
        "что",
        "как",
        "это",
        "для",
        "по",
        "не",
        "с",
        "к",
        "или",
        "а",
        "от",
        "до",
        "о",
        "об",
        "при",
        "когда",
        "где",
        "зачем",
        "какой",
        "какие",
        "какая",
        "какие",
        "его",
        "ее",
        "их",
        "уже",
        "ещё",
        "еще",
    }

    def _tokenize(value: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]+", (value or "").lower())
        return {token for token in tokens if len(token) > 2 and token not in stopwords}

    def _assign_cluster_phrases(
        phrases: list[str],
        outline_map: dict[str, dict[str, str]],
        block_titles: list[str],
    ) -> dict[str, list[str]]:
        assignments = {title: [] for title in block_titles}
        if not phrases:
            return assignments

        light_blocks = {
            "Вступление",
            "Мягкий переход к продукту:",
            "Закрывающее утверждение",
        }
        block_profiles = []
        for title in block_titles:
            meta = outline_map.get(title, {})
            text = " ".join(
                [
                    title,
                    str(meta.get("h2_title") or ""),
                    str(meta.get("subquery") or ""),
                    str(meta.get("micro_intent") or ""),
                ]
            )
            block_profiles.append(
                {
                    "title": title,
                    "tokens": _tokenize(text),
                    "is_light": title in light_blocks,
                }
            )

        phrase_tokens = {phrase: _tokenize(phrase) for phrase in phrases}

        def _pair_score(block_profile, phrase: str) -> float:
            tokens = phrase_tokens.get(phrase, set())
            if not tokens:
                return 0.0
            base = len(tokens & block_profile["tokens"])
            if base <= 0:
                return 0.0
            return base * (0.7 if block_profile["is_light"] else 1.0)

        remaining = list(phrases)
        if len(phrases) >= len(block_titles):
            pairs = []
            for block_profile in block_profiles:
                for phrase in phrases:
                    pairs.append(
                        (
                            _pair_score(block_profile, phrase),
                            len(phrase),
                            block_profile["title"],
                            phrase,
                        )
                    )
            pairs.sort(reverse=True)
            assigned_blocks: set[str] = set()
            assigned_phrases: set[str] = set()
            for score, _length, block_title, phrase in pairs:
                if block_title in assigned_blocks or phrase in assigned_phrases:
                    continue
                assignments[block_title].append(phrase)
                assigned_blocks.add(block_title)
                assigned_phrases.add(phrase)
                if len(assigned_blocks) >= len(block_titles):
                    break
            remaining = [phrase for phrase in phrases if phrase not in assigned_phrases]

        heavy_blocks = [profile for profile in block_profiles if not profile["is_light"]]
        target_blocks = heavy_blocks if heavy_blocks else block_profiles

        for phrase in remaining:
            best_block = None
            best_score = None
            for block_profile in target_blocks:
                score = _pair_score(block_profile, phrase)
                block_title = block_profile["title"]
                candidate = (score, -len(assignments[block_title]))
                if best_score is None or candidate > best_score:
                    best_score = candidate
                    best_block = block_profile
            if not best_block:
                continue
            assignments[best_block["title"]].append(phrase)

        return assignments

    level3: dict[str, dict[str, object]] = {}
    last_raw = ""

    def _summarize_raw(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 2000:
            return value
        return f"{value[:1500]} ... {value[-400:]}"

    def _persist_partial_structure() -> None:
        try:
            article.seo_blocks = dict(level3)
            article.save(update_fields=["seo_blocks", "updated_at"])
            sync_blocks_from_seo_blocks(article)
        except Exception:
            logger.exception("Failed to persist blueprint progress for article %s", article.id)

    def _fail_blueprint(reason: str, *, raw: str | None = None) -> None:
        article.status = "failed"
        article.save(update_fields=["status", "updated_at"])
        if raw:
            logger.error(
                "Blueprint AI error (%s) for article %s. Raw response: %s",
                reason,
                article.id,
                _summarize_raw(raw),
            )
        raise RuntimeError("ошибка AI")

    def _log_json_error(candidate: str, *, attempt: str) -> None:
        if not candidate or not candidate.strip():
            return
        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            start = max(0, exc.pos - 120)
            end = min(len(candidate), exc.pos + 120)
            snippet = candidate[start:end]
            log = logger.error if "compact" in (attempt or "").lower() else logger.warning
            log(
                "Blueprint AI JSON decode error [%s] for article %s: %s (line %s, col %s). Snippet: %s",
                attempt,
                article.id,
                exc.msg,
                exc.lineno,
                exc.colno,
                snippet,
            )

    def _request_json(
        prompt: str,
        *,
        attempt: str,
        schema_hint: str,
        max_tokens: int = 800,
        temperature: float = 0.35,
        allow_reasoning_repair: bool = False,
    ) -> tuple[dict | None, str]:
        nonlocal last_raw
        ai_raw = generator.get_ai_response(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
            plugins=[{"id": "response-healing"}],
            allow_fallback=False,
            retry_without_format=False,
            stream=True,
            timeout_seconds=300.0,
        )
        last_raw = ai_raw or ""
        if not ai_raw or not ai_raw.strip():
            logger.warning(
                "Blueprint AI empty response [%s] for article %s (stream). Retrying without stream",
                attempt,
                article.id,
            )
            ai_raw = generator.get_ai_response(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                plugins=[{"id": "response-healing"}],
                allow_fallback=False,
                retry_without_format=False,
                stream=False,
                timeout_seconds=300.0,
            ) or ""
            if not ai_raw.strip():
                logger.error("Blueprint AI empty response [%s] for article %s", attempt, article.id)

        logger.info(
            "Blueprint AI response length=%s (%s) for article %s",
            len(ai_raw),
            attempt,
            article.id,
        )
        logger.debug("Blueprint AI raw response (%s) for article %s: %s", attempt, article.id, ai_raw[:2000])

        candidate = _extract_final_answer(ai_raw or "")
        parse_source = candidate if candidate else (ai_raw if allow_reasoning_repair else "")
        parsed = _parse_ai_json_object(parse_source or "")
        if not isinstance(parsed, dict):
            if parse_source and schema_hint:
                repaired = generator._repair_json_structure(parse_source, schema_hint=schema_hint)
                if isinstance(repaired, dict):
                    return repaired, ai_raw
            if parse_source:
                cleaned = _strip_code_fences(parse_source)
                _log_json_error(cleaned or parse_source, attempt=attempt)

            ai_raw_fallback = generator.get_ai_response(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                plugins=[{"id": "response-healing"}],
                allow_fallback=True,
                retry_without_format=False,
                stream=True,
                timeout_seconds=300.0,
            )
            if ai_raw_fallback and ai_raw_fallback.strip():
                last_raw = ai_raw_fallback
                logger.info(
                    "Blueprint AI response length=%s (%s:fallback) for article %s",
                    len(ai_raw_fallback),
                    attempt,
                    article.id,
                )
                logger.debug(
                    "Blueprint AI raw response (%s:fallback) for article %s: %s",
                    attempt,
                    article.id,
                    ai_raw_fallback[:2000],
                )
                fallback_candidate = _extract_final_answer(ai_raw_fallback or "")
                fallback_source = (
                    fallback_candidate
                    if fallback_candidate
                    else (ai_raw_fallback if allow_reasoning_repair else "")
                )
                parsed = _parse_ai_json_object(fallback_source or "")
                if not isinstance(parsed, dict) and fallback_source and schema_hint:
                    repaired = generator._repair_json_structure(fallback_source, schema_hint=schema_hint)
                    if isinstance(repaired, dict):
                        return repaired, ai_raw_fallback
            return None, ai_raw_fallback or ai_raw
        return parsed, ai_raw

    def _build_outline_prompt(compact: bool) -> str:
        extra_rules = ""
        if compact:
            extra_rules = "\nДоп.условия: тексты короткие (до 8 слов), без двоеточий и кавычек внутри строк."
        block_map = "\n".join(
            [f"{idx + 1} — {block_labels[idx]}" for idx in range(len(block_titles))]
        )
        why_now_options = _format_why_now_options(article)
        solution_selected = _format_selected_solution(article)
        context_lines: list[str] = []
        if why_now_options:
            context_lines.append("Почему ищет сейчас (варианты):")
            context_lines.extend([f"- {item}" for item in why_now_options[:10]])
        if solution_selected:
            context_lines.append("К какому решению ведём:")
            context_lines.extend([f"- {item}" for item in solution_selected[:10]])
        context_block = "\n".join(context_lines).strip()
        context_hint = (
            "\nКонтекст:\n"
            + context_block
            + "\n\nУсловия контекста:\n"
            + "- Для блока 1 (Вступление) опирайся на варианты «Почему ищет сейчас».\n"
            + "- Для блока 7 (Что делать дальше) опирайся на «К какому решению ведём».\n"
            if context_block
            else ""
        )
        prompt = render_generator_prompt(
            ARTICLE_BLUEPRINT_OUTLINE_CODE,
            main_query=article.wordstat,
            extra_rules=extra_rules,
            block_map=block_map,
        )
        if prompt:
            return f"{prompt}{context_hint}" if context_hint else prompt
        return f"""
Сделай базовую структуру статьи по запросу: "{article.wordstat}".
{context_hint}

Для каждого блока:
- придумай 1 H2 заголовок (4–10 слов)
- сформулируй 1 интент (кратко)
{extra_rules}

Блоки (используй id):
{block_map}

Верни строго JSON внутри тегов <answer>...</answer>:
<answer>
{{
  "blocks": [
    {{
      "id": 1,
      "h2_title": "<H2 заголовок>",
      "intent": "<интент>"
    }}
  ]
}}
</answer>

НЕ добавляй subquery и key_points. НЕ пиши пояснений и текста статьи.
"""

    def _build_details_prompt(
        block_id: int,
        block_name: str,
        h2_title: str,
        intent: str,
        keywords: list[str],
        compact: bool,
    ) -> str:
        extra_rules = ""
        if compact:
            extra_rules = "\nДоп.условия: 3–4 key_points, каждый пункт короткий."
        why_now_options = _format_why_now_options(article)
        solution_selected = _format_selected_solution(article)
        context_hint = ""
        if block_id == 1 and why_now_options:
            context_hint = (
                "\nУчитывай варианты «Почему ищет сейчас»:\n"
                + "\n".join([f"- {item}" for item in why_now_options[:10]])
            )
        elif block_id == 7 and solution_selected:
            context_hint = (
                "\nУчитывай «К какому решению ведём»:\n"
                + "\n".join([f"- {item}" for item in solution_selected[:10]])
            )
        keyword_block = ""
        if keywords:
            keyword_block = "\nКлючевые фразы для блока (используй их в смыслах):\n" + "\n".join(
                [f"- {keyword}" for keyword in keywords]
            )
        prompt = render_generator_prompt(
            ARTICLE_BLUEPRINT_DETAILS_CODE,
            block_id=str(block_id),
            block_name=block_name,
            h2_title=h2_title,
            intent=intent,
            keyword_block=keyword_block,
            extra_rules=extra_rules,
        )
        if prompt:
            return f"{prompt}{context_hint}" if context_hint else prompt
        return f"""
Заполни детали для блока {block_id} ({block_name}).
H2: "{h2_title}"
Интент: "{intent}"
{keyword_block}
{context_hint}

Сформулируй:
- 1 подзапрос (subquery)
- 3–6 ключевых смыслов (key_points)
{extra_rules}

Верни строго JSON внутри тегов <answer>...</answer>:
<answer>
{{
  "subquery": "<подзапрос>",
  "key_points": ["<смысл 1>", "<смысл 2>", "<смысл 3>"]
}}
</answer>

НЕ добавляй другие поля. НЕ пиши пояснений.
"""

    try:
        generator = _new_ai_generator()

        outline_schema_hint = """
{
  "blocks": [
    {
      "id": 1,
      "h2_title": "строка",
      "intent": "строка"
    }
  ]
}
""".strip()

        details_schema_hint = """
{
  "subquery": "строка",
  "key_points": ["строка"]
}
""".strip()

        outline_prompt = _build_outline_prompt(compact=False)
        outline_parsed, outline_raw = _request_json(
            outline_prompt,
            attempt="outline",
            schema_hint=outline_schema_hint,
            max_tokens=520,
        )
        if not outline_parsed:
            outline_prompt_compact = _build_outline_prompt(compact=True)
            outline_parsed, outline_raw = _request_json(
                outline_prompt_compact,
                attempt="outline_compact",
                schema_hint=outline_schema_hint,
                max_tokens=450,
            )
        if not outline_parsed:
            _fail_blueprint("ai_invalid_json_outline", raw=outline_raw or "")

        blocks = outline_parsed.get("blocks")
        if not isinstance(blocks, list):
            logger.error(
                "Blueprint AI outline missing blocks for article %s. Keys: %s",
                article.id,
                outline_parsed.keys(),
            )
            _fail_blueprint("ai_missing_blocks_outline", raw=outline_raw[:2000] if outline_raw else "")

        outline_map: dict[str, dict[str, str]] = {}
        invalid_blocks = 0
        seen_ids: set[int] = set()
        for item in blocks:
            if not isinstance(item, dict):
                invalid_blocks += 1
                continue
            raw_id = item.get("id") or item.get("block_id")
            try:
                block_id = int(str(raw_id))
            except (TypeError, ValueError):
                invalid_blocks += 1
                continue
            if block_id not in block_id_map or block_id in seen_ids:
                invalid_blocks += 1
                continue
            h2_title = _normalize_inline_text(item.get("h2_title") or item.get("h2") or item.get("title") or "")
            micro_intent = _normalize_inline_text(item.get("intent") or item.get("micro_intent") or "")
            if not h2_title or not micro_intent:
                invalid_blocks += 1
                continue
            block = block_id_map[block_id]
            outline_map[block] = {
                "h2_title": h2_title,
                "subquery": "",
                "micro_intent": micro_intent,
            }
            seen_ids.add(block_id)

        missing_blocks = [title for title in block_titles if title not in outline_map]
        logger.info(
            "Blueprint AI outline parsed blocks=%s, matched=%s, invalid=%s for article %s",
            len(blocks),
            len(outline_map),
            invalid_blocks,
            article.id,
        )
        if invalid_blocks or missing_blocks:
            logger.warning(
                "Blueprint AI outline invalid=%s, missing=%s for article %s",
                invalid_blocks,
                missing_blocks,
                article.id,
            )
            _fail_blueprint("ai_incomplete_outline", raw=outline_raw or "")

        cluster_phrases = _normalize_phrase_list(article.wordstat_phrases or [])
        if not cluster_phrases:
            cluster_phrases = _normalize_phrase_list([article.wordstat]) if article.wordstat else []
        logger.info("Blueprint cluster phrases count=%s for article %s", len(cluster_phrases), article.id)
        logger.debug("Blueprint cluster phrases for article %s: %s", article.id, cluster_phrases)

        keyword_assignments = _assign_cluster_phrases(cluster_phrases, outline_map, block_titles)
        distribution = {key: len(value) for key, value in keyword_assignments.items()}
        logger.info("Blueprint keyword distribution for article %s: %s", article.id, distribution)

        for block in block_titles:
            meta = outline_map.get(block)
            if not meta:
                continue
            assigned_keywords = keyword_assignments.get(block) or []
            if not assigned_keywords and article.wordstat:
                assigned_keywords = [article.wordstat]
            block_id = next((bid for bid, title in block_id_map.items() if title == block), None)
            if block_id is None:
                _fail_blueprint("ai_block_id_missing", raw=outline_raw or "")
            details_prompt = _build_details_prompt(
                block_id,
                block,
                meta["h2_title"],
                meta["micro_intent"],
                assigned_keywords,
                compact=False,
            )
            details_parsed, details_raw = _request_json(
                details_prompt,
                attempt=f"details:{block}",
                schema_hint=details_schema_hint,
                max_tokens=700,
                temperature=0.4,
            )
            if not details_parsed:
                details_prompt_compact = _build_details_prompt(
                    block_id,
                    block,
                    meta["h2_title"],
                    meta["micro_intent"],
                    assigned_keywords,
                    compact=True,
                )
                details_parsed, details_raw = _request_json(
                    details_prompt_compact,
                    attempt=f"details_compact:{block}",
                    schema_hint=details_schema_hint,
                    max_tokens=520,
                    temperature=0.3,
                )
            if not details_parsed:
                _fail_blueprint("ai_invalid_json_details", raw=details_raw or "")

            subquery = _normalize_inline_text(details_parsed.get("subquery") or details_parsed.get("question") or "")
            raw_key_points = details_parsed.get("key_points")
            key_points = []
            if isinstance(raw_key_points, list):
                key_points = [
                    _normalize_inline_text(point) for point in raw_key_points if str(point).strip()
                ][:6]
            elif isinstance(raw_key_points, str) and raw_key_points.strip():
                key_points = [_normalize_inline_text(raw_key_points)]
            if not subquery or not key_points:
                _fail_blueprint("ai_missing_details", raw=details_raw or "")

            level3[block] = {
                "h2_title": meta["h2_title"],
                "subquery": subquery,
                "keywords": assigned_keywords,
                "micro_intent": meta["micro_intent"],
                "key_points": key_points,
            }
            _persist_partial_structure()
    except RuntimeError:
        raise
    except Exception as exc:
        logger.exception("Failed to generate level3 SEO structure for article %s", article.id)
        _fail_blueprint("ai_exception", raw=str(exc))

    if not level3:
        logger.error("Blueprint AI produced empty structure for article %s", article.id)
        _fail_blueprint("ai_empty_structure", raw=last_raw or "")

    with transaction.atomic():
        article.seo_blocks = level3
        article.status = "outline_ready"
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

    article.status = "article_ready"
    article.save(update_fields=["status", "updated_at"])

    return {"article_id": article.id, "generated_blocks": generated}
