from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Iterator
from urllib.parse import urljoin, urlparse, urlunparse

import gzip

import httpx
from bs4 import BeautifulSoup, Tag
from lxml import etree
from functools import lru_cache

from django.db import transaction
from django.utils import timezone
from time import monotonic

from ..models import (
    MindEdge,
    MindMap,
    MindNode,
    MindNodePosition,
    MindNodeProperty,
    WebsiteScan,
    WebsiteScanPage,
    WebsiteScanPageContent,
)

logger = logging.getLogger(__name__)

try:
    import h2  # type: ignore  # noqa: F401

    _HTTP2_AVAILABLE = True
except Exception:
    _HTTP2_AVAILABLE = False

try:
    import pymorphy2  # type: ignore

    _MORPH = pymorphy2.MorphAnalyzer()
    _LEMMATIZER_AVAILABLE = True
except Exception:
    _MORPH = None
    _LEMMATIZER_AVAILABLE = False


_SKIP_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".map",
    ".json",
    ".xml",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

_STOP_WORDS = {
    # RU
    "и",
    "в",
    "во",
    "на",
    "для",
    "по",
    "с",
    "со",
    "от",
    "до",
    "или",
    "а",
    "но",
    "что",
    "как",
    "мы",
    "вы",
    "они",
    "это",
    "этот",
    "эта",
    "эти",
    "тот",
    "та",
    "те",
    "уже",
    "еще",
    "ещё",
    "при",
    "над",
    "под",
    "без",
    "про",
    "из",
    "к",
    "ко",
    "об",
    "о",
    # EN
    "and",
    "the",
    "for",
    "with",
    "from",
    "this",
    "that",
    "you",
    "your",
    "our",
    "are",
    "was",
    "were",
    "what",
    "how",
    # Policy / legal / tracking
    "политика",
    "конфиденциальности",
    "согласие",
    "обработка",
    "персональных",
    "данных",
    "cookie",
    "cookies",
    "оферта",
    "правила",
    "условия",
    "лицензия",
    # Technical / URL parts / file types
    "id",
    "uid",
    "uuid",
    "http",
    "https",
    "www",
    "com",
    "ru",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    # UI / navigation
    "вход",
    "войти",
    "выход",
    "регистрация",
    "кабинет",
    "аккаунт",
    "меню",
    "каталог",
    "раздел",
    "страница",
    "сайт",
    "главная",
    "поиск",
    "фильтр",
    "сортировка",
    "подробнее",
    "читать",
    "перейти",
    "открыть",
    "показать",
    "выбрать",
    # Generic marketing adjectives
    "лучший",
    "лучшие",
    "топ",
    "новый",
    "новые",
    "современный",
    "популярный",
    "удобный",
    "качественный",
    "выгодный",
    "доступный",
    "надежный",
    "официальный",
    "проверенный",
    "реальный",
    # More RU stopwords / pronouns
    "у",
    "за",
    "через",
    "между",
    "ли",
    "же",
    "бы",
    "не",
    "ни",
    "чтобы",
    "который",
    "которые",
    "какой",
    "какая",
    "какие",
    "он",
    "она",
    "оно",
    "я",
    "ты",
    "их",
    "его",
    "ее",
    "её",
    "наш",
    "ваш",
}

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё]{3,}", re.UNICODE)
_HAS_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]", re.UNICODE)

_PHRASE_WEIGHTS = {
    "title": 5,
    "h1": 4,
    "h2": 3,
    "h3": 2,
    "anchors": 3,
    "seo_text": 1,
    "alt": 1,
    "description": 1,
    "keywords": 1,
}

_COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap/sitemap.xml",
]


@dataclass(frozen=True)
class RobotsInfo:
    robots_url: str
    robots_txt: str | None
    policy: "RobotsPolicy | None"
    sitemap_urls: list[str]


@dataclass(frozen=True)
class RobotsRule:
    directive: str  # allow|disallow
    pattern: str
    regex: re.Pattern


@dataclass(frozen=True)
class RobotsGroup:
    user_agents: list[str]
    rules: list[RobotsRule]


@dataclass(frozen=True)
class _BreadcrumbItem:
    title: str
    href: str | None


@dataclass(frozen=True)
class _MenuItem:
    title: str
    url: str
    parent_url: str | None


@dataclass(frozen=True)
class _HierarchyItem:
    path: str
    name: str
    source: str


class RobotsPolicy:
    """
    Minimal robots.txt evaluator with support for '*' and '$' (Google-style standard).

    Notes:
    - Empty Disallow value means "allow all" (ignored).
    - Empty Allow value is ignored.
    """

    def __init__(self, groups: list[RobotsGroup]):
        self._groups = groups

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern:
        raw = pattern.strip()
        if not raw:
            return re.compile(r"^$")  # never matches
        anchored = raw.endswith("$")
        if anchored:
            raw = raw[:-1]

        escaped = re.escape(raw).replace(r"\*", ".*")
        if anchored:
            return re.compile(rf"^{escaped}$")
        return re.compile(rf"^{escaped}")

    @classmethod
    def parse(cls, robots_txt: str) -> "RobotsPolicy":
        groups: list[RobotsGroup] = []
        current_uas: list[str] = []
        current_rules: list[RobotsRule] = []

        def flush():
            nonlocal current_uas, current_rules
            if current_uas:
                groups.append(RobotsGroup(user_agents=current_uas, rules=current_rules))
            current_uas = []
            current_rules = []

        for raw_line in (robots_txt or "").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                ua = value
                if not ua:
                    continue
                # New group starts when rules already collected.
                if current_rules and current_uas:
                    flush()
                current_uas.append(ua)
                continue

            if key in {"allow", "disallow"}:
                if not current_uas:
                    continue
                if key == "disallow" and value == "":
                    # Standard: empty Disallow => allow all (no restriction).
                    continue
                if key == "allow" and value == "":
                    continue
                regex = cls._compile_pattern(value)
                current_rules.append(RobotsRule(directive=key, pattern=value, regex=regex))
                continue

        flush()
        return cls(groups)

    @staticmethod
    def _ua_matches(token: str, user_agent: str) -> bool:
        token_l = (token or "").strip().lower()
        ua_l = (user_agent or "").strip().lower()
        if not token_l:
            return False
        if token_l == "*":
            return True
        return token_l in ua_l

    def _best_group(self, user_agent: str) -> RobotsGroup | None:
        best: tuple[int, RobotsGroup] | None = None
        for group in self._groups:
            best_len = -1
            for token in group.user_agents:
                if self._ua_matches(token, user_agent):
                    best_len = max(best_len, len(token.strip()))
            if best_len < 0:
                continue
            if best is None or best_len > best[0]:
                best = (best_len, group)
        return best[1] if best else None

    def can_fetch(self, user_agent: str, url: str) -> bool:
        group = self._best_group(user_agent)
        if not group:
            return True

        parsed = urlparse(url)
        target = parsed.path or "/"
        if parsed.params:
            target += f";{parsed.params}"
        if parsed.query:
            target += f"?{parsed.query}"

        best_match: tuple[int, str] | None = None  # (length, directive)
        for rule in group.rules:
            m = rule.regex.match(target)
            if not m:
                continue
            match_len = len(m.group(0))
            directive = rule.directive
            if best_match is None:
                best_match = (match_len, directive)
                continue
            if match_len > best_match[0]:
                best_match = (match_len, directive)
                continue
            if match_len == best_match[0] and best_match[1] == "disallow" and directive == "allow":
                best_match = (match_len, directive)

        if best_match is None:
            return True
        return best_match[1] != "disallow"


