from __future__ import annotations

import hashlib
import hmac
import time

from django.test import override_settings
from rest_framework.test import APIRequestFactory

from api.views_accounts import LogoutView, _verify_telegram_payload


def _signed_telegram_payload(bot_token: str, **overrides):
    payload = {
        "id": "123456",
        "first_name": "Alice",
        "username": "alice",
        "auth_date": str(int(time.time())),
    }
    payload.update(overrides)
    check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted((key, value) for key, value in payload.items() if value is not None)
    )
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return payload


@override_settings(DEBUG=False, TELEGRAM_BOT_TOKEN="test-bot-token")
def test_verify_telegram_payload_accepts_valid_signature():
    payload = _signed_telegram_payload("test-bot-token")

    assert _verify_telegram_payload(payload) is True


@override_settings(DEBUG=False, TELEGRAM_BOT_TOKEN="test-bot-token")
def test_verify_telegram_payload_rejects_stale_payload():
    payload = _signed_telegram_payload(
        "test-bot-token",
        auth_date=str(int(time.time()) - 86401),
    )

    assert _verify_telegram_payload(payload) is False


def test_logout_view_blacklists_refresh_token(monkeypatch):
    blacklisted = []

    class FakeRefreshToken:
        def __init__(self, raw_token: str):
            assert raw_token == "refresh-cookie-token"

        def blacklist(self):
            blacklisted.append(True)

        def get(self, key: str, default=None):
            if key == "jti":
                return "test-jti"
            return default

    monkeypatch.setattr("api.views_accounts.RefreshToken", FakeRefreshToken)

    factory = APIRequestFactory()
    request = factory.post("/api/auth/logout/")
    request.COOKIES["refresh_token"] = "refresh-cookie-token"

    response = LogoutView.as_view()(request)

    assert response.status_code == 200
    assert blacklisted == [True]
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
