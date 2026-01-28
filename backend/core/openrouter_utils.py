"""Shared helpers for OpenRouter API calls."""

from __future__ import annotations

import os
from typing import Dict

DEFAULT_OPENROUTER_REFERER = "https://zavod-content-factory.com"


def build_openrouter_headers(api_key: str, default_title: str) -> Dict[str, str]:
    """Build OpenRouter headers with optional env overrides."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    referer = (
        os.getenv("OPENROUTER_HTTP_REFERER")
        or os.getenv("OPENROUTER_REFERER")
        or DEFAULT_OPENROUTER_REFERER
    )
    if referer:
        headers["HTTP-Referer"] = referer

    title = (
        os.getenv("OPENROUTER_X_TITLE")
        or os.getenv("OPENROUTER_TITLE")
        or default_title
    )
    if title:
        headers["X-Title"] = title

    return headers
