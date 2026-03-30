from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Client,
    CRMTask,
    CRMTaskHistory,
    CoachGroup,
    CoachGroupTask,
    CoachingGoal,
    CoachingGoalCompetency,
    ContactCoachingProfile,
    InviteLink,
    MapContact,
    UserActiveClientPreference,
    UserTenantBinding,
    UserTenantRole,
)

User = get_user_model()


def create_coaching_crm_task(
    *,
    contact_id: int,
    goal_id: str | None = None,
    title: str,
    due_date: str | None = None,
    status: str = "open",
    created_at: datetime | None = None,
    done_at: datetime | None = None,
    is_milestone: bool = False,
    milestone_note: str = "",
) -> CRMTask:
    due_at = None
    if due_date:
        due_at = timezone.make_aware(datetime.combine(datetime.fromisoformat(due_date).date(), time(hour=12, minute=0)))
    created_at_value = created_at or timezone.now()
    return CRMTask.objects.create(
        source="coaching",
        contact_id=contact_id,
        goal_id=goal_id or None,
        title=title,
        description=None,
        status=status,
        priority=2,
        due_at=due_at,
        is_milestone=is_milestone,
        milestone_note=milestone_note,
        done_at=done_at,
        created_by=0,
        created_at=created_at_value,
        updated_at=done_at or created_at_value,
    )


def create_coaching_milestone_task(
    *,
    contact_id: int,
    text: str,
    goal_id: str | None = None,
    note: str = "",
    created_at: datetime | None = None,
) -> CRMTask:
    created_at_value = created_at or timezone.now()
    return create_coaching_crm_task(
        contact_id=contact_id,
        goal_id=goal_id,
        title=text,
        status="done",
        created_at=created_at_value,
        done_at=created_at_value,
        is_milestone=True,
        milestone_note=note,
    )


@pytest.fixture
def coaching_owner(db):
    return User.objects.create_user(
        username="coaching-owner",
        email="coaching-owner@example.com",
        password="testpass123",
        first_name="Coaching",
        last_name="Owner",
    )


@pytest.fixture
def coaching_tenant(coaching_owner):
    tenant = Client.objects.create(name="Coaching Tenant", slug="coaching-tenant")
    UserTenantRole.objects.create(user=coaching_owner, client=tenant, role="owner")
    UserActiveClientPreference.objects.create(user=coaching_owner, client=tenant)
    return tenant


@pytest.fixture
def coaching_contact(coaching_tenant):
    contact = MapContact.objects.create(name="Анна Иванова", email="anna@example.com")
    UserTenantBinding.objects.create(
        tenant=coaching_tenant,
        provider=UserTenantBinding.PROVIDER_CONTACT,
        provider_user_id=f"contact:{int(contact.id)}",
        contact_id=int(contact.id),
        is_active=True,
    )
    return contact


@pytest.fixture
def bind_contact_to_tenant(coaching_tenant):
    def _bind(contact: MapContact):
        UserTenantBinding.objects.create(
            tenant=coaching_tenant,
            provider=UserTenantBinding.PROVIDER_CONTACT,
            provider_user_id=f"contact:{int(contact.id)}",
            contact_id=int(contact.id),
            is_active=True,
        )
        return contact

    return _bind


@pytest.fixture
def coaching_api_client(coaching_owner):
    client = APIClient()
    client.force_authenticate(user=coaching_owner)
    return client


@pytest.fixture
def portal_user(db):
    return User.objects.create_user(
        username="coaching-portal-user",
        email="portal-user@example.com",
        password="testpass123",
        first_name="Portal",
        last_name="User",
    )


@pytest.fixture
def portal_api_client(portal_user):
    client = APIClient()
    client.force_authenticate(user=portal_user)
    return client


@pytest.mark.django_db
def test_crm_tasks_schema_supports_coaching_metadata():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'map' AND table_name = 'crm_tasks'
            """
        )
        columns = {row[0] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'map' AND tablename = 'crm_tasks'
            """
        )
        indexes = {row[0] for row in cursor.fetchall()}

        cursor.execute(
            """
            INSERT INTO map.crm_tasks (title, status, priority, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id, source
            """,
            ["schema test task", "open", 2, 0],
        )
        inserted_id, source = cursor.fetchone()

    assert {"source", "goal_id", "is_milestone", "milestone_note", "done_at"}.issubset(columns)
    assert "idx_crm_tasks_contact_source" in indexes
    assert "idx_crm_tasks_source_goal" in indexes
    assert source == "operator"
    assert CRMTask.objects.filter(id=inserted_id, source="operator").exists()


def create_coaching_goal(
    profile: ContactCoachingProfile,
    *,
    goal_id: str,
    title: str,
    progress: int,
    horizon: str = "quarter",
    status: str = "active",
    competency_links: list[dict] | None = None,
    created_at: str = "2026-03-01T10:00:00+03:00",
    goal_type: str = CoachingGoal.TYPE_PERSONAL,
    group=None,
) -> CoachingGoal:
    goal = CoachingGoal.objects.create(
        profile=profile,
        public_id=goal_id,
        goal_type=goal_type,
        title=title,
        progress=progress,
        horizon=horizon,
        status=status,
        sort_order=profile.goal_rows.count(),
        group=group,
        created_at=datetime.fromisoformat(created_at),
    )
    CoachingGoalCompetency.objects.bulk_create(
        [
            CoachingGoalCompetency(
                goal=goal,
                competency_id=str(link["competencyId"]),
                competency_name=str(link.get("competencyName") or ""),
                weight=float(link["weight"]),
                sort_order=index,
            )
            for index, link in enumerate(competency_links or [])
        ]
    )
    return goal


