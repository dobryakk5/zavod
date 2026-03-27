from __future__ import annotations

from collections import defaultdict

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ProjectTeamInvite, UserSocialAccount, UserTenantRole
from core.services.team_invites import (
    get_matching_project_membership,
    get_team_capacity_snapshot,
    normalize_account_handle,
    set_active_client_preference,
    sync_active_client_preference_after_membership_removal,
)

from .permissions import IsTenantOwner
from .serializers import PendingTeamInviteSerializer, TeamOverviewSerializer
from .throttles import TeamInvitationDayThrottle, TeamInvitationMinuteThrottle
from .utils import build_client_info_payload, get_active_client


def _provider_account_payload(account: UserSocialAccount) -> dict:
    extra_data = account.extra_data if isinstance(account.extra_data, dict) else {}
    handle = ""
    if account.provider == UserSocialAccount.PROVIDER_TELEGRAM:
        handle = normalize_account_handle(extra_data.get("username") or "")
    elif account.provider == UserSocialAccount.PROVIDER_VK:
        handle = normalize_account_handle(extra_data.get("screen_name") or "")

    display_name = (
        f"{extra_data.get('first_name', '')} {extra_data.get('last_name', '')}".strip()
        or extra_data.get("username")
        or extra_data.get("screen_name")
        or account.provider_id
    )
    return {
        "provider": account.provider,
        "handle": handle or None,
        "display_name": display_name,
    }


class ActiveClientView(APIView):
    def post(self, request):
        client_id_raw = request.data.get("client_id")
        try:
            client_id = int(client_id_raw)
        except (TypeError, ValueError):
            return Response({"error": "Некорректный client_id"}, status=status.HTTP_400_BAD_REQUEST)

        membership = (
            UserTenantRole.objects.select_related("client")
            .filter(user=request.user, client_id=client_id)
            .first()
        )
        if membership is None:
            return Response({"error": "Клиент недоступен"}, status=status.HTTP_403_FORBIDDEN)

        set_active_client_preference(request.user, membership.client)
        return Response(build_client_info_payload(request.user))


class ClientTeamView(APIView):
    permission_classes = [IsTenantOwner]

    def get(self, request):
        client = get_active_client(request.user)
        memberships = list(
            UserTenantRole.objects.select_related("user")
            .filter(client=client)
            .order_by("role", "user__username", "user_id")
        )
        user_ids = [membership.user_id for membership in memberships]
        accounts_by_user: dict[int, list[dict]] = defaultdict(list)
        for account in UserSocialAccount.objects.filter(user_id__in=user_ids).order_by("provider", "id"):
            accounts_by_user[account.user_id].append(_provider_account_payload(account))

        invite_by_user_id = {}
        accepted_invites = (
            ProjectTeamInvite.objects.select_related("invited_by")
            .filter(client=client, status=ProjectTeamInvite.Status.ACCEPTED, accepted_user_id__in=user_ids)
            .order_by("-accepted_at", "-id")
        )
        for invite in accepted_invites:
            invite_by_user_id.setdefault(invite.accepted_user_id, invite)

        members_payload = []
        for membership in memberships:
            user = membership.user
            invite = invite_by_user_id.get(user.id)
            display_name = user.get_full_name() or user.get_username()
            invited_by_name = None
            invite_id = None
            if invite is not None:
                invited_by_name = invite.invited_by.get_full_name() or invite.invited_by.get_username()
                invite_id = invite.id
            members_payload.append(
                {
                    "user_id": user.id,
                    "username": user.get_username(),
                    "display_name": display_name,
                    "role": membership.role,
                    "provider_accounts": accounts_by_user.get(user.id, []),
                    "invited_by": invited_by_name,
                    "joined_via_invite_id": invite_id,
                }
            )

        pending_invites = ProjectTeamInvite.objects.select_related("invited_by").filter(
            client=client,
            status=ProjectTeamInvite.Status.PENDING,
        ).order_by("-created_at", "-id")
        capacity = get_team_capacity_snapshot(client)
        serializer = TeamOverviewSerializer(
            {
                "members": members_payload,
                "pending_invites": pending_invites,
                "limit": capacity.limit,
                "used_slots": capacity.used_slots,
            }
        )
        return Response(serializer.data)


