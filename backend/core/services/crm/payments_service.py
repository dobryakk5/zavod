from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum

from core.models import MapCRMEvent, MapCRMPayment
from core.repositories.crm import payments_repository


def build_payments_summary(queryset: QuerySet[MapCRMPayment]) -> dict:
    stats = queryset.aggregate(
        total_paid=Sum("amount", filter=Q(status="paid")) or 0,
        total_pending=Sum("amount", filter=Q(status="pending")) or 0,
        count_paid=Count("id", filter=Q(status="paid")),
        count_pending=Count("id", filter=Q(status="pending")),
    )
    by_currency = list(
        queryset.values("currency")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("currency")
    )
    return {
        **stats,
        "by_currency": by_currency,
        "total_count": queryset.count(),
    }


def filter_payments_by_contact(
    queryset: QuerySet[MapCRMPayment],
    contact_id: str | None,
) -> QuerySet[MapCRMPayment]:
    if not contact_id:
        raise ValueError("Укажите contact_id")
    return queryset.filter(contact_id=contact_id)


def upsert_event_payment(event: MapCRMEvent) -> int | None:
    if event.price is None:
        return None

    description = f"Оплата встречи: {event.title}".strip() or "Оплата встречи"
    amount = Decimal(event.price)
    payment = payments_repository.get_latest_payment_by_event_id(event.id)

    if payment:
        if payment.status == "pending":
            payment.contact_id = event.contact_id
            payment.amount = amount
            payment.currency = "RUB"
            payment.description = description
            payment.planned_at = event.start_time
            payment.save(
                update_fields=[
                    "contact",
                    "amount",
                    "currency",
                    "description",
                    "planned_at",
                    "updated_at",
                ]
            )
        return int(payment.id)

    created = payments_repository.create_event_payment(
        contact_id=event.contact_id,
        event_id=event.id,
        amount=amount,
        description=description,
        planned_at=event.start_time,
    )
    return int(created.id)

