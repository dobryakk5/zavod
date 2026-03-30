from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Client,
    CoachGroup,
    CoachGroupTask,
    ContactCoachingProfile,
    InviteLink,
    MapContact,
    UserActiveClientPreference,
    UserTenantBinding,
    UserTenantRole,
)

User = get_user_model()


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
    assert profile.milestones[0]["text"] == "Рост компетенции Грамматика на 28%"
    assert profile.milestones[0]["goalId"] == ""
    assert profile.milestones[0]["clientId"] == coaching_contact.id


@pytest.mark.django_db
def test_tasks_endpoint_returns_profile_tasks_with_goal_titles(coaching_api_client, coaching_tenant, coaching_contact):
    yesterday = (timezone.now() - timedelta(days=1)).isoformat()
    tomorrow = (timezone.now() + timedelta(days=1)).isoformat()
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
        tasks=[
            {
                "id": "task-1",
                "text": "Подготовить фразы для отказа",
                "goalId": "goal-1",
                "status": "pending",
                "dueDate": tomorrow,
                "createdAt": "2026-03-20T10:00:00+03:00",
            },
            {
                "id": "task-2",
                "text": "Зафиксировать 3 сложные ситуации",
                "goalId": "goal-1",
                "status": "pending",
                "dueDate": yesterday,
                "createdAt": "2026-03-18T10:00:00+03:00",
            },
        ],
    )

    response = coaching_api_client.get(
        reverse("api:coaching-contact-tasks", args=[coaching_contact.id]),
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload[0]["id"] == "task-2"
    assert payload[0]["status"] == "overdue"
    assert payload[0]["goalTitle"] == "Наладить границы в работе"
    assert payload[1]["status"] == "pending"


@pytest.mark.django_db
def test_task_status_patch_marks_task_as_done(coaching_api_client, coaching_tenant, coaching_contact):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        tasks=[
            {
                "id": "task-1",
                "text": "Подготовить тезисы",
                "status": "pending",
                "createdAt": "2026-03-20T10:00:00+03:00",
            }
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-task-detail", args=["task-1"]),
        {"status": "done"},
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["doneAt"]

    profile.refresh_from_db()
    assert profile.tasks[0]["status"] == "done"
    assert profile.tasks[0]["doneAt"]


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
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
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
    assert profile.goals[0]["steps"][0]["dueDate"] == "2026-04-01"


@pytest.mark.django_db
def test_public_coaching_portal_returns_profile_only_after_invite_auth(
    coaching_tenant,
    coaching_contact,
):
    invite = InviteLink.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
    )
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Строить границы спокойно и последовательно",
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 55, "startScore": 25, "color": "#1D9E75"},
        ],
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [{"competencyId": "c1", "weight": 0.6}],
                "steps": [
                    {
                        "id": "step-1",
                        "text": "Подготовить фразы для отказа",
                        "done": False,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": "",
                        "dueDate": "2026-04-02",
                    }
                ],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
        milestones=[
            {
                "id": "ms-1",
                "clientId": int(coaching_contact.id),
                "goalId": "goal-1",
                "text": "Первая уверенная граница",
                "note": "",
                "createdAt": "2026-03-10T10:00:00+03:00",
            }
        ],
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

    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Спокойно отстаивать границы",
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

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
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Спокойно отстаивать границы",
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

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
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [
                    {
                        "id": "step-1",
                        "text": "Подготовить фразы для отказа",
                        "done": False,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": "",
                        "dueDate": "2026-04-02",
                    }
                ],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
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
        reverse("api:public-client-page-step-detail", args=[coaching_tenant.id, "step-1"]),
        {"done": True},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content
    patch_payload = patch_response.json()
    assert patch_payload["done"] is True
    assert patch_payload["doneAt"]

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.goals[0]["steps"][0]["done"] is True
    assert profile.goals[0]["steps"][0]["doneAt"]


@pytest.mark.django_db
def test_tenant_member_can_complete_public_step_with_contact_query(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [
                    {
                        "id": "step-1",
                        "text": "Подготовить фразы для отказа",
                        "done": False,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": "",
                        "dueDate": "2026-04-02",
                    }
                ],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

    patch_response = coaching_api_client.patch(
        f"{reverse('api:public-client-page-step-detail', args=[coaching_tenant.id, 'step-1'])}?contact_id={coaching_contact.id}",
        {"done": True},
        format="json",
    )

    assert patch_response.status_code == 200, patch_response.content
    patch_payload = patch_response.json()
    assert patch_payload["done"] is True
    assert patch_payload["doneAt"]

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.goals[0]["steps"][0]["done"] is True


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
    assert profile.goals[0]["competencyLinks"][0]["weight"] == pytest.approx(0.7)

    edit_response = coaching_api_client.get(
        reverse("api:coaching-contact-goals-edit", args=[coaching_contact.id]),
    )
    assert edit_response.status_code == 200, edit_response.content
    assert edit_response.json()[0]["competencyLinks"][0]["weight"] == 70
    assert edit_response.json()[0]["steps"][0]["text"] == "Составить план подготовки"
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
def test_goal_step_patch_allows_editing_text_and_due_date(
    coaching_api_client,
    coaching_tenant,
    coaching_contact,
):
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Наладить границы в работе",
                "progress": 30,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [
                    {
                        "id": "step-1",
                        "text": "Подготовить фразы для отказа",
                        "done": False,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": "",
                        "dueDate": "2026-04-02",
                    }
                ],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-goal-step-detail", args=["goal-1", "step-1"]),
        {"text": "Потренировать короткие ответы", "dueDate": "2026-04-08"},
        format="json",
    )

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["steps"][0]["text"] == "Потренировать короткие ответы"
    assert payload["steps"][0]["dueDate"] == "2026-04-08"

    profile = ContactCoachingProfile.objects.get(tenant=coaching_tenant, contact_id=coaching_contact.id)
    assert profile.goals[0]["steps"][0]["text"] == "Потренировать короткие ответы"
    assert profile.goals[0]["steps"][0]["dueDate"] == "2026-04-08"


