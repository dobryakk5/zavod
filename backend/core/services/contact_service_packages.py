from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import (
    Client,
    ClientProduct,
    ContactProductPurchase,
    ContactProductServiceUsage,
    MapCRMEvent,
)


SERVICE_MODE_COUNT = ContactProductServiceUsage.MODE_COUNT
SERVICE_MODE_MINUTES = ContactProductServiceUsage.MODE_MINUTES
SERVICE_MODES = {SERVICE_MODE_COUNT, SERVICE_MODE_MINUTES}


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        parsed = int(value)
        return parsed if parsed > 0 else None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(float(text.replace(",", ".")))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_service_mode(raw_kind: Any, raw_unit: Any) -> str | None:
    kind = str(raw_kind or "").strip().lower()
    unit = str(raw_unit or "").strip().lower()

    kind_is_service = kind in {
        "service_package",
        "service-package",
        "service",
        "package_service",
        "пакет_услуг",
        "пакет услуг",
    }

    count_units = {"count", "session", "sessions", "meeting", "meetings", "qty", "quantity", "встреча", "встречи", "встреч"}
    minute_units = {"minute", "minutes", "min", "time", "минута", "минуты", "минут", "мин"}

    if kind_is_service:
        if unit in count_units:
            return SERVICE_MODE_COUNT
        if unit in minute_units:
            return SERVICE_MODE_MINUTES

    # Fallback: если явно указан service_unit без kind
    if unit in count_units:
        return SERVICE_MODE_COUNT
    if unit in minute_units:
        return SERVICE_MODE_MINUTES
    return None


def extract_service_package_definition(product: ClientProduct | None) -> dict[str, Any] | None:
    if product is None:
        return None

    raw_packages = product.packages if isinstance(product.packages, list) else []
    for raw_item in raw_packages:
        if not isinstance(raw_item, dict):
            continue

        mode = _normalize_service_mode(
            raw_item.get("kind") or raw_item.get("type"),
            raw_item.get("service_unit") or raw_item.get("unit"),
        )
        if mode not in SERVICE_MODES:
            continue

        quantity = _to_int_or_none(
            raw_item.get("service_quantity")
            or raw_item.get("quantity")
            or raw_item.get("sessions_count")
            or raw_item.get("minutes_total")
            or raw_item.get("total_units")
        )
        if quantity is None:
            continue

        package_name = str(raw_item.get("name") or "").strip()
        return {
            "mode": mode,
            "total_units": quantity,
            "package_name": package_name[:255],
            "raw": raw_item,
        }
    return None


def is_service_package_purchase(purchase: ContactProductPurchase) -> bool:
    return (
        (purchase.service_package_mode or "").strip() in SERVICE_MODES
        and isinstance(purchase.service_package_total_units, int)
        and purchase.service_package_total_units > 0
    )


def _ru_plural(value: int, one: str, few: str, many: str) -> str:
    n = abs(int(value))
    if 11 <= (n % 100) <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def _format_service_units(mode: str, units: int) -> str:
    if mode == SERVICE_MODE_COUNT:
        return f"{units} {_ru_plural(units, 'встреча', 'встречи', 'встреч')}"
    return f"{units} {_ru_plural(units, 'минута', 'минуты', 'минут')}"


def build_service_package_payload(purchase: ContactProductPurchase) -> dict[str, Any] | None:
    if not is_service_package_purchase(purchase):
        return None

    mode = (purchase.service_package_mode or "").strip()
    total_units = int(purchase.service_package_total_units or 0)
    used_units = int(purchase.service_package_used_units or 0)
    remaining_units = total_units - used_units
    is_exhausted = remaining_units <= 0

    payload: dict[str, Any] = {
        "enabled": True,
        "mode": mode,
        "package_name": (purchase.service_package_name or "").strip() or None,
        "total_units": total_units,
        "used_units": used_units,
        "remaining_units": remaining_units,
        "is_exhausted": is_exhausted,
        "total_label": _format_service_units(mode, total_units),
        "used_label": _format_service_units(mode, used_units),
        "remaining_label": _format_service_units(mode, remaining_units),
    }
    if mode == SERVICE_MODE_COUNT:
        payload.update(
            {
                "total_sessions": total_units,
                "used_sessions": used_units,
                "remaining_sessions": remaining_units,
            }
        )
    elif mode == SERVICE_MODE_MINUTES:
        payload.update(
            {
                "total_minutes": total_units,
                "used_minutes": used_units,
                "remaining_minutes": remaining_units,
            }
        )
    return payload


