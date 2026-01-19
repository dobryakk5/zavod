import os
import time
import random
import psycopg2
from typing import Dict, Optional

from bs4 import BeautifulSoup

# ===== импортируем общее =====
from parse_tgstat import (
    BASE_URL,
    REQUEST_TIMEOUT,
    PG_DSN,
    DB_SCHEMA,
    HEADERS,
    COOKIES,
    TAG_SLEEP,
    PROGRESS_FILE,
    RESUME_ENABLED,
    parse_count,
    fetch_tgstat_page,
    extract_username,
    load_progress,
    mark_progress,
)

# ==========================
# DB utils
# ==========================
def table_name(name: str) -> str:
    return f"{DB_SCHEMA}.{name}" if DB_SCHEMA else name


def db():
    return psycopg2.connect(PG_DSN)

def random_sleep(min_sec: int = 1, max_sec: int = 10):
    delay = random.uniform(min_sec, max_sec)
    print(f"-> Sleep {delay:.2f}s")
    time.sleep(delay)


# ==========================
# LOAD TAGS WITHOUT CHANNELS
# ==========================
def load_tags_without_channels():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                t.slug,
                t.title,
                t.url,
                t.category_slug
            FROM {table_name('tgstat_tags')} t
            LEFT JOIN {table_name('tgstat_tag_channels')} tc
              ON tc.tag_slug = t.slug
            GROUP BY t.slug, t.title, t.url, t.category_slug
            HAVING COUNT(tc.username) = 0
            ORDER BY t.slug
            """
        )

        return [
            {
                "slug": row[0],
                "title": row[1],
                "url": row[2],
                "category_slug": row[3],
            }
            for row in cur.fetchall()
        ]


# ==========================
# TAG IDS
# ==========================
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
            """
            ,
            (tag_slugs,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


# ==========================
# PARSE CHANNELS
# ==========================
def parse_tag_channels(html: str, tag_slug: str):
    soup = BeautifulSoup(html, "lxml")
    container = soup.select_one("div.lm-list-container")

    if not container:
        return []

    channels = []

    for card in container.select("div.card.peer-item-box"):
        link = card.select_one("a[href*='/channel/@']")
        if not link:
            continue

        username = extract_username(link.get("href"))
        if not username:
            continue

        title = card.select_one(".font-16.text-dark")
        subs = card.select_one(".font-12.text-truncate b")

        channels.append(
            {
                "tag_slug": tag_slug,
                "username": username,
                "title": title.get_text(strip=True) if title else None,
                "subscribers": parse_count(subs.get_text(strip=True)) if subs else None,
                "url": link.get("href"),
            }
        )

    return channels


def fetch_tag_channels(tag):
    r = fetch_tgstat_page(tag["url"], headers=HEADERS, cookies=COOKIES)
    r.raise_for_status()
    return parse_tag_channels(r.text, tag["slug"])


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


# ==========================
# MAIN
# ==========================
def main():
    print("-> Load tags without channels")
    tags = load_tags_without_channels()

    if not tags:
        print("-> No empty tags found")
        return

    print(f"-> Found {len(tags)} empty tags")

    ensure_tag_ids([t["slug"] for t in tags])
    tag_id_map = load_tag_ids([t["slug"] for t in tags])

    processed = load_progress(PROGRESS_FILE)
    did_fetch = False

    for tag in tags:
        slug = tag["slug"]

        if RESUME_ENABLED and slug in processed:
            print(f"-> Skip {slug}")
            continue

        if did_fetch:
            random_sleep(1, 10)

        print(f"-> Fetch channels for {slug}")
        channels = fetch_tag_channels(tag)

        save_tag_channels(
            slug,
            tag_id_map.get(slug),
            channels,
        )

        mark_progress(PROGRESS_FILE, processed, slug)
        did_fetch = True


    print("Done")


if __name__ == "__main__":
    main()