@pytest.mark.django_db
def test_competencies_are_persisted_per_contact(coaching_api_client, coaching_tenant, coaching_contact):
    payload = [
        {
            "id": "c1",
            "name": "Говорение",
            "score": 55,
            "startScore": 25,
            "color": "#1D9E75",
        },
        {
            "id": "c2",
            "name": "Грамматика",
            "score": 48,
            "startScore": 20,
            "color": "#378ADD",
        },
    ]

    response = coaching_api_client.put(
        reverse("api:coaching-contact-competencies", args=[coaching_contact.id]),
        payload,
        format="json",
    )

    assert response.status_code == 200, response.content
    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.competencies == payload

    read_response = coaching_api_client.get(
        reverse("api:coaching-contact-competencies", args=[coaching_contact.id]),
    )
    assert read_response.status_code == 200, read_response.content
    assert read_response.json() == payload


@pytest.mark.django_db
def test_removing_competency_creates_growth_milestone(coaching_api_client, coaching_tenant, coaching_contact):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        competencies=[
            {
                "id": "c1",
                "name": "Говорение",
                "score": 55,
                "startScore": 25,
                "color": "#1D9E75",
            },
            {
                "id": "c2",
                "name": "Грамматика",
                "score": 48,
                "startScore": 20,
                "color": "#378ADD",
            },
        ],
    )

    response = coaching_api_client.put(
        reverse("api:coaching-contact-competencies", args=[coaching_contact.id]),
        [
            {
                "id": "c1",
                "name": "Говорение",
                "score": 55,
                "startScore": 25,
                "color": "#1D9E75",
            }
        ],
        format="json",
    )

    assert response.status_code == 200, response.content

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.competencies == [
        {
            "id": "c1",
            "name": "Говорение",
            "score": 55,
            "startScore": 25,
            "color": "#1D9E75",
        }
    ]
    milestone_task = CRMTask.objects.get(source="coaching", contact_id=int(coaching_contact.id), is_milestone=True)
    assert milestone_task.title == "Рост компетенции Грамматика на 28%"
    assert milestone_task.goal_id in {"", None}
    assert milestone_task.status == "done"


