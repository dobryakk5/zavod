from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from core.models import Client, ProjectTeamInvite, UserActiveClientPreference, UserSocialAccount, UserTenantRole

User = get_user_model()

PROVIDER_HANDLE_FIELDS = {
    UserSocialAccount.PROVIDER_TELEGRAM: "username",
    UserSocialAccount.PROVIDER_VK: "screen_name",
}


@dataclass(frozen=True)
class TeamCapacitySnapshot:
    limit: int
    used_slots: int

    @property
    def has_capacity(self) -> bool:
        return self.used_slots < self.limit


def normalize_account_handle(value: str) -> str:
    normalized = str(value or "").strip()
    normalized = normalized.lstrip("@")
    return normalized.lower()


def normalize_email_address(value: str) -> str:
    return str(value or "").strip().lower()


def get_team_capacity_snapshot(client: Client, *, exclude_pending_invite_id: int | None = None) -> TeamCapacitySnapshot:
    limit = int(getattr(settings, "TEAM_MAX_COLLABORATORS", 20) or 20)
    active_members = UserTenantRole.objects.filter(
        client=client,
        role__in=("editor", "viewer"),
    ).count()
    pending_invites_qs = ProjectTeamInvite.objects.filter(
        client=client,
        status=ProjectTeamInvite.Status.PENDING,
    )
    if exclude_pending_invite_id is not None:
        pending_invites_qs = pending_invites_qs.exclude(id=exclude_pending_invite_id)
    pending_invites = pending_invites_qs.count()
    return TeamCapacitySnapshot(limit=limit, used_slots=active_members + pending_invites)


def has_team_capacity(client: Client, *, exclude_pending_invite_id: int | None = None) -> bool:
    return get_team_capacity_snapshot(
        client,
        exclude_pending_invite_id=exclude_pending_invite_id,
    ).has_capacity


def _membership_queryset_for_user(user):
    role_priority = Case(
        When(role="owner", then=Value(0)),
        When(role="editor", then=Value(1)),
        When(role="viewer", then=Value(2)),
        default=Value(99),
        output_field=IntegerField(),
    )
    return (
        UserTenantRole.objects.select_related("client")
        .filter(user=user)
        .annotate(_role_priority=role_priority)
        .order_by("_role_priority", "client_id", "id")
    )


def list_user_memberships(user) -> list[UserTenantRole]:
    return list(_membership_queryset_for_user(user))


def set_active_client_preference(user, client: Client | None) -> UserActiveClientPreference:
    preference, _ = UserActiveClientPreference.objects.get_or_create(user=user)
    if preference.client_id != (client.id if client else None):
        preference.client = client
        preference.save(update_fields=["client", "updated_at"])
    return preference


def ensure_valid_active_client_preference(user) -> Client | None:
    memberships = list(_membership_queryset_for_user(user))
    available_client_ids = {item.client_id for item in memberships}
    if not available_client_ids:
        UserActiveClientPreference.objects.filter(user=user).update(client=None)
        return None

    preference = UserActiveClientPreference.objects.filter(user=user).select_related("client").first()
    if preference and preference.client_id in available_client_ids and preference.client is not None:
        return preference.client

    client = memberships[0].client
    set_active_client_preference(user, client)
    return client


def sync_active_client_preference_after_membership_removal(user, removed_client_id: int) -> None:
    preference = UserActiveClientPreference.objects.filter(user=user).first()
    if not preference or preference.client_id != removed_client_id:
        return
    next_client = _membership_queryset_for_user(user).exclude(client_id=removed_client_id).first()
    set_active_client_preference(user, next_client.client if next_client else None)


def get_user_provider_handles(user) -> dict[str, set[str]]:
    handles: dict[str, set[str]] = {}
    social_accounts = UserSocialAccount.objects.filter(user=user)
    for account in social_accounts:
        handle_field = PROVIDER_HANDLE_FIELDS.get(account.provider)
        if not handle_field or not isinstance(account.extra_data, dict):
            continue
        raw_value = account.extra_data.get(handle_field)
        normalized = normalize_account_handle(raw_value)
        if not normalized:
            continue
        handles.setdefault(account.provider, set()).add(normalized)
    return handles


def find_users_by_provider_handle(provider: str, normalized_handle: str):
    handle_field = PROVIDER_HANDLE_FIELDS.get(provider)
    if not handle_field or not normalized_handle:
        return User.objects.none()
    lookup = {f"social_accounts_auth__extra_data__{handle_field}__iexact": normalized_handle}
    return (
        User.objects.filter(social_accounts_auth__provider=provider, **lookup)
        .distinct()
        .order_by("id")
    )


def get_matching_project_membership(client: Client, provider: str, normalized_handle: str) -> UserTenantRole | None:
    if provider == ProjectTeamInvite.Provider.EMAIL:
        return (
            UserTenantRole.objects.select_related("user")
            .filter(client=client, user__email__iexact=normalized_handle)
            .order_by("id")
            .first()
        )

    users = find_users_by_provider_handle(provider, normalized_handle)
    if users.count() != 1:
        return None
    return (
        UserTenantRole.objects.select_related("user")
        .filter(client=client, user=users.first())
        .first()
    )


def accept_pending_team_invites(user) -> list[ProjectTeamInvite]:
    provider_handles = get_user_provider_handles(user)
    if not provider_handles:
        provider_handles = {}

    invite_match_query = Q()
    for provider, handles in provider_handles.items():
        if handles:
            invite_match_query |= Q(provider=provider, account_handle_normalized__in=sorted(handles))

    normalized_email = normalize_email_address(getattr(user, "email", ""))
    if normalized_email:
        invite_match_query |= Q(
            provider=ProjectTeamInvite.Provider.EMAIL,
            account_handle_normalized=normalized_email,
        )

    if not invite_match_query:
        return []

    accepted_invites: list[ProjectTeamInvite] = []
    with transaction.atomic():
        pending_invites = list(
            ProjectTeamInvite.objects.select_for_update()
            .select_related("client")
            .filter(status=ProjectTeamInvite.Status.PENDING)
            .filter(invite_match_query)
            .order_by("created_at", "id")
        )
        for invite in pending_invites:
            if not has_team_capacity(invite.client, exclude_pending_invite_id=invite.id):
                continue
            try:
                UserTenantRole.objects.get_or_create(
                    user=user,
                    client=invite.client,
                    defaults={"role": invite.role},
                )
            except IntegrityError:
                pass
            invite.status = ProjectTeamInvite.Status.ACCEPTED
            invite.accepted_user = user
            invite.accepted_at = timezone.now()
            invite.save(update_fields=["status", "accepted_user", "accepted_at"])
            accepted_invites.append(invite)

    if accepted_invites:
        ensure_valid_active_client_preference(user)

    return accepted_invites
