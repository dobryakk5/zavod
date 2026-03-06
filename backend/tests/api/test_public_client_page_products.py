from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import (
    Client,
    ClientProduct,
    ContactProductPurchase,
    KbDocument,
    KbDocumentShare,
    UserTenantRole,
    YooKassaPayment,
)


User = get_user_model()


class _MockYooKassaResponse:
    def __init__(self, *, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        return self._payload


@pytest.fixture
def tenant_user(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="testpass123",
        first_name="Owner",
        last_name="User",
    )


@pytest.fixture
def tenant(db, tenant_user):
    client = Client.objects.create(name="Test Portal", slug="test-portal")
    UserTenantRole.objects.create(user=tenant_user, client=client, role="owner")
    return client


@pytest.fixture
def tenant_api_client(tenant_user):
    client = APIClient()
    client.force_authenticate(user=tenant_user)
    return client


@pytest.fixture
def active_product(tenant):
    return ClientProduct.objects.create(
        owner=tenant,
        name="Digital Course",
        status=ClientProduct.STATUS_ACTIVE,
        short_description="Курс с материалами",
        packages=[{"name": "Base", "price": 1990}],
        structure={},
    )


@pytest.mark.django_db
class TestClientProductDigitalPage:
    def test_create_digital_product_page_creates_kb_document_and_link(self, tenant_api_client, active_product):
        url = reverse("client-product-create-digital-product-page", kwargs={"pk": active_product.id})

        response = tenant_api_client.post(url, {}, format="json")

        assert response.status_code == 201, response.content
        payload = response.json()
        assert payload["created"] is True
        assert payload["product"]["digital_product_document_id"] is not None
        assert payload["document"]["document_type"] == "product"

        active_product.refresh_from_db()
        assert active_product.digital_product_document_id == payload["document"]["id"]
        assert active_product.digital_product_document.title == active_product.name


@pytest.mark.django_db
class TestPublicClientPageDigitalProductPayments:
    def test_buy_creates_yookassa_payment_record(self, api_client, active_product, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 123,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._get_yookassa_credentials",
            lambda client: ("shop", "secret", "basic"),
        )
        monkeypatch.setattr(
            "api.views_public_client_page._yookassa_request",
            lambda *args, **kwargs: _MockYooKassaResponse(
                status_code=201,
                payload={
                    "id": "pay_123",
                    "status": "pending",
                    "confirmation": {"confirmation_url": "https://pay.example/confirm"},
                },
            ),
        )

        url = reverse("public-client-page-buy", kwargs={"client_id": active_product.owner_id})
        response = api_client.post(url, {"product_id": active_product.id}, format="json")

        assert response.status_code == 201, response.content
        body = response.json()
        assert body["id"] == "pay_123"
        assert body["payment_url"] == "https://pay.example/confirm"

        yk_payment = YooKassaPayment.objects.get(payment_id="pay_123")
        assert yk_payment.client_id == active_product.owner_id
        assert yk_payment.amount == Decimal("1990.00")
        assert yk_payment.plan_code == f"digital_product:{active_product.id}:contact:123"

    def test_buy_creates_tbank_payment_record(self, api_client, active_product, monkeypatch, settings):
        settings.TBANK_TERMINAL_KEY = "terminal_key"
        settings.TBANK_SECRET_KEY = "secret_key"
        settings.TBANK_API_URL = "https://securepay.tinkoff.ru/v2"
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 123,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._tbank_request",
            lambda *args, **kwargs: {
                "Success": True,
                "PaymentId": "tb_123",
                "Status": "NEW",
                "PaymentURL": "https://pay.example/tbank",
            },
        )

        url = reverse("public-client-page-buy", kwargs={"client_id": active_product.owner_id})
        response = api_client.post(
            url,
            {"product_id": active_product.id, "provider": "tbank"},
            format="json",
        )

        assert response.status_code == 201, response.content
        body = response.json()
        assert body["id"] == "tb_123"
        assert body["provider"] == "tbank"
        assert body["payment_url"] == "https://pay.example/tbank"

        payment = YooKassaPayment.objects.get(payment_id="tb_123")
        assert payment.client_id == active_product.owner_id
        assert payment.provider == YooKassaPayment.PROVIDER_TBANK
        assert payment.status == YooKassaPayment.STATUS_PENDING
        assert payment.plan_code == f"digital_product:{active_product.id}:contact:123"
        assert payment.amount == Decimal("1990.00")

    def test_buy_requires_contact_auth(self, api_client, active_product, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )

        url = reverse("public-client-page-buy", kwargs={"client_id": active_product.owner_id})
        response = api_client.post(url, {"product_id": active_product.id}, format="json")

        assert response.status_code == 401, response.content
        body = response.json()
        assert body["detail"] == "Для покупки войдите как контакт через Telegram или VK."
        assert YooKassaPayment.objects.count() == 0

    def test_payment_status_returns_share_link_when_product_page_exists(self, api_client, active_product, monkeypatch):
        document = KbDocument.objects.create(
            workspace=active_product.owner,
            title="Digital Course",
            document_type="product",
            content={"type": "doc", "content": []},
            is_published=True,
        )
        active_product.digital_product_document = document
        active_product.save(update_fields=["digital_product_document"])

        YooKassaPayment.objects.create(
            payment_id="pay_ok_1",
            client=active_product.owner,
            status="pending",
            amount=Decimal("1990.00"),
            plan_code=f"digital_product:{active_product.id}",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._get_yookassa_credentials",
            lambda client: ("shop", "secret", "basic"),
        )
        monkeypatch.setattr(
            "api.views_public_client_page._yookassa_request",
            lambda *args, **kwargs: _MockYooKassaResponse(
                status_code=200,
                payload={
                    "id": "pay_ok_1",
                    "status": "succeeded",
                    "paid": True,
                    "metadata": {
                        "payment_kind": "digital_product",
                        "client_id": str(active_product.owner_id),
                        "product_id": str(active_product.id),
                        "contact_id": "321",
                    },
                },
            ),
        )

        url = reverse("public-client-page-payment-status", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url, {"payment_id": "pay_ok_1"})

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["status"] == "succeeded"
        assert body["paid"] is True
        assert body["delivery"]["ready"] is True
        assert "/kb/share/" in body["delivery"]["url"]
        assert KbDocumentShare.objects.filter(document_id=document.id, is_active=True).exists()
        purchase = ContactProductPurchase.objects.get(
            client_id=active_product.owner_id,
            contact_id=321,
            product_id=active_product.id,
        )
        assert purchase.last_payment_id == YooKassaPayment.objects.get(payment_id="pay_ok_1").id
        assert purchase.product_name == active_product.name

    def test_tbank_payment_status_returns_share_link_when_product_page_exists(
        self,
        api_client,
        active_product,
        monkeypatch,
        settings,
    ):
        settings.TBANK_TERMINAL_KEY = "terminal_key"
        settings.TBANK_SECRET_KEY = "secret_key"
        settings.TBANK_API_URL = "https://securepay.tinkoff.ru/v2"

        document = KbDocument.objects.create(
            workspace=active_product.owner,
            title="Digital Course",
            document_type="product",
            content={"type": "doc", "content": []},
            is_published=True,
        )
        active_product.digital_product_document = document
        active_product.save(update_fields=["digital_product_document"])

        YooKassaPayment.objects.create(
            payment_id="tb_ok_1",
            client=active_product.owner,
            provider=YooKassaPayment.PROVIDER_TBANK,
            status=YooKassaPayment.STATUS_PENDING,
            amount=Decimal("1990.00"),
            plan_code=f"digital_product:{active_product.id}:contact:321",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._tbank_request",
            lambda *args, **kwargs: {
                "Success": True,
                "PaymentId": "tb_ok_1",
                "Status": "CONFIRMED",
                "Amount": 199000,
            },
        )

        url = reverse("public-client-page-payment-status", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url, {"payment_id": "tb_ok_1"})

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["provider"] == "tbank"
        assert body["status"] == "succeeded"
        assert body["paid"] is True
        assert body["delivery"]["ready"] is True
        assert "/kb/share/" in body["delivery"]["url"]
        purchase = ContactProductPurchase.objects.get(
            client_id=active_product.owner_id,
            contact_id=321,
            product_id=active_product.id,
        )
        assert purchase.last_payment_id == YooKassaPayment.objects.get(payment_id="tb_ok_1").id

    def test_payment_status_returns_owner_message_when_product_page_missing(self, api_client, active_product, monkeypatch):
        YooKassaPayment.objects.create(
            payment_id="pay_ok_2",
            client=active_product.owner,
            status="pending",
            amount=Decimal("1990.00"),
            plan_code=f"digital_product:{active_product.id}",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._get_yookassa_credentials",
            lambda client: ("shop", "secret", "basic"),
        )
        monkeypatch.setattr(
            "api.views_public_client_page._yookassa_request",
            lambda *args, **kwargs: _MockYooKassaResponse(
                status_code=200,
                payload={
                    "id": "pay_ok_2",
                    "status": "succeeded",
                    "paid": True,
                    "metadata": {
                        "payment_kind": "digital_product",
                        "client_id": str(active_product.owner_id),
                        "product_id": str(active_product.id),
                    },
                },
            ),
        )

        url = reverse("public-client-page-payment-status", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url, {"payment_id": "pay_ok_2"})

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["delivery"]["ready"] is False
        assert body["delivery"]["missing_product_page"] is True
        assert body["delivery"]["message"] == "Покажите информацию об оплате владельцу портала"

    def test_purchases_list_returns_open_link_for_contact(self, api_client, active_product, monkeypatch):
        document = KbDocument.objects.create(
            workspace=active_product.owner,
            title="Digital Course",
            document_type="product",
            content={"type": "doc", "content": []},
            is_published=True,
        )
        active_product.digital_product_document = document
        active_product.save(update_fields=["digital_product_document"])

        yk_payment = YooKassaPayment.objects.create(
            payment_id="pay_history_1",
            client=active_product.owner,
            status="succeeded",
            amount=Decimal("1990.00"),
            plan_code=f"digital_product:{active_product.id}",
        )
        ContactProductPurchase.objects.create(
            client=active_product.owner,
            contact_id=777,
            product_id=active_product.id,
            product_name=active_product.name,
            last_payment=yk_payment,
            amount=Decimal("1990.00"),
            currency="RUB",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 777,
        )

        url = reverse("public-client-page-purchases", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url)

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["contact_id"] == 777
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["product_id"] == active_product.id
        assert item["product_name"] == active_product.name
        assert item["delivery"]["ready"] is True
        assert "/kb/share/" in item["delivery"]["url"]

    def test_purchases_list_returns_fallback_when_product_page_missing(self, api_client, active_product, monkeypatch):
        yk_payment = YooKassaPayment.objects.create(
            payment_id="pay_history_2",
            client=active_product.owner,
            status="succeeded",
            amount=Decimal("1990.00"),
            plan_code=f"digital_product:{active_product.id}",
        )
        ContactProductPurchase.objects.create(
            client=active_product.owner,
            contact_id=888,
            product_id=active_product.id,
            product_name=active_product.name,
            last_payment=yk_payment,
            amount=Decimal("1990.00"),
            currency="RUB",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 888,
        )

        url = reverse("public-client-page-purchases", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url)

        assert response.status_code == 200, response.content
        item = response.json()["items"][0]
        assert item["delivery"]["ready"] is False
        assert item["delivery"]["missing_product_page"] is True
        assert item["delivery"]["message"] == "Покажите информацию об оплате владельцу портала"
