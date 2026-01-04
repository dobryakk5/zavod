from __future__ import annotations

from typing import Any, Dict, List, Optional


def merge_related_products(existing_items: Any, new_ref: Dict[str, Any]) -> List[Any]:
    """
    Merge a new related product reference into an existing related_products list.

    - Prepends new_ref
    - Removes duplicates by id (supports int, str, and dict-with-id forms)
    - Keeps unrelated/unknown items as-is
    """

    if not isinstance(existing_items, list):
        existing_items = []

    def _extract_id(value: Any) -> Optional[int]:
        if isinstance(value, dict):
            candidate = value.get("id")
        else:
            candidate = value
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if not candidate:
                return None
            try:
                return int(candidate)
            except ValueError:
                return None
        return None

    new_id = _extract_id(new_ref)
    if new_id is None:
        return list(existing_items)

    filtered: List[Any] = []
    for item in existing_items:
        if _extract_id(item) == new_id:
            continue
        filtered.append(item)

    return [new_ref, *filtered]


def remove_related_product(existing_items: Any, remove_id: Any) -> List[Any]:
    """
    Remove a related product reference from an existing related_products list by id.

    Supports int, str, and dict-with-id forms.
    """

    if not isinstance(existing_items, list):
        return []

    def _extract_id(value: Any) -> Optional[int]:
        if isinstance(value, dict):
            candidate = value.get("id")
        else:
            candidate = value
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str):
            candidate = candidate.strip()
            if not candidate:
                return None
            try:
                return int(candidate)
            except ValueError:
                return None
        return None

    target_id = _extract_id(remove_id)
    if target_id is None:
        return list(existing_items)

    filtered: List[Any] = []
    for item in existing_items:
        if _extract_id(item) == target_id:
            continue
        filtered.append(item)
    return filtered
