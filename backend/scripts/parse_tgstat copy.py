import os
import re
import time
from typing import Dict, Optional

import psycopg2
import requests as standard_requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    load_dotenv = None
    DOTENV_AVAILABLE = False

BASE_URL = "https://tgstat.ru"
REQUEST_TIMEOUT = 20

DOTENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
if DOTENV_AVAILABLE and os.path.exists(DOTENV_PATH):
    load_dotenv(DOTENV_PATH, override=False)

PG_DSN = (
    os.getenv("TGSTAT_PG_DSN")
    or os.getenv("DATABASE_URL")
    or "dbname=tgstat user=postgres password=postgres host=localhost port=5432"
)
DB_SCHEMA = os.getenv("TGSTAT_SCHEMA", "map").strip()

# ==========================
# curl_cffi
# ==========================
try:
    from curl_cffi import requests as curl_requests

    CURL_CFFI_AVAILABLE = True
    print("[INFO] TGSTAT: using curl_cffi")
except ImportError:
    curl_requests = None
    CURL_CFFI_AVAILABLE = False
    print("[WARNING] TGSTAT: curl_cffi not installed, using requests fallback")

# ==========================
# HEADERS
# ==========================
DEFAULT_TGSTAT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

HEADERS = {**DEFAULT_TGSTAT_HEADERS, "Referer": "https://tgstat.ru/"}

COOKIES = {
    "_ym_uid": "1766563088115253783",
    "_ym_d": "1766563088",
    "tgstat_idrk": "f42e71c821bf075ed23d7c9ff2e7e2c1a0e4cdbddcf769f0d6da948ed2183e19a%3A2%3A%7Bi%3A0%3Bs%3A11%3A%22tgstat_idrk%22%3Bi%3A1%3Bs%3A53%3A%22%5B13840610%2C%22sN0ZYVPFEYL160enEq47gBFhkBpowTA_%22%2C2592000%5D%22%3B%7D",
    "_tgstat_csrk": "b01ae69c3943e46c9cf5ec7366b4b4987f1f003c404cab0e0b3d7542225d9c59a%3A2%3A%7Bi%3A0%3Bs%3A12%3A%22_tgstat_csrk%22%3Bi%3A1%3Bs%3A32%3A%22ZjGaG8b0qSePywaRVNag6sWxgf7vRPjv%22%3B%7D",
    "_ga": "GA1.1.1429799223.1768559301",
    "_ga_ZEKJ7V8PH3": "GS2.1.s1768559301$o1$g1$t1768559384$j60$l0$h0",
    "cf_clearance": "26Os1hHvJMYFKOC69gXD355YTQvwePKu9kiJo2tvcsE-1768725158-1.2.1.1-BzXwjE3JlOsBqNs_j_V8ka1mCGuWZpU4B018SateB6hmzOqMBHWXnvtqt8YQYm0cRIuMnXhGJ23Pzp7qH3U1tG2n5X2ll9bEnmQCuAnO3HJ5NfCxmhrkmbQ3l4hTptpCnaD99G6kgx_OzcxzGzf5J_H1YjIgB3KD2Rli_cgcO44L5z1sJN59r7wn5tXfFM9QHzeQkk8bPo5fYgY7ipUvarPXNI.Yb8gTq92C2y8F7hI",
    "tgstat_settings": "0b1417a3039c45770c8cdf52e5361bea554baea7c8061b0fa029463d663c45b1a%3A2%3A%7Bi%3A0%3Bs%3A15%3A%22tgstat_settings%22%3Bi%3A1%3Bs%3A35%3A%22%7B%22fp%22%3A%22T7t4u8mVkl%22%2C%22theme%22%3A%22light%22%7D%22%3B%7D",
    "_tgstat_userlang": "a9c55d7d0ccdcd622b74ac6715f1b7fc3c850f3b8cb694e2ce0421457145cd18a%3A2%3A%7Bi%3A0%3Bs%3A16%3A%22_tgstat_userlang%22%3Bi%3A1%3Bs%3A2%3A%22ru%22%3B%7D",
    "tgstat_sirk": "tfopbbdk9gpt3a8pccvg8pl1ui",
}

SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


if DB_SCHEMA and not SCHEMA_RE.match(DB_SCHEMA):
    raise ValueError("TGSTAT_SCHEMA must be a valid SQL identifier.")


def parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


PROGRESS_FILE = os.getenv(
    "TGSTAT_PROGRESS_FILE",
    os.path.join(os.path.dirname(__file__), ".tgstat_progress.txt"),
).strip()
RESUME_ENABLED = parse_bool(os.getenv("TGSTAT_RESUME", "1"), default=True)
RESET_PROGRESS = parse_bool(os.getenv("TGSTAT_RESET_PROGRESS", "0"))
TAG_SLEEP = int(os.getenv("TGSTAT_TAG_SLEEP", "15"))
CATEGORY_SLEEP = int(os.getenv("TGSTAT_CATEGORY_SLEEP", "1"))