def grant_service_package_to_purchase(
    *,
    purchase: ContactProductPurchase,
    product: ClientProduct | None,
    top_up: bool = True,
) -> bool:
    definition = extract_service_package_definition(product)
    if not definition:
        return False

    mode = str(definition["mode"])
    total_units = int(definition["total_units"])
    package_name = str(definition.get("package_name") or "").strip()[:255]

    current_mode = (purchase.service_package_mode or "").strip()
    current_total = int(purchase.service_package_total_units or 0)
    current_used = int(purchase.service_package_used_units or 0)

    # Если режим поменяли в конфигурации продукта после начала использования,
    # не смешиваем единицы разных типов. Можно будет сделать ручную миграцию данных позже.
    if current_mode and current_mode != mode and current_used > 0:
        return False

    purchase.service_package_mode = mode
    purchase.service_package_name = package_name or purchase.service_package_name or ""
    if top_up and current_mode == mode and current_total > 0:
        purchase.service_package_total_units = current_total + total_units
    else:
        purchase.service_package_total_units = total_units if current_mode != mode else max(current_total, total_units)
    if purchase.service_package_used_units is None:
        purchase.service_package_used_units = 0
    purchase.save(
        update_fields=[
            "service_package_mode",
            "service_package_name",
            "service_package_total_units",
            "service_package_used_units",
            "updated_at",
        ]
    )
    return True


def _event_duration_minutes(event: MapCRMEvent) -> int:
    start = getattr(event, "start_time", None)
    end = getattr(event, "end_time", None)
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return 1
    delta = end - start
    seconds = max(delta.total_seconds(), 0)
    minutes = math.ceil(seconds / 60)
    return max(int(minutes), 1)


def _select_purchase_for_event(client: Client, contact_id: int) -> ContactProductPurchase | None:
    purchases = list(
        ContactProductPurchase.objects.filter(
            client=client,
            contact_id=contact_id,
            service_package_mode__in=[SERVICE_MODE_COUNT, SERVICE_MODE_MINUTES],
        )
        .exclude(service_package_total_units__isnull=True)
        .order_by("-paid_at", "-updated_at", "-id")
    )
    if not purchases:
        return None

    def remaining_units(item: ContactProductPurchase) -> int:
        return int(item.service_package_total_units or 0) - int(item.service_package_used_units or 0)

    purchases.sort(
        key=lambda item: (
            1 if remaining_units(item) > 0 else 0,
            item.paid_at or item.updated_at or timezone.now(),
            item.id,
        ),
        reverse=True,
    )
    return purchases[0]


def _adjust_purchase_used_units(purchase: ContactProductPurchase, delta_units: int) -> None:
    if delta_units == 0:
        return
    current = int(purchase.service_package_used_units or 0)
    purchase.service_package_used_units = max(0, current + int(delta_units))
    purchase.save(update_fields=["service_package_used_units", "updated_at"])


def remove_service_package_usage_for_event(*, event_id: int) -> bool:
    with transaction.atomic():
        usage = (
            ContactProductServiceUsage.objects.select_for_update()
            .select_related("purchase")
            .filter(event_id=event_id)
            .first()
        )
        if usage is None:
            return False

        purchase = (
            ContactProductPurchase.objects.select_for_update()
            .filter(id=usage.purchase_id)
            .first()
        )
        if purchase is not None:
            _adjust_purchase_used_units(purchase, -int(usage.units or 0))
        usage.delete()
        return True


