from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import ChannelAnalysis, Client, GenerationEvent, UserTenantRole


User = get_user_model()


@pytest.fixture
def tenant_owner(db):
    user = User.objects.create_user(
        username="analytics_owner",
        email="analytics-owner@example.com",
        password="testpass123",
        first_name="Owner",
        last_name="Analytics",
    )
    client = Client.objects.create(name="Analytics Tenant", slug="analytics-tenant")
    UserTenantRole.objects.create(user=user, client=client, role="owner")
    return user, client


@pytest.fixture
def tenant_api_client(tenant_owner):
    user, _client = tenant_owner
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_tg_channel_analyze_deducts_single_generation(tenant_owner, tenant_api_client, monkeypatch):
    _user, client = tenant_owner

    monkeypatch.setattr(
        "api.views_social.tasks.analyze_channel_task.delay",
        lambda analysis_id: SimpleNamespace(id=f"task-{analysis_id}"),
    )

    response = tenant_api_client.post(
        "/api/tg_channel/",
        {
            "action": "analyze",
            "channel_url": "https://t.me/example_channel",
            "channel_type": "telegram",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.data["success"] is True

    analysis = ChannelAnalysis.objects.get(client=client, task_id=response.data["task_id"])
    assert analysis.channel_type == "telegram"

    events_count = GenerationEvent.objects.filter(
        client=client,
        event_type=GenerationEvent.EVENT_CHANNEL_ANALYSIS,
    ).count()
    assert events_count == 1