def _normalize_base_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        raise ValueError("base_url is required")
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid base_url")
    # strip path/query/fragment – base for crawling is the origin root
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def _canonicalize_url(base_url: str, href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None

    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None

    # Drop fragments and query params for a stable "page tree" key.
    cleaned = parsed._replace(fragment="", query="")
    normalized = urlunparse(cleaned)
    if normalized.endswith("/") and parsed.path != "/":
        normalized = normalized.rstrip("/")
    return normalized


def _is_same_origin(base_url: str, url: str) -> bool:
    b = urlparse(base_url)
    u = urlparse(url)
    if u.scheme not in {"http", "https"}:
        return False
    return b.netloc == u.netloc


def _looks_like_html_page(url: str) -> bool:
    path = urlparse(url).path.lower()
    for ext in _SKIP_EXTENSIONS:
        if path.endswith(ext):
            return False
    return True


def _force_base_origin(base_url: str, url: str) -> str:
    b = urlparse(base_url)
    u = urlparse(url)
    if u.netloc == b.netloc and u.scheme != b.scheme:
        u = u._replace(scheme=b.scheme)
        return urlunparse(u)
    return url


def _url_depth_from_path(url: str) -> int:
    path = (urlparse(url).path or "/").strip("/")
    if not path:
        return 0
    return len([segment for segment in path.split("/") if segment])


def _path_key(url: str) -> str:
    path = urlparse(url).path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def _iter_url_path_prefixes(url: str, *, max_depth: int) -> Iterator[str]:
    """
    Yield path prefixes for URL, e.g. /a/b/c -> /a, /a/b, /a/b/c (limited by max_depth).
    """
    path = (urlparse(url).path or "/").strip("/")
    if not path:
        return
    segments = [seg for seg in path.split("/") if seg]
    current = ""
    for seg in segments[: max(0, int(max_depth or 0))]:
        current += "/" + seg
        yield current


def _url_from_base_and_path(base_url: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return base_url.rstrip("/") + path


def _extract_sitemaps_from_robots(robots_txt: str) -> list[str]:
    urls: list[str] = []
    for raw_line in (robots_txt or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith("sitemap:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate:
                urls.append(candidate)
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url in seen:
            continue
        out.append(url)
        seen.add(url)
    return out


def _looks_like_xml_response(url: str, resp: httpx.Response) -> bool:
    content_type = (resp.headers.get("content-type") or "").lower()
    if "xml" in content_type:
        return True
    lowered = (url or "").lower()
    return lowered.endswith((".xml", ".xml.gz"))


def _detect_sitemaps(client: httpx.Client, base_url: str, explicit: list[str]) -> list[str]:
    found: list[str] = []

    def _add(url: str):
        url = (url or "").strip()
        if not url:
            return
        if url not in found:
            found.append(url)

    # Prefer explicit sitemaps from robots first.
    for url in explicit or []:
        _add(url)

    detected_from_common = 0
    for path in _COMMON_SITEMAP_PATHS:
        candidate = base_url.rstrip("/") + path
        try:
            resp = client.get(candidate)
            if resp.status_code == 200 and _looks_like_xml_response(candidate, resp):
                if candidate not in found:
                    detected_from_common += 1
                _add(candidate)
        except httpx.HTTPError:
            continue

    logger.info(
        "WebsiteScan sitemaps detected: base=%s explicit=%s common_hits=%s total=%s",
        base_url,
        len(explicit or []),
        detected_from_common,
        len(found),
    )
    return found


def _fetch_robots(client: httpx.Client, base_url: str) -> RobotsInfo:
    parsed = urlparse(base_url)
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

    robots_txt: str | None = None
    status_code: int | None = None
    effective_url: str | None = None
    try:
        resp = client.get(robots_url)
        status_code = resp.status_code
        effective_url = str(getattr(resp, "url", "") or "")
        if status_code == 200 and isinstance(resp.text, str):
            robots_txt = resp.text
    except httpx.HTTPError:
        robots_txt = None

    policy = None
    sitemap_urls: list[str] = []
    if robots_txt:
        sitemap_urls = _extract_sitemaps_from_robots(robots_txt)
        try:
            policy = RobotsPolicy.parse(robots_txt)
        except Exception:
            policy = None

    logger.info(
        "WebsiteScan robots: base=%s robots=%s effective=%s status=%s txt_len=%s sitemaps=%s",
        base_url,
        robots_url,
        effective_url or "",
        status_code if status_code is not None else "",
        len(robots_txt or ""),
        len(sitemap_urls),
    )

    return RobotsInfo(
        robots_url=robots_url,
        robots_txt=robots_txt,
        policy=policy,
        sitemap_urls=sitemap_urls,
    )


def _parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Returns (page_urls, sitemap_urls_from_index).
    """
    try:
        root = etree.fromstring(xml_text.encode("utf-8", errors="ignore"))
    except Exception:
        return ([], [])

    # Typical namespaces: http://www.sitemaps.org/schemas/sitemap/0.9
    nsmap = root.nsmap or {}
    ns = nsmap.get(None)
    ns_prefix = f"{{{ns}}}" if ns else ""

    tag = root.tag
    if tag.endswith("sitemapindex"):
        locs = root.findall(f".//{ns_prefix}loc")
        return ([], [loc.text.strip() for loc in locs if loc is not None and (loc.text or "").strip()])

    locs = root.findall(f".//{ns_prefix}loc")
    return ([loc.text.strip() for loc in locs if loc is not None and (loc.text or "").strip()], [])


def _fetch_sitemap_urls(
    client: httpx.Client,
    sitemap_url: str,
    *,
    max_sitemaps: int = 10,
    max_urls: int = 2000,
) -> list[str]:
    urls: list[str] = []
    queue = deque([sitemap_url])
    seen_sitemaps: set[str] = set()

    while queue and len(seen_sitemaps) < max_sitemaps and len(urls) < max_urls:
        current = queue.popleft()
        if current in seen_sitemaps:
            continue
        seen_sitemaps.add(current)

        try:
            resp = client.get(current)
            if resp.status_code != 200:
                continue
        except httpx.HTTPError:
            continue

        xml_text = ""
        try:
            if (current or "").lower().endswith(".gz"):
                raw = gzip.decompress(resp.content)
                xml_text = raw.decode("utf-8", errors="ignore")
            else:
                xml_text = resp.text or ""
        except Exception:
            xml_text = resp.text or ""

        if not xml_text:
            continue

        page_urls, sitemap_urls = _parse_sitemap(xml_text)
        for u in page_urls:
            urls.append(u)
            if len(urls) >= max_urls:
                break

        for sm in sitemap_urls:
            if sm not in seen_sitemaps:
                queue.append(sm)

    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u in seen:
            continue
        out.append(u)
        seen.add(u)
    return out


def _extract_page_metadata(html_text: str) -> tuple[str, str, dict]:
    soup = BeautifulSoup(html_text, "lxml")

    def _texts(selector: str) -> list[str]:
        items: list[str] = []
        for tag in soup.select(selector):
            text = tag.get_text(" ", strip=True)
            if text:
                items.append(text)
        return items

    h1_list = _texts("h1")[:10]
    title = h1_list[0].strip() if h1_list else ""
    if not title:
        title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_tag and meta_tag.get("content"):
        meta_description = str(meta_tag.get("content") or "").strip()

    meta_keywords = ""
    keywords_tag = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
    if keywords_tag and keywords_tag.get("content"):
        meta_keywords = str(keywords_tag.get("content") or "").strip()

    headings = {
        "h1": h1_list,
        "h2": _texts("h2")[:20],
        "h3": _texts("h3")[:20],
        "meta_keywords": meta_keywords,
    }
    return title, meta_description, headings


def _extract_content_text(html_text: str, *, limit: int = 100_000) -> str:
    soup = BeautifulSoup(html_text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    body = soup.body or soup
    text = body.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit]
    return text


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    words = _TOKEN_RE.findall(text.lower())

    out: list[str] = []
    for w in words:
        if not w:
            continue
        lemma = _lemmatize_token(w)
        if not lemma:
            continue
        if lemma in _STOP_WORDS:
            continue
        out.append(lemma)
    return out


@lru_cache(maxsize=50_000)
def _lemmatize_token(token: str) -> str:
    token = (token or "").strip().lower()
    if not token:
        return ""

    # Lemmatize Cyrillic tokens; keep Latin as-is.
    if _LEMMATIZER_AVAILABLE and _HAS_CYRILLIC_RE.search(token):
        try:
            parsed = _MORPH.parse(token)  # type: ignore[union-attr]
            if parsed:
                lemma = (parsed[0].normal_form or "").strip().lower()
                return lemma or token
        except Exception:
            return token

    return token


def _extract_ngrams(words: list[str], n: int) -> list[str]:
    if n <= 1:
        return words
    if len(words) < n:
        return []
    return [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]


def _extract_phrase_sources(html_text: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html_text, "lxml")
    sources: dict[str, list[str]] = defaultdict(list)

    if soup.title and soup.title.string:
        sources["title"].append(str(soup.title.string))

    for tag in soup.find_all("h1"):
        text = tag.get_text(" ", strip=True)
        if text:
            sources["h1"].append(text)
    for tag in soup.find_all("h2"):
        text = tag.get_text(" ", strip=True)
        if text:
            sources["h2"].append(text)
    for tag in soup.find_all("h3"):
        text = tag.get_text(" ", strip=True)
        if text:
            sources["h3"].append(text)

    for a in soup.find_all("a"):
        text = a.get_text(" ", strip=True)
        if text and len(text) >= 4:
            sources["anchors"].append(text)

    # Only use already-present HTML attributes; we never download images here.
    for img in soup.find_all("img"):
        alt = img.get("alt")
        if alt and isinstance(alt, str) and alt.strip():
            sources["alt"].append(alt.strip())

    desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if desc and desc.get("content"):
        sources["description"].append(str(desc.get("content") or ""))

    kw = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
    if kw and kw.get("content"):
        sources["keywords"].append(str(kw.get("content") or ""))

    seo_containers = soup.find_all(
        ["div", "section", "article"],
        attrs={
            "class": re.compile(r"(seo|text|content|article|body|main)", re.I),
        },
    )
    for container in seo_containers[:10]:
        text = container.get_text(" ", strip=True)
        if text:
            sources["seo_text"].append(text[:20000])

    if not sources.get("seo_text"):
        body = soup.body or soup
        text = body.get_text(" ", strip=True)
        if text:
            sources["seo_text"].append(text[:20000])

    return sources


def _compute_wordstats_from_html(html_text: str, *, top_n: int = 6) -> list[dict]:
    sources = _extract_phrase_sources(html_text)

    uni: Counter[str] = Counter()
    bi: Counter[str] = Counter()
    tri: Counter[str] = Counter()

    for source, texts in sources.items():
        weight = int(_PHRASE_WEIGHTS.get(source, 1))
        for text in texts:
            words = _tokenize(text)
            if not words:
                continue
            for w in words:
                uni[w] += weight
            for bg in _extract_ngrams(words, 2):
                bi[bg] += weight
            for tg in _extract_ngrams(words, 3):
                tri[tg] += weight

    # tri-grams only when meaningful
    tri = Counter({k: v for k, v in tri.items() if v >= 2})

    # Drop uni-grams that dissolve into bigrams:
    # if a word appears inside some bigram and its own score is not greater than
    # (best bigram score containing it) + 30%, then exclude the uni-gram.
    max_bigram_for_word: dict[str, int] = {}
    for phrase, score in bi.items():
        try:
            score_int = int(score)
        except (TypeError, ValueError):
            score_int = 0
        for w in phrase.split():
            if not w:
                continue
            prev = max_bigram_for_word.get(w)
            if prev is None or score_int > prev:
                max_bigram_for_word[w] = score_int

    filtered_uni: Counter[str] = Counter()
    for word, score in uni.items():
        try:
            score_int = int(score)
        except (TypeError, ValueError):
            score_int = 0
        best_bigram = max_bigram_for_word.get(word)
        if best_bigram is not None and score_int <= best_bigram * 1.3:
            continue
        filtered_uni[word] = score_int
    uni = filtered_uni

    ranked: list[tuple[int, int, str]] = []
    for phrase, score in tri.items():
        ranked.append((int(score), 3, phrase))
    for phrase, score in bi.items():
        ranked.append((int(score), 2, phrase))
    for word, score in uni.items():
        ranked.append((int(score), 1, word))

    ranked.sort(key=lambda x: (x[0], x[1], len(x[2])), reverse=True)
    out: list[dict] = []
    for score, _, phrase in ranked[: max(1, int(top_n or 0))]:
        out.append({"word": phrase, "count": score})
    return out


def _extract_links(html_text: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html_text, "lxml")
    urls: list[str] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        resolved = _canonicalize_url(base_url, href)
        if resolved:
            urls.append(resolved)
    return urls


def _extract_anchor_texts(html_text: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html_text, "lxml")
    items: list[tuple[str, str]] = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        resolved = _canonicalize_url(base_url, href)
        if not resolved:
            continue
        resolved = _force_base_origin(base_url, resolved)
        if not _is_same_origin(base_url, resolved):
            continue
        if not _looks_like_html_page(resolved):
            continue
        label = _normalize_label(a.get_text(" ", strip=True))
        if not label or _is_separator_label(label):
            continue
        items.append((_path_key(resolved), label))
    return items


def _safe_page_content_html(page: WebsiteScanPage) -> str:
    try:
        content = page.content
    except WebsiteScanPageContent.DoesNotExist:
        return ""
    if not content or not content.content_html:
        return ""
    return content.content_html


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _is_separator_label(value: str) -> bool:
    return value in {"/", "\\", ">", "»", "·", "|", "→", "←"}


def _is_home_label(value: str) -> bool:
    lowered = value.lower()
    return lowered in {"home", "главная", "главная страница", "main", "index"}


_GENERIC_ANCHOR_LABELS = {
    "подробнее",
    "читать",
    "читать далее",
    "читать дальше",
    "подробнее тут",
    "читать полностью",
    "перейти",
    "открыть",
    "узнать больше",
    "more",
    "read more",
    "details",
}


def _best_anchor_label(counter: Counter[str] | None) -> str | None:
    if not counter:
        return None
    for label, _count in counter.most_common():
        if len(label) < 2:
            continue
        lowered = label.lower()
        if lowered in _GENERIC_ANCHOR_LABELS:
            continue
        tokens = _TOKEN_RE.findall(lowered)
        if tokens and all(token in _STOP_WORDS for token in tokens):
            continue
        return label
    return None


def _best_cluster_source(counter: Counter[str], *, priority: dict[str, int]) -> str | None:
    if not counter:
        return None
    best = sorted(counter.items(), key=lambda item: (item[1], priority.get(item[0], 0)), reverse=True)[0][0]
    return best


def _extract_breadcrumbs_from_container(
    container: BeautifulSoup,
    *,
    base_url: str,
) -> list[_BreadcrumbItem]:
    items: list[_BreadcrumbItem] = []
    li_nodes = container.find_all("li")
    nodes = li_nodes if li_nodes else container.find_all(["a", "span"], recursive=True)
    for node in nodes:
        title = ""
        href = None
        if node.name == "li":
            anchor = node.find("a", href=True)
            if anchor:
                title = anchor.get_text(strip=True)
                href = anchor.get("href")
            else:
                span = node.find("span")
                title = (span.get_text(strip=True) if span else node.get_text(strip=True))
        else:
            title = node.get_text(strip=True)
            if node.name == "a":
                href = node.get("href")
        title = _normalize_label(title)
        if not title or _is_separator_label(title):
            continue
        if href:
            href = _canonicalize_url(base_url, href)
        items.append(_BreadcrumbItem(title=title, href=href))

    deduped: list[_BreadcrumbItem] = []
    prev_key: tuple[str, str | None] | None = None
    for item in items:
        key = (item.title.lower(), item.href)
        if key == prev_key:
            continue
        deduped.append(item)
        prev_key = key
    return deduped


def _find_nav_near_h1(soup: BeautifulSoup) -> BeautifulSoup | None:
    h1 = soup.find("h1")
    if not h1:
        return None
    parent = h1.parent
    if isinstance(parent, Tag):
        nav = parent.find("nav")
        if isinstance(nav, Tag):
            return nav

    def _scan_siblings(iterator) -> BeautifulSoup | None:
        count = 0
        for sibling in iterator:
            if count >= 3:
                break
            count += 1
            if isinstance(sibling, Tag) and sibling.name == "nav":
                return sibling
            if isinstance(sibling, Tag):
                nav = sibling.find("nav")
                if isinstance(nav, Tag):
                    return nav
        return None

    nav = _scan_siblings(h1.previous_siblings)
    if nav:
        return nav
    return _scan_siblings(h1.next_siblings)


def _extract_breadcrumbs_json_ld(
    soup: BeautifulSoup,
    *,
    base_url: str,
) -> list[_BreadcrumbItem]:
    def _items_from_payload(payload: object) -> list[_BreadcrumbItem]:
        items: list[_BreadcrumbItem] = []
        if isinstance(payload, list):
            for entry in payload:
                items.extend(_items_from_payload(entry))
            return items
        if not isinstance(payload, dict):
            return items

        graph = payload.get("@graph")
        if graph:
            items.extend(_items_from_payload(graph))
            return items

        type_value = payload.get("@type")
        if isinstance(type_value, list):
            types = [str(entry or "").lower() for entry in type_value]
        else:
            types = [str(type_value or "").lower()]
        if "breadcrumblist" not in types:
            return items

        raw_items = payload.get("itemListElement") or []
        ordered: list[tuple[int, _BreadcrumbItem]] = []
        for idx, entry in enumerate(raw_items):
            if not isinstance(entry, dict):
                continue
            name = _normalize_label(str(entry.get("name") or ""))
            href: str | None = None
            item = entry.get("item")
            if isinstance(item, dict):
                href = item.get("@id") or item.get("url")
            elif isinstance(item, str):
                href = item
            if href:
                href = _canonicalize_url(base_url, href)
            if not name:
                continue
            position = entry.get("position")
            try:
                position_idx = int(position)
            except (TypeError, ValueError):
                position_idx = idx + 1
            ordered.append((position_idx, _BreadcrumbItem(title=name, href=href)))
        ordered.sort(key=lambda item: item[0])
        return [item for _, item in ordered]

    items: list[_BreadcrumbItem] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items.extend(_items_from_payload(payload))
    return items


def _extract_breadcrumbs(html_text: str, base_url: str) -> list[_BreadcrumbItem]:
    soup = BeautifulSoup(html_text, "lxml")

    container = soup.select_one('[itemtype*="Breadcrumb"]')
    if container:
        items = _extract_breadcrumbs_from_container(container, base_url=base_url)
        if len(items) >= 2:
            return items

    for selector in (".breadcrumb", ".breadcrumbs", ".crumbs"):
        container = soup.select_one(selector)
        if not container:
            continue
        items = _extract_breadcrumbs_from_container(container, base_url=base_url)
        if len(items) >= 2:
            return items

    nav = _find_nav_near_h1(soup)
    if isinstance(nav, Tag):
        items = _extract_breadcrumbs_from_container(nav, base_url=base_url)
        if 1 < len(items) <= 8:
            return items

    items = _extract_breadcrumbs_json_ld(soup, base_url=base_url)
    if len(items) >= 2:
        return items

    return []


_MENU_SKIP_KEYWORDS = {
    "breadcrumb",
    "breadcrumbs",
    "crumb",
    "crumbs",
    "footer",
    "mobile",
    "burger",
    "drawer",
    "offcanvas",
    "sidebar",
    "bottom",
}


def _has_keyword(value: str | None, keywords: set[str]) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(keyword in lowered for keyword in keywords)


def _should_skip_menu_element(element: BeautifulSoup) -> bool:
    current = element
    for _ in range(5):
        if not current or not hasattr(current, "get"):
            break
        if current.name == "footer":
            return True
        class_value = " ".join(current.get("class", []))
        if _has_keyword(class_value, _MENU_SKIP_KEYWORDS):
            return True
        if _has_keyword(current.get("id"), _MENU_SKIP_KEYWORDS):
            return True
        label = current.get("aria-label")
        if _has_keyword(label, _MENU_SKIP_KEYWORDS):
            return True
        current = current.parent
    return False


def _parse_menu_ul(ul: BeautifulSoup, *, base_url: str, parent_url: str | None = None) -> list[_MenuItem]:
    items: list[_MenuItem] = []
    for li in ul.find_all("li", recursive=False):
        anchors = [a for a in li.find_all("a", href=True) if a.find_parent("li") is li]
        anchor = anchors[0] if anchors else None
        parent_for_children = parent_url
        if anchor:
            title = _normalize_label(anchor.get_text(" ", strip=True))
            href = (anchor.get("href") or "").strip()
            if href and not href.startswith("#"):
                url = _canonicalize_url(base_url, href)
                if url:
                    url = _force_base_origin(base_url, url)
                if url and _is_same_origin(base_url, url) and _looks_like_html_page(url) and title:
                    items.append(_MenuItem(title=title, url=url, parent_url=parent_url))
                    parent_for_children = url

        submenus = [sub for sub in li.find_all("ul") if sub.find_parent("li") is li]
        for sub in submenus:
            items.extend(_parse_menu_ul(sub, base_url=base_url, parent_url=parent_for_children))
    return items


def _extract_menu_items(html_text: str, base_url: str) -> list[_MenuItem]:
    soup = BeautifulSoup(html_text, "lxml")
    selectors = (
        "nav ul",
        ".menu ul",
        ".main-menu ul",
        ".header-menu ul",
        ".navbar ul",
    )
    candidates: list[tuple[int, int, int, BeautifulSoup]] = []
    for selector in selectors:
        for ul in soup.select(selector):
            if _should_skip_menu_element(ul):
                continue
            top_items = ul.find_all("li", recursive=False)
            link_count = len([li for li in top_items if li.find("a", href=True)])
            if link_count < 2:
                continue
            class_value = " ".join(ul.get("class", []))
            score = link_count
            if ul.find_parent("nav"):
                score += 2
            if ul.find_parent("header"):
                score += 2
            if _has_keyword(class_value, {"menu", "main", "nav", "navbar"}):
                score += 2
            nested = len([child for child in ul.find_all("ul") if child.find_parent("ul") is ul])
            ul_depth = len(ul.find_parents("ul"))
            candidates.append((ul_depth, score, nested, ul))

    if not candidates:
        return []

    min_depth = min(entry[0] for entry in candidates)
    candidates = [entry for entry in candidates if entry[0] == min_depth]
    candidates.sort(key=lambda entry: (entry[1], entry[2]), reverse=True)
    _, _, _, chosen = candidates[0]
    items = _parse_menu_ul(chosen, base_url=base_url, parent_url=None)

    seen: set[str] = set()
    deduped: list[_MenuItem] = []
    for item in items:
        path = _path_key(item.url)
        if path in seen:
            continue
        seen.add(path)
        deduped.append(item)
    return deduped


def _path_depth(path: str) -> int:
    normalized = path.strip("/")
    if not normalized:
        return 0
    return len([seg for seg in normalized.split("/") if seg])


def _segment_from_path(path: str) -> str:
    normalized = path.strip("/")
    if not normalized:
        return "/"
    return normalized.split("/")[-1]


def _breadcrumb_chain_for_page(
    page_url: str,
    *,
    breadcrumbs: list[_BreadcrumbItem],
    max_depth: int,
) -> list[_HierarchyItem]:
    if not breadcrumbs:
        return []

    page_path = _path_key(page_url)
    segments = [seg for seg in page_path.strip("/").split("/") if seg]

    start_index = 0
    if breadcrumbs and (
        (breadcrumbs[0].href and _path_key(breadcrumbs[0].href) == "/")
        or _is_home_label(breadcrumbs[0].title)
    ):
        start_index = 1

    crumb_count = max(0, len(breadcrumbs) - start_index)
    chain: list[_HierarchyItem] = []
    sliced = breadcrumbs[start_index:]
    last_index = max(0, len(sliced) - 1)
    for idx, item in enumerate(sliced):
        path = None
        if item.href:
            path = _path_key(item.href)
        if not path:
            if idx == last_index:
                path = page_path
            else:
                if segments:
                    if crumb_count <= len(segments):
                        if idx < len(segments):
                            path = "/" + "/".join(segments[: idx + 1])
                    else:
                        depth_from_end = crumb_count - 1 - idx
                        prefix_len = len(segments) - depth_from_end
                        if prefix_len > 0:
                            path = "/" + "/".join(segments[:prefix_len])
        if not path:
            path = page_path
        if path == "/":
            continue
        if _path_depth(path) > max_depth:
            break
        chain.append(_HierarchyItem(path=path, name=item.title, source="breadcrumbs"))

    return chain


def _menu_chain_for_page(
    page_url: str,
    *,
    menu_parent_by_path: dict[str, str | None],
    menu_title_by_path: dict[str, str],
    menu_paths_by_depth: list[str],
    max_depth: int,
) -> list[_HierarchyItem]:
    if not menu_paths_by_depth:
        return []

    page_path = _path_key(page_url)
    match_path: str | None = None
    if page_path in menu_title_by_path:
        match_path = page_path
    else:
        for candidate in menu_paths_by_depth:
            if candidate == "/":
                continue
            if page_path == candidate or page_path.startswith(candidate.rstrip("/") + "/"):
                match_path = candidate
                break

    if not match_path:
        return []

    chain_paths: list[str] = []
    current = match_path
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        chain_paths.append(current)
        current = menu_parent_by_path.get(current)

    chain_paths.reverse()
    chain: list[_HierarchyItem] = []
    for path in chain_paths:
        if path == "/":
            continue
        if _path_depth(path) > max_depth:
            break
        chain.append(_HierarchyItem(path=path, name=menu_title_by_path.get(path, _segment_from_path(path)), source="menu"))

    if match_path and page_path != match_path:
        base_segments = [seg for seg in match_path.strip("/").split("/") if seg]
        full_segments = [seg for seg in page_path.strip("/").split("/") if seg]
        for idx in range(len(base_segments) + 1, len(full_segments) + 1):
            path = "/" + "/".join(full_segments[:idx])
            if _path_depth(path) > max_depth:
                break
            chain.append(_HierarchyItem(path=path, name=_segment_from_path(path), source="menu"))

    return chain


def _url_chain_for_page(page_url: str, *, max_depth: int) -> list[_HierarchyItem]:
    page_path = _path_key(page_url)
    segments = [seg for seg in page_path.strip("/").split("/") if seg]
    chain: list[_HierarchyItem] = []
    for idx, _ in enumerate(segments[: max_depth]):
        path = "/" + "/".join(segments[: idx + 1])
        chain.append(_HierarchyItem(path=path, name=_segment_from_path(path), source="url"))
    return chain


def _preferred_page_label(page: WebsiteScanPage) -> str | None:
    headings = page.headings or {}
    h1 = headings.get("h1")
    label = ""
    if isinstance(h1, list) and h1:
        label = str(h1[0] or "")
    elif isinstance(h1, str):
        label = h1
    if not label:
        label = str(page.title or "")
    label = _normalize_label(label)
    return label or None


def _label_for_path(
    path: str,
    *,
    page_by_path: dict[str, WebsiteScanPage],
    anchor_texts_by_path: dict[str, Counter[str]],
) -> str:
    label = _best_anchor_label(anchor_texts_by_path.get(path))
    if not label:
        page = page_by_path.get(path)
        if page:
            label = _preferred_page_label(page)
    return label or _segment_from_path(path)


def _link_chain_for_page(
    page_url: str,
    *,
    incoming_sources_by_path: dict[str, Counter[str]],
    incoming_counts_by_path: Counter[str],
    page_by_path: dict[str, WebsiteScanPage],
    anchor_texts_by_path: dict[str, Counter[str]],
    max_depth: int,
) -> list[_HierarchyItem]:
    page_path = _path_key(page_url)
    sources = incoming_sources_by_path.get(page_path)
    if not sources:
        return []
    best_parent: str | None = None
    best_score: tuple[int, int, int] | None = None
    for source_path, count in sources.items():
        if source_path == page_path:
            continue
        incoming_score = incoming_counts_by_path.get(source_path, 0)
        depth_score = -_path_depth(source_path)
        score = (count, incoming_score, depth_score)
        if best_score is None or score > best_score:
            best_score = score
            best_parent = source_path
    if not best_parent or best_parent == "/":
        return []
    if _path_depth(best_parent) > max_depth:
        return []
    chain: list[_HierarchyItem] = [
        _HierarchyItem(
            path=best_parent,
            name=_label_for_path(best_parent, page_by_path=page_by_path, anchor_texts_by_path=anchor_texts_by_path),
            source="links",
        ),
        _HierarchyItem(
            path=page_path,
            name=_label_for_path(page_path, page_by_path=page_by_path, anchor_texts_by_path=anchor_texts_by_path),
            source="links",
        ),
    ]
    return chain


def _build_hierarchy_tree(chains: Iterable[list[_HierarchyItem]], *, max_depth: int) -> _TreeNode:
    root = _TreeNode(name="/", path="/", depth=0)
    node_by_path: dict[str, _TreeNode] = {"/": root}
    parent_by_path: dict[str, str | None] = {"/": None}

    for chain in chains:
        root.count += 1
        parent = root
        for item in chain:
            if item.path == "/":
                continue
            if _path_depth(item.path) > max_depth:
                break
            node = node_by_path.get(item.path)
            if node is None:
                node = _TreeNode(name=item.name or _segment_from_path(item.path), path=item.path, depth=_path_depth(item.path))
                node_by_path[item.path] = node
                parent_by_path[item.path] = parent.path
                parent.children[item.path] = node
            else:
                existing_parent = parent_by_path.get(item.path)
                if existing_parent is None:
                    parent_by_path[item.path] = parent.path
                    parent.children[item.path] = node
                elif existing_parent == parent.path:
                    parent.children[item.path] = node
                if item.name and node.name == _segment_from_path(node.path):
                    node.name = item.name
            node.count += 1
            parent = node

    return root




def _page_label(url: str, title: str) -> str:
    if title.strip():
        return title.strip()[:80]
    parsed = urlparse(url)
    path = parsed.path.strip("/") or parsed.netloc
    return path.split("/")[-1][:80] or parsed.netloc


def _reset_mind_map(map_id: int) -> None:
    MindEdge.objects.filter(map_id=map_id).delete()
    MindNodeProperty.objects.filter(node__map_id=map_id).delete()
    MindNodePosition.objects.filter(node__map_id=map_id).delete()
    MindNode.objects.filter(map_id=map_id).delete()


class _TreeNode:
    __slots__ = ("name", "path", "depth", "children", "count")

    def __init__(self, name: str, *, path: str, depth: int):
        self.name = name
        self.path = path
        self.depth = depth
        self.children: dict[str, "_TreeNode"] = {}
        self.count = 0


def _build_url_tree(urls: Iterable[str], *, max_depth: int) -> _TreeNode:
    root = _TreeNode(name="/", path="/", depth=0)
    for url in urls:
        segments_raw = (urlparse(url).path or "/").strip("/")
        segments = [seg for seg in segments_raw.split("/") if seg] if segments_raw else []

        node = root
        node.count += 1

        current_path = ""
        for i, seg in enumerate(segments[: max_depth]):
            current_path += "/" + seg
            if current_path not in node.children:
                node.children[current_path] = _TreeNode(name=seg, path=current_path, depth=i + 1)
            node = node.children[current_path]
            node.count += 1

    return root


def _iter_tree(node: _TreeNode) -> Iterator[_TreeNode]:
    yield node
    for child in sorted(node.children.values(), key=lambda item: item.name):
        yield from _iter_tree(child)


def _compute_tree_layout_positions(
    tree: _TreeNode,
    *,
    gap_x: float,
    gap_y: float,
) -> dict[str, tuple[float, float]]:
    """
    Simple tidy-tree layout (Reingold–Tilford style):
    - x = depth * gap_x
    - leaves get incremental y
    - internal nodes get mean(children y)
    """

    positions: dict[str, tuple[float, float]] = {}
    next_y = 0.0

    def visit(node: _TreeNode) -> float:
        nonlocal next_y

        if not node.children:
            y = next_y
            next_y += gap_y
        else:
            child_ys: list[float] = []
            for child in sorted(node.children.values(), key=lambda c: c.name):
                child_ys.append(visit(child))
            y = sum(child_ys) / max(1, len(child_ys))

        x = float(node.depth) * gap_x
        positions[node.path] = (x, y)
        return y

    visit(tree)

    ys = [y for _, y in positions.values()]
    if ys:
        shift = (min(ys) + max(ys)) / 2.0
        for path, (x, y) in list(positions.items()):
            positions[path] = (x, y - shift)

    return positions


def _build_mind_map_for_scan(scan: WebsiteScan) -> int:
    client = scan.client
    base_url = scan.base_url
    netloc = urlparse(base_url).netloc

    max_depth = int(scan.max_depth or 3)
    pages = list(WebsiteScanPage.objects.filter(scan=scan).select_related("content").order_by("id"))
    primary_pages = [page for page in pages if not page.is_helper and page.url]
    urls = [page.url for page in primary_pages if page.url]

    menu_items: list[_MenuItem] = []
    menu_parent_by_path: dict[str, str | None] = {}
    menu_title_by_path: dict[str, str] = {}
    menu_paths_by_depth: list[str] = []
    anchor_texts_by_path: dict[str, Counter[str]] = defaultdict(Counter)
    incoming_sources_by_path: dict[str, Counter[str]] = defaultdict(Counter)
    incoming_counts_by_path: Counter[str] = Counter()
    page_by_path_obj: dict[str, WebsiteScanPage] = {}

    menu_candidates: list[tuple[int, list[_MenuItem]]] = []
    menu_pages: list[WebsiteScanPage] = []
    home_page = next((page for page in pages if page.url and _path_key(page.url) == "/"), None)
    if home_page:
        menu_pages.append(home_page)
    menu_pages.extend([page for page in pages if page is not home_page])
    for page in menu_pages:
        if not page.url:
            continue
        html = _safe_page_content_html(page)
        if not html:
            continue
        items = _extract_menu_items(html, base_url)
        if items:
            menu_candidates.append((len(items), items))
        if len(menu_candidates) >= 5:
            break
    if menu_candidates:
        menu_candidates.sort(key=lambda entry: entry[0], reverse=True)
        menu_items = menu_candidates[0][1]

    if menu_items:
        for item in menu_items:
            path = _path_key(item.url)
            parent_path = _path_key(item.parent_url) if item.parent_url else None
            if path not in menu_title_by_path:
                menu_title_by_path[path] = item.title
            if parent_path:
                menu_parent_by_path[path] = parent_path
        if menu_title_by_path:
            for path in sorted(menu_title_by_path.keys(), key=_path_depth):
                if path in menu_parent_by_path or path == "/":
                    continue
                segments = path.strip("/").split("/")
                while len(segments) > 1:
                    segments = segments[:-1]
                    candidate = "/" + "/".join(segments)
                    if candidate in menu_title_by_path:
                        menu_parent_by_path[path] = candidate
                        break
            menu_paths_by_depth = sorted(menu_title_by_path.keys(), key=_path_depth, reverse=True)
    if menu_title_by_path:
        max_menu_depth = max(_path_depth(path) for path in menu_title_by_path)
        logger.info("WebsiteScan menu items: id=%s items=%s max_depth=%s", scan.id, len(menu_title_by_path), max_menu_depth)
    else:
        logger.info("WebsiteScan menu items: id=%s items=0", scan.id)

    for page in pages:
        if page.url:
            path_key = _path_key(page.url)
            if path_key and (path_key not in page_by_path_obj or (page_by_path_obj[path_key].is_helper and not page.is_helper)):
                page_by_path_obj[path_key] = page

    for page in pages:
        html_text = _safe_page_content_html(page)
        if not html_text or not page.url:
            continue
        for path, label in _extract_anchor_texts(html_text, base_url):
            anchor_texts_by_path[path][label] += 1
        page_path = _path_key(page.url)
        for link in _extract_links(html_text, base_url):
            link = _force_base_origin(base_url, link)
            if not _is_same_origin(base_url, link):
                continue
            if not _looks_like_html_page(link):
                continue
            target_path = _path_key(link)
            if not target_path or target_path == page_path:
                continue
            incoming_sources_by_path[target_path][page_path] += 1
            incoming_counts_by_path[target_path] += 1

    source_counts: Counter[str] = Counter()
    node_source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    chains: list[list[_HierarchyItem]] = []
    page_chain_by_id: dict[int, list[_HierarchyItem]] = {}
    page_source_by_id: dict[int, str] = {}

    for page in pages:
        if not page.url:
            page_chain_by_id[page.id] = []
            page_source_by_id[page.id] = ""
            continue
        chain: list[_HierarchyItem] = []
        source = ""
        html_text = _safe_page_content_html(page)
        if html_text:
            breadcrumbs = _extract_breadcrumbs(html_text, base_url)
            chain = _breadcrumb_chain_for_page(page.url, breadcrumbs=breadcrumbs, max_depth=max_depth)
            if chain:
                source = "breadcrumbs"
        if not chain and menu_paths_by_depth:
            chain = _menu_chain_for_page(
                page.url,
                menu_parent_by_path=menu_parent_by_path,
                menu_title_by_path=menu_title_by_path,
                menu_paths_by_depth=menu_paths_by_depth,
                max_depth=max_depth,
            )
            if chain:
                source = "menu"
        if not chain and incoming_sources_by_path:
            chain = _link_chain_for_page(
                page.url,
                incoming_sources_by_path=incoming_sources_by_path,
                incoming_counts_by_path=incoming_counts_by_path,
                page_by_path=page_by_path_obj,
                anchor_texts_by_path=anchor_texts_by_path,
                max_depth=max_depth,
            )
            if chain:
                source = "links"
        if not chain:
            chain = _url_chain_for_page(page.url, max_depth=max_depth)
            source = "url"
        page_chain_by_id[page.id] = chain
        page_source_by_id[page.id] = source

        if not page.is_helper:
            if chain:
                source_counts[source] += 1
                for item in chain:
                    node_source_counts[item.path][source] += 1
            chains.append(chain)

    if pages:
        now = timezone.now()
        for page in pages:
            chain = page_chain_by_id.get(page.id, [])
            levels = [item.name for item in chain[:3]]
            page.cluster_level_1 = levels[0] if len(levels) > 0 else ""
            page.cluster_level_2 = levels[1] if len(levels) > 1 else ""
            page.cluster_level_3 = levels[2] if len(levels) > 2 else ""
            page.cluster_source = page_source_by_id.get(page.id, "")
            page.updated_at = now
        WebsiteScanPage.objects.bulk_update(
            pages,
            ["cluster_level_1", "cluster_level_2", "cluster_level_3", "cluster_source", "updated_at"],
        )

    source_priority = {"breadcrumbs": 3, "menu": 2, "links": 1, "url": 0}
    tree = _build_hierarchy_tree(chains, max_depth=max_depth) if chains else _build_url_tree(urls, max_depth=max_depth)
    if source_counts:
        logger.info(
            "WebsiteScan UI hierarchy sources: id=%s breadcrumbs=%s menu=%s links=%s url=%s",
            scan.id,
            source_counts.get("breadcrumbs", 0),
            source_counts.get("menu", 0),
            source_counts.get("links", 0),
            source_counts.get("url", 0),
        )
    page_rows = [
        {
            "url": page.url,
            "title": page.title,
            "status_code": page.status_code,
            "wordstats": page.wordstats,
            "is_helper": page.is_helper,
        }
        for page in pages
        if page.url
    ]
    page_by_path: dict[str, dict] = {}
    for row in page_rows:
        url = row.get("url")
        if not url:
            continue
        key = _path_key(str(url))
        if key not in page_by_path:
            page_by_path[key] = row
            continue
        # Prefer non-helper metadata when duplicates exist.
        if page_by_path[key].get("is_helper") and not row.get("is_helper"):
            page_by_path[key] = row

    title = f"Website: {netloc}"
    description = f"Auto-generated website tree for {base_url} ({len(urls)} pages)"

    with transaction.atomic():
        if scan.mind_map_id:
            mind_map = MindMap.objects.filter(owner=client, id=scan.mind_map_id).first()
        else:
            mind_map = None

        if mind_map is None:
            mind_map = MindMap.objects.create(
                owner=client,
                title=title,
                description=description,
                type="website",
                is_public=False,
            )
        else:
            mind_map.title = title
            mind_map.description = description
            mind_map.type = "website"
            mind_map.save(update_fields=["title", "description", "type", "updated_at"])
            _reset_mind_map(mind_map.id)

        GAP_Y = 44.0
        GAP_X = 112.0
        positions = _compute_tree_layout_positions(tree, gap_x=GAP_X, gap_y=GAP_Y)

        mind_node_by_path: dict[str, MindNode] = {}

        for node in _iter_tree(tree):
            page_url = base_url.rstrip("/") + node.path if node.path != "/" else base_url
            matched_page = page_by_path.get(node.path)
            page_title = (str(matched_page.get("title") or "").strip() if matched_page else "")
            node_label = _normalize_label(node.name)
            display_name = netloc if node.depth == 0 else (node_label or page_title or node.name)
            if len(display_name) > 80:
                display_name = display_name[:77].rstrip() + "..."
            meta = {
                "entity": "website",
                "metric_type": (str(matched_page.get("url") or page_url) if matched_page else page_url),
                "path": node.path,
                "url": page_url,
                "depth": node.depth,
                "count": node.count,
                "is_root": node.depth == 0,
            }
            source_counts_for_node = node_source_counts.get(node.path)
            if source_counts_for_node:
                meta["cluster_sources"] = dict(source_counts_for_node)
                best_source = _best_cluster_source(source_counts_for_node, priority=source_priority)
                if best_source:
                    meta["cluster_source"] = best_source
            if matched_page:
                meta.update(
                    {
                        "page_url": matched_page.get("url"),
                        "status_code": matched_page.get("status_code"),
                        "page_title": matched_page.get("title"),
                        "wordstats": matched_page.get("wordstats") or [],
                    }
                )

            mind_node = MindNode.objects.create(
                map_id=mind_map.id,
                text=display_name,
                meta=meta,
            )
            mind_node_by_path[node.path] = mind_node

            x, y = positions.get(node.path, (float(node.depth) * GAP_X, 0.0))
            MindNodePosition.objects.create(node=mind_node, layout_name="default", x=x, y=y)

            if matched_page and matched_page.get("wordstats"):
                top_words: list[MindNodeProperty] = []
                for idx, item in enumerate((matched_page.get("wordstats") or [])[:6]):
                    word = str(item.get("word") or "").strip()
                    if not word:
                        continue
                    count = item.get("count")
                    try:
                        count_value = int(count)
                    except (TypeError, ValueError):
                        count_value = 0
                    top_words.append(
                        MindNodeProperty(
                            node=mind_node,
                            title=word,
                            value=str(count_value),
                            delta=None,
                            order_index=idx,
                            meta={},
                        )
                    )
                if top_words:
                    MindNodeProperty.objects.bulk_create(top_words)

        edges: list[MindEdge] = []
        for parent in _iter_tree(tree):
            for child_key, child in parent.children.items():
                from_node = mind_node_by_path.get(parent.path)
                to_node = mind_node_by_path.get(child.path)
                if not from_node or not to_node:
                    continue
                edges.append(
                    MindEdge(
                        map_id=mind_map.id,
                        from_node_id=from_node.id,
                        to_node_id=to_node.id,
                        type="default",
                        label=None,
                        meta={"source_side": "right", "target_side": "left", "arrow": "forward"},
                    )
                )
        if edges:
            MindEdge.objects.bulk_create(edges)

        return mind_map.id


def run_website_scan(scan_id: int) -> None:
    scan = WebsiteScan.objects.select_related("client").get(id=scan_id)

    base_url = _normalize_base_url(scan.base_url)
    if base_url != scan.base_url:
        scan.base_url = base_url
        scan.save(update_fields=["base_url", "updated_at"])

    logger.info("WebsiteScan start: id=%s base=%s", scan.id, base_url)

    scan.status = WebsiteScan.STATUS_IN_PROGRESS
    scan.started_at = timezone.now()
    scan.progress = 0
    scan.error = ""
    scan.pages_total = None
    scan.save(update_fields=["status", "started_at", "progress", "error", "pages_total", "updated_at"])

    with httpx.Client(
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "SEO-Audit-Bot/1.0"},
        http2=_HTTP2_AVAILABLE,
    ) as client:
        if not _HTTP2_AVAILABLE:
            logger.info("WebsiteScan http2 disabled (missing dependency: h2)")
        # Resolve possible redirects (e.g. to www) and crawl the final origin.
        try:
            resp = client.get(base_url)
            effective_url = str(getattr(resp, "url", "") or "") or base_url
            effective_origin = _normalize_base_url(effective_url)
            logger.info(
                "WebsiteScan home preflight: id=%s requested=%s effective=%s status=%s content_type=%s",
                scan.id,
                base_url,
                effective_origin,
                getattr(resp, "status_code", None),
                (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower(),
            )
            if effective_origin != base_url:
                base_url = effective_origin
                scan.base_url = base_url
                scan.save(update_fields=["base_url", "updated_at"])
        except httpx.HTTPError as exc:
            logger.info("WebsiteScan home preflight failed: id=%s base=%s error=%s", scan.id, base_url, exc)

        robots = _fetch_robots(client, base_url)
        scan.robots_url = robots.robots_url
        scan.robots_txt = robots.robots_txt or ""

        sitemap_urls = _detect_sitemaps(client, base_url, robots.sitemap_urls)
        scan.sitemap_urls = sitemap_urls
        scan.save(update_fields=["robots_url", "robots_txt", "sitemap_urls", "updated_at"])

        robots_policy = robots.policy

        WebsiteScanPage.objects.filter(scan=scan).delete()

        def _can_fetch(url: str, user_agent: str) -> bool:
            if not robots_policy:
                return True
            try:
                return bool(robots_policy.can_fetch(user_agent, url))
            except Exception:
                return True

        max_pages = int(scan.max_pages or 100)
        max_depth = int(scan.max_depth or 3)

        logger.info(
            "WebsiteScan crawl config: id=%s max_pages=%s max_depth=%s robots=%s",
            scan.id,
            max_pages,
            max_depth,
            "present" if robots_policy else "missing",
        )

        seen_urls: set[str] = set()
        pages_done = 0
        last_progress_update = monotonic()

        def _maybe_update_progress() -> None:
            nonlocal last_progress_update
            now = monotonic()
            # Update at most every ~10 seconds to reduce DB writes.
            if now - last_progress_update < 10.0:
                return
            last_progress_update = now
            denominator = int(scan.pages_total or 0) or max_pages
            scan.progress = min(99, int(pages_done / max(1, denominator) * 100))
            scan.save(update_fields=["progress", "updated_at"])

        def _fetch_and_store(
            url: str,
            *,
            store_blocked: bool = False,
            is_helper: bool = False,
        ) -> WebsiteScanPage | None:
            nonlocal pages_done
            url = _canonicalize_url(base_url, url) or url
            if not url:
                return None
            url = _force_base_origin(base_url, url)
            if url in seen_urls:
                return None
            if not _is_same_origin(base_url, url):
                return None
            if not _looks_like_html_page(url):
                return None
            seen_urls.add(url)

            can_fetch_all = _can_fetch(url, "*")
            can_fetch_googlebot = _can_fetch(url, "Googlebot")
            if not can_fetch_all:
                if not store_blocked:
                    return None
                logger.info("WebsiteScan blocked by robots: id=%s url=%s", scan.id, url)

                depth_value = min(_url_depth_from_path(url), max_depth)
                page = WebsiteScanPage.objects.create(
                    scan=scan,
                    url=url,
                    parent=None,
                    depth=depth_value,
                    status_code=None,
                    content_type="",
                    title="",
                    meta_description="",
                    headings={},
                    wordstats=[],
                    can_fetch_all=False,
                    can_fetch_googlebot=can_fetch_googlebot,
                    is_helper=is_helper,
                    fetched_at=None,
                )
                if not is_helper:
                    pages_done += 1
                _maybe_update_progress()
                return page

            status_code = None
            content_type = ""
            title = ""
            meta_description = ""
            headings: dict = {}
            wordstats: list[dict] = []
            html_text: str | None = None

            try:
                resp = client.get(url)
                status_code = resp.status_code
                content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                if status_code == 200 and content_type in {"text/html", "application/xhtml+xml"}:
                    html_text = resp.text
            except httpx.HTTPError:
                html_text = None

            depth_value = min(_url_depth_from_path(url), max_depth)
            if html_text:
                title, meta_description, headings = _extract_page_metadata(html_text)
                wordstats = _compute_wordstats_from_html(html_text, top_n=6)

            page = WebsiteScanPage.objects.create(
                scan=scan,
                url=url,
                parent=None,
                depth=depth_value,
                status_code=status_code,
                content_type=content_type,
                title=title,
                meta_description=meta_description,
                headings=headings or {},
                wordstats=wordstats or [],
                can_fetch_all=can_fetch_all,
                can_fetch_googlebot=can_fetch_googlebot,
                is_helper=is_helper,
                fetched_at=timezone.now() if status_code else None,
            )
            if not is_helper:
                pages_done += 1

            if html_text:
                try:
                    WebsiteScanPageContent.objects.create(
                        page=page,
                        content_text=_extract_content_text(html_text),
                        content_html=html_text[:200_000],
                    )
                except Exception:
                    logger.warning("Failed to store content for %s", url, exc_info=True)

            _maybe_update_progress()
            return page

        # Strategy:
        # - If sitemap yields URLs, use it as a primary source for building the URL-path tree.
        # - Otherwise, crawl links from the homepage and expand up to `max_pages`.
        sitemap_page_urls: list[str] = []
        normalized: list[str] = []
        if sitemap_urls:
            for sitemap in sitemap_urls[:3]:
                sitemap_page_urls.extend(_fetch_sitemap_urls(client, sitemap, max_sitemaps=10, max_urls=5000))
                if len(sitemap_page_urls) >= 5000:
                    break
            seen: set[str] = set()
            for u in sitemap_page_urls:
                cu = _canonicalize_url(base_url, u)
                if not cu:
                    continue
                cu = _force_base_origin(base_url, cu)
                if not _is_same_origin(base_url, cu):
                    continue
                if not _looks_like_html_page(cu):
                    continue
                if cu in seen:
                    continue
                seen.add(cu)
                normalized.append(cu)

        if normalized:
            def _group_key(url: str) -> str:
                path = (urlparse(url).path or "/").strip("/")
                if not path:
                    return "/"
                return path.split("/", 1)[0]

            groups: dict[str, list[str]] = defaultdict(list)
            for url in normalized:
                groups[_group_key(url)].append(url)

            # Pick representative deep URLs per section first (so small max_pages still shows hierarchy),
            # then fill remaining slots from the same ordering.
            ordered_keys = sorted(groups.keys(), key=lambda key: (len(groups[key]), key), reverse=True)
            per_key_sorted: dict[str, list[str]] = {}
            for key in ordered_keys:
                urls = groups[key]
                per_key_sorted[key] = sorted(urls, key=_url_depth_from_path, reverse=True)

            selected: list[str] = []
            seen_selected: set[str] = set()

            # Pass 1: one per group
            for key in ordered_keys:
                for url in per_key_sorted[key]:
                    if url in seen_selected:
                        continue
                    selected.append(url)
                    seen_selected.add(url)
                    break
                if len(selected) >= max_pages:
                    break

            # Pass 2+: round-robin fill
            key_index = 0
            while len(selected) < max_pages and ordered_keys:
                key = ordered_keys[key_index]
                key_index = (key_index + 1) % len(ordered_keys)
                for url in per_key_sorted[key]:
                    if url in seen_selected:
                        continue
                    selected.append(url)
                    seen_selected.add(url)
                    break
                else:
                    # no more urls in this group
                    if all(all(u in seen_selected for u in per_key_sorted[k]) for k in ordered_keys):
                        break

            sitemap_page_urls = selected[:max_pages]

        if sitemap_page_urls:
            logger.info("WebsiteScan strategy: id=%s source=sitemap urls=%s", scan.id, len(sitemap_page_urls))
            primary_targets: list[str] = []
            seen_primary: set[str] = set()

            def _add_primary(raw_url: str) -> None:
                cu = _canonicalize_url(base_url, raw_url)
                if not cu:
                    return
                cu = _force_base_origin(base_url, cu)
                if not _is_same_origin(base_url, cu):
                    return
                if not _looks_like_html_page(cu):
                    return
                if cu in seen_primary:
                    return
                seen_primary.add(cu)
                primary_targets.append(cu)

            # Primary pages define progress total (exclude helper prefix pages).
            for u in [base_url, *sitemap_page_urls]:
                _add_primary(u)
                if len(primary_targets) >= max_pages:
                    break

            scan.pages_total = len(primary_targets)
            scan.save(update_fields=["pages_total", "updated_at"])

            helper_targets: list[str] = []
            seen_helper: set[str] = set()
            remaining_helper_budget = max(0, max_pages - len(primary_targets))
            if remaining_helper_budget:
                for u in primary_targets:
                    for prefix_path in _iter_url_path_prefixes(u, max_depth=max_depth):
                        hu = _url_from_base_and_path(base_url, prefix_path)
                        if hu in seen_primary or hu in seen_helper:
                            continue
                        seen_helper.add(hu)
                        helper_targets.append(hu)
                        if len(helper_targets) >= remaining_helper_budget:
                            break
                    if len(helper_targets) >= remaining_helper_budget:
                        break

            for u in helper_targets:
                _fetch_and_store(u, store_blocked=True, is_helper=True)

            for u in primary_targets:
                _fetch_and_store(u, store_blocked=True, is_helper=False)
        else:
            logger.info("WebsiteScan strategy: id=%s source=links", scan.id)
            queue: deque[tuple[str, int]] = deque()
            queue.append((base_url, 0))
            discovered: set[str] = set()

            while queue and len(seen_urls) < max_pages:
                current_url, depth = queue.popleft()
                if depth > max_depth:
                    continue
                canonical = _canonicalize_url(base_url, current_url)
                if not canonical:
                    continue
                canonical = _force_base_origin(base_url, canonical)
                if canonical in discovered:
                    continue
                discovered.add(canonical)

                page = _fetch_and_store(canonical, store_blocked=False, is_helper=False)
                if not page:
                    continue

                if not page.content_type or page.content_type not in {"text/html", "application/xhtml+xml"}:
                    continue

                # We need HTML to extract links; fetch again only when needed.
                try:
                    resp = client.get(canonical)
                    content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    if resp.status_code != 200 or content_type not in {"text/html", "application/xhtml+xml"}:
                        continue
                    html_text = resp.text
                except httpx.HTTPError:
                    continue

                links = _extract_links(html_text, base_url)
                if canonical == base_url:
                    logger.info("WebsiteScan home links: id=%s count=%s", scan.id, len(links))

                for link in links:
                    if len(seen_urls) >= max_pages:
                        break
                    link = _canonicalize_url(base_url, link)
                    if not link:
                        continue
                    link = _force_base_origin(base_url, link)
                    if not _is_same_origin(base_url, link):
                        continue
                    if not _looks_like_html_page(link):
                        continue

                    # If we discovered a deep URL, also enqueue its parent path pages so the tree
                    # has intermediate nodes with titles (e.g. /context).
                    next_depth = depth + 1
                    for prefix_path in _iter_url_path_prefixes(link, max_depth=max_depth):
                        queue.append((_url_from_base_and_path(base_url, prefix_path), next_depth))
                    queue.append((link, next_depth))

        mind_map_id: int | None = None
        if not pages_done and not WebsiteScanPage.objects.filter(scan=scan).exists():
            scan.progress = 100
            scan.status = WebsiteScan.STATUS_FAILED
            scan.finished_at = timezone.now()
            scan.error = (scan.error or "").strip() or "Не удалось обнаружить ни одной страницы (robots.txt мог запрещать обход)."
            scan.save(update_fields=["progress", "status", "finished_at", "error", "updated_at"])
            logger.info("WebsiteScan finished empty: id=%s base=%s", scan.id, base_url)
            return

        try:
            mind_map_id = _build_mind_map_for_scan(scan)
        except Exception as exc:
            logger.error("Failed to build mind map for WebsiteScan %s: %s", scan.id, exc, exc_info=True)
            scan.error = (scan.error or "").strip() or f"Mind map build failed: {exc}"

        scan.mind_map_id = mind_map_id
        scan.progress = 100
        scan.status = WebsiteScan.STATUS_COMPLETED
        scan.finished_at = timezone.now()
        scan.save(update_fields=["mind_map_id", "progress", "status", "finished_at", "error", "updated_at"])
        logger.info("WebsiteScan finished: id=%s pages=%s mind_map_id=%s", scan.id, pages_done, mind_map_id)
