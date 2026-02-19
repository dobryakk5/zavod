from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_INSTAGRAM_PROFILE_URL = "https://www.instagram.com/api/v1/users/web_profile_info/"
_INSTAGRAM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Accept": "application/json",
    "X-IG-App-ID": "936619743392459",
}
_MAX_PROFILE_REQUEST_ATTEMPTS = 3
_DEFAULT_RETRY_DELAYS = (1.5, 3.0, 5.0)
_INSTAGRAM_GLOBAL_COOLDOWN_SECONDS = 60 * 60
_INSTAGRAM_RATE_LIMIT_STATE_FILE = Path(
    os.getenv("INSTAGRAM_RATE_LIMIT_STATE_FILE", "/tmp/zavod_instagram_rate_limit.json")
)


class InstagramRateLimitError(RuntimeError):
    """Instagram ограничил количество запросов (HTTP 429)."""


def _compute_retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = (response.headers.get("Retry-After") or "").strip()
    if retry_after:
        try:
            delay = float(retry_after)
            if delay > 0:
                return min(delay, 30.0)
        except ValueError:
            pass
    index = min(max(attempt - 1, 0), len(_DEFAULT_RETRY_DELAYS) - 1)
    return _DEFAULT_RETRY_DELAYS[index]


def _read_global_rate_limit_until_ts() -> Optional[float]:
    try:
        if not _INSTAGRAM_RATE_LIMIT_STATE_FILE.exists():
            return None
        raw = _INSTAGRAM_RATE_LIMIT_STATE_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        payload = json.loads(raw)
        value = payload.get("rate_limited_until_ts")
        if value is None:
            return None
        return float(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Не удалось прочитать state-файл cooldown Instagram: %s", exc)
        return None


def _write_global_rate_limit_until_ts(until_ts: float) -> None:
    payload = {"rate_limited_until_ts": float(until_ts)}
    tmp_path = _INSTAGRAM_RATE_LIMIT_STATE_FILE.with_suffix(
        f"{_INSTAGRAM_RATE_LIMIT_STATE_FILE.suffix}.tmp"
    )
    try:
        _INSTAGRAM_RATE_LIMIT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        tmp_path.replace(_INSTAGRAM_RATE_LIMIT_STATE_FILE)
    except OSError as exc:
        logger.warning("Не удалось записать state-файл cooldown Instagram: %s", exc)


def _get_global_rate_limit_remaining_seconds() -> int:
    until_ts = _read_global_rate_limit_until_ts()
    if until_ts is None:
        return 0
    remaining = int(round(until_ts - time.time()))
    return max(0, remaining)


def _activate_global_rate_limit() -> int:
    until_ts = time.time() + _INSTAGRAM_GLOBAL_COOLDOWN_SECONDS
    _write_global_rate_limit_until_ts(until_ts)
    return _INSTAGRAM_GLOBAL_COOLDOWN_SECONDS


def normalize_instagram_username(value: str) -> str:
    """
    Преобразовать ссылку или @username в валидное имя Instagram.
    Возвращает пустую строку, если распознать не удалось.
    """
    if not value:
        return ""

    text = value.strip()
    if not text:
        return ""

    # Убираем @ в начале
    if text.startswith("@"):
        text = text[1:]

    # Разбираем URL и берем первый сегмент пути
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        text = parsed.path or ""
        text = text.strip("/")
    else:
        lowered = text.lower()
        if lowered.startswith(("instagram.com/", "www.instagram.com/", "m.instagram.com/")):
            parsed = urlparse(f"https://{text}")
            text = (parsed.path or "").strip("/")

    # Удаляем query параметры, если они есть
    if "?" in text:
        text = text.split("?", 1)[0]

    text = text.strip("/")
    if not text or "/" in text:
        return ""

    if not _USERNAME_RE.match(text):
        return ""

    return text.lower()


def _extract_caption(node: Dict) -> str:
    caption_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
    parts = []
    for edge in caption_edges:
        text = ((edge or {}).get("node") or {}).get("text")
        if text:
            parts.append(str(text).strip())
    caption = "\n\n".join(part for part in parts if part)
    return caption.strip()


def _extract_posts(user_payload: Dict, limit: int) -> List[Dict]:
    media = user_payload.get("edge_owner_to_timeline_media") or {}
    edges = media.get("edges") or []
    posts: List[Dict] = []
    for edge in edges:
        node = (edge or {}).get("node") or {}
        if not node:
            continue
        taken_at = node.get("taken_at_timestamp")
        dt = None
        if isinstance(taken_at, (int, float)) and taken_at > 0:
            dt = datetime.fromtimestamp(int(taken_at), tz=timezone.utc)
        caption = _extract_caption(node)
        likes_count = ((node.get("edge_liked_by") or {}).get("count")) or 0
        preview_likes = ((node.get("edge_media_preview_like") or {}).get("count")) or 0
        comments_count = ((node.get("edge_media_to_comment") or {}).get("count")) or 0
        video_views = node.get("video_view_count") or 0
        interactions = likes_count + comments_count

        posts.append(
            {
                "id": node.get("id"),
                "text": caption,
                "views": video_views or likes_count or preview_likes or interactions,
                "reactions": likes_count or preview_likes,
                "comments": comments_count,
                "forwards": interactions,
                "date": dt,
                "url": f"https://www.instagram.com/p/{node.get('shortcode')}/" if node.get("shortcode") else "",
                "preview": node.get("display_url") or node.get("thumbnail_src") or "",
            }
        )
        if len(posts) >= limit:
            break
    return posts


def fetch_instagram_profile(username: str, *, limit: int = 40) -> Tuple[Dict, List[Dict]]:
    """
    Получить профиль Instagram и последние посты через web API.
    """
    normalized = normalize_instagram_username(username)
    if not normalized:
        raise ValueError("Некорректный Instagram аккаунт")

    cooldown_left = _get_global_rate_limit_remaining_seconds()
    if cooldown_left > 0:
        logger.warning(
            "Instagram global cooldown активен (%ss), пропускаем запрос профиля %s",
            cooldown_left,
            normalized,
        )
        raise InstagramRateLimitError(
            f"Instagram временно ограничил запросы. Повторите анализ через {cooldown_left} сек."
        )

    params = {"username": normalized}
    response = None
    for attempt in range(1, _MAX_PROFILE_REQUEST_ATTEMPTS + 1):
        try:
            response = requests.get(
                _INSTAGRAM_PROFILE_URL,
                params=params,
                headers=_INSTAGRAM_HEADERS,
                timeout=15,
            )
        except requests.RequestException as exc:
            if attempt < _MAX_PROFILE_REQUEST_ATTEMPTS:
                delay = _DEFAULT_RETRY_DELAYS[min(attempt - 1, len(_DEFAULT_RETRY_DELAYS) - 1)]
                logger.warning(
                    "Ошибка запроса Instagram профиля %s (attempt %s/%s): %s. Retry in %.1fs",
                    normalized,
                    attempt,
                    _MAX_PROFILE_REQUEST_ATTEMPTS,
                    exc,
                    delay,
                )
                time.sleep(delay)
                continue
            logger.error("Ошибка запроса Instagram профиля %s: %s", normalized, exc)
            raise RuntimeError("Instagram временно недоступен, попробуйте позже") from exc

        if response.status_code == 429:
            cooldown_seconds = _activate_global_rate_limit()
            logger.error(
                "Instagram API вернул ошибку 429 для %s: %s",
                normalized,
                response.text[:200],
            )
            raise InstagramRateLimitError(
                f"Instagram временно ограничил запросы. Повторите анализ через {cooldown_seconds} сек."
            )

        if response.status_code in {500, 502, 503, 504} and attempt < _MAX_PROFILE_REQUEST_ATTEMPTS:
            delay = _compute_retry_delay(response, attempt)
            logger.warning(
                "Instagram API вернул %s для %s (attempt %s/%s). Retry in %.1fs",
                response.status_code,
                normalized,
                attempt,
                _MAX_PROFILE_REQUEST_ATTEMPTS,
                delay,
            )
            time.sleep(delay)
            continue
        break

    if response is None:
        raise RuntimeError("Instagram временно недоступен, попробуйте позже")

    if response.status_code == 404:
        raise ValueError("Instagram аккаунт не найден")

    if response.status_code == 429:
        cooldown_seconds = _activate_global_rate_limit()
        logger.error(
            "Instagram API вернул ошибку 429 для %s: %s",
            normalized,
            response.text[:200],
        )
        raise InstagramRateLimitError(
            f"Instagram временно ограничил запросы. Повторите анализ через {cooldown_seconds} сек."
        )

    if response.status_code >= 500:
        logger.error(
            "Instagram API вернул ошибку %s для %s: %s",
            response.status_code,
            normalized,
            response.text[:200],
        )
        raise RuntimeError("Instagram временно недоступен, попробуйте позже")

    if response.status_code >= 400:
        logger.error(
            "Instagram API вернул ошибку %s для %s: %s",
            response.status_code,
            normalized,
            response.text[:200],
        )
        raise RuntimeError("Instagram API вернул ошибку при получении профиля")

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("Не удалось распарсить ответ Instagram: %s", exc)
        raise RuntimeError("Instagram вернул неожиданный ответ") from exc

    user_payload = ((payload or {}).get("data") or {}).get("user") or {}
    if not user_payload:
        raise RuntimeError("Instagram не вернул данные профиля")

    profile = {
        "username": user_payload.get("username") or normalized,
        "full_name": user_payload.get("full_name") or user_payload.get("username") or normalized,
        "biography": user_payload.get("biography") or "",
        "followers_count": int(((user_payload.get("edge_followed_by") or {}).get("count")) or 0),
        "following_count": int(((user_payload.get("edge_follow") or {}).get("count")) or 0),
        "profile_pic_url": user_payload.get("profile_pic_url_hd") or user_payload.get("profile_pic_url") or "",
        "external_url": user_payload.get("external_url") or "",
    }

    posts = _extract_posts(user_payload, limit=limit)
    return profile, posts
