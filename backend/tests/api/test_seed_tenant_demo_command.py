from __future__ import annotations

import pytest
from django.core.management import call_command

from core.models import (
    Client,
    CoachingGoal,
    ContactCoachingProfile,
    MapContact,
    MapCRMDeal,
    MapCRMEvent,
    MapCRMNote,
    MapCRMPayment,
    UserTenantBinding,
)


@pytest.mark.django_db
def test_seed_tenant_demo_command_creates_idempotent_demo_dataset():
    tenant = Client.objects.create(name="Demo Tenant", slug="demo-tenant-command")

    call_command("seed_tenant_demo", tenant_id=tenant.id)

    contact_ids = list(
        UserTenantBinding.objects
        .filter(tenant_id=tenant.id, provider="contact", contact_id__isnull=False)
        .values_list("contact_id", flat=True)
        .distinct()
    )

    assert len(contact_ids) == 5
    assert MapContact.objects.filter(id__in=contact_ids).count() == 5
    assert ContactCoachingProfile.objects.filter(tenant_id=tenant.id, contact_id__in=contact_ids).count() == 5
    assert MapCRMEvent.objects.filter(contact_id__in=contact_ids).count() >= 10
    assert MapCRMDeal.objects.filter(contact_id__in=contact_ids).count() == 5
    assert MapCRMPayment.objects.filter(contact_id__in=contact_ids).count() == 5
    assert MapCRMNote.objects.filter(contact_id__in=contact_ids).count() >= 5

    avg_progresses = sorted(
        round(
            sum(goal.progress for goal in CoachingGoal.objects.filter(profile=profile))
            / max(CoachingGoal.objects.filter(profile=profile).count(), 1)
        )
        for profile in ContactCoachingProfile.objects.filter(tenant_id=tenant.id)
    )
    assert avg_progresses[0] < avg_progresses[-1]

    call_command("seed_tenant_demo", tenant_id=tenant.id)

    contact_ids_after_rerun = list(
        UserTenantBinding.objects
        .filter(tenant_id=tenant.id, provider="contact", contact_id__isnull=False)
        .values_list("contact_id", flat=True)
        .distinct()
    )

    assert len(contact_ids_after_rerun) == 5
    assert ContactCoachingProfile.objects.filter(tenant_id=tenant.id, contact_id__in=contact_ids_after_rerun).count() == 5
    assert MapCRMDeal.objects.filter(contact_id__in=contact_ids_after_rerun).count() == 5
    assert MapCRMPayment.objects.filter(contact_id__in=contact_ids_after_rerun).count() == 5