@pytest.mark.django_db
def test_tasks_endpoint_returns_profile_tasks_with_goal_titles(coaching_api_client, coaching_tenant, coaching_contact):
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(
        profile,
        goal_id="goal-1",
        title="Наладить границы в работе",
        progress=30,
    )
    first_task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date=tomorrow,
        created_at=timezone.make_aware(datetime(2026, 3, 20, 10, 0, 0)),
    )
    second_task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Зафиксировать 3 сложные ситуации",
        due_date=yesterday,
        created_at=timezone.make_aware(datetime(2026, 3, 18, 10, 0, 0)),
    )

    response = coaching_api_client.get(
        reverse("api:coaching-contact-tasks", args=[coaching_contact.id]),
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload[0]["id"] == str(second_task.id)
    assert payload[0]["status"] == "overdue"
    assert payload[0]["goalTitle"] == "Наладить границы в работе"
    assert payload[1]["id"] == str(first_task.id)
    assert payload[1]["status"] == "pending"


@pytest.mark.django_db
def test_task_status_patch_marks_task_as_done(coaching_api_client, coaching_tenant, coaching_contact):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        title="Подготовить тезисы",
        created_at=timezone.make_aware(datetime(2026, 3, 20, 10, 0, 0)),
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-task-detail", args=[task.id]),
        {"status": "done"},
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["doneAt"]

    task.refresh_from_db()
    assert task.status == "done"
    assert task.done_at is not None
    assert CRMTaskHistory.objects.filter(task=task, note="Коуч отметил задачу выполненной").exists()


@pytest.mark.django_db
def test_coach_can_create_and_revoke_contact_invite_link(coaching_api_client, coaching_tenant, coaching_contact):
    create_response = coaching_api_client.post(
        reverse("api:coaching-contact-invite", args=[coaching_contact.id]),
        format="json",
    )

    assert create_response.status_code == 200, create_response.content
    payload = create_response.json()
    assert payload["clientId"] == str(coaching_contact.id)
    assert payload["token"]
    assert payload["url"].endswith(f"/invite/{payload['token']}")
    assert InviteLink.objects.filter(tenant=coaching_tenant, contact_id=int(coaching_contact.id)).count() == 1

    revoke_response = coaching_api_client.delete(
        reverse("api:coaching-contact-invite", args=[coaching_contact.id]),
    )

    assert revoke_response.status_code == 204, revoke_response.content
    assert InviteLink.objects.filter(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        used_at__isnull=True,
    ).count() == 0


@pytest.mark.django_db
def test_goal_step_create_persists_due_date(coaching_api_client, coaching_tenant, coaching_contact):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(
        profile,
        goal_id="goal-1",
        title="Наладить границы в работе",
        progress=30,
    )

    response = coaching_api_client.post(
        reverse("api:coaching-goal-steps", args=["goal-1"]),
        {"text": "Подготовить 3 сценария ответа", "dueDate": "2026-04-01"},
        format="json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload["text"] == "Подготовить 3 сценария ответа"
    assert payload["dueDate"] == "2026-04-01"
    assert payload["goalId"] == "goal-1"

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.goal_rows.filter(public_id="goal-1").exists()
    task = CRMTask.objects.get(source="coaching", contact_id=int(coaching_contact.id), goal_id="goal-1")
    assert task.title == "Подготовить 3 сценария ответа"
    assert task.due_at is not None
    assert CRMTaskHistory.objects.filter(task=task, note="Создано коучем").exists()


@pytest.mark.django_db
def test_public_coaching_portal_returns_profile_only_after_invite_auth(
    coaching_tenant,
    coaching_contact,
):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Строить границы спокойно и последовательно",
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 55, "startScore": 25, "color": "#1D9E75"},
        ],
    )
    create_coaching_goal(
        profile,
        goal_id="goal-1",
        title="Наладить границы в работе",
        progress=30,
        competency_links=[{"competencyId": "c1", "competencyName": "Говорение", "weight": 0.6}],
    )
    create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )
    create_coaching_milestone_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        text="Первая уверенная граница",
        created_at=datetime.fromisoformat("2026-03-10T10:00:00+03:00"),
    )

    client = APIClient()
    auth_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )

    assert auth_response.status_code == 200, auth_response.content
    assert auth_response.json()["clientId"] == int(coaching_tenant.id)

    response = client.get(
        reverse("api:public-client-page-coaching", args=[coaching_tenant.id]),
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["client"]["id"] == int(coaching_contact.id)
    assert payload["client"]["name"] == "Анна Иванова"
    assert payload["client"]["intention"] == "Строить границы спокойно и последовательно"
    assert payload["client"]["focus"] == "Наладить границы в работе"
    assert payload["competencies"][0]["name"] == "Говорение"
    assert payload["goals"][0]["competencyLinks"][0]["competencyName"] == "Говорение"
    assert payload["goals"][0]["steps"][0]["goalTitle"] == "Наладить границы в работе"
    assert payload["milestones"][0]["text"] == "Первая уверенная граница"
    invite.refresh_from_db()
    assert invite.used_at is not None


@pytest.mark.django_db
def test_milestones_endpoint_creates_done_milestone_task(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)

    response = coaching_api_client.post(
        reverse("api:coaching-contact-milestones", args=[coaching_contact.id]),
        {
            "goalId": "goal-1",
            "text": "Первая уверенная граница",
            "note": "Зафиксировано на сессии",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload["goalId"] == "goal-1"
    assert payload["text"] == "Первая уверенная граница"
    assert payload["note"] == "Зафиксировано на сессии"
    assert payload["createdAt"]

    task = CRMTask.objects.get(source="coaching", contact_id=int(coaching_contact.id), is_milestone=True, goal_id="goal-1")
    assert task.title == "Первая уверенная граница"
    assert task.milestone_note == "Зафиксировано на сессии"
    assert task.status == "done"
    assert task.done_at is not None

    list_response = coaching_api_client.get(
        reverse("api:coaching-contact-milestones", args=[coaching_contact.id]),
    )
    assert list_response.status_code == 200, list_response.content
    assert list_response.json()[0]["id"] == str(task.id)


@pytest.mark.django_db
def test_invite_auth_token_cannot_be_reused(coaching_tenant, coaching_contact):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )

    client = APIClient()
    first_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )
    second_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )

    assert first_response.status_code == 200, first_response.content
    assert second_response.status_code == 410, second_response.content


@pytest.mark.django_db
def test_public_coaching_portal_no_longer_resolves_contact_by_email_auth(
    portal_api_client,
    portal_user,
    coaching_tenant,
    coaching_contact,
):
    portal_user.email = "anna@example.com"
    portal_user.save(update_fields=["email"])

    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Спокойно отстаивать границы",
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)

    page_response = portal_api_client.get(
        reverse("api:public-client-page", args=[coaching_tenant.id]),
    )
    assert page_response.status_code == 200, page_response.content
    page_payload = page_response.json()
    assert page_payload["request_contact_id"] == int(coaching_contact.id)
    assert page_payload["request_contact_name"] == "Анна Иванова"

    coaching_response = portal_api_client.get(
        reverse("api:public-client-page-coaching", args=[coaching_tenant.id]),
    )
    assert coaching_response.status_code == 401, coaching_response.content


