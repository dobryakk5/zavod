import os
import time
import random
import psycopg2
from typing import Dict, Optional

from bs4 import BeautifulSoup

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
# DB utils
# ==========================
def table_name(name: str) -> str:
    return f"{DB_SCHEMA}.{name}" if DB_SCHEMA else name


def db():
    return psycopg2.connect(PG_DSN)


# ==========================
# random sleep
# ==========================
def random_sleep(min_sec: int = 1, max_sec: int = 10):
    delay = random.uniform(min_sec, max_sec)
    print(f"-> Sleep {delay:.2f}s")
    time.sleep(delay)


# ==========================
# LOAD EMPTY CATEGORIES
# ==========================
def load_empty_categories():
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                c.slug,
                c.title,
                c.url
            FROM {table_name('tgstat_categories')} c
            LEFT JOIN {table_name('tgstat_tags')} t
              ON t.category_slug = c.slug
            GROUP BY c.slug, c.title, c.url
            HAVING COUNT(t.slug) = 0
            ORDER BY c.slug
            """
        )

        return [
            {
                "slug": row[0],
                "title": row[1],
                "url": row[2],
            }
            for row in cur.fetchall()
        ]


# ==========================
# PARSE SUBCATEGORIES
# ==========================
def extract_tag_slug(href: str) -> str:
    return href.strip("/").split("/tag/", 1)[-1]


def fetch_subgroups_for_category(category):
    r = fetch_tgstat_page(category["url"], headers=HEADERS, cookies=COOKIES)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    tags = {}

    for card in soup.select("div.card.card-body"):
        tag_link = card.select_one("div.font-18 a")
        if not tag_link:
            continue

        href = tag_link.get("href")
        if not href or "/tag/" not in href:
            continue

        tag_slug = extract_tag_slug(href)

        tag = {
            "slug": tag_slug,
            "title": tag_link.get_text(strip=True),
            "url": BASE_URL + href,
            "category_slug": category["slug"],
            "more": 0,
        }

        more = card.select_one("div.font-12 b")
        if more:
            tag["more"] = parse_count(more.get_text(strip=True))

        tags[tag_slug] = tag

    return list(tags.values())


# ==========================
# SAVE TAGS
# ==========================
def save_tags(tags):
    if not tags:
        return

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


# ==========================
# MAIN
# ==========================
def main():
    print("-> Load empty categories")
    categories = load_empty_categories()

    if not categories:
        print("-> No empty categories found")
        return

    print(f"-> Found {len(categories)} empty categories")

    did_fetch = False

    for category in categories:
        if did_fetch:
            random_sleep(1, 10)

        print(f"-> Fetch subcategories for {category['slug']}")
        tags = fetch_subgroups_for_category(category)

        print(f"   -> Found {len(tags)} tags")
        save_tags(tags)

        did_fetch = True

    print("Done (empty categories)")


if __name__ == "__main__":
    main()
