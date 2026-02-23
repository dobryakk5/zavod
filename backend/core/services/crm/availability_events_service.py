from __future__ import annotations


def create_availability_event_for_tenant(*, serializer, tenant_id: int):
    return serializer.save(tenant_id=tenant_id)