@pytest.mark.django_db
def test_goal_progress_patch_updates_goal_and_related_competencies(coaching_api_client, coaching_tenant, coaching_contact):
    profile = ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        competencies=[
            {"id": "c1", "name": "Говорение", "score": 50, "startScore": 25, "color": "#1D9E75"},
            {"id": "c2", "name": "Грамматика", "score": 40, "startScore": 20, "color": "#378ADD"},
        ],
        goals=[
            {
                "id": "goal-1",
                "title": "Уверенно отвечать устно",
                "progress": 20,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [
                    {"competencyId": "c1", "competencyName": "Говорение", "weight": 0.6},
                    {"competencyId": "c2", "competencyName": "Грамматика", "weight": 0.4},
                ],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

    response = coaching_api_client.patch(
        reverse("api:coaching-goal-detail", args=["goal-1"]),
        {"progress": 50},
        format="json",
    )

    assert response.status_code == 200, response.content
    profile.refresh_from_db()
    assert profile.goals[0]["progress"] == 50
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
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(coaching_contact.id),
        intention="Перестать откладывать сложные разговоры",
        goals=[
            {
                "id": "goal-1",
                "title": "Дойти до B1",
                "progress": 60,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
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

    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(anna.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Прокачать уверенность",
                "progress": 70,
                "horizon": "month",
                "status": "active",
                "competencyLinks": [],
                "steps": [
                    {
                        "id": "step-1",
                        "text": "Сделать упражнение",
                        "done": True,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": (fixed_now - timedelta(days=3)).date().isoformat(),
                    },
                    {
                        "id": "step-2",
                        "text": "Подвести итоги недели",
                        "done": True,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": (fixed_now - timedelta(days=45)).date().isoformat(),
                    },
                ],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
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
    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(maria.id),
        goals=[
            {
                "id": "goal-2",
                "title": "Выстроить режим",
                "progress": 50,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [
                    {
                        "id": "step-3",
                        "text": "Ложиться спать до 23:00 пять дней",
                        "done": True,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": (fixed_now - timedelta(days=10)).date().isoformat(),
                    },
                    {
                        "id": "step-4",
                        "text": "Запланировать утренний ритуал",
                        "done": False,
                        "isMilestone": False,
                        "milestoneNote": "",
                        "doneAt": "",
                    },
                ],
                "createdAt": "2026-03-05T10:00:00+03:00",
            }
        ],
        sessions=[],
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
        milestones=[
            {
                "id": "m1",
                "clientId": int(olga.id),
                "text": "Разговор с руководителем",
                "note": "",
                "createdAt": (fixed_now - timedelta(days=2)).isoformat(),
            }
        ],
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
        milestones=[
            {
                "id": "m2",
                "clientId": int(mihail.id),
                "text": "Получил оффер",
                "note": "",
                "createdAt": (fixed_now - timedelta(days=1)).isoformat(),
            }
        ],
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

    ContactCoachingProfile.objects.create(
        tenant=coaching_tenant,
        contact_id=int(first_contact.id),
        goals=[
            {
                "id": "goal-1",
                "title": "Уверенность в переговорах",
                "progress": 60,
                "horizon": "quarter",
                "status": "active",
                "competencyLinks": [],
                "steps": [],
                "createdAt": "2026-03-01T10:00:00+03:00",
            }
        ],
    )

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
    first_goal = first_profile.goals[0]
    second_goal = second_profile.goals[0]

    assert first_goal["id"] == f"group-{group.id}"
    assert first_goal["steps"][0]["dueDate"] == "2026-04-05"
    assert second_goal["steps"][0]["goalId"] == f"group-{group.id}"

    step_id = first_goal["steps"][0]["id"]
    patch_response = coaching_api_client.patch(
        reverse("api:coaching-goal-step-detail", args=[f"group-{group.id}", step_id]),
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
    assert second_profile.goals == []

    task = CoachGroupTask.objects.get(group=group)
    assert len(task.step_refs) == 1
    assert int(task.step_refs[0]["contactId"]) == int(first_contact.id)

    detail_response = coaching_api_client.get(reverse("api:coach-group-detail", args=[group.id]))

    assert detail_response.status_code == 200, detail_response.content
    detail_payload = detail_response.json()
    assert detail_payload["group"]["memberCount"] == 1
    assert detail_payload["tasks"][0]["totalCount"] == 1
