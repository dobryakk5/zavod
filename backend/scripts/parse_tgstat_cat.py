import time
import random
import psycopg2
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from parse_tgstat import (
    BASE_URL,
    PG_DSN,
    DB_SCHEMA,
    HEADERS,
    COOKIES,
    fetch_tgstat_page,
    parse_count,
)

# ==========================
# DB
# ==========================
def db():
    return psycopg2.connect(PG_DSN)


def table(name: str) -> str:
    return f"{DB_SCHEMA}.{name}" if DB_SCHEMA else name


# ==========================
# utils
# ==========================
def random_sleep(min_sec=1, max_sec=10):
    delay = random.uniform(min_sec, max_sec)
    print(f"-> Sleep {delay:.2f}s")
    time.sleep(delay)


def extract_username(url: str) -> str | None:
    if not url:
        return None
    path = urlparse(url).path
    if "/channel/@" not in path:
        return None
    return path.split("/channel/@", 1)[1].strip("/")


# ==========================
# LOAD CATEGORIES
# ==========================
def load_categories():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, slug, title, url
            FROM {table('tgstat_categories')}
            ORDER BY id
            """
        )
        return [
            {
                "id": row[0],
                "slug": row[1],
                "title": row[2],
                "url": row[3],
            }
            for row in cur.fetchall()
        ]

# ------ 0

def load_categories_without_channels():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                c.id,
                c.slug,
                c.title,
                c.url
            FROM {table('tgstat_categories')} c
            LEFT JOIN {table('tgstat_tag_channels')} tc
              ON tc.category_id = c.id
            GROUP BY
                c.id, c.slug, c.title, c.url
            HAVING COUNT(tc.id) = 0
            ORDER BY c.id
            """
        )

        return [
            {
                "id": row[0],
                "slug": row[1],
                "title": row[2],
                "url": row[3],
            }
            for row in cur.fetchall()
        ]


# ==========================
# PARSE CHANNELS FROM CATEGORY
# ==========================
def parse_category_channels(html: str, category_id: int):
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
        username = extract_username(url)
        if not username:
            continue

        title = card.select_one(".font-16.text-dark")
        subs = card.select_one(".font-12.text-truncate b")

        channels.append(
            {
                "username": username,
                "title": title.get_text(strip=True) if title else None,
                "subscribers": parse_count(subs.get_text(strip=True)) if subs else None,
                "url": BASE_URL + url if url.startswith("/") else url,
                "category_id": category_id,
            }
        )

    return channels


# ==========================
# SAVE
# ==========================
def save_category_channels(channels):
    if not channels:
        return

    with db() as conn, conn.cursor() as cur:
        for ch in channels:
            cur.execute(
                f"""
                INSERT INTO {table('tgstat_tag_channels')}
                (
                    tag_slug,
                    tag_id,
                    category_id,
                    username,
                    title,
                    subscribers,
                    url
                )
                VALUES (
                    NULL,
                    NULL,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    ch["category_id"],
                    ch["username"],
                    ch["title"],
                    ch["subscribers"],
                    ch["url"],
                ),
            )


# ==========================
# MAIN
# ==========================
def main():
    #categories = load_categories()
    categories = load_categories_without_channels()

    print(f"-> Loaded {len(categories)} categories")

    did_fetch = False

    for cat in categories:
        if did_fetch:
            random_sleep(1, 10)

        print(f"-> Fetch channels for category {cat['slug']}")

        r = fetch_tgstat_page(cat["url"], headers=HEADERS, cookies=COOKIES)
        r.raise_for_status()

        channels = parse_category_channels(r.text, cat["id"])
        print(f"   -> Found {len(channels)} channels")

        save_category_channels(channels)
        did_fetch = True

    print("Done")


if __name__ == "__main__":
    main()