if not PROGRESS_FILE:
    RESUME_ENABLED = False


def table_name(name: str) -> str:
    if DB_SCHEMA:
        return f"{DB_SCHEMA}.{name}"
    return name


def parse_count(raw: str) -> int:
    if not raw:
        return 0
    raw = raw.strip().lower().replace("\xa0", "").replace(" ", "")
    raw = raw.replace(",", ".")
    if not raw:
        return 0
    if raw.endswith("k"):
        return int(float(raw[:-1]) * 1000)
    if raw.endswith("m"):
        return int(float(raw[:-1]) * 1_000_000)
    try:
        return int(float(raw))
    except ValueError:
        return 0


def db():
    return psycopg2.connect(PG_DSN)


def fetch_tgstat_page(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    proxy: Optional[str] = None,
    timeout: int = REQUEST_TIMEOUT,
    allow_redirects: bool = True,
    impersonate: str = "chrome124",
):
    headers = headers or DEFAULT_TGSTAT_HEADERS
    cookies = cookies or {}

    if CURL_CFFI_AVAILABLE and curl_requests:
        session = curl_requests.Session()
        params = {
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
            "impersonate": impersonate,
        }
        if cookies:
            params["cookies"] = cookies
        if proxy:
            params["proxies"] = {"http": proxy, "https": proxy}

        return session.get(url, **params)

    session = standard_requests.Session()
    if cookies:
        session.cookies.update(cookies)
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    return session.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=allow_redirects,
    )


def load_progress(path: str) -> set[str]:
    if not RESUME_ENABLED:
        return set()
    if RESET_PROGRESS and os.path.exists(path):
        os.remove(path)
        return set()
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def mark_progress(path: str, processed: set[str], tag_slug: str) -> None:
    if not RESUME_ENABLED or not tag_slug or tag_slug in processed:
        return
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{tag_slug}\n")
    processed.add(tag_slug)


def extract_slug(href: str) -> str:
    path = urlparse(href).path if "://" in href else href
    return path.strip("/").strip()


def extract_tag_slug(href: str) -> str:
    path = urlparse(href).path if "://" in href else href
    if "/tag/" in path:
        return path.split("/tag/", 1)[1].strip("/")
    return path.strip("/")


def extract_username(href: str) -> str:
    path = urlparse(href).path if "://" in href else href
    return path.split("@")[-1].split("/")[0].strip()


def parse_tag_channels(html: str, tag_slug: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("div.lm-list-container")

    if not container:
        return []

    channels = []

    for card in container.select("div.card.peer-item-box"):
        link = card.select_one("a[href*='/channel/@']")
        if not link:
            continue

        url = link.get("href")
        if not url:
            continue

        username = extract_username(url)
        if not username:
            continue

        title = card.select_one(".font-16.text-dark")
        desc = card.select_one(".font-14.text-muted.line-clamp-2")
        cats = card.select_one(".font-12.text-body")
        subs = card.select_one(".font-12.text-truncate b")
        last_post = card.select_one(
            "div[data-original-title*='Последняя публикация']"
        )

        channels.append(
            {
                "tag_slug": tag_slug,
                "username": username,
                "title": title.get_text(strip=True) if title else None,
                "description": desc.get_text(strip=True) if desc else None,
                "categories": cats.get_text(strip=True) if cats else None,
                "subscribers": parse_count(subs.get_text(strip=True)) if subs else None,
                "last_post_raw": last_post.get_text(strip=True) if last_post else None,
                "url": urljoin(BASE_URL, url),
            }
        )

    return channels


def fetch_categories():
    r = fetch_tgstat_page(BASE_URL, headers=HEADERS, cookies=COOKIES)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    html = r.text

    print("HTML length:", len(html))
    print("HTML head:", html[:500].replace("\n", " "))

    with open("tgstat_home_debug.html", "w", encoding="utf-8") as f:
        f.write(html)

    slides = soup.select("div.slick-slide[data-slick-index]")
    #if not slides: raise RuntimeError("TGSTAT: no slick slides found on homepage")

    categories = {}

    slides = soup.select("div.slick-slide[data-slick-index]")

    for slide in slides:
        slide_index = int(slide.get("data-slick-index", -1))

        item = slide.select_one("div.slick-slider-item")
        if not item:
            continue

        row = item.select_one("div.row.align-items-center")
        if not row:
            continue

        cols = row.select("div.col")
        i = 0

        while i < len(cols) - 1:
            left = cols[i]
            right = cols[i + 1]

            link = left.select_one("a.text-dark[href]")
            if not link:
                i += 1
                continue

            href = link["href"]
            slug = extract_slug(href)

            categories[slug] = {
                "slug": slug,
                "title": link.get_text(strip=True),
                "url": urljoin(BASE_URL, href),
                "channels_count": parse_count(right.get_text(strip=True)),
                "slick_index": slide_index,
            }

            i += 2

    return list(categories.values())




def fetch_subgroups_for_category(category):
    r = fetch_tgstat_page(category["url"], headers=HEADERS, cookies=COOKIES)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    tags = {}

    for card in soup.select("div.card.card-body"):
        tag_link = card.select_one("div.font-18 a")
        if not tag_link:
            continue

        tag_href = tag_link.get("href")
        if not tag_href:
            continue

        tag_slug = extract_tag_slug(tag_href)
        if not tag_slug:
            continue

        tag = {
            "slug": tag_slug,
            "title": tag_link.get_text(strip=True),
            "url": urljoin(BASE_URL, tag_href),
            "category_slug": category["slug"],
            "more": 0,
            "channels": [],
        }

        more = card.select_one("div.font-12 b")
        if more:
            tag["more"] = parse_count(more.get_text(strip=True))

        tags[tag_slug] = tag

    return list(tags.values())


def fetch_tag_channels(tag):
    r = fetch_tgstat_page(tag["url"], headers=HEADERS, cookies=COOKIES)
    r.raise_for_status()
    return parse_tag_channels(r.text, tag["slug"])


def save_categories(categories):
    with db() as conn, conn.cursor() as cur:
        for c in categories:
            cur.execute(
                f"""
                INSERT INTO {table_name('tgstat_categories')}
                (slug, title, url, parsed_at)
                VALUES (%s, %s, %s, NULL)
                ON CONFLICT (slug) DO NOTHING
                """,
                (c["slug"], c["title"], c["url"]),
            )


def mark_category_parsed(category_slug):
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {table_name('tgstat_categories')}
            SET parsed_at = now()
            WHERE slug = %s
            """,
            (category_slug,),
        )


def load_categories_parsed_today(category_slugs):
    if not category_slugs:
        return set()
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT slug
            FROM {table_name('tgstat_categories')}
            WHERE slug = ANY(%s)
              AND parsed_at::date = CURRENT_DATE
            """,
            (category_slugs,),
        )
        return {row[0] for row in cur.fetchall()}


