#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests


def _try_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    # Prefer backend env (where keys usually live)
    load_dotenv("backend/.env")


def _mask(value: str, *, keep_start: int = 4, keep_end: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_start + keep_end + 3:
        return value[:2] + "…" + value[-2:]
    return value[:keep_start] + "…" + value[-keep_end:]


def google_cse_search(query: str, *, api_key: str, cx: str, num: int = 10) -> dict[str, Any]:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": num,
    }
    r = requests.get(url, params=params, timeout=10)
    if not r.ok:
        # Keep raw body to make it easy to debug.
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    return r.json()


def parse_cse_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for i, item in enumerate(data.get("items", []) or [], start=1):
        results.append(
            {
                "position": i,
                "title": item.get("title"),
                "url": item.get("link"),
                "domain": item.get("displayLink"),
                "snippet": item.get("snippet"),
            }
        )
    return results


def main() -> int:
    _try_load_dotenv()

    query = "привлечение клиентов"
    api_key = (os.getenv("Google_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    cx = (os.getenv("CSE_ID") or os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_CX") or "").strip()

    print("Google_API_KEY:", _mask(api_key) if api_key else "(missing)")
    print("CSE_ID:", _mask(cx) if cx else "(missing)")
    print("Query:", query)

    if not api_key or not cx:
        print("Missing env vars: need Google_API_KEY/GOOGLE_API_KEY and CSE_ID/GOOGLE_CSE_ID/GOOGLE_CX", file=sys.stderr)
        return 2

    try:
        data = google_cse_search(query, api_key=api_key, cx=cx, num=10)
    except Exception as exc:
        print("Search failed:", str(exc), file=sys.stderr)
        return 1

    results = parse_cse_results(data)
    print(f"Results: {len(results)}")
    for r in results[:10]:
        print(r["position"], r.get("domain"), r.get("title"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

