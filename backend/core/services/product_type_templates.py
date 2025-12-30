from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.db import transaction

from core.models import Client, ProductType


def _normalize_name(value: str | None) -> str:
    return (value or "").strip().lower()


def get_fibonatty_client() -> Optional[Client]:
    slug = (getattr(settings, "FIBONATTY_TEMPLATE_CLIENT_SLUG", None) or "fibonatty").strip()
    if slug:
        client = Client.objects.filter(slug=slug).first()
        if client:
            return client

    client = Client.objects.filter(name__iexact="Fibonatty").first()
    if client:
        return client

    return Client.objects.filter(name__icontains="Fibonatty").order_by("id").first()


def sync_product_types(source: Client, target: Client) -> int:
    if source.pk == target.pk:
        return 0

    source_rows = list(
        ProductType.objects.filter(owner=source)
        .order_by("id")
        .values("name", "value", "goal")
    )
    if not source_rows:
        return 0

    existing_names = {
        _normalize_name(name)
        for name in ProductType.objects.filter(owner=target).values_list("name", flat=True)
    }

    to_create: list[ProductType] = []
    for row in source_rows:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        key = _normalize_name(name)
        if key in existing_names:
            continue
        existing_names.add(key)
        to_create.append(
            ProductType(
                owner=target,
                name=name,
                value=row.get("value"),
                goal=row.get("goal"),
            )
        )

    if not to_create:
        return 0

    ProductType.objects.bulk_create(to_create)
    return len(to_create)


@transaction.atomic
def ensure_system_product_type_templates() -> int:
    """
    Ensure system client contains product type templates.

    Currently seeds/syncs from the Fibonatty client (if present).
    Returns the number of ProductType rows added to the system client.
    """

    system_client = Client.get_system_client()
    source_client = get_fibonatty_client()
    if not source_client:
        return 0
    if source_client.pk == system_client.pk:
        return 0
    return sync_product_types(source_client, system_client)
