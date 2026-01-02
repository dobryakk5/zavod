from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Iterator
from urllib.parse import urljoin, urlparse, urlunparse

import gzip

import httpx
from bs4 import BeautifulSoup
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

    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_tag and meta_tag.get("content"):
        meta_description = str(meta_tag.get("content") or "").strip()

    meta_keywords = ""
    keywords_tag = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
    if keywords_tag and keywords_tag.get("content"):
        meta_keywords = str(keywords_tag.get("content") or "").strip()

    def _texts(selector: str) -> list[str]:
        items: list[str] = []
        for tag in soup.select(selector):
            text = tag.get_text(" ", strip=True)
            if text:
                items.append(text)
        return items

    headings = {
        "h1": _texts("h1")[:10],
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
            if seg not in node.children:
                node.children[seg] = _TreeNode(name=seg, path=current_path, depth=i + 1)
            node = node.children[seg]
            node.count += 1

    return root


def _iter_tree(node: _TreeNode) -> Iterator[_TreeNode]:
    yield node
    for key in sorted(node.children.keys()):
        yield from _iter_tree(node.children[key])


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

    primary_rows = WebsiteScanPage.objects.filter(scan=scan, is_helper=False).values_list("url", flat=True).order_by("id")
    urls = [u for u in primary_rows if u]
    tree = _build_url_tree(urls, max_depth=int(scan.max_depth or 3))
    page_rows = WebsiteScanPage.objects.filter(scan=scan).values("url", "title", "status_code", "wordstats", "is_helper").order_by("id")
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

        GAP_Y = 220.0
        GAP_X = 560.0
        positions = _compute_tree_layout_positions(tree, gap_x=GAP_X, gap_y=GAP_Y)

        mind_node_by_path: dict[str, MindNode] = {}

        for node in _iter_tree(tree):
            page_url = base_url.rstrip("/") + node.path if node.path != "/" else base_url
            matched_page = page_by_path.get(node.path)
            page_title = (str(matched_page.get("title") or "").strip() if matched_page else "")
            display_name = netloc if node.depth == 0 else (page_title or node.name)
            meta = {
                "entity": "website",
                "metric_type": (str(matched_page.get("url") or page_url) if matched_page else page_url),
                "path": node.path,
                "url": page_url,
                "depth": node.depth,
                "count": node.count,
                "is_root": node.depth == 0,
            }
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
            # Update at most every ~2 seconds to reduce DB writes.
            if now - last_progress_update < 5.0 and pages_done % 3 != 0:
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