def sync_service_package_usage_for_event(*, client: Client, event: MapCRMEvent) -> dict[str, Any] | None:
    event_id = getattr(event, "id", None)
    if event_id is None:
        return None

    with transaction.atomic():
        usage = (
            ContactProductServiceUsage.objects.select_for_update()
            .select_related("purchase")
            .filter(event_id=event_id)
            .first()
        )

        if getattr(event, "status", None) != "completed":
            if usage is not None:
                purchase = (
                    ContactProductPurchase.objects.select_for_update()
                    .filter(id=usage.purchase_id)
                    .first()
                )
                if purchase is not None:
                    _adjust_purchase_used_units(purchase, -int(usage.units or 0))
                usage.delete()
            return None

        if getattr(event, "contact_id", None) is None:
            return None

        desired_contact_id = int(event.contact_id)

        if usage is not None and (usage.client_id != client.id or usage.contact_id != desired_contact_id):
            purchase = (
                ContactProductPurchase.objects.select_for_update()
                .filter(id=usage.purchase_id)
                .first()
            )
            if purchase is not None:
                _adjust_purchase_used_units(purchase, -int(usage.units or 0))
            usage.delete()
            usage = None

        desired_units_minutes = _event_duration_minutes(event)

        if usage is not None:
            purchase = (
                ContactProductPurchase.objects.select_for_update()
                .filter(id=usage.purchase_id)
                .first()
            )
            if purchase is None:
                usage.delete()
                usage = None
            else:
                if usage.mode == SERVICE_MODE_MINUTES:
                    diff = desired_units_minutes - int(usage.units or 0)
                    if diff:
                        _adjust_purchase_used_units(purchase, diff)
                        usage.units = desired_units_minutes
                usage.event_started_at = getattr(event, "start_time", None)
                usage.event_ended_at = getattr(event, "end_time", None)
                if usage.pk:
                    update_fields = ["event_started_at", "event_ended_at", "updated_at"]
                    if usage.mode == SERVICE_MODE_MINUTES:
                        update_fields.insert(0, "units")
                    usage.save(update_fields=update_fields)
                if usage is not None:
                    return {"purchase_id": usage.purchase_id, "event_id": int(event_id), "mode": usage.mode, "units": int(usage.units or 0)}

        if usage is None:
            purchase = _select_purchase_for_event(client, desired_contact_id)
            if purchase is None or not is_service_package_purchase(purchase):
                return None

            purchase = ContactProductPurchase.objects.select_for_update().get(pk=purchase.pk)
            mode = (purchase.service_package_mode or "").strip()
            if mode not in SERVICE_MODES:
                return None

            units = 1 if mode == SERVICE_MODE_COUNT else desired_units_minutes
            _adjust_purchase_used_units(purchase, units)

            created = ContactProductServiceUsage.objects.create(
                purchase=purchase,
                client=client,
                contact_id=desired_contact_id,
                event_id=int(event_id),
                mode=mode,
                units=units,
                event_started_at=getattr(event, "start_time", None),
                event_ended_at=getattr(event, "end_time", None),
            )
            return {"purchase_id": created.purchase_id, "event_id": int(event_id), "mode": created.mode, "units": int(created.units or 0)}

    return None


def list_contact_service_package_items(*, client: Client, contact_id: int) -> list[dict[str, Any]]:
    purchases = list(
        ContactProductPurchase.objects.filter(
            client=client,
            contact_id=contact_id,
            service_package_mode__in=[SERVICE_MODE_COUNT, SERVICE_MODE_MINUTES],
        )
        .exclude(service_package_total_units__isnull=True)
        .order_by("-paid_at", "-updated_at", "-id")
    )
    if not purchases:
        return []

    product_ids = [int(item.product_id) for item in purchases if item.product_id]
    products_by_id = {
        int(product.id): product
        for product in ClientProduct.objects.filter(owner_id=client.id, id__in=product_ids).only("id", "name")
    }

    items: list[dict[str, Any]] = []
    for purchase in purchases:
        service_payload = build_service_package_payload(purchase)
        if not service_payload:
            continue
        product = products_by_id.get(int(purchase.product_id))
        product_name = (
            ((getattr(product, "name", "") or "").strip())
            or (purchase.product_name or "").strip()
            or f"Продукт #{purchase.product_id}"
        )
        items.append(
            {
                "purchase_id": int(purchase.id),
                "product_id": int(purchase.product_id),
                "product_name": product_name,
                "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
                "amount": str(purchase.amount) if purchase.amount is not None else None,
                "currency": purchase.currency or "RUB",
                "service_package": service_payload,
            }
        )
    return items
