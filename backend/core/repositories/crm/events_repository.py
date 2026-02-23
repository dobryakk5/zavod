from __future__ import annotations

from django.db.models import QuerySet

from core.models import (
    MapAvailabilityEvent,
    MapCRMEvent,
    MapCRMEventType,
    MapCRMNote,
)


def get_event_types_queryset() -> QuerySet[MapCRMEventType]:
    return MapCRMEventType.objects.all()


def get_events_queryset() -> QuerySet[MapCRMEvent]:
    return MapCRMEvent.objects.select_related("contact", "event_type").order_by("-start_time")


def get_availability_events_queryset(tenant_id: int) -> QuerySet[MapAvailabilityEvent]:
    return MapAvailabilityEvent.objects.filter(tenant_id=tenant_id).order_by("-start_time")


def get_notes_queryset() -> QuerySet[MapCRMNote]:
    return MapCRMNote.objects.select_related("contact").order_by("-created_at")

