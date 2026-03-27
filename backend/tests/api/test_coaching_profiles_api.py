from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Client, ContactCoachingProfile, MapContact, UserActiveClientPreference, UserSocialAccount, UserTenantBinding, UserTenantRole

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
def test_public_steps_endpoint_returns_goal_steps_and_allows_completion(
    portal_api_client,
    portal_user,
    coaching_tenant,
    coaching_contact,
):
    provider_id = f"telegram-{portal_user.id}"
    UserSocialAccount.objects.create(
        user=portal_user,
        provider=UserSocialAccount.PROVIDER_TELEGRAM,
        provider_id=provider_id,
        extra_data={"username": "portal-user"},
    )
    UserTenantBinding.objects.create(
        tenant=coaching_tenant,
        provider=UserTenantBinding.PROVIDER_TELEGRAM,
        provider_user_id=provider_id,
        contact_id=int(coaching_contact.id),
        is_active=True,
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

    list_response = portal_api_client.get(
        reverse("api:public-client-page-steps", args=[coaching_tenant.id]),
    )

    assert list_response.status_code == 200, list_response.content
    list_payload = list_response.json()
    assert list_payload["items"][0]["goalTitle"] == "Наладить границы в работе"
    assert list_payload["items"][0]["dueDate"] == "2026-04-02"

    patch_response = portal_api_client.patch(
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
