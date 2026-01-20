"""SEO-related AI helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .ai_generator import AIContentGenerator
from .ai_generator_base import logger
from .ai_generator_content import _parse_ai_json_response
from .prompt_settings import render_generator_prompt

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


def _normalize_seed_group_key(value: str) -> str | None:
    normalized = normalize_phrase(value)
    if not normalized:
        return None
    if "коммер" in normalized or "commercial" in normalized:
        return "Коммерческие"
    if "категор" in normalized or "category" in normalized:
        return "Категорийные"
    if "проблем" in normalized or "problem" in normalized:
        return "Проблемные"
    if "альтернатив" in normalized or "alternative" in normalized:
        return "Альтернативные формулировки"
    return None


def _cleanup_seed_phrase(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^[\s\-–—•\*\d\.\)\(]+", "", text).strip()
    return _WHITESPACE_RE.sub(" ", text)


def _extract_seed_phrases(raw_value) -> List[str]:
    if isinstance(raw_value, dict):
        raw_value = (
            raw_value.get("phrases")
            or raw_value.get("items")
            or raw_value.get("keywords")
            or raw_value.get("values")
            or []
        )

    if isinstance(raw_value, str):
        items = raw_value.replace("\r", "\n").split("\n")
    elif isinstance(raw_value, list):
        items = raw_value
    else:
        return []

    seen: set[str] = set()
    phrases: List[str] = []
    for item in items:
        if isinstance(item, dict):
            candidate = item.get("phrase") or item.get("value") or item.get("keyword") or ""
        else:
            candidate = item
        cleaned = _cleanup_seed_phrase(candidate)
        if not cleaned:
            continue
        normalized = normalize_phrase(cleaned)
        if normalized in seen:
            continue
        seen.add(normalized)
        phrases.append(cleaned)
    return phrases


def _normalize_seed_groups(payload) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    if isinstance(payload, dict):
        if isinstance(payload.get("groups"), list):
            return _normalize_seed_groups(payload.get("groups"))
        for key, value in payload.items():
            group_key = _normalize_seed_group_key(key)
            if not group_key:
                continue
            phrases = _extract_seed_phrases(value)
            if phrases:
                groups[group_key] = phrases
    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            group_label = (
                item.get("group")
                or item.get("name")
                or item.get("title")
                or item.get("type")
                or ""
            )
            group_key = _normalize_seed_group_key(group_label)
            if not group_key:
                continue
            phrases = _extract_seed_phrases(
                item.get("phrases") or item.get("items") or item.get("keywords") or item.get("values")
            )
            if phrases:
                groups[group_key] = phrases
    return groups


def _parse_seed_groups_from_text(text: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    current_group: str | None = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        group_key = _normalize_seed_group_key(line)
        if group_key:
            current_group = group_key
            groups.setdefault(group_key, [])
            continue
        if not current_group:
            continue
        cleaned = _cleanup_seed_phrase(line)
        if not cleaned:
            continue
        if cleaned not in groups[current_group]:
            groups[current_group].append(cleaned)
    return groups


def generate_wordstat_seed_groups(
    *,
    niche: str,
    product_service: str,
    audience: str | None = None,
    language: str = "ru",
) -> Dict[str, object]:
    niche_value = (niche or "").strip()
    product_value = (product_service or "").strip()
    audience_value = (audience or "").strip()

    if not niche_value or not product_value or not audience_value:
        return {"success": False, "error": "missing_required_fields"}

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        logger.error("Failed to init AI generator for Wordstat seed groups: %s", exc, exc_info=True)
        return {"success": False, "error": "ai_init_error"}

    language_note = "Пиши на русском языке." if language.lower().startswith("ru") else "Пиши на языке ниши."

    prompt = render_generator_prompt(
        "seo_wordstat_seed_groups",
        language_note=language_note,
        niche_value=niche_value,
        product_value=product_value,
        audience_value=audience_value,
    )
    if not prompt:
        return {"success": False, "error": "Missing generator prompt: seo_wordstat_seed_groups"}

    ai_response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=800,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    if not ai_response:
        return {"success": False, "error": "ai_no_response"}

    parsed, normalized_text, parse_error = _parse_ai_json_response(ai_response)
    if parse_error or not isinstance(parsed, dict):
        repaired = generator._repair_json_structure(
            normalized_text,
            schema_hint="""
{
  "Коммерческие": ["string", "string", "string"],
  "Категорийные": ["string", "string", "string"],
  "Проблемные": ["string", "string", "string"],
  "Альтернативные формулировки": ["string", "string", "string"]
}
""",
        )
        if repaired and isinstance(repaired, dict):
            parsed = repaired
            parse_error = None

    groups = _normalize_seed_groups(parsed) if isinstance(parsed, dict) else {}
    if not groups and normalized_text:
        groups = _parse_seed_groups_from_text(normalized_text)

    if parse_error and not groups:
        logger.error("Seed groups JSON parse failed: %s", parse_error)
        return {"success": False, "error": "ai_json_parse_failed", "raw_response": normalized_text}

    return {"success": True, "groups": groups, "raw_response": normalized_text}


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
    existing_rules_block = ""
    existing_clusters_block = ""
    if existing_cleaned:
        existing_rules_block = render_generator_prompt("seo_wordstat_cluster_existing_rules")
        existing_clusters_block = render_generator_prompt(
            "seo_wordstat_cluster_existing_clusters",
            existing_clusters_json=json.dumps(existing_cleaned, ensure_ascii=False),
        )

    prompt = render_generator_prompt(
        "seo_wordstat_cluster",
        language_note=language_note,
        existing_rules_block=existing_rules_block,
        phrases_count=len(cleaned),
        phrases_json=json.dumps(cleaned, ensure_ascii=False),
        existing_clusters_block=existing_clusters_block,
        schema_hint=schema_hint,
    )
    if not prompt:
        return {"success": False, "error": "Missing generator prompt: seo_wordstat_cluster"}

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


def analyze_seo_text(
    *,
    text: str,
    main_query: str | None = None,
    found_keywords: list[dict[str, Any]] | None = None,
    missing_keywords: list[dict[str, Any]] | None = None,
    cluster_coverage: list[dict[str, Any]] | None = None,
    language: str = "ru",
    include_rewrite: bool = False,
) -> Dict[str, object]:
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return {"success": False, "error": "text_required"}

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        logger.error("Failed to init AI generator for SEO analysis: %s", exc, exc_info=True)
        return {"success": False, "error": "ai_init_error"}

    truncated_text = cleaned_text[:8000] + ("…" if len(cleaned_text) > 8000 else "")

    found_payload = [
        {
            "phrase": str(item.get("phrase") or ""),
            "count": int(item.get("count") or 0),
            "cluster": item.get("cluster"),
        }
        for item in (found_keywords or [])[:80]
    ]
    missing_payload = [
        {
            "phrase": str(item.get("phrase") or ""),
            "cluster": item.get("cluster"),
        }
        for item in (missing_keywords or [])[:80]
    ]
    clusters_payload = [
        {
            "cluster": str(item.get("cluster") or ""),
            "found": int(item.get("found") or 0),
            "total": int(item.get("total") or 0),
        }
        for item in (cluster_coverage or [])
    ]

    language_note = "Пиши на русском языке." if language.lower().startswith("ru") else "Пиши на языке текста."
    rewrite_note_code = "seo_text_rewrite_note_on" if include_rewrite else "seo_text_rewrite_note_off"
    rewrite_note = render_generator_prompt(rewrite_note_code)

    prompt = render_generator_prompt(
        "seo_text_analysis",
        language_note=language_note,
        main_query=main_query or "не задан",
        found_payload=json.dumps(found_payload, ensure_ascii=False),
        missing_payload=json.dumps(missing_payload, ensure_ascii=False),
        clusters_payload=json.dumps(clusters_payload, ensure_ascii=False),
        truncated_text=truncated_text,
        rewrite_note=rewrite_note,
    )
    if not prompt:
        return {"success": False, "error": "Missing generator prompt: seo_text_analysis"}

    ai_response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=1200,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    if not ai_response:
        return {"success": False, "error": "ai_no_response"}

    parsed, normalized_text, parse_error = _parse_ai_json_response(ai_response)
    if parse_error or not isinstance(parsed, dict):
        repaired = generator._repair_json_structure(
            normalized_text,
            schema_hint="""
{
  "intent": "string",
  "strengths": ["string"],
  "gaps": ["string"],
  "recommendations": ["string"],
  "keyword_advice": {
    "include": ["string"],
    "exclude": ["string"],
    "separate_article": ["string"]
  },
  "rewrite_plan": {
    "h1": "string",
    "h2": ["string"],
    "h3": ["string"],
    "add_blocks": ["string"],
    "notes": ["string"]
  },
  "rewrite_text": "string"
}
""",
        )
        if repaired and isinstance(repaired, dict):
            parsed = repaired
            parse_error = None

    if parse_error or not isinstance(parsed, dict):
        logger.error("SEO analysis JSON parse failed: %s", parse_error)
        return {
            "success": False,
            "error": "ai_json_parse_failed",
            "raw_response": normalized_text,
        }

    return {"success": True, "result": parsed}


__all__ = [
    "cluster_wordstat_phrases",
    "normalize_phrase",
    "analyze_seo_text",
    "generate_wordstat_seed_groups",
]
