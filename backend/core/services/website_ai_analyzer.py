from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from core.ai_generator import AIContentGenerator
from core.ai_generator_content import _parse_ai_json_response

from . import website_scan_service

logger = logging.getLogger(__name__)


_LINK_KEYWORDS_RE = re.compile(
    r"(pricing|prices?|tariff|tariffs|plans?|services?|service|uslugi|usluga|ceny|tseny|stoimost|prajs|prays|price-list|pricelist)",
    re.IGNORECASE,
)

_SERVICES_LINK_RE = re.compile(r"(services?|service|uslugi|usluga|услуг|услуги|service)", re.IGNORECASE)
_PRICES_LINK_RE = re.compile(
    r"(pricing|prices?|price|tariffs?|tarif|tarify|plans?|ceny|tseny|stoimost|цены|стоимость|тариф|прайс)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WebsiteAiAnalysisPage:
    url: str
    title: str
    meta_description: str
    headings: dict[str, Any]
    text: str


@dataclass(frozen=True)
class WebsiteAiAnalysisResult:
    input_url: str
    base_url: str
    is_competitor: bool
    one_liner: str
    offers: list[str]
    pricing: str
    home_title: str = ""
    home_text: str = ""
    services_url: str | None = None
    prices_url: str | None = None
    evidence_urls: list[str] = field(default_factory=list)
    error: str | None = None


def _normalize_origin(url: str) -> str:
    try:
        return website_scan_service._normalize_base_url(url)  # type: ignore[attr-defined]
    except Exception:
        # Best-effort fallback; keep scheme+netloc if possible.
        raw = (url or "").strip()
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            raise
        return f"{parsed.scheme}://{parsed.netloc}/"

def _extract_services_and_prices_links_from_home(html_text: str, base_url: str) -> tuple[str | None, str | None]:
    """Extract one internal services link and one internal prices link from homepage."""
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return None, None

    soup = BeautifulSoup(html_text, "lxml")
    services: list[str] = []
    prices: list[str] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        anchor_text = a.get_text(" ", strip=True) or ""
        candidate = website_scan_service._canonicalize_url(base_url, str(href))  # type: ignore[attr-defined]
        if not candidate:
            continue
        candidate = website_scan_service._force_base_origin(base_url, candidate)  # type: ignore[attr-defined]
        if not website_scan_service._is_same_origin(base_url, candidate):  # type: ignore[attr-defined]
            continue
        if not website_scan_service._looks_like_html_page(candidate):  # type: ignore[attr-defined]
            continue

        path = urlparse(candidate).path or ""
        haystack = " ".join([path, anchor_text]).strip()
        if not haystack:
            continue

        if _SERVICES_LINK_RE.search(haystack) or _LINK_KEYWORDS_RE.search(path):
            services.append(candidate)
        if _PRICES_LINK_RE.search(haystack) or _LINK_KEYWORDS_RE.search(path):
            prices.append(candidate)

    def _first_unique(values: list[str]) -> str | None:
        seen: set[str] = set()
        for u in values:
            if u in seen:
                continue
            seen.add(u)
            return u
        return None

    return _first_unique(services), _first_unique(prices)


def _fetch_html(client: httpx.Client, url: str) -> tuple[int | None, str | None, str | None]:
    try:
        resp = client.get(url)
    except httpx.HTTPError:
        logger.info("WebsiteAiAnalyzer fetch failed: url=%s", url, exc_info=True)
        return None, None, None

    content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if resp.status_code != 200:
        return resp.status_code, content_type, None
    if content_type not in {"text/html", "application/xhtml+xml"}:
        return resp.status_code, content_type, None
    return resp.status_code, content_type, resp.text or ""


def _page_from_html(url: str, html_text: str) -> WebsiteAiAnalysisPage:
    title, meta_description, headings = website_scan_service._extract_page_metadata(html_text)  # type: ignore[attr-defined]
    text = website_scan_service._extract_content_text(html_text, limit=60_000)  # type: ignore[attr-defined]
    return WebsiteAiAnalysisPage(
        url=url,
        title=title,
        meta_description=meta_description,
        headings=headings,
        text=text,
    )


def _truncate_for_prompt(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def analyze_website_for_competitor_insights(
    input_url: str,
    *,
    max_pages: int = 3,
) -> WebsiteAiAnalysisResult:
    """
    Fetches max 3 pages: homepage + services + prices, then asks the default AI model for a brief summary.

    Rule: if homepage doesn't link to BOTH services and prices, it's not a competitor.
    """
    normalized_origin = _normalize_origin(input_url)

    with httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "SEO-Audit-Bot/1.0"},
        http2=getattr(website_scan_service, "_HTTP2_AVAILABLE", False),
        trust_env=True,
    ) as client:
        # Preflight to follow redirects and lock to final origin.
        try:
            pre = client.get(normalized_origin)
            effective_url = str(getattr(pre, "url", "") or "") or normalized_origin
            normalized_origin = _normalize_origin(effective_url)
        except httpx.HTTPError:
            pass

        status_code, content_type, home_html = _fetch_html(client, normalized_origin)
        if not home_html:
            return WebsiteAiAnalysisResult(
                input_url=input_url,
                base_url=normalized_origin,
                is_competitor=False,
                one_liner="Не удалось загрузить главную страницу",
                offers=[],
                pricing="",
                home_title="",
                home_text="",
                services_url=None,
                prices_url=None,
                evidence_urls=[],
                error=f"home_fetch_failed status={status_code} content_type={content_type}",
            )

        home_page = _page_from_html(normalized_origin, home_html)

        services_url, prices_url = _extract_services_and_prices_links_from_home(home_html, normalized_origin)

        # Strict rule from the request: if homepage doesn't link to services AND prices => not a competitor.
        if not services_url or not prices_url:
            return WebsiteAiAnalysisResult(
                input_url=input_url,
                base_url=normalized_origin,
                is_competitor=False,
                one_liner="",
                offers=[],
                pricing="",
                home_title=home_page.title,
                home_text=home_page.text,
                services_url=services_url,
                prices_url=prices_url,
                evidence_urls=[normalized_origin],
            )

        pages: list[WebsiteAiAnalysisPage] = []
        pages.append(home_page)
        for url in [services_url, prices_url][:2]:
            _, _, html_text = _fetch_html(client, url)
            if not html_text:
                continue
            pages.append(_page_from_html(url, html_text))

        if not pages:
            return WebsiteAiAnalysisResult(
                input_url=input_url,
                base_url=normalized_origin,
                is_competitor=True,
                one_liner="Сайт похож на конкурента, но не удалось загрузить страницы услуг/цен",
                offers=[],
                pricing="не найдено",
                home_title=home_page.title,
                home_text=home_page.text,
                services_url=services_url,
                prices_url=prices_url,
                evidence_urls=[normalized_origin],
            )

    try:
        generator = AIContentGenerator()
    except Exception as exc:
        return WebsiteAiAnalysisResult(
            input_url=input_url,
            base_url=normalized_origin,
            is_competitor=True,
            one_liner="Не удалось инициализировать AI",
            offers=[],
            pricing="",
            home_title=home_page.title if "home_page" in locals() else "",
            home_text=home_page.text if "home_page" in locals() else "",
            services_url=services_url,
            prices_url=prices_url,
            evidence_urls=[p.url for p in pages[:3]],
            error=str(exc),
        )

    pages_for_prompt: list[str] = []
    for page in pages[:3]:
        pages_for_prompt.append(
            "\n".join(
                [
                    f"URL: {page.url}",
                    f"TITLE: {_truncate_for_prompt(page.title, 200)}",
                    f"DESCRIPTION: {_truncate_for_prompt(page.meta_description, 400)}",
                    f"H1: {_truncate_for_prompt(' | '.join((page.headings or {}).get('h1') or []), 400)}",
                    f"H2: {_truncate_for_prompt(' | '.join((page.headings or {}).get('h2') or []), 600)}",
                    f"TEXT: {_truncate_for_prompt(page.text, 6000)}",
                ]
            )
        )

    prompt = f"""Ты — аналитик конкурентов. Тебе дан сайт компании и текст главной страницы + страниц услуг/цен.

Важное правило: если на ГЛАВНОЙ странице нет ссылок на страницы услуг и цен (в меню/блоках), то это НЕ конкурент.

Нужно кратко ответить, что компания продаёт и по каким ценам.

Верни ЧИСТЫЙ JSON строго такой структуры:
{{
  "is_competitor": true,
  "one_liner": "1 строка: что продаёт и цена/диапазон",
  "offers": ["список основных услуг/продуктов (до 5)"],
  "pricing": "кратко: цены/тарифы/диапазоны/условия; если не найдено — 'не найдено'",
  "evidence_urls": ["URL страниц, на которых видно услуги/цены (до 5)"]
}}

Сайт: {normalized_origin}

Материалы:
{'\n\n'.join(pages_for_prompt)}
"""

    response = generator.get_ai_response(prompt, max_tokens=650, temperature=0.25)
    payload, _, _ = _parse_ai_json_response(response or "")
    if not isinstance(payload, dict):
        return WebsiteAiAnalysisResult(
            input_url=input_url,
            base_url=normalized_origin,
            is_competitor=True,
            one_liner=(response or "").strip()[:240] or "AI не вернула структурированный ответ",
            offers=[],
            pricing="",
            home_title=home_page.title if "home_page" in locals() else "",
            home_text=home_page.text if "home_page" in locals() else "",
            services_url=services_url,
            prices_url=prices_url,
            evidence_urls=[p.url for p in pages[:3]],
            error="ai_json_parse_failed",
        )

    is_competitor = bool(payload.get("is_competitor", True))
    one_liner = str(payload.get("one_liner") or "").strip() or "—"
    pricing = str(payload.get("pricing") or "").strip() or "—"

    offers: list[str] = []
    raw_offers = payload.get("offers")
    if isinstance(raw_offers, list):
        for item in raw_offers[:10]:
            text = str(item or "").strip()
            if text:
                offers.append(text)

    evidence_urls: list[str] = []
    raw_urls = payload.get("evidence_urls")
    if isinstance(raw_urls, list):
        for item in raw_urls[:10]:
            text = str(item or "").strip()
            if text:
                evidence_urls.append(text)

    return WebsiteAiAnalysisResult(
        input_url=input_url,
        base_url=normalized_origin,
        is_competitor=is_competitor,
        one_liner=one_liner,
        offers=offers[:5],
        pricing=pricing,
        home_title=home_page.title if "home_page" in locals() else "",
        home_text=home_page.text if "home_page" in locals() else "",
        services_url=services_url,
        prices_url=prices_url,
        evidence_urls=evidence_urls[:5],
    )


def analyze_websites_for_competitor_insights(
    urls: Iterable[str],
    *,
    max_sites: int = 5,
    max_pages_per_site: int = 3,
) -> list[WebsiteAiAnalysisResult]:
    results: list[WebsiteAiAnalysisResult] = []
    for url in list(urls or [])[: max(0, int(max_sites or 0))]:
        normalized = (str(url or "")).strip()
        if not normalized:
            continue
        try:
            results.append(analyze_website_for_competitor_insights(normalized, max_pages=min(3, int(max_pages_per_site or 3))))
        except Exception as exc:
            logger.error("WebsiteAiAnalyzer failed: url=%s err=%s", normalized, exc, exc_info=True)
            results.append(
                WebsiteAiAnalysisResult(
                    input_url=normalized,
                    base_url=normalized,
                    is_competitor=False,
                    one_liner="Ошибка анализа сайта",
                    offers=[],
                    pricing="",
                    services_url=None,
                    prices_url=None,
                    evidence_urls=[],
                    error=str(exc),
                )
            )
    return results


__all__ = [
    "WebsiteAiAnalysisPage",
    "WebsiteAiAnalysisResult",
    "analyze_website_for_competitor_insights",
    "analyze_websites_for_competitor_insights",
]
