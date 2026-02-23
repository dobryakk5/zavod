from __future__ import annotations

from django.db.models import QuerySet

from core.models import MapCRMCategory


def get_categories_queryset() -> QuerySet[MapCRMCategory]:
    return MapCRMCategory.objects.all()

