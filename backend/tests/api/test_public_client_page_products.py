from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Client,
    ClientProduct,
    ContactProductPurchase,
    MapContact,
    ProductCourse,
    ProductCourseComment,
    ProductCourseEvent,
    ProductCourseLesson,
    ProductCourseModule,
    ProductCourseProgress,
    UserTenantBinding,
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


@pytest.fixture
def published_course(active_product):
    course = ProductCourse.objects.create(
        owner=active_product.owner,
        product=active_product,
        title="Курс по продукту",
        description="Описание курса",
        is_published=True,
    )
    module = ProductCourseModule.objects.create(
        course=course,
        title="Модуль 1",
        position=0,
    )
    preview_lesson = ProductCourseLesson.objects.create(
        module=module,
        title="Урок без оплаты",
        position=0,
        is_preview=True,
        content={"type": "doc", "content": []},
    )
    paid_lesson = ProductCourseLesson.objects.create(
        module=module,
        title="Платный урок",
        position=1,
        is_preview=False,
        content={"type": "doc", "content": []},
    )
    return {
        "course": course,
        "module": module,
        "preview_lesson": preview_lesson,
        "paid_lesson": paid_lesson,
    }


@pytest.mark.django_db
class TestPublicClientPageCourseProductPayments:
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
        assert yk_payment.plan_code == f"course_product:{active_product.id}:contact:123"

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
        assert payment.plan_code == f"course_product:{active_product.id}:contact:123"
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

    def test_payment_status_returns_course_link_when_course_is_published(self, api_client, active_product, monkeypatch):
        ProductCourse.objects.create(
            owner=active_product.owner,
            product=active_product,
            title="Курс",
            is_published=True,
        )

        YooKassaPayment.objects.create(
            payment_id="pay_ok_1",
            client=active_product.owner,
            status="pending",
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}",
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
                        "payment_kind": "course_product",
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
        assert body["delivery"]["url"].endswith(f"/c/{active_product.owner_id}/products/{active_product.id}/course")
        purchase = ContactProductPurchase.objects.get(
            client_id=active_product.owner_id,
            contact_id=321,
            product_id=active_product.id,
        )
        assert purchase.last_payment_id == YooKassaPayment.objects.get(payment_id="pay_ok_1").id
        assert purchase.product_name == active_product.name

    def test_payment_status_returns_owner_message_when_course_missing(self, api_client, active_product, monkeypatch):
        YooKassaPayment.objects.create(
            payment_id="pay_ok_2",
            client=active_product.owner,
            status="pending",
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}",
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
                        "payment_kind": "course_product",
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
        assert body["delivery"]["missing_course"] is True
        assert body["delivery"]["message"] == "Курс пока не опубликован. Свяжитесь с владельцем портала."

    def test_payment_status_notifies_contact_once_per_payment(self, api_client, active_product, monkeypatch):
        YooKassaPayment.objects.create(
            payment_id="pay_notify_1",
            client=active_product.owner,
            status="pending",
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}:contact:321",
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
                    "id": "pay_notify_1",
                    "status": "succeeded",
                    "paid": True,
                    "metadata": {
                        "payment_kind": "course_product",
                        "client_id": str(active_product.owner_id),
                        "product_id": str(active_product.id),
                        "contact_id": "321",
                    },
                    "amount": {"value": "1990.00", "currency": "RUB"},
                },
            ),
        )

        notifications: list[dict] = []
        monkeypatch.setattr(
            "api.views_public_client_page._notify_contact_purchase_success",
            lambda **kwargs: notifications.append(kwargs) or True,
        )

        url = reverse("public-client-page-payment-status", kwargs={"client_id": active_product.owner_id})
        first = api_client.get(url, {"payment_id": "pay_notify_1"})
        second = api_client.get(url, {"payment_id": "pay_notify_1"})

        assert first.status_code == 200, first.content
        assert second.status_code == 200, second.content
        assert len(notifications) == 1

    def test_payment_status_notifies_even_when_payment_already_succeeded(self, api_client, active_product, monkeypatch):
        YooKassaPayment.objects.create(
            payment_id="pay_notify_2",
            client=active_product.owner,
            status=YooKassaPayment.STATUS_SUCCEEDED,
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}:contact:555",
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
                    "id": "pay_notify_2",
                    "status": "succeeded",
                    "paid": True,
                    "metadata": {
                        "payment_kind": "course_product",
                        "client_id": str(active_product.owner_id),
                        "product_id": str(active_product.id),
                        "contact_id": "555",
                    },
                    "amount": {"value": "1990.00", "currency": "RUB"},
                },
            ),
        )

        notifications: list[dict] = []
        monkeypatch.setattr(
            "api.views_public_client_page._notify_contact_purchase_success",
            lambda **kwargs: notifications.append(kwargs) or True,
        )

        url = reverse("public-client-page-payment-status", kwargs={"client_id": active_product.owner_id})
        response = api_client.get(url, {"payment_id": "pay_notify_2"})

        assert response.status_code == 200, response.content
        assert len(notifications) == 1

    def test_tbank_payment_status_returns_course_link_when_course_is_published(
        self,
        api_client,
        active_product,
        monkeypatch,
        settings,
    ):
        settings.TBANK_TERMINAL_KEY = "terminal_key"
        settings.TBANK_SECRET_KEY = "secret_key"
        settings.TBANK_API_URL = "https://securepay.tinkoff.ru/v2"

        ProductCourse.objects.create(
            owner=active_product.owner,
            product=active_product,
            title="Курс",
            is_published=True,
        )

        YooKassaPayment.objects.create(
            payment_id="tb_ok_1",
            client=active_product.owner,
            provider=YooKassaPayment.PROVIDER_TBANK,
            status=YooKassaPayment.STATUS_PENDING,
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}:contact:321",
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
        assert body["delivery"]["url"].endswith(f"/c/{active_product.owner_id}/products/{active_product.id}/course")
        purchase = ContactProductPurchase.objects.get(
            client_id=active_product.owner_id,
            contact_id=321,
            product_id=active_product.id,
        )
        assert purchase.last_payment_id == YooKassaPayment.objects.get(payment_id="tb_ok_1").id

    def test_purchases_list_returns_open_link_for_contact(self, api_client, active_product, monkeypatch):
        ProductCourse.objects.create(
            owner=active_product.owner,
            product=active_product,
            title="Курс",
            is_published=True,
        )

        yk_payment = YooKassaPayment.objects.create(
            payment_id="pay_history_1",
            client=active_product.owner,
            status="succeeded",
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}",
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
        assert item["delivery"]["url"].endswith(f"/c/{active_product.owner_id}/products/{active_product.id}/course")

    def test_purchases_list_returns_fallback_when_course_missing(self, api_client, active_product, monkeypatch):
        yk_payment = YooKassaPayment.objects.create(
            payment_id="pay_history_2",
            client=active_product.owner,
            status="succeeded",
            amount=Decimal("1990.00"),
            plan_code=f"course_product:{active_product.id}",
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
        assert item["delivery"]["missing_course"] is True
        assert item["delivery"]["message"] == "Курс пока не опубликован. Свяжитесь с владельцем портала."


@pytest.mark.django_db
class TestPublicClientPageCourseEndpoints:
    def test_course_overview_requires_auth(self, api_client, active_product, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course",
            kwargs={"client_id": active_product.owner_id, "product_id": active_product.id},
        )
        response = api_client.get(url)

        assert response.status_code == 401, response.content

    def test_course_overview_allows_contact_auth(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 555,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course",
            kwargs={"client_id": active_product.owner_id, "product_id": active_product.id},
        )
        response = api_client.get(url)

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["access"]["is_contact_bound"] is True
        assert body["access"]["is_paid"] is False
        lessons = body["course"]["modules"][0]["lessons"]
        assert lessons[0]["id"] == published_course["preview_lesson"].id
        assert lessons[0]["is_locked"] is False
        assert lessons[1]["id"] == published_course["paid_lesson"].id
        assert lessons[1]["is_locked"] is True

    def test_course_overview_allows_tenant_auth_and_unlocks_lessons(
        self,
        tenant_api_client,
        active_product,
        published_course,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )

        url = reverse(
            "public-client-page-product-course",
            kwargs={"client_id": active_product.owner_id, "product_id": active_product.id},
        )
        response = tenant_api_client.get(url)

        assert response.status_code == 200, response.content
        body = response.json()
        assert body["access"]["is_tenant_user"] is True
        lessons = body["course"]["modules"][0]["lessons"]
        assert lessons[0]["is_locked"] is False
        assert lessons[1]["is_locked"] is False

    def test_lesson_endpoint_requires_auth(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course-lesson",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        response = api_client.get(url)

        assert response.status_code == 401, response.content

    def test_lesson_endpoint_blocks_non_preview_without_purchase(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 555,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course-lesson",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["paid_lesson"].id,
            },
        )
        response = api_client.get(url)

        assert response.status_code == 403, response.content
        assert response.json()["is_locked"] is True

    def test_lesson_endpoint_allows_preview_without_purchase(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 555,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course-lesson",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        response = api_client.get(url)

        assert response.status_code == 200, response.content
        assert response.json()["id"] == published_course["preview_lesson"].id

    def test_lesson_unlock_at_respected_for_preview(self, api_client, active_product, published_course, monkeypatch):
        preview_lesson = published_course["preview_lesson"]
        preview_lesson.unlock_at = timezone.now() + timedelta(days=1)
        preview_lesson.save(update_fields=["unlock_at"])

        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 555,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        url = reverse(
            "public-client-page-product-course-lesson",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": preview_lesson.id,
            },
        )
        response = api_client.get(url)

        assert response.status_code == 403, response.content
        assert response.json()["is_locked"] is True

    def test_complete_is_idempotent_and_updates_progress(self, api_client, active_product, published_course, monkeypatch):
        contact_id = 555
        ContactProductPurchase.objects.create(
            client=active_product.owner,
            contact_id=contact_id,
            product_id=active_product.id,
            product_name=active_product.name,
            amount=Decimal("1990.00"),
            currency="RUB",
        )

        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: contact_id,
        )

        complete_url = reverse(
            "public-client-page-product-course-lesson-complete",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["paid_lesson"].id,
            },
        )
        first = api_client.post(complete_url, {}, format="json")
        second = api_client.post(complete_url, {}, format="json")

        assert first.status_code == 200, first.content
        assert second.status_code == 200, second.content
        assert ProductCourseProgress.objects.filter(
            owner_id=active_product.owner_id,
            contact_id=contact_id,
            lesson_id=published_course["paid_lesson"].id,
        ).count() == 1
        assert ProductCourseEvent.objects.filter(
            owner_id=active_product.owner_id,
            contact_id=contact_id,
            lesson_id=published_course["paid_lesson"].id,
            event_type=ProductCourseEvent.EVENT_LESSON_COMPLETED,
        ).count() == 1

        overview_url = reverse(
            "public-client-page-product-course",
            kwargs={"client_id": active_product.owner_id, "product_id": active_product.id},
        )
        overview = api_client.get(overview_url)
        assert overview.status_code == 200, overview.content
        progress = overview.json()["course"]["progress"]
        assert progress["completed_lessons"] == 1
        assert progress["total_lessons"] == 2

    def test_complete_requires_contact_binding(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )

        complete_url = reverse(
            "public-client-page-product-course-lesson-complete",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        response = api_client.post(complete_url, {}, format="json")

        assert response.status_code == 401, response.content

    def test_complete_requires_paid_purchase_for_non_preview(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: 999,
        )

        complete_url = reverse(
            "public-client-page-product-course-lesson-complete",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["paid_lesson"].id,
            },
        )
        response = api_client.post(complete_url, {}, format="json")

        assert response.status_code == 403, response.content

    def test_lesson_comments_requires_contact_binding(self, api_client, active_product, published_course, monkeypatch):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )
        comments_url = reverse(
            "public-client-page-product-course-lesson-comments",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        response = api_client.get(comments_url)
        assert response.status_code == 401, response.content

    def test_lesson_comments_roundtrip_for_contact(self, api_client, active_product, published_course, monkeypatch):
        contact_id = 555
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: contact_id,
        )

        comments_url = reverse(
            "public-client-page-product-course-lesson-comments",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        get_response = api_client.get(comments_url)
        assert get_response.status_code == 200, get_response.content
        assert get_response.json()["comments"] == []

        post_response = api_client.post(comments_url, {"message_text": "Вопрос по уроку"}, format="json")
        assert post_response.status_code == 201, post_response.content
        assert ProductCourseComment.objects.filter(
            owner_id=active_product.owner_id,
            contact_id=contact_id,
            lesson_id=published_course["preview_lesson"].id,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
        ).count() == 1

        get_after_post = api_client.get(comments_url)
        assert get_after_post.status_code == 200, get_after_post.content
        comments = get_after_post.json()["comments"]
        assert len(comments) == 1
        assert comments[0]["message_text"] == "Вопрос по уроку"
        assert comments[0]["author_role"] == ProductCourseComment.AUTHOR_STUDENT

    def test_lesson_comments_allows_tenant_and_creates_curator_comment(
        self,
        tenant_api_client,
        tenant_user,
        active_product,
        published_course,
    ):
        lesson = published_course["preview_lesson"]
        ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=555,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Вопрос ученика",
        )

        comments_url = reverse(
            "public-client-page-product-course-lesson-comments",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": lesson.id,
            },
        )
        get_response = tenant_api_client.get(comments_url)
        assert get_response.status_code == 200, get_response.content
        list_payload = get_response.json()
        assert list_payload["is_tenant_user"] is True
        assert len(list_payload["comments"]) == 1
        assert list_payload["comments"][0]["can_delete"] is True

        post_response = tenant_api_client.post(
            comments_url,
            {"message_text": "Ответ куратора"},
            format="json",
        )
        assert post_response.status_code == 201, post_response.content
        created = post_response.json()["comment"]
        assert created["author_role"] == ProductCourseComment.AUTHOR_CURATOR
        assert created["author_user_id"] == tenant_user.id

    def test_contact_can_delete_only_own_student_comment(self, api_client, active_product, published_course, monkeypatch):
        contact_id = 555
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: contact_id,
        )

        lesson = published_course["preview_lesson"]
        own_comment = ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=contact_id,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Мой комментарий",
        )
        other_comment = ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=777,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Чужой комментарий",
        )
        curator_comment = ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=contact_id,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_CURATOR,
            author_user_id=123,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Ответ куратора",
        )

        comments_url = reverse(
            "public-client-page-product-course-lesson-comments",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": lesson.id,
            },
        )

        delete_own = api_client.delete(f"{comments_url}?comment_id={own_comment.id}")
        assert delete_own.status_code == 204, delete_own.content
        assert not ProductCourseComment.objects.filter(id=own_comment.id).exists()

        delete_other = api_client.delete(f"{comments_url}?comment_id={other_comment.id}")
        assert delete_other.status_code == 403, delete_other.content
        assert ProductCourseComment.objects.filter(id=other_comment.id).exists()

        delete_curator = api_client.delete(f"{comments_url}?comment_id={curator_comment.id}")
        assert delete_curator.status_code == 403, delete_curator.content
        assert ProductCourseComment.objects.filter(id=curator_comment.id).exists()

    def test_tenant_can_delete_any_lesson_comment(self, tenant_api_client, active_product, published_course):
        lesson = published_course["preview_lesson"]
        student_comment = ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=555,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Комментарий ученика",
        )
        curator_comment = ProductCourseComment.objects.create(
            owner_id=active_product.owner_id,
            contact_id=777,
            product_id=active_product.id,
            course_id=published_course["course"].id,
            module_id=published_course["module"].id,
            lesson_id=lesson.id,
            author_role=ProductCourseComment.AUTHOR_CURATOR,
            author_user_id=42,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Комментарий куратора",
        )

        comments_url = reverse(
            "public-client-page-product-course-lesson-comments",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": lesson.id,
            },
        )

        delete_student = tenant_api_client.delete(f"{comments_url}?comment_id={student_comment.id}")
        assert delete_student.status_code == 204, delete_student.content
        delete_curator = tenant_api_client.delete(f"{comments_url}?comment_id={curator_comment.id}")
        assert delete_curator.status_code == 204, delete_curator.content
        assert not ProductCourseComment.objects.filter(id__in=[student_comment.id, curator_comment.id]).exists()

    def test_tenant_can_complete_paid_lesson_with_auto_contact_and_purchase(
        self,
        tenant_api_client,
        tenant_user,
        active_product,
        published_course,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )

        complete_url = reverse(
            "public-client-page-product-course-lesson-complete",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["paid_lesson"].id,
            },
        )
        response = tenant_api_client.post(complete_url, {}, format="json")

        assert response.status_code == 200, response.content
        binding = UserTenantBinding.objects.filter(
            tenant_id=active_product.owner_id,
            provider=UserTenantBinding.PROVIDER_CONTACT,
            provider_user_id=f"user:{tenant_user.id}",
            is_active=True,
        ).first()
        assert binding is not None
        assert binding.contact_id is not None and int(binding.contact_id) > 0
        assert MapContact.objects.filter(id=int(binding.contact_id)).exists()
        assert ContactProductPurchase.objects.filter(
            client_id=active_product.owner_id,
            contact_id=int(binding.contact_id),
            product_id=active_product.id,
        ).exists()
        assert ProductCourseProgress.objects.filter(
            owner_id=active_product.owner_id,
            contact_id=int(binding.contact_id),
            lesson_id=published_course["paid_lesson"].id,
        ).exists()

    def test_authenticated_user_can_access_and_complete_preview_with_auto_contact(
        self,
        api_client,
        active_product,
        published_course,
        monkeypatch,
    ):
        user = User.objects.create_user(email="student-preview@example.com", password="testpass123")
        api_client.force_authenticate(user=user)
        monkeypatch.setattr(
            "api.views_public_client_page._resolve_request_contact_id_for_client",
            lambda request, client_id: None,
        )
        monkeypatch.setattr(
            "api.views_public_client_page._has_tenant_course_access",
            lambda request, client_id: False,
        )

        overview_url = reverse(
            "public-client-page-product-course",
            kwargs={"client_id": active_product.owner_id, "product_id": active_product.id},
        )
        overview = api_client.get(overview_url)
        assert overview.status_code == 200, overview.content
        lessons = overview.json()["course"]["modules"][0]["lessons"]
        assert lessons[0]["id"] == published_course["preview_lesson"].id
        assert lessons[0]["is_locked"] is False
        assert lessons[1]["id"] == published_course["paid_lesson"].id
        assert lessons[1]["is_locked"] is True

        complete_url = reverse(
            "public-client-page-product-course-lesson-complete",
            kwargs={
                "client_id": active_product.owner_id,
                "product_id": active_product.id,
                "lesson_id": published_course["preview_lesson"].id,
            },
        )
        response = api_client.post(complete_url, {}, format="json")
        assert response.status_code == 200, response.content

        binding = UserTenantBinding.objects.filter(
            tenant_id=active_product.owner_id,
            provider=UserTenantBinding.PROVIDER_CONTACT,
            provider_user_id=f"user:{user.id}",
            is_active=True,
        ).first()
        assert binding is not None
        assert binding.contact_id is not None and int(binding.contact_id) > 0
        assert ProductCourseProgress.objects.filter(
            owner_id=active_product.owner_id,
            contact_id=int(binding.contact_id),
            lesson_id=published_course["preview_lesson"].id,
        ).exists()
