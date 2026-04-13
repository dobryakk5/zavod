from __future__ import annotations

import copy

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import ProjectTeamInvite, UserActiveClientPreference, UserSocialAccount, UserTenantRole
from core.services.team_invites import accept_pending_team_invites
from config.settings.base import REST_FRAMEWORK as BASE_REST_FRAMEWORK

User = get_user_model()


@pytest.fixture
def owner_user(db):
    return User.objects.create_user(
        username="team-owner",
        email="team-owner@example.com",
        password="testpass123",
        first_name="Team",
        last_name="Owner",
    )


@pytest.fixture
def owner_client(owner_user):
    client = APIClient()
    client.force_authenticate(user=owner_user)
    return client


@pytest.fixture
def project(owner_user):
    from core.models import Client

    client = Client.objects.create(name="Team Project", slug="team-project")
    UserTenantRole.objects.create(user=owner_user, client=client, role="owner")
    return client


def _link_social(user, provider: str, handle: str, provider_id: str | None = None):
    extra_data = {"username": handle} if provider == UserSocialAccount.PROVIDER_TELEGRAM else {"screen_name": handle}
    return UserSocialAccount.objects.create(
        user=user,
        provider=provider,
        provider_id=provider_id or f"{provider}-{user.id}",
        extra_data=extra_data,
    )


def _api_client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_client_info_returns_memberships_and_active_client_id(owner_client, owner_user, project):
    from core.models import Client

    second = Client.objects.create(name="Second Project", slug="second-project")
    UserTenantRole.objects.create(user=owner_user, client=second, role="editor")

    response = owner_client.get(reverse("api:client-info"))

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["active_client_id"] == project.id
    assert payload["role"] == "owner"
    assert payload["memberships"] == [
        {"client": {"id": second.id, "name": second.name, "slug": second.slug}, "role": "editor"},
        {"client": {"id": project.id, "name": project.name, "slug": project.slug}, "role": "owner"},
    ] or payload["memberships"] == [
        {"client": {"id": project.id, "name": project.name, "slug": project.slug}, "role": "owner"},
        {"client": {"id": second.id, "name": second.name, "slug": second.slug}, "role": "editor"},
    ]


@pytest.mark.django_db
def test_switch_active_client_returns_same_payload_shape(owner_user, project):
    from core.models import Client

    second = Client.objects.create(name="Second Project", slug="second-project")
    UserTenantRole.objects.create(user=owner_user, client=second, role="editor")
    client = _api_client_for(owner_user)

    info_response = client.get(reverse("api:client-info"))
    switch_response = client.post(reverse("api:client-active"), {"client_id": second.id}, format="json")

    assert info_response.status_code == 200, info_response.content
    assert switch_response.status_code == 200, switch_response.content
    assert set(info_response.json().keys()) == set(switch_response.json().keys())
    assert switch_response.json()["active_client_id"] == second.id
    assert switch_response.json()["client"]["id"] == second.id


@pytest.mark.django_db
def test_owner_can_rename_active_project(owner_client, project):
    response = owner_client.patch(reverse("api:client-info"), {"name": "Renamed Project"}, format="json")

    assert response.status_code == 200, response.content
    project.refresh_from_db()
    assert project.name == "Renamed Project"
    assert response.json()["client"]["name"] == "Renamed Project"
    assert response.json()["memberships"][0]["client"]["name"] == "Renamed Project"


@pytest.mark.django_db
def test_editor_cannot_rename_active_project(project):
    editor = User.objects.create_user(username="team-editor", email="team-editor@example.com", password="testpass123")
    UserTenantRole.objects.create(user=editor, client=project, role="editor")
    client = _api_client_for(editor)

    response = client.patch(reverse("api:client-info"), {"name": "Editor Rename"}, format="json")

    assert response.status_code == 403, response.content
    project.refresh_from_db()
    assert project.name == "Team Project"


@pytest.mark.django_db
def test_create_team_invitation_returns_pending_created(owner_client, project):
    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "telegram", "account_handle": "@new_user"},
        format="json",
    )

    assert response.status_code == 202, response.content
    payload = response.json()
    assert payload["status"] == "pending_created"
    invite = ProjectTeamInvite.objects.get(client=project)
    assert invite.account_handle_normalized == "new_user"
    assert invite.status == ProjectTeamInvite.Status.PENDING


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="https://frontend.example.com",
)
def test_create_email_team_invitation_sends_magic_link(owner_client, project):
    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "email", "account_handle": "new-user@example.com"},
        format="json",
    )

    assert response.status_code == 202, response.content
    payload = response.json()
    assert payload["status"] == "pending_created"
    assert "email" in payload["message"].lower()

    invite = ProjectTeamInvite.objects.get(client=project, provider=ProjectTeamInvite.Provider.EMAIL)
    assert invite.account_handle_normalized == "new-user@example.com"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new-user@example.com"]
    assert "https://frontend.example.com/auth/email/verify?token=" in mail.outbox[0].body