@pytest.mark.django_db
def test_tenant_member_can_open_public_coaching_portal_with_contact_query(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Спокойно отстаивать границы",
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)

    response = coaching_api_client.get(
        reverse("api:public-client-page-coaching", args=[coaching_tenant.id]),
        {"contact_id": coaching_contact.id},
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["client"]["id"] == int(coaching_contact.id)
    assert payload["client"]["name"] == "Анна Иванова"
    assert payload["client"]["intention"] == "Спокойно отстаивать границы"
    assert payload["goals"][0]["title"] == "Наладить границы в работе"


@pytest.mark.django_db
def test_public_steps_endpoint_returns_goal_steps_and_allows_completion_after_invite_auth(
    coaching_tenant,
    coaching_contact,
):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )

    client = APIClient()
    auth_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )
    assert auth_response.status_code == 200, auth_response.content

    list_response = client.get(
        reverse("api:public-client-page-steps", args=[coaching_tenant.id]),
    )

    assert list_response.status_code == 200, list_response.content
    list_payload = list_response.json()
    assert list_payload["items"][0]["goalTitle"] == "Наладить границы в работе"
    assert list_payload["items"][0]["dueDate"] == "2026-04-02"

    patch_response = client.patch(
        reverse("api:public-client-page-step-detail", args=[coaching_tenant.id, task.id]),
        {"done": True},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content
    patch_payload = patch_response.json()
    assert patch_payload["done"] is True
    assert patch_payload["doneAt"]

    task.refresh_from_db()
    assert task.status == "done"
    assert task.done_at is not None
    assert CRMTaskHistory.objects.filter(task=task, note="Клиент отметил задачу выполненной").exists()


@pytest.mark.django_db
def test_tenant_member_can_complete_public_step_with_contact_query(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )

    patch_response = coaching_api_client.patch(
        f"{reverse('api:public-client-page-step-detail', args=[coaching_tenant.id, task.id])}?contact_id={coaching_contact.id}",
        {"done": True},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content
    patch_payload = patch_response.json()
    assert patch_payload["done"] is True
    assert patch_payload["doneAt"]

    task.refresh_from_db()
    assert task.status == "done"


@pytest.mark.django_db
def test_public_step_detail_allows_client_editing_fields_and_tracks_history_after_invite_auth(
    coaching_tenant,
    coaching_contact,
):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )

    client = APIClient()
    auth_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )
    assert auth_response.status_code == 200, auth_response.content

    patch_response = client.patch(
        reverse("api:public-client-page-step-detail", args=[coaching_tenant.id, task.id]),
        {
            "text": "Обновить формулировки отказа",
            "dueDate": "2026-04-05",
            "isMilestone": True,
            "milestoneNote": "Проверить на следующей встрече",
        },
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content
    patch_payload = patch_response.json()
    assert patch_payload["text"] == "Обновить формулировки отказа"
    assert patch_payload["dueDate"] == "2026-04-05"
    assert patch_payload["isMilestone"] is True
    assert patch_payload["milestoneNote"] == "Проверить на следующей встрече"

    task.refresh_from_db()
    assert task.title == "Обновить формулировки отказа"
    assert task.is_milestone is True
    assert task.milestone_note == "Проверить на следующей встрече"
    assert task.status == "open"
    assert CRMTaskHistory.objects.filter(task=task, note="Клиент обновил задачу", status="open").exists()


@pytest.mark.django_db
def test_public_step_history_endpoint_allows_client_comment_after_invite_auth(
    coaching_tenant,
    coaching_contact,
):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )

    client = APIClient()
    auth_response = client.post(
        reverse("api:invite-auth", args=[invite.token]),
        format="json",
    )
    assert auth_response.status_code == 200, auth_response.content

    comment_response = client.post(
        reverse("api:public-client-page-step-history", args=[coaching_tenant.id, task.id]),
        {"note": "Хочу обсудить это на следующей встрече"},
        format="json",
    )

    assert comment_response.status_code == 201, comment_response.content
    comment_payload = comment_response.json()
    assert comment_payload["note"] == "Хочу обсудить это на следующей встрече"
    assert comment_payload["created_by"] == -int(coaching_contact.id)
    assert comment_payload["status"] == "open"

    list_response = client.get(
        reverse("api:public-client-page-step-history", args=[coaching_tenant.id, task.id]),
    )

    assert list_response.status_code == 200, list_response.content
    list_payload = list_response.json()
    assert any(item["note"] == "Хочу обсудить это на следующей встрече" for item in list_payload)


@pytest.mark.django_db
def test_goals_edit_is_persisted_and_list_endpoint_resolves_competency_names(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 55, "startScore": 25, "color": "#1D9E75"},
            {"id": "c2", "name": "Грамматика", "score": 48, "startScore": 20, "color": "#378ADD"},
        ],
    )
    payload = [
        {
            "id": "goal-1",
            "title": "Подготовиться к устной части экзамена",
            "progress": 40,
            "horizon": "quarter",
            "status": "active",
            "competencyLinks": [
                {"competencyId": "c1", "competencyName": "Говорение", "weight": 0.7},
                {"competencyId": "c2", "competencyName": "Грамматика", "weight": 0.3},
            ],
            "steps": [
                {
                    "id": "step-1",
                    "text": "Составить план подготовки",
                    "done": False,
                    "isMilestone": False,
                    "milestoneNote": "",
                    "doneAt": "",
                }
            ],
            "createdAt": "2026-03-01T10:00:00+03:00",
        }
    ]

    response = coaching_api_client.put(
        reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id]),
        payload,
        format="json",
    )

    assert response.status_code == 200, response.content
    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    goal = profile.goal_rows.get(public_id="goal-1")
    assert goal.competency_links.order_by("sort_order", "id").first().weight == pytest.approx(0.7)

    edit_response = coaching_api_client.get(
        reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id]),
    )
    assert edit_response.status_code == 200, edit_response.content
    assert edit_response.json()[0]["competencyLinks"][0]["weight"] == 70
    assert edit_response.json()[0]["steps"] == []
    assert edit_response.json()[0]["createdAt"] == "2026-03-01T10:00:00+03:00"

    goals_response = coaching_api_client.get(
        reverse("api:coaching-contact-goals", args=[coaching_contact.id]),
        {"horizon": "quarter"},
    )
    assert goals_response.status_code == 200, goals_response.content
    competencies = goals_response.json()[0]["competencies"]
    assert competencies[0]["name"] == "Говорение"
    assert competencies[0]["weight"] == pytest.approx(0.7)
    assert competencies[1]["name"] == "Грамматика"
    assert competencies[1]["weight"] == pytest.approx(0.3)


