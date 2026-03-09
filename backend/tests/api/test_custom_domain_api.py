from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Client, UserTenantRole
from core.services.custom_domain import CustomDomainVerificationResult


User = get_user_model()


@pytest.fixture
def tenant_owner(db):
    user = User.objects.create_user(
        username="owner-custom-domain",
        email="owner-custom-domain@example.com",
        password="testpass123",
        first_name="Owner",
        last_name="CustomDomain",
    )
    tenant = Client.objects.create(name="Custom Domain Tenant", slug="custom-domain-tenant")
    UserTenantRole.objects.create(user=user, client=tenant, role="owner")
    return user, tenant


@pytest.fixture
def tenant_owner_client(tenant_owner):
    user, _tenant = tenant_owner
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_client_settings_normalizes_custom_domain_and_resets_verified(tenant_owner_client, tenant_owner):
    _user, tenant = tenant_owner
    tenant.custom_domain = "old.example.com"
    tenant.domain_verified = True
    tenant.save(update_fields=["custom_domain", "domain_verified"])

    url = reverse("api:client-settings")
    response = tenant_owner_client.patch(
        url,
        {"custom_domain": "https://WWW.New-Example.com/path"},
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["custom_domain"] == "www.new-example.com"
    assert payload["domain_verified"] is False

    tenant.refresh_from_db()
    assert tenant.custom_domain == "www.new-example.com"
    assert tenant.domain_verified is False


@pytest.mark.django_db
def test_verify_custom_domain_endpoint_marks_domain_verified(monkeypatch, tenant_owner_client, tenant_owner):
    _user, tenant = tenant_owner

    monkeypatch.setattr(
        "api.views_accounts.verify_custom_domain_dns",
        lambda *args, **kwargs: CustomDomainVerificationResult(
            verified=True,
            method="cname",
            domain="www.example.com",
            expected_cname="fibonatty.ru",
            resolved_cname=["fibonatty.ru"],
            resolved_ips=[],
            error=None,
        ),
    )

    url = reverse("api:client-custom-domain-verify")
    response = tenant_owner_client.post(url, {"domain": "www.example.com"}, format="json")

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["verified"] is True
    assert payload["method"] == "cname"
    assert payload["domain"] == "www.example.com"

    tenant.refresh_from_db()
    assert tenant.custom_domain == "www.example.com"
    assert tenant.domain_verified is True


@pytest.mark.django_db
def test_public_client_page_by_domain_requires_verified_domain(api_client, tenant_owner):
    _user, tenant = tenant_owner
    tenant.custom_domain = "www.unverified.example.com"
    tenant.domain_verified = False
    tenant.save(update_fields=["custom_domain", "domain_verified"])

    url = reverse("api:public-client-page-by-domain")
    response = api_client.get(url, {"domain": "www.unverified.example.com"})
    assert response.status_code == 404, response.content


@pytest.mark.django_db
def test_public_client_page_by_domain_returns_payload(monkeypatch, api_client, tenant_owner):
    _user, tenant = tenant_owner
    tenant.custom_domain = "www.verified.example.com"
    tenant.domain_verified = True
    tenant.save(update_fields=["custom_domain", "domain_verified"])

    monkeypatch.setattr(
        "api.views_public_client_page._build_public_client_page_payload",
        lambda client_id: {
            "client": {"id": client_id, "name": tenant.name},
            "events": [],
            "products": [],
            "tasks_enabled": False,
            "settings": {},
        },
    )

    url = reverse("api:public-client-page-by-domain")
    response = api_client.get(url, {"domain": "https://www.verified.example.com/path"})

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["client"]["id"] == tenant.id
    assert payload["client"]["name"] == tenant.name


@pytest.mark.django_db
def test_caddy_ask_returns_200_for_verified_domain(api_client, tenant_owner):
    _user, tenant = tenant_owner
    tenant.custom_domain = "www.caddy-ok.example.com"
    tenant.domain_verified = True
    tenant.save(update_fields=["custom_domain", "domain_verified"])

    url = reverse("api:caddy-ask")
    response = api_client.get(url, {"domain": "WWW.Caddy-Ok.Example.com."})

    assert response.status_code == 200, response.content


@pytest.mark.django_db
def test_caddy_ask_returns_403_for_unknown_domain(api_client):
    url = reverse("api:caddy-ask")
    response = api_client.get(url, {"domain": "www.unknown-caddy-domain.example.com"})

    assert response.status_code == 403, response.content
