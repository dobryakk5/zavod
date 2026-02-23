from __future__ import annotations

from django.db.models import QuerySet

from core.models import MapCRMTag, MapContact, MapContactTag


def get_contact_tags_queryset() -> QuerySet[MapContactTag]:
    return MapContactTag.objects.select_related("contact", "tag")


def upsert_contact_tag(
    contact: MapContact,
    tag: MapCRMTag,
    description: str,
) -> tuple[MapContactTag, bool]:
    return MapContactTag.objects.update_or_create(
        contact=contact,
        tag=tag,
        defaults={"description": description},
    )


def delete_contact_tag_for_contact(
    contact: MapContact,
    tag_id: int | str,
) -> tuple[int, dict[str, int]]:
    return MapContactTag.objects.filter(
        contact=contact,
        tag_id=tag_id,
    ).delete()


def delete_contact_tag_by_ids(
    contact_id: int | str,
    tag_id: int | str,
) -> tuple[int, dict[str, int]]:
    return MapContactTag.objects.filter(
        contact_id=contact_id,
        tag_id=tag_id,
    ).delete()