@pytest.mark.django_db
def test_goals_edit_rejects_reserved_group_prefix(
    coaching_api_client,
    coaching_contact,
):
    response = coaching_api_client.put(
        reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id]),
        [
            {
                "id": "group-42",
                "title": "Недопустимая цель",
                "progress": 10,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
        format="json",
    )

    assert response.status_code == 400, response.content
    assert "group-" in str(response.json())


@pytest.mark.django_db
def test_goals_edit_removes_tasks_for_deleted_personal_goals(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Первая цель", progress=40)
    create_coaching_goal(profile, goal_id="goal-2", title="Вторая цель", progress=25)
    create_coaching_crm_task(contact_id=int(coaching_contact.id), goal_id="goal-1", title="Шаг первой цели")
    removed_task = create_coaching_crm_task(contact_id=int(coaching_contact.id), goal_id="goal-2", title="Шаг второй цели")

    response = coaching_api_client.put(
        reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id]),
        [
            {
                "id": "goal-1",
                "title": "Первая цель",
                "progress": 40,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
        format="json",
    )

    assert response.status_code == 200, response.content
    profile.refresh_from_db()
    assert profile.goal_rows.filter(public_id="goal-1").exists()
    assert not profile.goal_rows.filter(public_id="goal-2").exists()
    assert CRMTask.objects.filter(id=removed_task.id).count() == 0
    assert CRMTask.objects.filter(source="coaching", contact_id=int(coaching_contact.id), goal_id="goal-1").count() == 1


@pytest.mark.django_db
def test_goals_edit_get_avoids_n_plus_one_queries(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 55, "startScore": 25, "color": "#1D9E75"},
            {"id": "c2", "name": "Грамматика", "score": 48, "startScore": 20, "color": "#378ADD"},
        ],
    )
    create_coaching_goal(
        profile,
        goal_id="goal-1",
        title="Базовая цель",
        progress=40,
        competency_links=[
            {"competencyId": "c1", "competencyName": "Говорение", "weight": 0.6},
            {"competencyId": "c2", "competencyName": "Грамматика", "weight": 0.4},
        ],
    )
    create_coaching_crm_task(contact_id=int(coaching_contact.id), goal_id="goal-1", title="Первый шаг")

    endpoint = reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id])
    with CaptureQueriesContext(connection) as base_queries:
        base_response = coaching_api_client.get(endpoint)

    assert base_response.status_code == 200, base_response.content

    for index in range(2, 6):
        create_coaching_goal(
            profile,
            goal_id=f"goal-{index}",
            title=f"Цель {index}",
            progress=10 * index,
            competency_links=[
                {"competencyId": "c1", "competencyName": "Говорение", "weight": 0.5},
                {"competencyId": "c2", "competencyName": "Грамматика", "weight": 0.5},
            ],
        )
        create_coaching_crm_task(contact_id=int(coaching_contact.id), goal_id=f"goal-{index}", title=f"Шаг {index}")

    with CaptureQueriesContext(connection) as expanded_queries:
        expanded_response = coaching_api_client.get(endpoint)

    assert expanded_response.status_code == 200, expanded_response.content
    assert len(expanded_response.json()) == 5
    assert len(expanded_queries) <= len(base_queries) + 1


