from __future__ import annotations

from pathlib import Path

import pytest
from django.test import RequestFactory

from api.social_avatar_storage import persist_social_avatar


class _MockResponse:
    def __init__(self, *, chunks: list[bytes], content_type: str = "image/jpeg"):
        self._chunks = chunks
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int = 0):
        _ = chunk_size
        for chunk in self._chunks:
            yield chunk


def test_persist_social_avatar_saves_to_media(monkeypatch, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    request = RequestFactory().get("/api/auth/telegram")

    monkeypatch.setattr(
        "api.social_avatar_storage.requests.get",
        lambda *args, **kwargs: _MockResponse(chunks=[b"fake-image-bytes"], content_type="image/jpeg"),
    )

    photo_url, metadata = persist_social_avatar(
        request=request,
        photo_url="https://example.com/avatar.jpg",
        provider="telegram",
        provider_id="123",
    )

    assert photo_url is not None
    assert photo_url.startswith("http://testserver/media/user_avatars/telegram/123")
    assert metadata["photo_storage_path"].startswith("user_avatars/telegram/123")
    assert metadata["photo_url_external"] == "https://example.com/avatar.jpg"
    assert Path(settings.MEDIA_ROOT, metadata["photo_storage_path"]).exists()


def test_persist_social_avatar_skips_non_public_url(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    request = RequestFactory().get("/api/auth/telegram")

    photo_url, metadata = persist_social_avatar(
        request=request,
        photo_url="http://localhost/avatar.jpg",
        provider="telegram",
        provider_id="123",
    )

    assert photo_url == "http://localhost/avatar.jpg"
    assert metadata["photo_url_external"] == "http://localhost/avatar.jpg"
    assert not Path(settings.MEDIA_ROOT, "user_avatars").exists()
