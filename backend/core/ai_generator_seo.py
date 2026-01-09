"""SEO-related AI helpers."""

from __future__ import annotations

import json
import re
from typing import Dict, List

from .ai_generator import AIContentGenerator
from .ai_generator_base import logger
from .ai_generator_content import _parse_ai_json_response

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_phrase(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip().lower())


def _prepare_phrases(raw_phrases: List[str]) -> List[str]:
    seen: set[str] = set()
    cleaned: List[str] = []
    for phrase in raw_phrases or []:
        if not isinstance(phrase, str):
            continue
        normalized = normalize_phrase(phrase)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(_WHITESPACE_RE.sub(" ", phrase.strip()))
    return cleaned


def cluster_wordstat_phrases(
    phrases: List[str],
    *,
    existing_clusters: List[str] | None = None,
    language: str = "ru",
) -> Dict[str, object]:
    cleaned = _prepare_phrases(phrases)
    if not cleaned:
        return {"success": False, "error": "no_phrases"}

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        logger.error("Failed to init AI generator for Wordstat clustering: %s", exc, exc_info=True)
        return {"success": False, "error": "ai_init_error"}

    schema_hint = """
{
  "clusters": [
    {"name": "string", "phrases": ["string"]}
  ],
  "unclustered": ["string"]
}
"""

    existing_cleaned: List[str] = []
    if existing_clusters:
        seen_names: set[str] = set()
        for name in existing_clusters:
            if not isinstance(name, str):
                continue
            cleaned_name = _WHITESPACE_RE.sub(" ", name.strip())
            if not cleaned_name:
                continue
            normalized = cleaned_name.lower()
            if normalized in seen_names:
                continue
            seen_names.add(normalized)
            existing_cleaned.append(cleaned_name)

    language_note = "Пиши на русском языке." if language.lower().startswith("ru") else "Пиши на языке фраз."

    prompt = f"""Ты SEO-специалист. Кластеризуй поисковые фразы по интенту пользователя.

Требования:
- {language_note}
- Используй ТОЛЬКО фразы из списка ниже.
- Каждая фраза должна попасть ровно в один кластер ИЛИ в unclustered.
- Названия кластеров должны быть короткими и понятными (2–5 слов).
- Не используй искусственные имена вида "Кластер 1".
- Сохраняй исходные формулировки фраз без изменений.
{"- Если фраза подходит под существующий кластер, используй его название ТОЧНО как в списке.\n" if existing_cleaned else ""}{"- Если ни один из существующих кластеров не подходит, создай новый.\n" if existing_cleaned else ""}

Список фраз ({len(cleaned)}):
{json.dumps(cleaned, ensure_ascii=False)}

{f"Существующие кластеры:\n{json.dumps(existing_cleaned, ensure_ascii=False)}\n" if existing_cleaned else ""}

Формат ответа: СТРОГО валидный JSON по схеме:
{schema_hint}
"""

    ai_response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=2200,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    if not ai_response:
        return {"success": False, "error": "ai_no_response"}

    parsed, normalized_text, parse_error = _parse_ai_json_response(ai_response)
    if parse_error or not isinstance(parsed, dict):
        repaired = generator._repair_json_structure(normalized_text, schema_hint=schema_hint)
        if repaired and isinstance(repaired, dict):
            parsed = repaired
            parse_error = None
    if parse_error or not isinstance(parsed, dict):
        logger.error("Wordstat clustering JSON parse failed: %s", parse_error)
        return {"success": False, "error": "ai_json_parse_failed", "raw_response": normalized_text}

    raw_clusters = parsed.get("clusters")
    if not isinstance(raw_clusters, list):
        return {"success": False, "error": "ai_missing_clusters", "raw_response": parsed}

    allowed = {normalize_phrase(p): p for p in cleaned}
    phrase_to_cluster: Dict[str, str] = {}
    clusters: List[Dict[str, object]] = []
    existing_map = {normalize_phrase(name): name for name in existing_cleaned}

    for cluster in raw_clusters:
        if not isinstance(cluster, dict):
            continue
        name = str(cluster.get("name") or "").strip()
        if not name:
            continue
        normalized_name = normalize_phrase(name)
        safe_name = (existing_map.get(normalized_name) or name)[:255]
        phrases_list = cluster.get("phrases") or []
        if not isinstance(phrases_list, list):
            continue
        unique_phrases: List[str] = []
        for phrase in phrases_list:
            normalized = normalize_phrase(phrase)
            if not normalized or normalized not in allowed:
                continue
            if normalized in phrase_to_cluster:
                continue
            phrase_to_cluster[normalized] = safe_name
            unique_phrases.append(allowed[normalized])
        if unique_phrases:
            clusters.append({"name": safe_name, "phrases": unique_phrases})

    return {
        "success": True,
        "clusters": clusters,
        "phrase_to_cluster": phrase_to_cluster,
    }


__all__ = ["cluster_wordstat_phrases", "normalize_phrase"]
