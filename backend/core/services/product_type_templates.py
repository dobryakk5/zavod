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
        .values(
            "name",
            "value",
            "goal",
            "requirements_name",
            "requirements_packages",
            "requirements_audience",
            "requirements_transformation",
            "requirements_metrics",
            "requirements_method",
            "requirements_lesson_format",
            "requirements_program_modules",
            "requirements_packaging",
        )
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
                requirements_name=row.get("requirements_name"),
                requirements_packages=row.get("requirements_packages"),
                requirements_audience=row.get("requirements_audience"),
                requirements_transformation=row.get("requirements_transformation"),
                requirements_metrics=row.get("requirements_metrics"),
                requirements_method=row.get("requirements_method"),
                requirements_lesson_format=row.get("requirements_lesson_format"),
                requirements_program_modules=row.get("requirements_program_modules"),
                requirements_packaging=row.get("requirements_packaging"),
            )
        )

    if not to_create:
        return 0

    ProductType.objects.bulk_create(to_create)
    return len(to_create)


@transaction.atomic
def migrate_client_product_types_to_system(client: Client) -> int:
    """
    Move (and deduplicate) client-scoped product types into the system client.

    - Products that reference client-owned types are re-pointed to the system type by normalized name.
    - Client-owned ProductType rows are deleted afterwards.
    - If a client type name doesn't exist in system, it is created in system (including requirements_* fields).

    Returns the number of ClientProduct rows updated.
    """

    system_client = Client.get_system_client()
    if client.pk == system_client.pk:
        return 0

    from core.models import ClientProduct  # local import to avoid circulars in managed=False models

    client_types = list(ProductType.objects.filter(owner=client).order_by("id"))
    if not client_types:
        return 0

    ensure_system_product_type_templates()

    system_types = list(ProductType.objects.filter(owner=system_client).order_by("id"))
    system_by_name = {_normalize_name(t.name): t for t in system_types if (t.name or "").strip()}

    updated_products = 0

    for old_type in client_types:
        key = _normalize_name(old_type.name)
        if not key:
            continue

        system_type = system_by_name.get(key)
        if not system_type:
            system_type = ProductType.objects.create(
                owner=system_client,
                name=(old_type.name or "").strip() or "Type",
                value=old_type.value,
                goal=old_type.goal,
                requirements_name=getattr(old_type, "requirements_name", None),
                requirements_packages=getattr(old_type, "requirements_packages", None),
                requirements_audience=getattr(old_type, "requirements_audience", None),
                requirements_transformation=getattr(old_type, "requirements_transformation", None),
                requirements_metrics=getattr(old_type, "requirements_metrics", None),
                requirements_method=getattr(old_type, "requirements_method", None),
                requirements_lesson_format=getattr(old_type, "requirements_lesson_format", None),
                requirements_program_modules=getattr(old_type, "requirements_program_modules", None),
                requirements_packaging=getattr(old_type, "requirements_packaging", None),
            )
            system_by_name[key] = system_type

        updated_products += ClientProduct.objects.filter(owner=client, product_type=old_type).update(product_type=system_type)

    ProductType.objects.filter(owner=client).delete()
    return updated_products


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