@pytest.mark.django_db
def test_create_team_invitation_returns_existing_pending(owner_client, project):
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.TELEGRAM,
        account_handle_raw="@pending_user",
        account_handle_normalized="pending_user",
        role=ProjectTeamInvite.Role.EDITOR,
    )

    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "telegram", "account_handle": "@pending_user"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "existing_pending"
    assert ProjectTeamInvite.objects.filter(client=project).count() == 1


@pytest.mark.django_db
def test_create_team_invitation_returns_already_member_for_existing_handle(owner_client, project):
    user = User.objects.create_user(username="member-user", email="member@example.com", password="testpass123")
    _link_social(user, UserSocialAccount.PROVIDER_TELEGRAM, "member_handle")
    UserTenantRole.objects.create(user=user, client=project, role="editor")

    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "telegram", "account_handle": "@member_handle"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "already_member"


@pytest.mark.django_db
def test_create_email_team_invitation_returns_already_member_for_existing_email(owner_client, project):
    user = User.objects.create_user(username="member-email", email="member@example.com", password="testpass123")
    UserTenantRole.objects.create(user=user, client=project, role="editor")

    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "email", "account_handle": "member@example.com"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "already_member"


@pytest.mark.django_db
def test_revoked_invitation_can_be_recreated(owner_client, project):
    owner = project.usertenantrole_set.get(role="owner").user
    invite = ProjectTeamInvite.objects.create(
        client=project,
        invited_by=owner,
        provider=ProjectTeamInvite.Provider.VK,
        account_handle_raw="screen-name",
        account_handle_normalized="screen-name",
        role=ProjectTeamInvite.Role.EDITOR,
        status=ProjectTeamInvite.Status.REVOKED,
    )

    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "vk", "account_handle": "screen-name"},
        format="json",
    )

    assert response.status_code == 202, response.content
    assert ProjectTeamInvite.objects.filter(client=project, provider="vk").count() == 2
    assert ProjectTeamInvite.objects.exclude(id=invite.id).get().status == ProjectTeamInvite.Status.PENDING


@pytest.mark.django_db
def test_team_limit_blocks_new_invitation(owner_client, project, settings):
    settings.TEAM_MAX_COLLABORATORS = 1
    user = User.objects.create_user(username="existing-editor", email="editor@example.com", password="testpass123")
    UserTenantRole.objects.create(user=user, client=project, role="editor")

    response = owner_client.post(
        reverse("api:client-team-invitations"),
        {"provider": "telegram", "account_handle": "@overflow"},
        format="json",
    )

    assert response.status_code == 409, response.content
    assert response.json()["error"] == "team_limit_reached"


@pytest.mark.django_db
def test_pending_invite_accepts_on_first_authenticated_request(project):
    invited = User.objects.create_user(username="invited-user", email="invited@example.com", password="testpass123")
    _link_social(invited, UserSocialAccount.PROVIDER_TELEGRAM, "first_login")
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.TELEGRAM,
        account_handle_raw="@first_login",
        account_handle_normalized="first_login",
        role=ProjectTeamInvite.Role.EDITOR,
    )
    client = _api_client_for(invited)

    response = client.get(reverse("api:client-info"))

    assert response.status_code == 200, response.content
    assert response.json()["client"]["id"] == project.id
    invite = ProjectTeamInvite.objects.get(client=project, account_handle_normalized="first_login")
    assert invite.status == ProjectTeamInvite.Status.ACCEPTED
    assert UserTenantRole.objects.filter(user=invited, client=project, role="editor").exists()


@pytest.mark.django_db
def test_email_pending_invite_accepts_on_first_authenticated_request(project):
    invited = User.objects.create_user(username="email-invited", email="email-invited@example.com", password="testpass123")
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.EMAIL,
        account_handle_raw="email-invited@example.com",
        account_handle_normalized="email-invited@example.com",
        role=ProjectTeamInvite.Role.EDITOR,
    )
    client = _api_client_for(invited)

    response = client.get(reverse("api:client-info"))

    assert response.status_code == 200, response.content
    assert response.json()["client"]["id"] == project.id
    invite = ProjectTeamInvite.objects.get(client=project, account_handle_normalized="email-invited@example.com")
    assert invite.status == ProjectTeamInvite.Status.ACCEPTED
    assert UserTenantRole.objects.filter(user=invited, client=project, role="editor").exists()


@pytest.mark.django_db
def test_accept_pending_invites_is_idempotent(project):
    invited = User.objects.create_user(username="repeat-user", email="repeat@example.com", password="testpass123")
    _link_social(invited, UserSocialAccount.PROVIDER_VK, "repeat-handle")
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.VK,
        account_handle_raw="repeat-handle",
        account_handle_normalized="repeat-handle",
        role=ProjectTeamInvite.Role.EDITOR,
    )

    accept_pending_team_invites(invited)
    accept_pending_team_invites(invited)

    assert UserTenantRole.objects.filter(user=invited, client=project).count() == 1
    assert ProjectTeamInvite.objects.filter(client=project, status=ProjectTeamInvite.Status.ACCEPTED).count() == 1


