import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

INSTAGRAM_CAPTION_LIMIT = 2200


def build_absolute_media_url(raw_url: str) -> Optional[str]:
    """
    Преобразовать относительный MEDIA URL в абсолютный.

    Returns:
        Полный URL или None, если базовый адрес не настроен.
    """
    if not raw_url:
        return None

    if raw_url.startswith(("http://", "https://")):
        return raw_url

    base_url = getattr(settings, "PUBLIC_MEDIA_BASE_URL", None) or getattr(
        settings, "WAGTAILADMIN_BASE_URL", None
    )
    if not base_url:
        return None

    normalized_base = base_url.rstrip("/") + "/"
    normalized_path = raw_url.lstrip("/")
    return urljoin(normalized_base, normalized_path)


class InstagramPublisher:
    """Публикация изображений и видео через Instagram Graph API."""

    def __init__(self, access_token: str, business_account_id: str, api_version: str = "v19.0"):
        self.access_token = access_token
        self.business_account_id = business_account_id
        version = api_version.strip()
        if not version.startswith("v"):
            version = f"v{version}"
        self.base_url = f"https://graph.facebook.com/{version}"

    def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}/{path}", data=data, timeout=30)
        response.raise_for_status()
        return response.json()

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/{path}", params=params, timeout=15)
        response.raise_for_status()
        return response.json()

    def _format_caption(self, caption: str) -> str:
        cleaned = (caption or "").strip()
        if len(cleaned) > INSTAGRAM_CAPTION_LIMIT:
            return cleaned[:INSTAGRAM_CAPTION_LIMIT]
        return cleaned

    def _create_media(self, *, image_url: Optional[str] = None, video_url: Optional[str] = None, caption: str = "") -> str:
        if not image_url and not video_url:
            raise ValueError("Не указан ни image_url, ни video_url для Instagram.")

        payload: Dict[str, Any] = {
            "caption": self._format_caption(caption),
            "access_token": self.access_token,
        }

        if video_url:
            payload.update({"media_type": "VIDEO", "video_url": video_url})
        else:
            payload["image_url"] = image_url

        result = self._post(f"{self.business_account_id}/media", payload)
        creation_id = result.get("id")
        if not creation_id:
            raise RuntimeError("Instagram API не вернул creation_id.")
        return creation_id

    def _wait_for_video(self, creation_id: str, *, max_attempts: int = 15, delay_seconds: float = 2.0) -> None:
        """Ожидает, пока видео контейнер перейдет в состояние FINISHED."""
        for attempt in range(max_attempts):
            result = self._get(
                creation_id,
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
            )
            status_code = (result.get("status_code") or "").upper()

            if status_code == "FINISHED":
                return

            if status_code in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Instagram вернул статус {status_code} для контейнера {creation_id}")

            time.sleep(delay_seconds)

        raise TimeoutError(f"Видео контейнер {creation_id} не завершил обработку за отведенное время.")

    def _publish_media(self, creation_id: str) -> str:
        result = self._post(
            f"{self.business_account_id}/media_publish",
            {"creation_id": creation_id, "access_token": self.access_token},
        )
        media_id = result.get("id")
        if not media_id:
            raise RuntimeError("Instagram API не вернул media_id при публикации.")
        return media_id

    def _fetch_permalink(self, media_id: str) -> Optional[str]:
        try:
            result = self._get(
                media_id,
                params={"fields": "permalink", "access_token": self.access_token},
            )
        except Exception:
            return None
        permalink = result.get("permalink")
        return permalink if isinstance(permalink, str) else None

    def publish_post(self, *, caption: str, image_url: Optional[str] = None, video_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Публикует пост в Instagram.

        Returns:
            {'success': bool, 'media_id': str, 'url': str, 'error': str}
        """
        try:
            creation_id = self._create_media(image_url=image_url, video_url=video_url, caption=caption)

            if video_url:
                self._wait_for_video(creation_id)

            media_id = self._publish_media(creation_id)
            permalink = self._fetch_permalink(media_id)

            return {
                "success": True,
                "media_id": media_id,
                "url": permalink or "",
            }
        except requests.HTTPError as exc:
            details = exc.response.text[:500] if exc.response is not None else str(exc)
            logger.error("Instagram API error: %s", details)
            return {"success": False, "error": details}
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка публикации в Instagram: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}


class YouTubePublisher:
    """Публикация видео на YouTube через YouTube Data API v3."""

    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_uri: str = "https://oauth2.googleapis.com/token",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_uri = token_uri

    def _build_credentials(self):
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
        except ImportError as exc:  # pragma: no cover - guarded by requirements
            raise ImportError("Установите google-auth и зависимости для YouTube публикации.") from exc

        creds = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return creds

    def publish_video(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        privacy_status: str = "public",
    ) -> Dict[str, Any]:
        """
        Загружает и публикует видео на YouTube.

        Returns:
            {'success': bool, 'video_id': str, 'url': str, 'access_token': str, 'error': str}
        """
        if not os.path.exists(video_path):
            return {"success": False, "error": f"Видео файл не найден: {video_path}"}

        try:
            creds = self._build_credentials()
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:  # pragma: no cover - guarded by requirements
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": str(exc)}

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title or "Untitled video",
                "description": description,
            },
            "status": {
                "privacyStatus": privacy_status,
            },
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

        try:
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response.get("id")
            url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            refreshed_token = getattr(creds, "token", None)
            expires_at = getattr(creds, "expiry", None)

            return {
                "success": True,
                "video_id": video_id,
                "url": url,
                "access_token": refreshed_token,
                "access_token_expires_at": expires_at,
            }
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка публикации на YouTube: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}
