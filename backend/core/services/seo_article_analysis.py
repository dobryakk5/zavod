from __future__ import annotations

from collections import Counter
from typing import Iterable

import httpx

from core.services import website_scan_service


def extract_text_from_url(url: str, *, limit: int = 60_000) -> tuple[str, dict[str, object]]:
    raw_url = (url or "").strip()
    if not raw_url:
        raise ValueError("Укажите ссылку")
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"

    with httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "SEO-Audit-Bot/1.0"},
        http2=getattr(website_scan_service, "_HTTP2_AVAILABLE", False),
        trust_env=True,
    ) as client:
        try:
            resp = client.get(raw_url)
        except httpx.HTTPError as exc:
            raise ValueError("Не удалось загрузить страницу") from exc

    content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if resp.status_code != 200:
        raise ValueError("Не удалось загрузить страницу")
    if content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError("Ссылка должна вести на HTML страницу")

    html_text = resp.text or ""
    title, meta_description, headings = website_scan_service._extract_page_metadata(html_text)
    text = website_scan_service._extract_content_text(html_text, limit=limit)

    source = {
        "url": str(getattr(resp, "url", "") or raw_url),
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
    }
    return text, source


def _normalize_phrase_for_match(phrase: str) -> str:
    tokens = website_scan_service._tokenize(phrase)
    if not tokens:
        return ""
    return " ".join(tokens).strip()


def _build_ngram_counts(text: str, *, max_n: int = 3) -> Counter[str]:
    tokens = website_scan_service._tokenize(text)
    counts: Counter[str] = Counter()
    if not tokens:
        return counts
    for size in range(1, max_n + 1):
        for phrase in website_scan_service._extract_ngrams(tokens, size):
            counts[phrase] += 1
    return counts


def analyze_text_against_wordstat(
    text: str,
    wordstat_results: Iterable[object],
    *,
    max_ngram: int = 3,
) -> dict[str, object]:
    cleaned_text = (text or "").strip()
    tokens = website_scan_service._tokenize(cleaned_text)
    counts = _build_ngram_counts(cleaned_text, max_n=max_ngram)
    word_count = len(tokens)

    normalized: dict[str, dict[str, object]] = {}
    for row in wordstat_results:
        phrase = str(getattr(row, "phrase", "") or "").strip()
        if not phrase:
            continue
        normalized_phrase = _normalize_phrase_for_match(phrase)
        if not normalized_phrase:
            continue
        freq = int(getattr(row, "count", 0) or 0)
        cluster_obj = getattr(row, "cluster", None)
        cluster_name = str(getattr(cluster_obj, "name", "") or "").strip() or None
        existing = normalized.get(normalized_phrase)
        if existing and freq <= int(existing.get("freq", 0) or 0):
            continue
        normalized[normalized_phrase] = {
            "phrase": phrase,
            "freq": freq,
            "cluster": cluster_name,
            "normalized": normalized_phrase,
        }

    found: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    cluster_totals: Counter[str] = Counter()
    cluster_found: Counter[str] = Counter()

    for normalized_phrase, meta in normalized.items():
        cluster_label = str(meta.get("cluster") or "Без кластера")
        cluster_totals[cluster_label] += 1
        count = counts.get(normalized_phrase, 0)
        payload = {
            "phrase": meta.get("phrase"),
            "freq": meta.get("freq", 0),
            "cluster": meta.get("cluster"),
        }
        if count:
            payload["count"] = int(count)
            found.append(payload)
            cluster_found[cluster_label] += 1
        else:
            missing.append(payload)

    found.sort(key=lambda item: (int(item.get("count", 0)), int(item.get("freq", 0))), reverse=True)
    missing.sort(key=lambda item: int(item.get("freq", 0)), reverse=True)

    cluster_coverage: list[dict[str, object]] = []
    for cluster_name, total in sorted(cluster_totals.items()):
        cluster_coverage.append(
            {
                "cluster": cluster_name,
                "found": int(cluster_found.get(cluster_name, 0)),
                "total": int(total),
            }
        )

    total_keywords = len(normalized)
    coverage_percent = round((len(found) / total_keywords) * 100, 1) if total_keywords else 0.0

    return {
        "coverage_percent": coverage_percent,
        "total_keywords": total_keywords,
        "found_keywords": found,
        "missing_keywords": missing,
        "cluster_coverage": cluster_coverage,
        "word_count": word_count,
    }
