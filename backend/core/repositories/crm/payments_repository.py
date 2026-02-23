from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db.models import QuerySet

from core.models import MapCRMPayment


def get_payments_queryset() -> QuerySet[MapCRMPayment]:
    return MapCRMPayment.objects.select_related("contact")


def get_latest_payment_by_event_id(event_id: int) -> MapCRMPayment | None:
    return MapCRMPayment.objects.filter(event_id=event_id).order_by("-id").first()


def create_event_payment(
    *,
    contact_id: int,
    event_id: int,
    amount: Decimal,
    description: str,
    planned_at: datetime | None,
) -> MapCRMPayment:
    return MapCRMPayment.objects.create(
        contact_id=contact_id,
        event_id=event_id,
        product_id=None,
        amount=amount,
        currency="RUB",
        status="pending",
        payment_method="",
        transaction_id="",
        description=description,
        planned_at=planned_at,
        paid_at=None,
    )