@pytest.mark.django_db
def test_pending_invite_stays_pending_when_team_limit_reached(project, settings):
    settings.TEAM_MAX_COLLABORATORS = 1
    existing = User.objects.create_user(username="occupied", email="occupied@example.com", password="testpass123")
    UserTenantRole.objects.create(user=existing, client=project, role="editor")
    invited = User.objects.create_user(username="blocked", email="blocked@example.com", password="testpass123")
    _link_social(invited, UserSocialAccount.PROVIDER_TELEGRAM, "blocked-handle")
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.TELEGRAM,
        account_handle_raw="@blocked-handle",
        account_handle_normalized="blocked-handle",
        role=ProjectTeamInvite.Role.EDITOR,
    )
    client = _api_client_for(invited)

    response = client.get(reverse("api:client-info"))

    assert response.status_code == 403, response.content
    invite = ProjectTeamInvite.objects.get(client=project, account_handle_normalized="blocked-handle")
    assert invite.status == ProjectTeamInvite.Status.PENDING
    assert not UserTenantRole.objects.filter(user=invited, client=project).exists()


@pytest.mark.django_db
def test_remove_member_switches_removed_users_preference(owner_client, owner_user, project):
    from core.models import Client

    second_project = Client.objects.create(name="Spare Project", slug="spare-project")
    member = User.objects.create_user(username="delete-me", email="delete-me@example.com", password="testpass123")
    UserTenantRole.objects.create(user=member, client=project, role="editor")
    UserTenantRole.objects.create(user=member, client=second_project, role="viewer")
    UserActiveClientPreference.objects.create(user=member, client=project)

    response = owner_client.delete(reverse("api:client-team-member-detail", kwargs={"user_id": member.id}))

    assert response.status_code == 204, response.content
    preference = UserActiveClientPreference.objects.get(user=member)
    assert preference.client_id == second_project.id
    assert not UserTenantRole.objects.filter(user=member, client=project).exists()


@pytest.mark.django_db
def test_remove_owner_is_forbidden(owner_client, owner_user, project):
    response = owner_client.delete(reverse("api:client-team-member-detail", kwargs={"user_id": owner_user.id}))

    assert response.status_code == 403, response.content
    assert response.json()["error"] == "cannot_remove_owner"


@pytest.mark.django_db
def test_remove_unknown_member_returns_404(owner_client, project):
    response = owner_client.delete(reverse("api:client-team-member-detail", kwargs={"user_id": 999999}))

    assert response.status_code == 404, response.content


@pytest.mark.django_db
def test_revoking_pending_invite_marks_it_revoked(owner_client, project):
    invite = ProjectTeamInvite.objects.create(
        client=project,
        invited_by=project.usertenantrole_set.get(role="owner").user,
        provider=ProjectTeamInvite.Provider.VK,
        account_handle_raw="revokable",
        account_handle_normalized="revokable",
        role=ProjectTeamInvite.Role.EDITOR,
    )

    response = owner_client.delete(reverse("api:client-team-invitation-detail", kwargs={"invite_id": invite.id}))

    assert response.status_code == 204, response.content
    invite.refresh_from_db()
    assert invite.status == ProjectTeamInvite.Status.REVOKED
    assert invite.revoked_at is not None


@pytest.mark.django_db
def test_team_overview_contains_members_and_pending_invites(owner_client, owner_user, project):
    member = User.objects.create_user(username="team-member", email="team-member@example.com", password="testpass123")
    _link_social(member, UserSocialAccount.PROVIDER_VK, "team-member-vk")
    UserTenantRole.objects.create(user=member, client=project, role="editor")
    ProjectTeamInvite.objects.create(
        client=project,
        invited_by=owner_user,
        provider=ProjectTeamInvite.Provider.TELEGRAM,
        account_handle_raw="@pending-overview",
        account_handle_normalized="pending-overview",
        role=ProjectTeamInvite.Role.EDITOR,
    )

    response = owner_client.get(reverse("api:client-team"))

    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["limit"] >= 1
    assert payload["used_slots"] >= 2
    assert any(item["user_id"] == member.id for item in payload["members"])
    assert any(item["account_handle_normalized"] == "pending-overview" for item in payload["pending_invites"])


@pytest.mark.django_db
def test_team_invitation_endpoint_is_rate_limited(owner_user, project):
    client = _api_client_for(owner_user)
    rest_framework_settings = copy.deepcopy(BASE_REST_FRAMEWORK)
    rest_framework_settings["DEFAULT_THROTTLE_RATES"] = {
        "team_invitation_minute": "1/min",
        "team_invitation_day": "100/day",
    }

    cache.clear()
    with override_settings(REST_FRAMEWORK=rest_framework_settings):
        first_response = client.post(
            reverse("api:client-team-invitations"),
            {"provider": "telegram", "account_handle": "@rate-one"},
            format="json",
        )
        second_response = client.post(
            reverse("api:client-team-invitations"),
            {"provider": "telegram", "account_handle": "@rate-two"},
            format="json",
        )

    assert first_response.status_code == 202, first_response.content
    assert second_response.status_code == 429, second_response.content
