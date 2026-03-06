from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Client, MapContact, UserTenantBinding, UserTenantRole


User = get_user_model()


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _bind_contact_to_tenant(*, tenant: Client, contact: MapContact, marker: str) -> None:
    UserTenantBinding.objects.create(
        tenant=tenant,
        provider=UserTenantBinding.PROVIDER_CONTACT,
        provider_user_id=f"contact:{int(contact.id)}:{marker}",
        contact_id=int(contact.id),
        is_active=True,
    )


@pytest.mark.django_db
def test_crm_contacts_list_and_update_are_scoped_by_tenant_binding():
    user_t1 = User.objects.create_user(email="tenant1-crm@example.com", password="testpass123")
    user_t2 = User.objects.create_user(email="tenant2-crm@example.com", password="testpass123")
    tenant_1 = Client.objects.create(name="Tenant One CRM", slug="tenant-one-crm")
    tenant_2 = Client.objects.create(name="Tenant Two CRM", slug="tenant-two-crm")
    UserTenantRole.objects.create(user=user_t1, client=tenant_1, role="owner")
    UserTenantRole.objects.create(user=user_t2, client=tenant_2, role="owner")

    shared = MapContact.objects.create(name="Shared Contact")
    only_t1 = MapContact.objects.create(name="Only Tenant 1")
    only_t2 = MapContact.objects.create(name="Only Tenant 2")
    _bind_contact_to_tenant(tenant=tenant_1, contact=shared, marker="t1-shared")
    _bind_contact_to_tenant(tenant=tenant_2, contact=shared, marker="t2-shared")
    _bind_contact_to_tenant(tenant=tenant_1, contact=only_t1, marker="t1-only")
    _bind_contact_to_tenant(tenant=tenant_2, contact=only_t2, marker="t2-only")

    api_t1 = _auth_client(user_t1)
    api_t2 = _auth_client(user_t2)

    resp_t1 = api_t1.get("/api/crm/contacts/")
    resp_t2 = api_t2.get("/api/crm/contacts/")
    assert resp_t1.status_code == 200, resp_t1.content
    assert resp_t2.status_code == 200, resp_t2.content

    ids_t1 = {int(item["id"]) for item in resp_t1.json()}
    ids_t2 = {int(item["id"]) for item in resp_t2.json()}
    assert int(shared.id) in ids_t1
    assert int(only_t1.id) in ids_t1
    assert int(only_t2.id) not in ids_t1
    assert int(shared.id) in ids_t2
    assert int(only_t2.id) in ids_t2
    assert int(only_t1.id) not in ids_t2

    forbidden_patch = api_t1.patch(
        f"/api/crm/contacts/{int(only_t2.id)}/",
        {"name": "Cross Tenant Rename"},
        format="json",
    )
    assert forbidden_patch.status_code == 404


@pytest.mark.django_db
def test_crm_contact_create_binds_new_contact_to_active_tenant_only():
    user_t1 = User.objects.create_user(email="tenant1-create@example.com", password="testpass123")
    user_t2 = User.objects.create_user(email="tenant2-create@example.com", password="testpass123")
    tenant_1 = Client.objects.create(name="Tenant One Create", slug="tenant-one-create")
    tenant_2 = Client.objects.create(name="Tenant Two Create", slug="tenant-two-create")
    UserTenantRole.objects.create(user=user_t1, client=tenant_1, role="owner")
    UserTenantRole.objects.create(user=user_t2, client=tenant_2, role="owner")

    api_t1 = _auth_client(user_t1)
    api_t2 = _auth_client(user_t2)

    created = api_t1.post("/api/crm/contacts/", {"name": "Tenant1 New Contact"}, format="json")
    assert created.status_code == 201, created.content
    contact_id = int(created.json()["id"])

    assert UserTenantBinding.objects.filter(
        tenant=tenant_1,
        contact_id=contact_id,
    ).exists()
    assert not UserTenantBinding.objects.filter(
        tenant=tenant_2,
        contact_id=contact_id,
    ).exists()

    list_t2 = api_t2.get("/api/crm/contacts/")
    assert list_t2.status_code == 200, list_t2.content
    ids_t2 = {int(item["id"]) for item in list_t2.json()}
    assert contact_id not in ids_t2


@pytest.mark.django_db
def test_crm_contact_delete_detaches_current_tenant_and_keeps_shared_contact():
    user_t1 = User.objects.create_user(email="tenant1-delete@example.com", password="testpass123")
    user_t2 = User.objects.create_user(email="tenant2-delete@example.com", password="testpass123")
    tenant_1 = Client.objects.create(name="Tenant One Delete", slug="tenant-one-delete")
    tenant_2 = Client.objects.create(name="Tenant Two Delete", slug="tenant-two-delete")
    UserTenantRole.objects.create(user=user_t1, client=tenant_1, role="owner")
    UserTenantRole.objects.create(user=user_t2, client=tenant_2, role="owner")

    shared = MapContact.objects.create(name="Shared For Delete")
    _bind_contact_to_tenant(tenant=tenant_1, contact=shared, marker="delete-t1")
    _bind_contact_to_tenant(tenant=tenant_2, contact=shared, marker="delete-t2")

    api_t1 = _auth_client(user_t1)
    api_t2 = _auth_client(user_t2)

    detached = api_t1.delete(f"/api/crm/contacts/{int(shared.id)}/")
    assert detached.status_code == 204, detached.content
    assert MapContact.objects.filter(id=shared.id).exists()
    assert not UserTenantBinding.objects.filter(tenant=tenant_1, contact_id=shared.id).exists()
    assert UserTenantBinding.objects.filter(tenant=tenant_2, contact_id=shared.id).exists()

    list_t2 = api_t2.get("/api/crm/contacts/")
    assert list_t2.status_code == 200, list_t2.content
    ids_t2 = {int(item["id"]) for item in list_t2.json()}
    assert int(shared.id) in ids_t2

    deleted = api_t2.delete(f"/api/crm/contacts/{int(shared.id)}/")
    assert deleted.status_code == 204, deleted.content
    assert not MapContact.objects.filter(id=shared.id).exists()
