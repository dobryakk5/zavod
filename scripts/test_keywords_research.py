import os
import sys
import json
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yandex_direct_api_client import YandexDirectAPIClient


def _parse_ids(value: Optional[str]) -> Optional[List[int]]:
    if not value:
        return None
    return [int(part) for part in value.split(',') if part.strip()]


def main():
    access_token = os.environ.get("YD_TOKEN")
    login = os.environ.get("YD_LOGIN")
    use_sandbox = os.environ.get("YD_USE_SANDBOX", "false").lower() in {"1", "true", "yes"}
    keyword_text = os.environ.get("YD_KEYWORD", "купить велосипед")
    region_ids = _parse_ids(os.environ.get("YD_GEO_ID", "225"))
    minus_keywords_env = os.environ.get("YD_MINUS_KEYWORDS", "")
    minus_keywords = [kw.strip() for kw in minus_keywords_env.split(',') if kw.strip()]

    if not access_token or not login:
        raise RuntimeError("Установите переменные окружения YD_TOKEN и YD_LOGIN")

    client = YandexDirectAPIClient(
        access_token=access_token,
        login=login,
        use_sandbox=use_sandbox
    )

    print(f"Ищем данные по фразе: {keyword_text}")
    result = client.find_keywords(
        keyword_texts=[keyword_text],
        region_ids=region_ids,
        minus_keywords=minus_keywords or None,
        limit=int(os.environ.get("YD_LIMIT", "10"))
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
