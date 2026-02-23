from __future__ import annotations

from django.db.models import QuerySet

from core.models import MapCRMTag


def get_tags_queryset() -> QuerySet[MapCRMTag]:
    return MapCRMTag.objects.all()


def get_tag_by_id(tag_id: int | str) -> MapCRMTag:
    return MapCRMTag.objects.get(id=tag_id)

