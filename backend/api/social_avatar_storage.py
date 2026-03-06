from __future__ import annotations

import ipaddress
import logging
import mimetypes
import re
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

DEFAULT_AVATAR_TIMEOUT_SECONDS = 10
DEFAULT_AVATAR_MAX_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return cleaned or fallback


def _is_public_remote_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return False

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return True

    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _guess_extension(photo_url: str, content_type: str) -> str:
    parsed_ct = (content_type or "").split(";", 1)[0].strip().lower()
    if parsed_ct in ALLOWED_CONTENT_TYPE_TO_EXT:
        return ALLOWED_CONTENT_TYPE_TO_EXT[parsed_ct]

    path_ext = (urlparse(photo_url).path.rsplit(".", 1)[-1] if "." in urlparse(photo_url).path else "").lower()
    if path_ext:
        candidate = f".{path_ext}"
        if candidate in ALLOWED_EXTENSIONS:
            return candidate

    guessed_ext = mimetypes.guess_extension(parsed_ct or "")
    if guessed_ext in ALLOWED_EXTENSIONS:
        return guessed_ext

    return ".jpg"


def _make_absolute_url(request, url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    normalized = url if url.startswith("/") else f"/{url}"
    return request.build_absolute_uri(normalized) if request is not None else normalized


def persist_social_avatar(
    *,
    request,
    photo_url: str | None,
    provider: str,
    provider_id: str | int,
) -> tuple[str | None, dict]:
    """
    Download avatar from provider and store it in local media storage.

    Returns tuple:
    - effective photo url for API/UI (stored local URL if saved, otherwise original)
    - metadata to merge into UserSocialAccount.extra_data
    """
    original_url = (photo_url or "").strip()
    if not original_url:
        return None, {}

    if not _is_public_remote_url(original_url):
        logger.warning("Skip avatar download for non-public URL: %s", original_url)
        return original_url, {"photo_url_external": original_url}

    timeout = int(getattr(settings, "SOCIAL_AVATAR_TIMEOUT_SECONDS", DEFAULT_AVATAR_TIMEOUT_SECONDS))
    max_bytes = int(getattr(settings, "SOCIAL_AVATAR_MAX_BYTES", DEFAULT_AVATAR_MAX_BYTES))
    safe_provider = _safe_segment(str(provider).lower(), "provider")
    safe_provider_id = _safe_segment(str(provider_id), "user")

    try:
        with requests.get(original_url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")

            payload = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                payload.extend(chunk)
                if len(payload) > max_bytes:
                    raise ValueError("avatar file is too large")

            if not payload:
                raise ValueError("avatar file is empty")

        extension = _guess_extension(original_url, content_type)
        storage_path = f"user_avatars/{safe_provider}/{safe_provider_id}{extension}"

        if default_storage.exists(storage_path):
            default_storage.delete(storage_path)

        saved_path = default_storage.save(storage_path, ContentFile(bytes(payload)))
        storage_url = _make_absolute_url(request, default_storage.url(saved_path))

        metadata = {
            "photo_url_external": original_url,
            "photo_storage_path": saved_path,
        }
        if storage_url:
            metadata["photo_storage_url"] = storage_url

        effective_photo_url = storage_url or original_url
        return effective_photo_url, metadata
    except Exception as error:
        logger.warning(
            "Failed to persist social avatar provider=%s provider_id=%s url=%s: %s",
            safe_provider,
            safe_provider_id,
            original_url,
            error,
        )
        return original_url, {"photo_url_external": original_url}
