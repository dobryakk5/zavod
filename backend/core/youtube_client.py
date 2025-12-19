from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_CHANNEL_ID_RE = re.compile(r"^UC[0-9A-Za-z_-]{21,}$")
_HANDLE_RE = re.compile(r"^@[A-Za-z0-9._-]{3,60}$")
_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]{3,100}$")

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def normalize_youtube_identifier(value: str) -> str:
    """
    Привести URL или handle YouTube канала к унифицированному идентификатору.
    Возвращает пустую строку, если распознать не удалось.
    """
    if not value:
        return ""

    text = value.strip()
    if not text:
        return ""

    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        path = (parsed.path or "").strip("/")
        if not path:
            return ""

        if path.startswith("@"):
            text = f"@{path.split('/')[0][1:]}"
        else:
            parts = [part for part in path.split("/") if part]
            if not parts:
                return ""
            if parts[0] in {"channel", "c", "user"} and len(parts) > 1:
                text = parts[1]
            else:
                text = parts[0]

    text = text.strip()
    if not text:
        return ""

    if _CHANNEL_ID_RE.match(text):
        return text

    if text.startswith("@"):
        handle = f"@{re.sub(r'[^A-Za-z0-9._-]', '', text[1:])}"
        if _HANDLE_RE.match(handle):
            return handle
        return ""

    sanitized = re.sub(r"[^A-Za-z0-9._-]", "", text)
    if _CHANNEL_ID_RE.match(sanitized) or _SLUG_RE.match(sanitized):
        return sanitized
    return ""


def _resolve_channel_id(api_key: str, identifier: str) -> str:
    if not api_key:
        raise RuntimeError("YouTube API key is not configured")

    if _CHANNEL_ID_RE.match(identifier):
        return identifier

    query = identifier.lstrip("@")
    if not query:
        raise ValueError("Некорректный YouTube канал")

    params = {
        "key": api_key,
        "q": query,
        "type": "channel",
        "part": "id,snippet",
        "maxResults": 1,
    }
    response = requests.get(SEARCH_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = data.get("items") or []
    if not items:
        raise ValueError("YouTube канал не найден")

    item = items[0]
    channel_id = (item.get("id") or {}).get("channelId") or (item.get("snippet") or {}).get("channelId")
    if not channel_id:
        raise RuntimeError("Не удалось определить ID YouTube канала")
    return channel_id


def _fetch_channel_details(api_key: str, channel_id: str) -> Dict:
    params = {
        "key": api_key,
        "id": channel_id,
        "part": "snippet,statistics",
        "maxResults": 1,
    }
    response = requests.get(CHANNELS_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = data.get("items") or []
    if not items:
        raise RuntimeError("YouTube API не вернул данные канала")
    channel = items[0]
    snippet = channel.get("snippet", {})
    statistics = channel.get("statistics", {})
    return {
        "channel_id": channel_id,
        "title": snippet.get("title") or "",
        "description": snippet.get("description") or "",
        "custom_url": snippet.get("customUrl") or "",
        "country": snippet.get("country") or "",
        "thumbnail": ((snippet.get("thumbnails") or {}).get("high") or {}).get("url")
        or ((snippet.get("thumbnails") or {}).get("default") or {}).get("url")
        or "",
        "subscriber_count": int(statistics.get("subscriberCount") or 0),
        "view_count": int(statistics.get("viewCount") or 0),
        "video_count": int(statistics.get("videoCount") or 0),
    }


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _fetch_channel_videos(api_key: str, channel_id: str, *, max_videos: int) -> List[Dict]:
    max_results = max(1, min(max_videos, 50))
    search_params = {
        "key": api_key,
        "channelId": channel_id,
        "part": "id,snippet",
        "order": "date",
        "type": "video",
        "maxResults": max_results,
    }
    response = requests.get(SEARCH_URL, params=search_params, timeout=20)
    response.raise_for_status()
    search_data = response.json()
    items = search_data.get("items") or []
    video_ids = [
        (item.get("id") or {}).get("videoId")
        for item in items
        if (item.get("id") or {}).get("videoId")
    ]

    if not video_ids:
        return []

    stats_params = {
        "key": api_key,
        "id": ",".join(video_ids),
        "part": "snippet,statistics",
    }
    stats_response = requests.get(VIDEOS_URL, params=stats_params, timeout=20)
    stats_response.raise_for_status()
    stats_data = stats_response.json()
    stats_items = stats_data.get("items") or []
    stats_index = {item.get("id"): item for item in stats_items}

    videos: List[Dict] = []
    for video_id in video_ids:
        item = stats_index.get(video_id)
        if not item:
            continue
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        published_at = _parse_timestamp(snippet.get("publishedAt"))
        description = snippet.get("description") or ""
        title = snippet.get("title") or ""
        views = int(statistics.get("viewCount") or 0)
        likes = int(statistics.get("likeCount") or 0)
        comments = int(statistics.get("commentCount") or 0)

        videos.append(
            {
                "id": video_id,
                "title": title,
                "text": description,
                "views": views,
                "reactions": likes,
                "comments": comments,
                "forwards": likes + comments,
                "date": published_at,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "preview": ((snippet.get("thumbnails") or {}).get("high") or {}).get("url")
                or ((snippet.get("thumbnails") or {}).get("default") or {}).get("url")
                or "",
            }
        )

    return videos


def fetch_youtube_channel(api_key: str, identifier: str, *, max_videos: int = 40) -> Tuple[Dict, List[Dict]]:
    """
    Получить информацию о YouTube канале и последние видео.
    """
    normalized = normalize_youtube_identifier(identifier)
    if not normalized:
        raise ValueError("Некорректный YouTube канал")

    channel_id = _resolve_channel_id(api_key, normalized)
    profile = _fetch_channel_details(api_key, channel_id)
    videos = _fetch_channel_videos(api_key, channel_id, max_videos=max_videos)
    return profile, videos
