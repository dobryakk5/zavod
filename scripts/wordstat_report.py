import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import requests


WORDSTAT_TOP_REQUESTS_URL = "https://api.wordstat.yandex.net/v1/topRequests"
WORDSTAT_USER_INFO_URL = "https://api.wordstat.yandex.net/v1/userInfo"
BACKEND_ENV_PATH = Path(__file__).resolve().parents[1] / "backend" / ".env"


def _parse_int_list(raw_value: Optional[str]) -> Optional[List[int]]:
    if not raw_value:
        return None
    result = []
    for part in raw_value.split(","):
        part = part.strip()
        if part:
            result.append(int(part))
    return result or None


def _parse_str_list(raw_value: Optional[str]) -> Optional[List[str]]:
    if not raw_value:
        return None
    result = [part.strip() for part in raw_value.split(",") if part.strip()]
    return result or None


def _load_token_from_env_file() -> Optional[str]:
    if not BACKEND_ENV_PATH.exists():
        return None
    try:
        with BACKEND_ENV_PATH.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                if key.strip() == "WORDSTAT_TOKEN":
                    return value.strip().strip("'").strip('"')
    except OSError:
        return None
    return None


def fetch_user_info(token: str) -> dict:
    response = requests.post(
        WORDSTAT_USER_INFO_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
        },
        json={},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"userInfo failed: {response.status_code} {response.text}"
        )
    return response.json()


def fetch_top_requests(
    token: str,
    phrase: str,
    regions: Optional[List[int]] = None,
    devices: Optional[List[str]] = None,
    include_parent: bool = False,
) -> dict:
    payload = {"phrase": phrase}
    if regions:
        payload["regions"] = regions
    if devices:
        payload["devices"] = devices
    if include_parent:
        payload["includeParent"] = True

    response = requests.post(
        WORDSTAT_TOP_REQUESTS_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"topRequests failed: {response.status_code} {response.text}")

    data = response.json()
    if "error" in data:
        raise RuntimeError(f"Wordstat error: {data['error']}")
    return data


def main():
    token = os.environ.get("WORDSTAT_TOKEN") or _load_token_from_env_file()
    phrase = os.environ.get("WORDSTAT_PHRASE", "купить велосипед").strip()
    regions = _parse_int_list(os.environ.get("WORDSTAT_REGIONS"))
    devices = _parse_str_list(os.environ.get("WORDSTAT_DEVICES"))
    include_parent = os.environ.get("WORDSTAT_INCLUDE_PARENT", "false").lower() in {
        "1",
        "true",
        "yes",
    }

    if not token:
        print(
            "Установите WORDSTAT_TOKEN с OAuth-токеном Wordstat API "
            f"или добавьте его в {BACKEND_ENV_PATH}."
        )
        sys.exit(1)

    user_info = fetch_user_info(token)
    print("Информация о пользователе Wordstat:")
    print(json.dumps(user_info, ensure_ascii=False, indent=2))

    result = fetch_top_requests(
        token=token,
        phrase=phrase,
        regions=regions,
        devices=devices,
        include_parent=include_parent,
    )

    print("Результаты topRequests:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