def save_tags(tags):
    with db() as conn, conn.cursor() as cur:
        for t in tags:
            cur.execute(
                f"""
                INSERT INTO {table_name('tgstat_tags')}
                (slug, title, url, category_slug, more_channels_count)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO NOTHING
                """,
                (
                    t["slug"],
                    t["title"],
                    t["url"],
                    t["category_slug"],
                    t["more"],
                ),
            )


def ensure_tag_ids(tag_slugs):
    if not tag_slugs:
        return
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {table_name('tgstat_tags')}
            SET id = DEFAULT
            WHERE slug = ANY(%s) AND id IS NULL
            """,
            (tag_slugs,),
        )


def load_tag_ids(tag_slugs):
    if not tag_slugs:
        return {}
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT slug, id
            FROM {table_name('tgstat_tags')}
            WHERE slug = ANY(%s)
            """,
            (tag_slugs,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def save_tag_channels(tag_slug, tag_id, channels):
    if not channels:
        return
    with db() as conn, conn.cursor() as cur:
        for ch in channels:
            cur.execute(
                f"""
                INSERT INTO {table_name('tgstat_tag_channels')}
                (tag_slug, tag_id, username, title, subscribers, url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    tag_slug,
                    tag_id,
                    ch["username"],
                    ch["title"],
                    ch["subscribers"],
                    ch["url"],
                ),
            )


def main():
    print("-> Fetch categories")
    categories = fetch_categories()

    print("-> Save categories")
    save_categories(categories)

    parsed_today = load_categories_parsed_today([c["slug"] for c in categories])

    processed = load_progress(PROGRESS_FILE)
    did_fetch_categories = False
    did_fetch_tags = False
    all_tags = []

    for category in categories:
        if category["slug"] in parsed_today:
            print(f"-> Skip subgroups for {category['slug']}")
            continue

        if CATEGORY_SLEEP > 0 and did_fetch_categories:
            print(f"-> Sleep {CATEGORY_SLEEP}s")
            time.sleep(CATEGORY_SLEEP)

        print(f"-> Fetch subgroups for {category['slug']}")
        tags = fetch_subgroups_for_category(category)
        save_tags(tags)
        all_tags.extend(tags)
        mark_category_parsed(category["slug"])
        did_fetch_categories = True

    ensure_tag_ids([tag["slug"] for tag in all_tags])
    tag_id_map = load_tag_ids([tag["slug"] for tag in all_tags])

    for tag in all_tags:
        tag_slug = tag["slug"]
        if RESUME_ENABLED and tag_slug in processed:
            print(f"-> Skip channels for {tag_slug}")
            continue

        if TAG_SLEEP > 0 and did_fetch_tags:
            print(f"-> Sleep {TAG_SLEEP}s")
            time.sleep(TAG_SLEEP)

        print(f"-> Fetch channels for {tag_slug}")
        channels = fetch_tag_channels(tag)
        save_tag_channels(tag_slug, tag_id_map.get(tag_slug), channels)
        mark_progress(PROGRESS_FILE, processed, tag_slug)
        did_fetch_tags = True

    print("Done")


if __name__ == "__main__":
    main()
