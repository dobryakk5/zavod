from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
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

    params = {"username": normalized}
    try:
        response = requests.get(
            _INSTAGRAM_PROFILE_URL,
            params=params,
            headers=_INSTAGRAM_HEADERS,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Ошибка запроса Instagram профиля %s: %s", normalized, exc)
        raise RuntimeError("Instagram временно недоступен, попробуйте позже") from exc

    if response.status_code == 404:
        raise ValueError("Instagram аккаунт не найден")

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
