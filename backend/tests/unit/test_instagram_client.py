from unittest.mock import Mock, patch

import pytest

from core.instagram_client import InstagramRateLimitError, fetch_instagram_profile


def _mock_response(status_code: int, *, payload=None, text: str = "", headers=None) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.text = text
    response.headers = headers or {}
    if payload is None:
        response.json.side_effect = ValueError("No JSON payload")
    else:
        response.json.return_value = payload
    return response


def test_fetch_instagram_profile_retries_on_503_and_returns_data():
    payload = {
        "data": {
            "user": {
                "username": "law.kameneva",
                "full_name": "Law Kameneva",
                "biography": "",
                "edge_followed_by": {"count": 100},
                "edge_follow": {"count": 10},
                "edge_owner_to_timeline_media": {"edges": []},
            }
        }
    }
    limited_response = _mock_response(503, text="Service Unavailable", headers={"Retry-After": "1"})
    success_response = _mock_response(200, payload=payload)

    with (
        patch("core.instagram_client._get_global_rate_limit_remaining_seconds", return_value=0),
        patch("core.instagram_client.requests.get", side_effect=[limited_response, success_response]) as mocked_get,
        patch("core.instagram_client.time.sleep") as mocked_sleep,
    ):
        profile, posts = fetch_instagram_profile("law.kameneva")

    assert mocked_get.call_count == 2
    mocked_sleep.assert_called_once_with(1.0)
    assert profile["username"] == "law.kameneva"
    assert posts == []


def test_fetch_instagram_profile_raises_rate_limit_immediately_on_429():
    limited_response = _mock_response(429, text="Too Many Requests", headers={"Retry-After": "2"})

    with (
        patch("core.instagram_client._get_global_rate_limit_remaining_seconds", return_value=0),
        patch("core.instagram_client._activate_global_rate_limit", return_value=3600) as mocked_activate,
        patch("core.instagram_client.requests.get", return_value=limited_response) as mocked_get,
    ):
        with pytest.raises(InstagramRateLimitError, match="Instagram временно ограничил запросы"):
            fetch_instagram_profile("law.kameneva")

    mocked_activate.assert_called_once()
    assert mocked_get.call_count == 1


def test_fetch_instagram_profile_skips_request_when_global_cooldown_active():
    with (
        patch("core.instagram_client._get_global_rate_limit_remaining_seconds", return_value=1800),
        patch("core.instagram_client.requests.get") as mocked_get,
    ):
        with pytest.raises(InstagramRateLimitError, match="через 1800 сек"):
            fetch_instagram_profile("law.kameneva")

    mocked_get.assert_not_called()
