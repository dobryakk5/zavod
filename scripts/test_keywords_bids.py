import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yandex_direct_api_client import YandexDirectAPIClient


def _parse_ids(value: Optional[str]) -> Optional[List[int]]:
    if not value:
        return None
    return [int(part) for part in value.split(',') if part.strip()]


def _chunk(items: List[int], size: int) -> List[List[int]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def main():
    access_token = os.environ.get("YD_TOKEN")
    login = os.environ.get("YD_LOGIN")
    use_sandbox = os.environ.get("YD_USE_SANDBOX", "false").lower() in {"1", "true", "yes"}
    keyword_text_filter = os.environ.get("YD_KEYWORD_TEXT", "").lower().strip()
    campaign_ids = _parse_ids(os.environ.get("YD_CAMPAIGN_IDS"))
    ad_group_ids = _parse_ids(os.environ.get("YD_ADGROUP_IDS"))
    keyword_ids = _parse_ids(os.environ.get("YD_KEYWORD_IDS"))
    limit = int(os.environ.get("YD_MAX_KEYWORDS", "50"))

    if not access_token or not login:
        raise RuntimeError("Установите переменные окружения YD_TOKEN и YD_LOGIN")

    client = YandexDirectAPIClient(
        access_token=access_token,
        login=login,
        use_sandbox=use_sandbox
    )

    keywords = client.get_keywords(
        campaign_ids=campaign_ids,
        ad_group_ids=ad_group_ids,
        keyword_ids=keyword_ids
    )

    if keyword_text_filter:
        keywords = [
            kw for kw in keywords
            if keyword_text_filter in kw.get('Keyword', '').lower()
        ]

    if not keywords:
        print("Ключевые слова не найдены. Уточните фильтры.")
        return

    keywords = keywords[:limit]
    keyword_ids_chunked = _chunk([kw['Id'] for kw in keywords], size=1000)
    bids: Dict[int, Dict[str, Any]] = {}

    for chunk in keyword_ids_chunked:
        for bid in client.get_bids(keyword_ids=chunk):
            bids[bid['KeywordId']] = bid

    print(f"Найдено ключевых слов: {len(keywords)}")
    for kw in keywords:
        bid_info = bids.get(kw['Id'], {})
        print(
            f"- {kw.get('Keyword')} (ID={kw['Id']}): "
            f"State={kw.get('State')} Status={kw.get('Status')} "
            f"Bid={bid_info.get('Bid')} ContextBid={bid_info.get('ContextBid')}"
        )


if __name__ == "__main__":
    main()