class ClientTeamInvitationsView(APIView):
    permission_classes = [IsTenantOwner]
    throttle_classes = [TeamInvitationMinuteThrottle, TeamInvitationDayThrottle]

    def post(self, request):
        client = get_active_client(request.user)
        provider = str(request.data.get("provider") or "").strip().lower()
        if provider not in {ProjectTeamInvite.Provider.TELEGRAM, ProjectTeamInvite.Provider.VK}:
            return Response({"error": "Некорректный provider"}, status=status.HTTP_400_BAD_REQUEST)

        account_handle_raw = str(request.data.get("account_handle") or "").strip()
        normalized_handle = normalize_account_handle(account_handle_raw)
        if not normalized_handle:
            return Response({"error": "Введите аккаунт"}, status=status.HTTP_400_BAD_REQUEST)

        existing_member = get_matching_project_membership(client, provider, normalized_handle)
        if existing_member is not None:
            return Response(
                {
                    "status": "already_member",
                    "message": "Приглашение обработано. Когда пользователь войдёт подходящим аккаунтом, доступ будет доступен в проекте.",
                }
            )

        existing_pending = ProjectTeamInvite.objects.filter(
            client=client,
            provider=provider,
            account_handle_normalized=normalized_handle,
            status=ProjectTeamInvite.Status.PENDING,
        ).first()
        if existing_pending is not None:
            return Response(
                {
                    "status": "existing_pending",
                    "message": "Приглашение обработано. Когда пользователь войдёт подходящим аккаунтом, доступ будет доступен в проекте.",
                    "invite_id": existing_pending.id,
                }
            )

        capacity = get_team_capacity_snapshot(client)
        if not capacity.has_capacity:
            return Response(
                {
                    "error": "team_limit_reached",
                    "limit": capacity.limit,
                    "used_slots": capacity.used_slots,
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            invite = ProjectTeamInvite.objects.create(
                client=client,
                invited_by=request.user,
                provider=provider,
                account_handle_raw=account_handle_raw,
                account_handle_normalized=normalized_handle,
                role=ProjectTeamInvite.Role.EDITOR,
                status=ProjectTeamInvite.Status.PENDING,
            )
        except IntegrityError:
            invite = ProjectTeamInvite.objects.filter(
                client=client,
                provider=provider,
                account_handle_normalized=normalized_handle,
                status=ProjectTeamInvite.Status.PENDING,
            ).first()
            return Response(
                {
                    "status": "existing_pending",
                    "message": "Приглашение обработано. Когда пользователь войдёт подходящим аккаунтом, доступ будет доступен в проекте.",
                    "invite_id": invite.id if invite else None,
                }
            )

        return Response(
            {
                "status": "pending_created",
                "message": "Приглашение обработано. Когда пользователь войдёт подходящим аккаунтом, доступ будет доступен в проекте.",
                "invite_id": invite.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ClientTeamInvitationDetailView(APIView):
    permission_classes = [IsTenantOwner]

    def delete(self, request, invite_id: int):
        client = get_active_client(request.user)
        invite = ProjectTeamInvite.objects.filter(
            id=invite_id,
            client=client,
            status=ProjectTeamInvite.Status.PENDING,
        ).first()
        if invite is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        invite.status = ProjectTeamInvite.Status.REVOKED
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["status", "revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientTeamMemberDetailView(APIView):
    permission_classes = [IsTenantOwner]

    def delete(self, request, user_id: int):
        client = get_active_client(request.user)
        membership = (
            UserTenantRole.objects.select_related("user")
            .filter(client=client, user_id=user_id)
            .first()
        )
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if membership.role == "owner":
            return Response(
                {"error": "cannot_remove_owner"},
                status=status.HTTP_403_FORBIDDEN,
            )

        with transaction.atomic():
            removed_user = membership.user
            removed_client_id = membership.client_id
            membership.delete()
            sync_active_client_preference_after_membership_removal(removed_user, removed_client_id)

        return Response(status=status.HTTP_204_NO_CONTENT)
