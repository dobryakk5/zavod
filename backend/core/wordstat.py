import os
from typing import Any, Dict, List, Optional

import requests

WORDSTAT_TOP_REQUESTS_URL = "https://api.wordstat.yandex.net/v1/topRequests"
WORDSTAT_USER_INFO_URL = "https://api.wordstat.yandex.net/v1/userInfo"


class WordstatError(Exception):
    """Базовая ошибка клиента Wordstat."""


class WordstatClient:
    """Простой клиент для Wordstat API."""

    def __init__(self, token: str):
        token = (token or "").strip()
        if not token:
            raise WordstatError("WORDSTAT_TOKEN не задан")
        self.token = token

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
        }

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = requests.post(url, headers=self._headers, json=payload, timeout=30)
        except requests.RequestException as exc:
            raise WordstatError(f"Ошибка подключения к Wordstat: {exc}") from exc

        if response.status_code != 200:
            raise WordstatError(f"{url} вернул {response.status_code}: {response.text}")

        data = response.json()
        if isinstance(data, dict) and "error" in data:
            raise WordstatError(f"Wordstat error: {data['error']}")
        return data

    def fetch_user_info(self) -> Dict[str, Any]:
        return self._post(WORDSTAT_USER_INFO_URL, {})

    def fetch_top_requests(
        self,
        phrase: str,
        regions: Optional[List[int]] = None,
        devices: Optional[List[str]] = None,
        include_parent: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"phrase": phrase}
        if regions:
            payload["regions"] = regions
        if devices:
            payload["devices"] = devices
        if include_parent:
            payload["includeParent"] = True
        return self._post(WORDSTAT_TOP_REQUESTS_URL, payload)


def get_wordstat_client(token: Optional[str] = None) -> WordstatClient:
    token_value = (token or os.getenv("WORDSTAT_TOKEN") or "").strip()
    if not token_value:
        raise WordstatError("WORDSTAT_TOKEN не задан в окружении")
    return WordstatClient(token_value)


__all__ = ["WordstatClient", "WordstatError", "get_wordstat_client"]