@pytest.mark.django_db
def test_goal_step_patch_allows_editing_text_and_due_date(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Наладить границы в работе", progress=30)
    task = create_coaching_crm_task(
        contact_id=int(coaching_contact.id),
        goal_id="goal-1",
        title="Подготовить фразы для отказа",
        due_date="2026-04-02",
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-goal-step-detail", args=["goal-1", task.id]),
        {
            "text": "Потренировать короткие ответы",
            "dueDate": "2026-04-08",
            "isMilestone": True,
            "milestoneNote": "Ключевой шаг перед следующей сессией",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["steps"][0]["text"] == "Потренировать короткие ответы"
    assert payload["steps"][0]["dueDate"] == "2026-04-08"
    assert payload["steps"][0]["isMilestone"] is True
    assert payload["steps"][0]["milestoneNote"] == "Ключевой шаг перед следующей сессией"

    task.refresh_from_db()
    assert task.title == "Потренировать короткие ответы"
    assert task.due_at is not None
    assert task.is_milestone is True
    assert task.milestone_note == "Ключевой шаг перед следующей сессией"
    assert CRMTaskHistory.objects.filter(task=task, note="Обновлено коучем").exists()


@pytest.mark.django_db
def test_goal_progress_patch_updates_goal_and_related_competencies(coaching_api_client, coaching_tenant, coaching_contact):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 50, "startScore": 25, "color": "#1D9E75"},
            {"id": "c2", "name": "Грамматика", "score": 40, "startScore": 20, "color": "#378ADD"},
        ],
    )
    create_coaching_goal(
        profile,
        goal_id="goal-1",
        title="Уверенно отвечать устно",
        progress=20,
        competency_links=[
            {"competencyId": "c1", "competencyName": "Говорение", "weight": 0.6},
            {"competencyId": "c2", "competencyName": "Грамматика", "weight": 0.4},
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-goal-detail", args=["goal-1"]),
        {"progress": 50},
        format="json",
    )

    assert response.status_code == 200, response.content
    profile.refresh_from_db()
    assert profile.goal_rows.get(public_id="goal-1").progress == 50
    assert profile.competencies[0]["score"] == 68
    assert profile.competencies[1]["score"] == 52

    payload = response.json()
    assert payload["progress"] == 50
    assert payload["competencies"][0]["name"] == "Говорение"
    assert payload["competencies"][0]["weight"] == pytest.approx(0.6)
    assert payload["competencies"][1]["name"] == "Грамматика"
    assert payload["competencies"][1]["weight"] == pytest.approx(0.4)


@pytest.mark.django_db
def test_contact_detail_returns_profile_summary(coaching_api_client, coaching_tenant, coaching_contact):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Перестать откладывать сложные разговоры",
        sessions=[
            {
                "id": "sess-1",
                "clientId": int(coaching_contact.id),
                "number": 1,
                "date": "2026-03-30T18:00:00+03:00",
                "notes": "Разбор speaking",
                "coachNotes": "",
            }
        ],
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Дойти до B1", progress=60)

    response = coaching_api_client.get(
        reverse("api:coaching-contact-detail", args=[coaching_contact.id]),
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["id"] == str(coaching_contact.id)
    assert payload["focus"] == "Дойти до B1"
    assert payload["intention"] == "Перестать откладывать сложные разговоры"
    assert payload["sessionsCount"] == 1
    assert payload["avgProgress"] == 60


@pytest.mark.django_db
def test_contact_detail_patch_updates_intention_without_touching_other_profile_fields(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Старое намерение",
        wheel=[{"id": "energy", "score": 6}],
        competencies=[
            {"id": "c1", "name": "Эмпатия", "score": 55, "startScore": 35, "color": "#1D9E75"},
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-contact-detail", args=[coaching_contact.id]),
        {"intention": "Новое намерение клиента"},
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["intention"] == "Новое намерение клиента"

    profile.refresh_from_db()
    assert profile.intention == "Новое намерение клиента"
    assert profile.wheel == [{"id": "energy", "score": 6}]
    assert profile.competencies == [
        {"id": "c1", "name": "Эмпатия", "score": 55, "startScore": 35, "color": "#1D9E75"},
    ]


@pytest.mark.django_db
def test_create_session_creates_single_draft_and_does_not_increment_completed_count(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        sessions=[
            {
                "id": "sess-done-1",
                "clientId": int(coaching_contact.id),
                "number": 1,
                "date": "2026-03-20T12:00:00+03:00",
                "notes": "Разобрали конфликт",
                "coachNotes": "Договориться о границах",
            }
        ],
    )

    response = coaching_api_client.post(
        reverse("api:coaching-contact-sessions", args=[coaching_contact.id]),
        {},
        format="json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload["number"] == 2
    assert payload["status"] == "draft"

    second_response = coaching_api_client.post(
        reverse("api:coaching-contact-sessions", args=[coaching_contact.id]),
        {},
        format="json",
    )
    assert second_response.status_code == 200, second_response.content
    assert second_response.json()["id"] == payload["id"]

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert len(profile.sessions) == 2
    assert profile.sessions[0]["status"] == "draft"

    detail_response = coaching_api_client.get(reverse("api:coaching-contact-detail", args=[coaching_contact.id]))
    assert detail_response.status_code == 200, detail_response.content
    assert detail_response.json()["sessionsCount"] == 1


@pytest.mark.django_db
def test_session_patch_updates_draft_and_allows_finishing(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        sessions=[
            {
                "id": "sess-draft-1",
                "clientId": int(coaching_contact.id),
                "number": 3,
                "date": "2026-03-28T12:00:00+03:00",
                "notes": "",
                "coachNotes": "",
                "status": "draft",
            }
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-session-detail", args=["sess-draft-1"]),
        {
            "notes": "Разобрали сложный разговор с руководителем",
            "coachNotes": "Подготовить три формулировки к следующей встрече",
            "status": "done",
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["notes"] == "Разобрали сложный разговор с руководителем"
    assert payload["coachNotes"] == "Подготовить три формулировки к следующей встрече"
    assert payload["status"] == "done"

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.sessions[0]["status"] == "done"
    assert profile.sessions[0]["notes"] == "Разобрали сложный разговор с руководителем"

    list_response = coaching_api_client.get(reverse("api:coaching-contact-sessions", args=[coaching_contact.id]))
    assert list_response.status_code == 200, list_response.content
    assert list_response.json()[0]["status"] == "done"


@pytest.mark.django_db
def test_coach_stats_returns_completed_tasks_for_last_30_days(
    coaching_api_client,
    coaching_tenant,
    bind_contact_to_tenant,
    monkeypatch,
):
    fixed_now = timezone.make_aware(datetime(2026, 3, 25, 10, 0, 0))
    monkeypatch.setattr("backend.api.views_coaching.timezone.now", lambda: fixed_now)

    anna = bind_contact_to_tenant(MapContact.objects.create(name="Анна Иванова", email="anna@example.com"))
    maria = bind_contact_to_tenant(MapContact.objects.create(name="Мария Петрова", email="maria@example.com"))

    anna_profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(anna.id),
        sessions=[
            {
                "id": "sess-1",
                "clientId": int(anna.id),
                "number": 1,
                "date": fixed_now.isoformat(),
                "notes": "",
                "coachNotes": "",
            }
        ],
    )
    create_coaching_goal(anna_profile, goal_id="goal-1", title="Прокачать уверенность", progress=70, horizon="month")
    create_coaching_crm_task(
        contact_id=int(anna.id),
        goal_id="goal-1",
        title="Сделать упражнение",
        status="done",
        done_at=fixed_now - timedelta(days=3),
    )
    create_coaching_crm_task(
        contact_id=int(anna.id),
        goal_id="goal-1",
        title="Подвести итоги недели",
        status="done",
        done_at=fixed_now - timedelta(days=45),
    )
    maria_profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(maria.id),
        sessions=[],
    )
    create_coaching_goal(maria_profile, goal_id="goal-2", title="Выстроить режим", progress=50)
    create_coaching_crm_task(
        contact_id=int(maria.id),
        goal_id="goal-2",
        title="Ложиться спать до 23:00 пять дней",
        status="done",
        done_at=fixed_now - timedelta(days=10),
    )
    create_coaching_crm_task(
        contact_id=int(maria.id),
        goal_id="goal-2",
        title="Запланировать утренний ритуал",
    )

    response = coaching_api_client.get(reverse("api:coach-stats"))

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["activeClients"] == 2
    assert payload["completedTasks"] == 2
    assert payload["tasksCompletionRate"] == 2
    assert payload["avgProgress"] == 60
    assert payload["sessionsToday"] == 1


@pytest.mark.django_db
def test_coach_clients_returns_prioritized_client_statuses(
    coaching_api_client,
    coaching_tenant,
    bind_contact_to_tenant,
    monkeypatch,
):
    fixed_now = timezone.make_aware(datetime(2026, 3, 18, 10, 0, 0))
    monkeypatch.setattr("backend.api.views_coaching.timezone.now", lambda: fixed_now)

    olga = bind_contact_to_tenant(MapContact.objects.create(name="Ольга Смирнова", email="olga@example.com"))
    mihail = bind_contact_to_tenant(MapContact.objects.create(name="Михаил Козлов", email="mihail@example.com"))
    dmitry = bind_contact_to_tenant(MapContact.objects.create(name="Дмитрий Нечаев", email="dmitry@example.com"))

    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(olga.id),
        sessions=[
            {
                "id": "sess-1",
                "clientId": int(olga.id),
                "number": 1,
                "date": (fixed_now - timedelta(days=14)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-2",
                "clientId": int(olga.id),
                "number": 2,
                "date": (fixed_now - timedelta(days=7)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-3",
                "clientId": int(olga.id),
                "number": 3,
                "date": (fixed_now - timedelta(days=1)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
        ],
    )
    create_coaching_milestone_task(
        contact_id=int(olga.id),
        text="Разговор с руководителем",
        created_at=fixed_now - timedelta(days=2),
    )
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(mihail.id),
        sessions=[
            {
                "id": "sess-1",
                "clientId": int(mihail.id),
                "number": 1,
                "date": (fixed_now - timedelta(days=9)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-2",
                "clientId": int(mihail.id),
                "number": 2,
                "date": (fixed_now - timedelta(days=2)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-3",
                "clientId": int(mihail.id),
                "number": 3,
                "date": (fixed_now + timedelta(days=1, hours=9)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
        ],
    )
    create_coaching_milestone_task(
        contact_id=int(mihail.id),
        text="Получил оффер",
        created_at=fixed_now - timedelta(days=1),
    )
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(dmitry.id),
        sessions=[
            {
                "id": "sess-1",
                "clientId": int(dmitry.id),
                "number": 1,
                "date": (fixed_now - timedelta(days=35)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-2",
                "clientId": int(dmitry.id),
                "number": 2,
                "date": (fixed_now - timedelta(days=28)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
            {
                "id": "sess-3",
                "clientId": int(dmitry.id),
                "number": 3,
                "date": (fixed_now - timedelta(days=24)).isoformat(),
                "notes": "",
                "coachNotes": "",
            },
        ],
    )

    response = coaching_api_client.get(reverse("api:coach-clients"))

    assert response.status_code == 200, response.content
    payload = {item["name"]: item for item in response.json()}
    assert payload["Михаил Козлов"]["clientStatus"] == {
        "kind": "tomorrow",
        "label": "Завтра 19:00",
        "at": (fixed_now + timedelta(days=1, hours=9)).isoformat(),
    }
    assert payload["Ольга Смирнова"]["clientStatus"] == {
        "kind": "milestone",
        "label": "Прорыв",
        "at": None,
    }
    assert payload["Дмитрий Нечаев"]["clientStatus"] == {
        "kind": "inactive",
        "label": "24 дня без сессии",
        "at": (fixed_now - timedelta(days=24)).isoformat(),
    }


@pytest.mark.django_db
def test_coach_groups_can_be_created_and_listed(coaching_api_client):
    create_response = coaching_api_client.post(
        reverse("api:coach-groups"),
        {"name": "Утренний поток"},
        format="json",
    )

    assert create_response.status_code == 201, create_response.content
    payload = create_response.json()
    assert payload["name"] == "Утренний поток"
    assert payload["memberCount"] == 0

    list_response = coaching_api_client.get(reverse("api:coach-groups"))

    assert list_response.status_code == 200, list_response.content
    assert list_response.json() == [payload]


@pytest.mark.django_db
def test_coach_group_detail_returns_members_with_progress(
    coaching_api_client,
    coaching_tenant,
    bind_contact_to_tenant,
):
    first_contact = bind_contact_to_tenant(MapContact.objects.create(name="Мария Петрова", email="maria@example.com"))
    second_contact = bind_contact_to_tenant(MapContact.objects.create(name="Игорь Соколов", email="igor@example.com"))
    group = CoachGroup.objects.create(tenant=coaching_tenant, name="Вечерняя группа")
    group.members.create(contact_id=int(first_contact.id))
    group.members.create(contact_id=int(second_contact.id))

    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(first_contact.id),
    )
    create_coaching_goal(profile, goal_id="goal-1", title="Уверенность в переговорах", progress=60)

    response = coaching_api_client.get(reverse("api:coach-group-detail", args=[group.id]))

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["group"]["name"] == "Вечерняя группа"
    assert [item["name"] for item in payload["members"]] == ["Мария Петрова", "Игорь Соколов"]
    assert payload["members"][0]["focus"] == "Уверенность в переговорах"
    assert payload["members"][0]["avgProgress"] == 60
    assert payload["members"][1]["avgProgress"] == 0


@pytest.mark.django_db
def test_group_task_creates_steps_for_all_members_and_counts_completion(
    coaching_api_client,
    coaching_tenant,
    bind_contact_to_tenant,
):
    first_contact = bind_contact_to_tenant(MapContact.objects.create(name="Полина Алексеева", email="polina@example.com"))
    second_contact = bind_contact_to_tenant(MapContact.objects.create(name="Сергей Орлов", email="sergey@example.com"))
    group = CoachGroup.objects.create(tenant=coaching_tenant, name="Практика границ")
    group.members.create(contact_id=int(first_contact.id))
    group.members.create(contact_id=int(second_contact.id))

    response = coaching_api_client.post(
        reverse("api:coach-group-tasks", args=[group.id]),
        {"text": "Написать 3 спокойных отказа", "dueDate": "2026-04-05"},
        format="json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload["text"] == "Написать 3 спокойных отказа"
    assert payload["dueDate"] == "2026-04-05"
    assert payload["doneCount"] == 0
    assert payload["totalCount"] == 2

    first_profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=int(first_contact.id))
    second_profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=int(second_contact.id))
    first_goal = first_profile.goal_rows.get(public_id=f"group-{group.id}")
    second_goal = second_profile.goal_rows.get(public_id=f"group-{group.id}")

    assert first_goal.public_id == f"group-{group.id}"
    assert first_goal.goal_type == CoachingGoal.TYPE_GROUP
    assert second_goal.goal_type == CoachingGoal.TYPE_GROUP

    first_task = CRMTask.objects.get(source="coaching", contact_id=int(first_contact.id), goal_id=f"group-{group.id}")
    second_task = CRMTask.objects.get(source="coaching", contact_id=int(second_contact.id), goal_id=f"group-{group.id}")
    assert first_task.due_at is not None
    assert second_task.goal_id == f"group-{group.id}"

    patch_response = coaching_api_client.patch(
        reverse("api:coaching-goal-step-detail", args=[f"group-{group.id}", first_task.id]),
        {"done": True},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content

    detail_response = coaching_api_client.get(reverse("api:coach-group-detail", args=[group.id]))

    assert detail_response.status_code == 200, detail_response.content
    detail_payload = detail_response.json()
    assert detail_payload["tasks"][0]["doneCount"] == 1
    assert detail_payload["tasks"][0]["totalCount"] == 2


@pytest.mark.django_db
def test_removing_member_from_group_cleans_member_steps_and_task_refs(
    coaching_api_client,
    coaching_tenant,
    bind_contact_to_tenant,
):
    first_contact = bind_contact_to_tenant(MapContact.objects.create(name="Елена Белова", email="elena@example.com"))
    second_contact = bind_contact_to_tenant(MapContact.objects.create(name="Артем Крылов", email="artem@example.com"))
    group = CoachGroup.objects.create(tenant=coaching_tenant, name="Разбор кейсов")
    group.members.create(contact_id=int(first_contact.id))
    group.members.create(contact_id=int(second_contact.id))

    create_task_response = coaching_api_client.post(
        reverse("api:coach-group-tasks", args=[group.id]),
        {"text": "Описать конфликт и границы"},
        format="json",
    )

    assert create_task_response.status_code == 201, create_task_response.content

    remove_response = coaching_api_client.delete(
        reverse("api:coach-group-member-detail", args=[group.id, second_contact.id]),
    )

    assert remove_response.status_code == 204, remove_response.content

    second_profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=int(second_contact.id))
    assert second_profile.goal_rows.count() == 0

    task = CoachGroupTask.objects.get(group=group)
    assert len(task.step_refs) == 1
    assert int(task.step_refs[0]["contactId"]) == int(first_contact.id)
    assert str(task.step_refs[0]["taskId"]).isdigit()
    assert CRMTask.objects.filter(source="coaching", contact_id=int(second_contact.id), goal_id=f"group-{group.id}").count() == 0

    detail_response = coaching_api_client.get(reverse("api:coach-group-detail", args=[group.id]))

    assert detail_response.status_code == 200, detail_response.content
    detail_payload = detail_response.json()
    assert detail_payload["group"]["memberCount"] == 1
    assert detail_payload["tasks"][0]["totalCount"] == 1
