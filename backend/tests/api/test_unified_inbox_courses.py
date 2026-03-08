from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Client,
    ClientProduct,
    MapContact,
    ProductCourse,
    ProductCourseComment,
    ProductCourseEvent,
    ProductCourseLesson,
    ProductCourseModule,
    ProductCourseProgress,
    UserTenantRole,
)


User = get_user_model()


@pytest.fixture
def tenant(db):
    return Client.objects.create(name="Inbox LMS", slug="inbox-lms")


@pytest.fixture
def owner_user(db):
    return User.objects.create_user(email="inbox-owner@example.com", password="testpass123")


@pytest.fixture
def owner_api_client(owner_user, tenant):
    UserTenantRole.objects.create(user=owner_user, client=tenant, role="owner")
    client = APIClient()
    client.force_authenticate(user=owner_user)
    return client


@pytest.fixture
def course_context(tenant):
    contact = MapContact.objects.create(name="Ученик Inbox")
    product = ClientProduct.objects.create(
        owner=tenant,
        name="Inbox product",
        status=ClientProduct.STATUS_ACTIVE,
        short_description="desc",
        packages=[{"name": "Base", "price": 1000}],
        structure={},
    )
    course = ProductCourse.objects.create(
        owner=tenant,
        product=product,
        title="Inbox course",
        is_published=True,
    )
    module = ProductCourseModule.objects.create(course=course, title="Модуль", position=0)
    lesson = ProductCourseLesson.objects.create(
        module=module,
        title="Урок inbox",
        position=0,
        is_preview=True,
        content={"type": "doc", "content": []},
    )
    return {
        "contact": contact,
        "product": product,
        "course": course,
        "module": module,
        "lesson": lesson,
    }


@pytest.mark.django_db
class TestUnifiedInboxCourses:
    def test_threads_include_courses_channel(self, owner_api_client, tenant, course_context):
        contact = course_context["contact"]
        product = course_context["product"]
        course = course_context["course"]
        module = course_context["module"]
        lesson = course_context["lesson"]
        progress = ProductCourseProgress.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            lesson=lesson,
            completed_at=timezone.now(),
        )
        ProductCourseEvent.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            product=product,
            course=course,
            module=module,
            lesson=lesson,
            progress=progress,
            event_type=ProductCourseEvent.EVENT_LESSON_COMPLETED,
            actor_role=ProductCourseEvent.ACTOR_STUDENT,
        )
        ProductCourseComment.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            product=product,
            course=course,
            module=module,
            lesson=lesson,
            author_role=ProductCourseComment.AUTHOR_STUDENT,
            channel=ProductCourseComment.CHANNEL_COURSES,
            message_text="Комментарий ученика",
        )

        response = owner_api_client.get(reverse("client-unified-inbox"))
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["sources"]["courses"]["thread_count"] == 1
        course_threads = [item for item in body["threads"] if item["sourceChannel"] == "courses"]
        assert len(course_threads) == 1
        thread = course_threads[0]
        assert thread["courseEvent"]["lesson_id"] == lesson.id
        assert "Курсы" in thread["subject"]

    def test_accept_course_thread_updates_progress_and_creates_records(self, owner_api_client, tenant, owner_user, course_context):
        contact = course_context["contact"]
        product = course_context["product"]
        course = course_context["course"]
        module = course_context["module"]
        lesson = course_context["lesson"]
        progress = ProductCourseProgress.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            lesson=lesson,
            completed_at=timezone.now(),
        )
        ProductCourseEvent.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            product=product,
            course=course,
            module=module,
            lesson=lesson,
            progress=progress,
            event_type=ProductCourseEvent.EVENT_LESSON_COMPLETED,
            actor_role=ProductCourseEvent.ACTOR_STUDENT,
        )
        thread_id = f"course:{tenant.id}:{int(contact.id)}:{lesson.id}"

        response = owner_api_client.post(
            reverse("client-unified-inbox-course-accept"),
            {"thread_id": thread_id},
            format="json",
        )
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["accepted"] is True
        assert body["thread_id"] == thread_id

        progress.refresh_from_db()
        assert progress.curator_user_id == owner_user.id
        assert progress.curator_completed_at is not None
        assert ProductCourseEvent.objects.filter(
            owner=tenant,
            contact_id=int(contact.id),
            lesson=lesson,
            event_type=ProductCourseEvent.EVENT_LESSON_ACCEPTED,
        ).count() == 1
        assert ProductCourseComment.objects.filter(
            owner=tenant,
            contact_id=int(contact.id),
            lesson=lesson,
            author_role=ProductCourseComment.AUTHOR_SYSTEM,
        ).count() == 1

    def test_reply_for_course_thread_creates_course_comment(self, owner_api_client, tenant, course_context):
        contact = course_context["contact"]
        product = course_context["product"]
        course = course_context["course"]
        module = course_context["module"]
        lesson = course_context["lesson"]
        ProductCourseEvent.objects.create(
            owner=tenant,
            contact_id=int(contact.id),
            product=product,
            course=course,
            module=module,
            lesson=lesson,
            event_type=ProductCourseEvent.EVENT_LESSON_COMPLETED,
            actor_role=ProductCourseEvent.ACTOR_STUDENT,
        )
        thread_id = f"course:{tenant.id}:{int(contact.id)}:{lesson.id}"

        response = owner_api_client.post(
            reverse("client-unified-inbox-reply"),
            {
                "thread_id": thread_id,
                "channel": "courses",
                "text": "Комментарий куратора",
                "contact_id": int(contact.id),
            },
            format="json",
        )
        assert response.status_code == 200, response.content
        assert ProductCourseComment.objects.filter(
            owner=tenant,
            contact_id=int(contact.id),
            lesson=lesson,
            author_role=ProductCourseComment.AUTHOR_CURATOR,
            channel=ProductCourseComment.CHANNEL_COURSES,
        ).count() == 1
