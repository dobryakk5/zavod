from __future__ import annotations

from core.models import MapCRMTag, MapContact, MapContactTag
from core.repositories.crm import contact_tags_repository, tags_repository


def add_tag_to_contact(
    *,
    contact: MapContact,
    tag_id: int | str | None,
    description: str = "",
) -> tuple[MapContactTag, bool]:
    if not tag_id:
        raise ValueError("Укажите tag_id")

    try:
        tag = tags_repository.get_tag_by_id(tag_id)
    except MapCRMTag.DoesNotExist as exc:
        raise LookupError("Тег не найден") from exc

    return contact_tags_repository.upsert_contact_tag(
        contact=contact,
        tag=tag,
        description=description,
    )


def remove_tag_from_contact(
    *,
    contact: MapContact,
    tag_id: int | str | None,
) -> int:
    if not tag_id:
        raise ValueError("Укажите tag_id")
    deleted_count, _ = contact_tags_repository.delete_contact_tag_for_contact(
        contact=contact,
        tag_id=tag_id,
    )
    return deleted_count


def remove_tag_by_ids(
    *,
    contact_id: int | str | None,
    tag_id: int | str | None,
) -> int:
    if contact_id is None or tag_id is None:
        raise ValueError("contact_id и tag_id обязательны.")

    deleted_count, _ = contact_tags_repository.delete_contact_tag_by_ids(
        contact_id=contact_id,
        tag_id=tag_id,
    )
    return deleted_count
