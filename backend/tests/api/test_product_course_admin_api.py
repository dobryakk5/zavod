from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Client, ClientProduct, UserTenantRole


User = get_user_model()


@pytest.fixture
def tenant(db):
    return Client.objects.create(name="LMS tenant", slug="lms-tenant")


@pytest.fixture
def owner_user(db):
    return User.objects.create_user(email="owner-lms@example.com", password="testpass123")


@pytest.fixture
def editor_user(db):
    return User.objects.create_user(email="editor-lms@example.com", password="testpass123")


@pytest.fixture
def viewer_user(db):
    return User.objects.create_user(email="viewer-lms@example.com", password="testpass123")


@pytest.fixture
def owner_api_client(owner_user, tenant):
    UserTenantRole.objects.create(user=owner_user, client=tenant, role="owner")
    client = APIClient()
    client.force_authenticate(user=owner_user)
    return client


@pytest.fixture
def editor_api_client(editor_user, tenant):
    UserTenantRole.objects.create(user=editor_user, client=tenant, role="editor")
    client = APIClient()
    client.force_authenticate(user=editor_user)
    return client


@pytest.fixture
def viewer_api_client(viewer_user, tenant):
    UserTenantRole.objects.create(user=viewer_user, client=tenant, role="viewer")
    client = APIClient()
    client.force_authenticate(user=viewer_user)
    return client


@pytest.fixture
def active_product(tenant):
    return ClientProduct.objects.create(
        owner=tenant,
        name="LMS Product",
        status=ClientProduct.STATUS_ACTIVE,
        short_description="Описание",
        packages=[{"name": "Base", "price": 1000}],
        structure={},
    )


@pytest.mark.django_db
class TestProductCourseAdminApi:
    def test_owner_can_crud_course_modules_lessons(self, owner_api_client, active_product):
        course_url = reverse("client-product-manage-course", kwargs={"pk": active_product.id})
        response = owner_api_client.get(course_url)
        assert response.status_code == 200, response.content
        assert response.json()["course"] is None

        response = owner_api_client.put(
            course_url,
            {
                "title": "Курс",
                "description": "Описание курса",
                "is_published": False,
            },
            format="json",
        )
        assert response.status_code == 200, response.content
        course_payload = response.json()["course"]
        assert course_payload["title"] == "Курс"

        create_module_url = reverse("client-product-create-course-module", kwargs={"pk": active_product.id})
        response = owner_api_client.post(create_module_url, {"title": "Модуль 1"}, format="json")
        assert response.status_code == 201, response.content
        module_id = response.json()["id"]

        create_lesson_url = reverse(
            "client-product-create-course-lesson",
            kwargs={"pk": active_product.id, "module_id": module_id},
        )
        response = owner_api_client.post(
            create_lesson_url,
            {"title": "Урок 1", "is_preview": True, "content": {"type": "doc", "content": []}},
            format="json",
        )
        assert response.status_code == 201, response.content
        lesson_id = response.json()["id"]

        patch_module_url = reverse(
            "client-product-manage-course-module",
            kwargs={"pk": active_product.id, "module_id": module_id},
        )
        response = owner_api_client.patch(patch_module_url, {"title": "Модуль 1 updated"}, format="json")
        assert response.status_code == 200, response.content
        assert response.json()["title"] == "Модуль 1 updated"

        patch_lesson_url = reverse(
            "client-product-manage-course-lesson",
            kwargs={"pk": active_product.id, "lesson_id": lesson_id},
        )
        response = owner_api_client.patch(
            patch_lesson_url,
            {"title": "Урок 1 updated", "is_preview": False},
            format="json",
        )
        assert response.status_code == 200, response.content
        assert response.json()["title"] == "Урок 1 updated"
        assert response.json()["is_preview"] is False

        reorder_modules_url = reverse("client-product-reorder-course-modules", kwargs={"pk": active_product.id})
        response = owner_api_client.patch(reorder_modules_url, {"ordered_ids": [module_id]}, format="json")
        assert response.status_code == 204, response.content

        reorder_lessons_url = reverse(
            "client-product-reorder-course-lessons",
            kwargs={"pk": active_product.id, "module_id": module_id},
        )
        response = owner_api_client.patch(reorder_lessons_url, {"ordered_ids": [lesson_id]}, format="json")
        assert response.status_code == 204, response.content

        response = owner_api_client.delete(patch_lesson_url)
        assert response.status_code == 204, response.content

        response = owner_api_client.delete(patch_module_url)
        assert response.status_code == 204, response.content

    def test_editor_can_update_course(self, editor_api_client, active_product):
        course_url = reverse("client-product-manage-course", kwargs={"pk": active_product.id})
        response = editor_api_client.put(course_url, {"title": "Editor course"}, format="json")

        assert response.status_code == 200, response.content
        assert response.json()["course"]["title"] == "Editor course"

    def test_viewer_cannot_modify_course(self, viewer_api_client, active_product):
        course_url = reverse("client-product-manage-course", kwargs={"pk": active_product.id})
        response = viewer_api_client.put(course_url, {"title": "Forbidden"}, format="json")

        assert response.status_code == 403, response.content

        create_module_url = reverse("client-product-create-course-module", kwargs={"pk": active_product.id})
        response = viewer_api_client.post(create_module_url, {"title": "Nope"}, format="json")

        assert response.status_code == 403, response.content
