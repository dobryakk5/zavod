from __future__ import annotations

from core.models import MapCRMTag


def group_tags_by_type(tags: list[MapCRMTag]) -> dict[str, list[MapCRMTag]]:
    grouped: dict[str, list[MapCRMTag]] = {
        "goal": [],
        "pain": [],
        "experience": [],
    }
    for tag in tags:
        if tag.type in grouped:
            grouped[tag.type].append(tag)
    return grouped

