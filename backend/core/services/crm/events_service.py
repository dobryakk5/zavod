from __future__ import annotations

from core.models import MapCRMEvent
from core.services.crm.payments_service import upsert_event_payment


def on_event_created(event: MapCRMEvent) -> None:
    upsert_event_payment(event)


def on_event_updated(event: MapCRMEvent, request_data: dict) -> None:
    if "price" in request_data and event.price is not None:
        upsert_event_payment(event)

