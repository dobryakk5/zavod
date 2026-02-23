from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from core.models import MapContact, MapContactTag


def get_contacts_queryset() -> QuerySet[MapContact]:
    return MapContact.objects.prefetch_related(
        Prefetch(
            "contact_tags",
            queryset=MapContactTag.objects.select_related("tag"),
        )
    )


def get_contact_telegram_row(contact_id: int) -> dict[str, str] | None:
    return MapContact.objects.filter(id=contact_id).values("tg_username").first()

