"""SEO-related AI helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .ai_generator import AIContentGenerator
from .ai_generator_base import logger
from .ai_generator_content import (
    _parse_ai_json_response,
    _salvage_json_objects_for_key,
    _try_parse_json_object,
)
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


def normalize_wordstat_phrases_ai(
    *,
    phrases: List[str],
    language: str = "ru",
) -> Dict[str, object]:
    cleaned = _prepare_phrases(phrases)
    if not cleaned:
        return {"success": False, "error": "no_phrases"}

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        logger.error(
            "Failed to init AI generator for Wordstat phrase normalization: %s",
            exc,
            exc_info=True,
        )
        return {"success": False, "error": "ai_init_error"}

    language_note = "Пиши на русском языке." if language.lower().startswith("ru") else "Пиши на языке ниши."
    prompt = render_generator_prompt(
        "seo_wordstat_normalize_phrases",
        language_note=language_note,
        phrases_count=str(len(cleaned)),
        phrases_json=json.dumps(cleaned, ensure_ascii=False),
    )
    if not prompt:
        return {"success": False, "error": "missing_prompt"}

    ai_response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=1200,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    if not ai_response:
        return {"success": False, "error": "ai_no_response"}

    parsed, normalized_text, parse_error = _parse_ai_json_response(ai_response)
    if not parse_error and isinstance(parsed, list):
        parsed = {"phrases": parsed}
    if parse_error or not isinstance(parsed, dict):
        parsed_candidate = _try_parse_json_object(normalized_text)
        if not parsed_candidate:
            parsed_candidate = _try_parse_json_object(ai_response)
        if isinstance(parsed_candidate, dict):
            parsed = parsed_candidate
            parse_error = None

    if parse_error or not isinstance(parsed, dict):
        repaired = generator._repair_json_structure(
            normalized_text,
            schema_hint="""
{
  "phrases": [
    {
      "raw_phrase": "string",
      "normalized_phrase": "string|null",
      "comment": "string"
    }
  ]
}
""",
        )
        if repaired and isinstance(repaired, list):
            repaired = {"phrases": repaired}
        if repaired and isinstance(repaired, dict):
            parsed = repaired
            parse_error = None

    if parse_error or not isinstance(parsed, dict):
        salvaged = _salvage_json_objects_for_key(normalized_text, "phrases")
        if not salvaged:
            salvaged = _salvage_json_objects_for_key(ai_response, "phrases")
        if salvaged:
            parsed = {"phrases": salvaged}
            parse_error = None

    if parse_error or not isinstance(parsed, dict):
        logger.error("Wordstat normalization JSON parse failed: %s", parse_error)
        return {
            "success": False,
            "error": "ai_json_parse_failed",
            "raw_response": normalized_text,
        }

    raw_items = parsed.get("phrases") or parsed.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []

    mapped: Dict[str, Dict[str, str | None]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        raw_phrase = str(item.get("raw_phrase") or item.get("phrase") or "").strip()
        if not raw_phrase:
            continue
        normalized_value = item.get("normalized_phrase")
        if normalized_value is None:
            normalized_phrase = None
        else:
            normalized_phrase = _WHITESPACE_RE.sub(" ", str(normalized_value).strip())
            if not normalized_phrase or normalized_phrase.lower() == "null":
                normalized_phrase = None
        comment = str(item.get("comment") or "").strip()
        mapped[normalize_phrase(raw_phrase)] = {
            "raw_phrase": raw_phrase,
            "normalized_phrase": normalized_phrase,
            "comment": comment,
        }

    results: List[Dict[str, str | None]] = []
    for phrase in cleaned:
        key = normalize_phrase(phrase)
        item = mapped.get(key)
        if item:
            results.append(
                {
                    "raw_phrase": phrase,
                    "normalized_phrase": item.get("normalized_phrase"),
                    "comment": item.get("comment") or "",
                }
            )
        else:
            results.append({"raw_phrase": phrase, "normalized_phrase": None, "comment": ""})

    return {"success": True, "phrases": results}


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


def select_wordstat_association_seeds(
    *,
    niche: str,
    product_service: str,
    associations: List[Dict[str, Any]],
    audience: str | None = None,
    group_name: str | None = None,
    language: str = "ru",
    max_results: int = 3,
) -> Dict[str, object]:
    niche_value = (niche or "").strip()
    product_value = (product_service or "").strip()
    audience_value = (audience or "").strip()
    group_value = (group_name or "").strip()

    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in associations or []:
        phrase = str(item.get("phrase") or "").strip()
        if not phrase:
            continue
        try:
            count = int(item.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        normalized = normalize_phrase(phrase)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append({"phrase": phrase, "count": count, "norm": normalized})

    if not candidates:
        return {"success": False, "error": "no_candidates"}

    candidates.sort(key=lambda item: (-item["count"], item["phrase"]))

    def _fallback_phrases() -> List[str]:
        return [item["phrase"] for item in candidates[:max_results]]

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        logger.error(
            "Failed to init AI generator for Wordstat association seeds: %s",
            exc,
            exc_info=True,
        )
        return {
            "success": True,
            "phrases": _fallback_phrases(),
            "used_fallback": True,
            "error": "ai_init_error",
        }

    language_note = "Пиши на русском языке." if language.lower().startswith("ru") else "Пиши на языке ниши."
    prompt = render_generator_prompt(
        "seo_wordstat_top_associations",
        language_note=language_note,
        niche_value=niche_value,
        product_value=product_value,
        audience_value=audience_value,
        group_name=group_value or "-",
        associations_count=str(len(candidates)),
        associations_json=json.dumps(
            [{"phrase": item["phrase"], "count": item["count"]} for item in candidates],
            ensure_ascii=False,
        ),
    )
    if not prompt:
        logger.error("Missing generator prompt: seo_wordstat_top_associations")
        return {
            "success": True,
            "phrases": _fallback_phrases(),
            "used_fallback": True,
            "error": "missing_prompt",
        }

    ai_response = generator.get_ai_response(
        prompt=prompt,
        max_tokens=400,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    if not ai_response:
        return {
            "success": True,
            "phrases": _fallback_phrases(),
            "used_fallback": True,
            "error": "ai_no_response",
        }

    parsed, normalized_text, parse_error = _parse_ai_json_response(ai_response)
    if parse_error or not isinstance(parsed, (dict, list)):
        repaired = generator._repair_json_structure(
            normalized_text,
            schema_hint="""
{
  "phrases": ["string", "string", "string"]
}
""",
        )
        if repaired and isinstance(repaired, dict):
            parsed = repaired
            parse_error = None

    extracted: List[str] = []
    if isinstance(parsed, dict):
        raw_list = (
            parsed.get("phrases")
            or parsed.get("associations")
            or parsed.get("top_associations")
            or parsed.get("keywords")
            or []
        )
        if isinstance(raw_list, list):
            extracted = [str(item) for item in raw_list]
        elif isinstance(raw_list, str):
            extracted = _extract_seed_phrases(raw_list)
    elif isinstance(parsed, list):
        extracted = [str(item) for item in parsed]

    normalized_map = {item["norm"]: item["phrase"] for item in candidates}
    selected: List[str] = []
    selected_norms: set[str] = set()
    for item in extracted:
        phrase = str(item or "").strip()
        if not phrase:
            continue
        normalized = normalize_phrase(phrase)
        if normalized in normalized_map and normalized not in selected_norms:
            selected.append(normalized_map[normalized])
            selected_norms.add(normalized)
        if len(selected) >= max_results:
            break

    used_fallback = False
    if len(selected) < max_results:
        used_fallback = True
        for item in candidates:
            if item["norm"] in selected_norms:
                continue
            selected.append(item["phrase"])
            selected_norms.add(item["norm"])
            if len(selected) >= max_results:
                break

    if not selected:
        selected = _fallback_phrases()
        used_fallback = True

    return {
        "success": True,
        "phrases": selected,
        "raw_response": normalized_text,
        "used_fallback": used_fallback,
    }


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
    "normalize_wordstat_phrases_ai",
    "analyze_seo_text",
    "generate_wordstat_seed_groups",
    "select_wordstat_association_seeds",
]
