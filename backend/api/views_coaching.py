from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta
from uuid import uuid4

from django.db import transaction
from django.db.models import Count, Q
from django.db.utils import NotSupportedError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    CRMTask,
    CoachGroup,
    CoachGroupMember,
    CoachGroupTask,
    CoachingGoal,
    CoachingGoalCompetency,
    ContactCoachingProfile,
    InviteLink,
    MapContact,
    UserTenantBinding,
)

from .coaching_tasks import (
    COACHING_DONE_STATUSES,
    COACHING_TASK_SOURCE,
    COACH_DONE_HISTORY_NOTE,
    COACH_REOPEN_HISTORY_NOTE,
    CREATE_HISTORY_NOTE,
    EDIT_HISTORY_NOTE,
    completed_coaching_task_count_last_30_days,
    coaching_task_queryset,
    create_coaching_milestone,
    create_coaching_task,
    flatten_coaching_steps,
    has_recent_coaching_milestone,
    has_overdue_coaching_task,
    list_coaching_milestones,
    list_coaching_task_payloads,
    list_coaching_tasks_by_goal,
    serialize_coaching_milestone,
    serialize_coaching_task,
    serialize_coaching_step,
    update_coaching_task,
    CoachingTaskUpdate,
)
from .coaching_goals import (
    GROUP_GOAL_ID_PREFIX,
    average_progress as average_goal_progress,
    competencies_map,
    goal_display_title,
    goal_focus as resolve_goal_focus,
    goal_progress_for_payload,
    goal_title_map as build_goal_title_map,
    group_goal_id,
    group_goal_title,
    is_group_goal_public_id,
    profile_goal_rows,
    serialize_goal_for_edit,
    serialize_goal_for_list,
)
from .invite_auth import build_frontend_url
from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers_coaching import (
    CoachGroupCreateSerializer,
    CoachGroupMemberCreateSerializer,
    CoachGroupMembersBulkCreateSerializer,
    CoachGroupTaskCreateSerializer,
    CoachingCompetencySerializer,
    CoachingContactUpdateSerializer,
    CoachingGoalEditSerializer,
    CoachingGoalStepCreateSerializer,
    CoachingGoalStepUpdateSerializer,
    CoachingMilestoneCreateSerializer,
    CoachingOnboardingSerializer,
    CoachingSessionCreateSerializer,
    CoachingSessionUpdateSerializer,
)
from .utils import get_active_client


def _tenant_contact_ids_queryset(tenant_id: int):
    return (
        UserTenantBinding.objects
        .filter(tenant_id=tenant_id, contact_id__isnull=False, contact_id__gt=0)
        .values_list("contact_id", flat=True)
    )


def _tenant_contact_or_none(tenant_id: int, contact_id: int) -> MapContact | None:
    return (
        MapContact.objects
        .filter(id=contact_id, id__in=_tenant_contact_ids_queryset(tenant_id))
        .first()
    )


def _get_profile(tenant_id: int, contact_id: int) -> ContactCoachingProfile | None:
    return ContactCoachingProfile.objects.filter(tenant_id=tenant_id, contact_id=contact_id).first()


def _get_or_create_profile(tenant_id: int, contact_id: int) -> ContactCoachingProfile:
    profile, _ = ContactCoachingProfile.objects.get_or_create(
        tenant_id=tenant_id,
        contact_id=contact_id,
    )
    return profile


def _parse_moment(value: str | None):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is not None:
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    d = parse_date(value)
    if d is not None:
        return timezone.make_aware(
            datetime.combine(d, time.min),
            timezone.get_current_timezone(),
        )
    return None


def _contact_initials(name: str) -> str:
    parts = [part for part in (name or "").split() if part]
    if not parts:
        return "—"
    return "".join(part[:1].upper() for part in parts[:2])


def _group_task_refs(task: CoachGroupTask) -> list[dict]:
    refs = task.step_refs if isinstance(task.step_refs, list) else []
    return [ref for ref in refs if isinstance(ref, dict)]


def _profile_goals(profile: ContactCoachingProfile) -> list[CoachingGoal]:
    return profile_goal_rows(profile)


def _ensure_group_goal(profile: ContactCoachingProfile, group: CoachGroup) -> CoachingGoal:
    goal_id = group_goal_id(int(group.id))
    goal, created = CoachingGoal.objects.get_or_create(
        profile=profile,
        public_id=goal_id,
        defaults={
            "goal_type": CoachingGoal.TYPE_GROUP,
            "title": group_goal_title(group.name),
            "progress": 0,
            "horizon": CoachingGoal.HORIZON_MONTH,
            "status": CoachingGoal.STATUS_ACTIVE,
            "sort_order": profile.goal_rows.count(),
            "group": group,
            "created_at": timezone.now(),
        },
    )
    changed_fields: list[str] = []
    if goal.goal_type != CoachingGoal.TYPE_GROUP:
        goal.goal_type = CoachingGoal.TYPE_GROUP
        changed_fields.append("goal_type")
    expected_title = group_goal_title(group.name)
    if goal.title != expected_title:
        goal.title = expected_title
        changed_fields.append("title")
    if goal.group_id != group.id:
        goal.group = group
        changed_fields.append("group")
    if created:
        return goal
    if changed_fields:
        goal.save(update_fields=changed_fields + ["updated_at"])
    return goal


def _drop_group_goal_if_no_tasks(profile: ContactCoachingProfile | None, goal_id: str) -> bool:
    if profile is None:
        return False
    goal = (
        CoachingGoal.objects
        .filter(profile=profile, public_id=goal_id, goal_type=CoachingGoal.TYPE_GROUP)
        .first()
    )
    if goal is None:
        return False
    if coaching_task_queryset(contact_id=int(profile.contact_id), goal_id=goal_id).exists():
        return False
    goal.delete()
    return True


def _build_group_step_done_index(
    group_id: int,
    contact_ids: list[int],
) -> dict[tuple[int, str], bool]:
    goal_id = group_goal_id(group_id)
    done_index: dict[tuple[int, str], bool] = {}
    for task in coaching_task_queryset(goal_id=goal_id).filter(contact_id__in=contact_ids):
        done_index[(int(task.contact_id), str(task.id))] = str(task.status or "").strip().lower() in COACHING_DONE_STATUSES
    return done_index

def _goal_focus(profile: ContactCoachingProfile) -> str:
    return resolve_goal_focus(_profile_goals(profile), profile.competencies if isinstance(profile.competencies, list) else [])


def _profile_avg_progress(profile: ContactCoachingProfile) -> int:
    return average_goal_progress(_profile_goals(profile))


def _session_status_value(session: dict) -> str:
    status_value = str(session.get("status") or "").strip().lower()
    if status_value in {"draft", "done"}:
        return status_value
    return "done"


def _serialize_session(profile: ContactCoachingProfile, session: dict) -> dict:
    return {
        "id": str(session.get("id") or ""),
        "clientId": int(session.get("clientId") or profile.contact_id),
        "number": int(session.get("number") or 1),
        "date": str(session.get("date") or timezone.now().isoformat()),
        "notes": str(session.get("notes") or ""),
        "coachNotes": str(session.get("coachNotes") or ""),
        "status": _session_status_value(session),
    }


def _sort_sessions(items: list[dict]) -> list[dict]:
    drafts = [item for item in items if str(item.get("status") or "") == "draft"]
    done = [item for item in items if str(item.get("status") or "") != "draft"]
    drafts.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    done.sort(key=lambda item: str(item.get("date") or ""), reverse=True)
    return [*drafts, *done]


def _profile_sessions(profile: ContactCoachingProfile, *, include_drafts: bool = True) -> list[dict]:
    sessions = [
        _serialize_session(profile, item)
        for item in (profile.sessions or [])
        if isinstance(item, dict)
    ]
    if not include_drafts:
        sessions = [item for item in sessions if item["status"] != "draft"]
    return _sort_sessions(sessions)


def _profile_completed_tasks_last_30_days(profile: ContactCoachingProfile, today) -> int:
    return completed_coaching_task_count_last_30_days(profile.contact_id, today)


def _profile_next_session(profile: ContactCoachingProfile) -> str | None:
    now = timezone.now()
    future_dates = []
    for session in _profile_sessions(profile, include_drafts=False):
        dt = _parse_moment(str(session.get("date") or ""))
        if dt is not None and dt >= now:
            future_dates.append(dt)
    if not future_dates:
        return None
    return min(future_dates).isoformat()


def _profile_items(profile: ContactCoachingProfile, field_name: str) -> list[dict]:
    raw_items = getattr(profile, field_name, [])
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def _profile_next_session_moment(profile: ContactCoachingProfile, now: datetime) -> datetime | None:
    future_dates = []
    for session in _profile_sessions(profile, include_drafts=False):
        moment = _parse_moment(str(session.get("date") or ""))
        if moment is not None and moment >= now:
            future_dates.append(moment)
    if not future_dates:
        return None
    return min(future_dates)


def _profile_last_session_moment(profile: ContactCoachingProfile, now: datetime) -> datetime | None:
    past_dates = []
    for session in _profile_sessions(profile, include_drafts=False):
        moment = _parse_moment(str(session.get("date") or ""))
        if moment is not None and moment <= now:
            past_dates.append(moment)
    if not past_dates:
        return None
    return max(past_dates)


def _profile_has_overdue_task(profile: ContactCoachingProfile, now: datetime) -> bool:
    return has_overdue_coaching_task(profile.contact_id, profile.tenant.timezone, now)


def _profile_has_recent_milestone(profile: ContactCoachingProfile, now: datetime) -> bool:
    return has_recent_coaching_milestone(profile.contact_id, now)


def _format_status_time(moment: datetime) -> str:
    return timezone.localtime(moment).strftime("%H:%M")


def _pluralize_days(days: int) -> str:
    mod10 = days % 10
    mod100 = days % 100
    if mod10 == 1 and mod100 != 11:
        return "день"
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return "дня"
    return "дней"


def _client_status(profile: ContactCoachingProfile) -> dict | None:
    now = timezone.now()

    next_session = _profile_next_session_moment(profile, now)
    if next_session is not None:
        delta_days = (timezone.localdate(next_session) - timezone.localdate(now)).days
        if delta_days == 0:
            return {
                "kind": "today",
                "label": f"Сегодня {_format_status_time(next_session)}",
                "at": next_session.isoformat(),
            }
        if delta_days == 1:
            return {
                "kind": "tomorrow",
                "label": f"Завтра {_format_status_time(next_session)}",
                "at": next_session.isoformat(),
            }

    if _profile_has_overdue_task(profile, now):
        return {
            "kind": "overdue",
            "label": "Задание просрочено",
            "at": None,
        }

    if _profile_has_recent_milestone(profile, now):
        return {
            "kind": "milestone",
            "label": "Прорыв",
            "at": None,
        }

    sessions_count = len(_profile_sessions(profile, include_drafts=False))
    if sessions_count <= 2:
        return {
            "kind": "new",
            "label": "Новый",
            "at": None,
        }

    last_session = _profile_last_session_moment(profile, now)
    if last_session is not None:
        days_since = (timezone.localdate(now) - timezone.localdate(last_session)).days
        if days_since > 21:
            return {
                "kind": "inactive",
                "label": f"{days_since} {_pluralize_days(days_since)} без сессии",
                "at": last_session.isoformat(),
            }

    return None


def _serialize_contact(contact: MapContact, tenant_id: int, profile: ContactCoachingProfile | None) -> dict:
    profile = profile or ContactCoachingProfile(tenant_id=tenant_id, contact_id=int(contact.id))
    return {
        "id": str(contact.id),
        "name": contact.name,
        "email": str(contact.email or ""),
        "initials": _contact_initials(contact.name),
        "focus": _goal_focus(profile),
        "intention": str(profile.intention or ""),
        "sessionsCount": len(_profile_sessions(profile, include_drafts=False)),
        "avgProgress": _profile_avg_progress(profile),
        "nextSession": _profile_next_session(profile),
        "clientStatus": _client_status(profile),
        "coachId": str(tenant_id),
        "createdAt": contact.created_at.isoformat() if contact.created_at else timezone.now().isoformat(),
    }


def _serialize_group(group: CoachGroup, member_count: int | None = None) -> dict:
    return {
        "id": str(group.id),
        "name": str(group.name or ""),
        "initials": _contact_initials(group.name),
        "memberCount": int(member_count if member_count is not None else getattr(group, "member_count", 0) or 0),
        "createdAt": group.created_at.isoformat() if group.created_at else timezone.now().isoformat(),
    }


def _serialize_group_member(contact: MapContact, profile: ContactCoachingProfile | None) -> dict:
    profile = profile or ContactCoachingProfile(contact_id=int(contact.id), tenant_id=0)
    return {
        "clientId": str(contact.id),
        "name": str(contact.name or ""),
        "initials": _contact_initials(contact.name),
        "focus": _goal_focus(profile),
        "avgProgress": _profile_avg_progress(profile),
    }


def _goal_title_map(profile: ContactCoachingProfile) -> dict[str, str]:
    return build_goal_title_map(_profile_goals(profile))


def _flatten_profile_goal_steps(profile: ContactCoachingProfile, *, done: bool | None = None) -> list[dict]:
    return flatten_coaching_steps(
        profile.contact_id,
        profile.tenant.timezone,
        done=done,
        goal_titles_by_id=_goal_title_map(profile),
    )


def _normalize_competencies(data: list[dict]) -> list[dict]:
    return [
        {
            "id": str(item["id"]),
            "name": item["name"],
            "score": int(item["score"]),
            "startScore": int(item["startScore"]),
            "color": item.get("color") or "",
        }
        for item in data
    ]


def _build_removed_competency_milestones(contact_id: int, previous: list[dict], current: list[dict]) -> list[dict]:
    current_ids = {
        str(item.get("id") or "")
        for item in current
        if isinstance(item, dict) and item.get("id")
    }
    created_at = timezone.now().isoformat()
    milestones: list[dict] = []
    for item in previous:
        if not isinstance(item, dict):
            continue
        competency_id = str(item.get("id") or "")
        if not competency_id or competency_id in current_ids:
            continue
        name = str(item.get("name") or "").strip() or "без названия"
        growth = max(int(item.get("score") or 0) - int(item.get("startScore") or 0), 0)
        milestones.append(
            {
                "clientId": contact_id,
                "goalId": "",
                "text": f"Рост компетенции {name} на {growth}%",
                "note": "",
                "createdAt": created_at,
            }
        )
    return milestones


def _parse_goal_created_at(value: str | None):
    parsed = _parse_moment(value)
    return parsed or timezone.now()


def _replace_personal_goals(profile: ContactCoachingProfile, validated_goals: list[dict]) -> list[CoachingGoal]:
    existing_goals = {
        goal.public_id: goal
        for goal in (
            CoachingGoal.objects
            .filter(profile=profile, goal_type=CoachingGoal.TYPE_PERSONAL)
            .prefetch_related("competency_links")
        )
    }
    incoming_ids: list[str] = []

    for position, payload in enumerate(validated_goals):
        goal_id = str(payload["id"]).strip()
        incoming_ids.append(goal_id)
        goal = existing_goals.get(goal_id)
        if goal is None:
            goal = CoachingGoal(
                profile=profile,
                public_id=goal_id,
                goal_type=CoachingGoal.TYPE_PERSONAL,
                created_at=_parse_goal_created_at(payload.get("createdAt")),
            )
        goal.title = str(payload["title"] or "")
        goal.progress = int(payload["progress"])
        goal.horizon = payload["horizon"]
        goal.status = payload["status"]
        goal.sort_order = position
        goal.group = None
        goal.save()

        goal.competency_links.all().delete()
        CoachingGoalCompetency.objects.bulk_create(
            [
                CoachingGoalCompetency(
                    goal=goal,
                    competency_id=str(link["competencyId"]),
                    competency_name=str(link.get("competencyName") or ""),
                    weight=round(float(link["weight"]), 4),
                    sort_order=link_index,
                )
                for link_index, link in enumerate(payload.get("competencyLinks") or [])
            ]
        )

    removed_goal_ids = set(existing_goals) - set(incoming_ids)
    if removed_goal_ids:
        CRMTask.objects.filter(
            source=COACHING_TASK_SOURCE,
            contact_id=profile.contact_id,
            goal_id__in=removed_goal_ids,
        ).delete()

    if incoming_ids:
        CoachingGoal.objects.filter(profile=profile, goal_type=CoachingGoal.TYPE_PERSONAL).exclude(public_id__in=incoming_ids).delete()
    else:
        CoachingGoal.objects.filter(profile=profile, goal_type=CoachingGoal.TYPE_PERSONAL).delete()

    return list(
        CoachingGoal.objects
        .filter(profile=profile)
        .select_related("group")
        .prefetch_related("competency_links")
        .order_by("sort_order", "created_at", "id")
    )


def _find_profile_goal(tenant_id: int, goal_id: str) -> tuple[ContactCoachingProfile, CoachingGoal] | tuple[None, None]:
    goal = (
        CoachingGoal.objects
        .select_related("profile__tenant", "group")
        .prefetch_related("competency_links")
        .filter(profile__tenant_id=tenant_id, public_id=goal_id)
        .first()
    )
    if goal is None:
        return None, None
    return goal.profile, goal


def _goal_response(profile: ContactCoachingProfile, goal: CoachingGoal) -> dict:
    competencies_by_id = competencies_map(profile)
    steps_by_goal_id = list_coaching_tasks_by_goal(profile.contact_id, profile.tenant.timezone, _goal_title_map(profile))
    return serialize_goal_for_list(goal, profile.contact_id, competencies_by_id, steps_by_goal_id)


def _goal_title_for_task(profile: ContactCoachingProfile, goal_id: str | None) -> str:
    if not goal_id:
        return ""
    for goal in _profile_goals(profile):
        if str(goal.public_id or "") == str(goal_id):
            return goal_display_title(goal)
    return ""


def _find_coaching_task(tenant_id: int, task_id: str) -> CRMTask | None:
    try:
        task_pk = int(task_id)
    except (TypeError, ValueError):
        return None
    allowed_contact_ids = list(_tenant_contact_ids_queryset(tenant_id))
    if not allowed_contact_ids:
        return None
    return (
        coaching_task_queryset()
        .filter(id=task_pk, contact_id__in=allowed_contact_ids)
        .first()
    )


def _serialize_group_task(task: CoachGroupTask, done_index: dict[tuple[int, str], bool] | None = None) -> dict:
    done_count = 0
    refs = _group_task_refs(task)
    for ref in refs:
        try:
            contact_id = int(ref.get("contactId"))
        except (TypeError, ValueError):
            continue
        task_id = str(ref.get("taskId") or "")
        if done_index and done_index.get((contact_id, task_id)):
            done_count += 1

    return {
        "id": str(task.id),
        "groupId": str(task.group_id),
        "text": str(task.text or ""),
        "dueDate": task.due_date.isoformat() if task.due_date else None,
        "createdAt": task.created_at.isoformat() if task.created_at else timezone.now().isoformat(),
        "doneCount": done_count,
        "totalCount": len(refs),
    }


def _serialize_invite_link(invite: InviteLink, request) -> dict:
    return {
        "id": str(invite.id),
        "clientId": str(invite.contact_id),
        "token": str(invite.token),
        "url": build_frontend_url(request, f"/invite/{invite.token}"),
        "expiresAt": invite.expires_at.isoformat() if invite.expires_at else None,
        "usedAt": invite.used_at.isoformat() if invite.used_at else None,
        "createdAt": invite.created_at.isoformat() if invite.created_at else timezone.now().isoformat(),
    }


def _delete_group_task_steps(task: CoachGroupTask) -> None:
    refs_by_contact: dict[int, list[str]] = {}
    for ref in _group_task_refs(task):
        try:
            contact_id = int(ref.get("contactId"))
        except (TypeError, ValueError):
            continue
        task_id = str(ref.get("taskId") or "")
        if not task_id:
            continue
        refs_by_contact.setdefault(contact_id, []).append(task_id)

    goal_id = group_goal_id(int(task.group_id))
    for contact_id, task_ids in refs_by_contact.items():
        CRMTask.objects.filter(
            id__in=[int(task_id) for task_id in task_ids if task_id.isdigit()],
            source=COACHING_TASK_SOURCE,
            contact_id=contact_id,
        ).delete()
        profile = _get_profile(int(task.group.tenant_id), contact_id)
        _drop_group_goal_if_no_tasks(profile, goal_id)


def _adjust_competencies_for_goal(profile: ContactCoachingProfile, goal: CoachingGoal, next_progress: int) -> None:
    previous_progress = int(goal.progress or 0)
    delta = next_progress - previous_progress
    if delta == 0:
        return

    competencies = []
    links_by_competency_id = {
        str(link.competency_id or ""): link
        for link in goal.competency_links.all()
    }
    for competency in profile.competencies or []:
        if not isinstance(competency, dict):
            continue
        link = links_by_competency_id.get(str(competency.get("id") or ""))
        if link is None:
            competencies.append(competency)
            continue

        next_score = round(float(competency.get("score") or 0) + (delta * float(link.weight or 0)))
        competencies.append(
            {
                **competency,
                "score": max(0, min(100, int(next_score))),
            }
        )
    profile.competencies = competencies


class CoachStatsView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        tenant = get_active_client(request.user)
        contact_ids = list(set(_tenant_contact_ids_queryset(int(tenant.id))))
        profiles = {
            profile.contact_id: profile
            for profile in (
                ContactCoachingProfile.objects
                .filter(tenant=tenant, contact_id__in=contact_ids)
                .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            )
        }

        all_goals = []
        today = timezone.localdate()
        sessions_today = 0
        completed_tasks = 0
        for profile in profiles.values():
            for goal in _profile_goals(profile):
                all_goals.append(int(goal.progress or 0))
            completed_tasks += _profile_completed_tasks_last_30_days(profile, today)
            for session in _profile_sessions(profile, include_drafts=False):
                moment = _parse_moment(str(session.get("date") or ""))
                if moment is not None and timezone.localdate(moment) == today:
                    sessions_today += 1

        avg_progress = round(sum(all_goals) / len(all_goals)) if all_goals else 0
        return Response(
            {
                "activeClients": len(contact_ids),
                "completedTasks": completed_tasks,
                "tasksCompletionRate": completed_tasks,
                "avgProgress": avg_progress,
                "sessionsToday": sessions_today,
            }
        )


class CoachClientsView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        tenant = get_active_client(request.user)
        contacts = list(
            MapContact.objects
            .filter(id__in=_tenant_contact_ids_queryset(int(tenant.id)))
            .order_by("name", "id")
        )
        profiles = {
            profile.contact_id: profile
            for profile in (
                ContactCoachingProfile.objects
                .filter(tenant=tenant, contact_id__in=[int(contact.id) for contact in contacts])
                .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            )
        }
        payload = [_serialize_contact(contact, int(tenant.id), profiles.get(int(contact.id))) for contact in contacts]
        return Response(payload)


class CoachingContactDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)
        profile = _get_profile(int(tenant.id), contact_id)
        return Response(_serialize_contact(contact, int(tenant.id), profile))

    def patch(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingContactUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        profile.intention = serializer.validated_data.get("intention") or ""
        profile.save(update_fields=["intention"])
        return Response(_serialize_contact(contact, int(tenant.id), profile))


class ContactCompetenciesView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)
        profile = _get_or_create_profile(int(tenant.id), contact_id)
        payload = profile.competencies if isinstance(profile.competencies, list) else []
        return Response(payload)

    def put(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingCompetencySerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        previous_competencies = [item for item in (profile.competencies or []) if isinstance(item, dict)]
        next_competencies = _normalize_competencies(serializer.validated_data)
        new_milestones = _build_removed_competency_milestones(contact_id, previous_competencies, next_competencies)
        with transaction.atomic():
            profile.competencies = next_competencies
            profile.save()
            for milestone in new_milestones:
                create_coaching_milestone(
                    contact_id=contact_id,
                    goal_id=milestone.get("goalId") or None,
                    text=str(milestone["text"]),
                    note=str(milestone.get("note") or ""),
                    created_at=_parse_moment(str(milestone.get("createdAt") or "")) or timezone.now(),
                )
        return Response(profile.competencies)


class ContactGoalsEditView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = (
            ContactCoachingProfile.objects
            .filter(tenant_id=int(tenant.id), contact_id=contact_id)
            .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            .first()
        )
        if profile is None:
            profile = _get_or_create_profile(int(tenant.id), contact_id)
        goals = _profile_goals(profile)
        competencies_by_id = competencies_map(profile)
        steps_by_goal_id = list_coaching_tasks_by_goal(profile.contact_id, tenant.timezone, _goal_title_map(profile))
        payload = [
            {
                **serialize_goal_for_edit(goal, competencies_by_id),
                "steps": deepcopy(steps_by_goal_id.get(str(goal.public_id or ""), [])),
                "progress": goal_progress_for_payload(goal, steps_by_goal_id.get(str(goal.public_id or ""), [])),
            }
            for goal in goals
        ]
        return Response(payload)

    def put(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingGoalEditSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        goals = _replace_personal_goals(profile, serializer.validated_data)
        profile = (
            ContactCoachingProfile.objects
            .filter(id=profile.id)
            .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            .first()
            or profile
        )
        competencies_by_id = competencies_map(profile)
        steps_by_goal_id = list_coaching_tasks_by_goal(profile.contact_id, tenant.timezone, _goal_title_map(profile))
        payload = [
            {
                **serialize_goal_for_edit(goal, competencies_by_id),
                "steps": deepcopy(steps_by_goal_id.get(str(goal.public_id or ""), [])),
                "progress": goal_progress_for_payload(goal, steps_by_goal_id.get(str(goal.public_id or ""), [])),
            }
            for goal in goals
        ]
        return Response(payload)


class ContactGoalsView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        horizon = str(request.query_params.get("horizon") or "").strip()
        profile = _get_or_create_profile(int(tenant.id), contact_id)
        profile = (
            ContactCoachingProfile.objects
            .filter(id=profile.id)
            .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            .first()
            or profile
        )
        competencies_by_id = competencies_map(profile)
        steps_by_goal_id = list_coaching_tasks_by_goal(profile.contact_id, tenant.timezone, _goal_title_map(profile))
        goals = []
        for goal in _profile_goals(profile):
            if horizon and str(goal.horizon or "") != horizon:
                continue
            goals.append(serialize_goal_for_list(goal, competencies_by_id=competencies_by_id, contact_id=contact_id, steps_by_goal_id=steps_by_goal_id))
        return Response(goals)


class ContactStepsView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        raw_done = str(request.query_params.get("done") or "").strip().lower()
        done: bool | None = None
        if raw_done in {"1", "true", "yes"}:
            done = True
        elif raw_done in {"0", "false", "no"}:
            done = False

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        return Response(_flatten_profile_goal_steps(profile, done=done))


class ContactGoalDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, goal_id: str):
        tenant = get_active_client(request.user)
        profile, goal = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        raw_progress = request.data.get("progress")
        try:
            next_progress = int(raw_progress)
        except (TypeError, ValueError):
            return Response({"error": "Некорректный progress"}, status=status.HTTP_400_BAD_REQUEST)
        if next_progress < 0 or next_progress > 100:
            return Response({"error": "Некорректный progress"}, status=status.HTTP_400_BAD_REQUEST)

        _adjust_competencies_for_goal(profile, goal, next_progress)
        goal.progress = next_progress
        profile.save(update_fields=["competencies"])
        goal.save(update_fields=["progress", "updated_at"])
        profile = (
            ContactCoachingProfile.objects
            .filter(id=profile.id)
            .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            .first()
            or profile
        )
        goal = next((item for item in _profile_goals(profile) if item.id == goal.id), goal)
        return Response(_goal_response(profile, goal))


class ContactGoalStepsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, goal_id: str):
        tenant = get_active_client(request.user)
        profile, goal = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingGoalStepCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = create_coaching_task(
            contact_id=profile.contact_id,
            goal_id=str(goal.public_id or ""),
            title=serializer.validated_data["text"],
            due_date=serializer.validated_data.get("dueDate") or "",
            tenant_timezone=tenant.timezone,
            history_note=CREATE_HISTORY_NOTE,
        )
        return Response(
            serialize_coaching_step(task, tenant_timezone=tenant.timezone, goal_title=goal_display_title(goal)),
            status=status.HTTP_201_CREATED,
        )


class ContactGoalStepDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, goal_id: str, step_id: str):
        tenant = get_active_client(request.user)
        profile, goal = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingGoalStepUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response({"error": "Нет данных для обновления"}, status=status.HTTP_400_BAD_REQUEST)
        task = (
            coaching_task_queryset(contact_id=profile.contact_id, goal_id=goal_id)
            .filter(id=step_id)
            .first()
        )
        if task is None:
            return Response({"error": "Шаг не найден"}, status=status.HTTP_404_NOT_FOUND)
        history_note = EDIT_HISTORY_NOTE
        next_status = None
        next_done_at = task.done_at
        if "done" in serializer.validated_data:
            done = bool(serializer.validated_data["done"])
            next_status = "done" if done else "open"
            next_done_at = timezone.now() if done else None
            history_note = COACH_DONE_HISTORY_NOTE if done else COACH_REOPEN_HISTORY_NOTE
        task = update_coaching_task(
            task,
            tenant_timezone=tenant.timezone,
            changes=CoachingTaskUpdate(
                title=serializer.validated_data.get("text") if "text" in serializer.validated_data else None,
                due_date=serializer.validated_data.get("dueDate") if "dueDate" in serializer.validated_data else None,
                is_milestone=serializer.validated_data.get("isMilestone") if "isMilestone" in serializer.validated_data else None,
                milestone_note=serializer.validated_data.get("milestoneNote") if "milestoneNote" in serializer.validated_data else None,
                status=next_status,
                done_at=next_done_at if "done" in serializer.validated_data else None,
                history_note=history_note,
            ),
        )
        profile = (
            ContactCoachingProfile.objects
            .filter(id=profile.id)
            .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            .first()
            or profile
        )
        goal = next((item for item in _profile_goals(profile) if item.public_id == goal_id), goal)
        return Response(_goal_response(profile, goal))

    def delete(self, request, goal_id: str, step_id: str):
        tenant = get_active_client(request.user)
        profile, goal = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)
        task = (
            coaching_task_queryset(contact_id=profile.contact_id, goal_id=goal_id)
            .filter(id=step_id)
            .first()
        )
        if task is None:
            return Response({"error": "Шаг не найден"}, status=status.HTTP_404_NOT_FOUND)
        task.delete()
        _drop_group_goal_if_no_tasks(profile, goal_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactMilestonesView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        return Response(list_coaching_milestones(profile.contact_id))

    def post(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingMilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        task = create_coaching_milestone(
            contact_id=profile.contact_id,
            goal_id=serializer.validated_data.get("goalId") or None,
            text=serializer.validated_data["text"],
            note=serializer.validated_data.get("note") or "",
        )
        return Response(serialize_coaching_milestone(task), status=status.HTTP_201_CREATED)


class ContactTasksView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        tasks = list_coaching_task_payloads(profile.contact_id, tenant.timezone, _goal_title_map(profile))
        return Response(tasks)


class ContactTaskDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, task_id: str):
        tenant = get_active_client(request.user)
        task = _find_coaching_task(int(tenant.id), task_id)
        if task is None:
            return Response({"error": "Задание не найдено"}, status=status.HTTP_404_NOT_FOUND)

        next_status = str(request.data.get("status") or "").strip().lower()
        if next_status not in {"pending", "done", "overdue"}:
            return Response({"error": "Некорректный status"}, status=status.HTTP_400_BAD_REQUEST)
        profile = _get_or_create_profile(int(tenant.id), int(task.contact_id))
        goal_title = _goal_title_for_task(profile, str(task.goal_id or "").strip() or None)
        task = update_coaching_task(
            task,
            tenant_timezone=tenant.timezone,
            changes=CoachingTaskUpdate(
                status="done" if next_status == "done" else "open",
                done_at=timezone.now() if next_status == "done" else None,
                history_note=COACH_DONE_HISTORY_NOTE if next_status == "done" else COACH_REOPEN_HISTORY_NOTE,
            ),
        )
        return Response(serialize_coaching_task(task, tenant_timezone=tenant.timezone, goal_title=goal_title))


class ContactSessionsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        return Response(_profile_sessions(profile))

    def post(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        current_sessions = [item for item in (profile.sessions or []) if isinstance(item, dict)]
        existing_draft = next(
            (item for item in current_sessions if _session_status_value(item) == "draft"),
            None,
        )
        if existing_draft is not None:
            return Response(_serialize_session(profile, existing_draft))

        session = {
            "id": uuid4().hex,
            "clientId": contact_id,
            "number": len(current_sessions) + 1,
            "date": serializer.validated_data.get("date") or timezone.now().isoformat(),
            "notes": serializer.validated_data.get("notes") or "",
            "coachNotes": serializer.validated_data.get("coachNotes") or "",
            "status": "draft",
        }
        profile.sessions = [session, *current_sessions]
        profile.save()
        return Response(_serialize_session(profile, session), status=status.HTTP_201_CREATED)


class ContactSessionDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, session_id: str):
        tenant = get_active_client(request.user)
        serializer = CoachingSessionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not serializer.validated_data:
            return Response({"error": "Нет полей для обновления"}, status=status.HTTP_400_BAD_REQUEST)

        for profile in ContactCoachingProfile.objects.filter(tenant_id=int(tenant.id)).order_by("id"):
            sessions = list(profile.sessions or [])
            for index, session in enumerate(sessions):
                if not isinstance(session, dict) or str(session.get("id") or "") != session_id:
                    continue

                next_session = deepcopy(session)
                if "notes" in serializer.validated_data:
                    next_session["notes"] = serializer.validated_data.get("notes") or ""
                if "coachNotes" in serializer.validated_data:
                    next_session["coachNotes"] = serializer.validated_data.get("coachNotes") or ""
                if "status" in serializer.validated_data:
                    next_session["status"] = serializer.validated_data["status"]
                else:
                    next_session["status"] = _session_status_value(next_session)

                next_session["clientId"] = int(next_session.get("clientId") or profile.contact_id)
                next_session["number"] = int(next_session.get("number") or index + 1)
                next_session["date"] = str(next_session.get("date") or timezone.now().isoformat())
                sessions[index] = next_session
                profile.sessions = sessions
                profile.save(update_fields=["sessions"])
                return Response(_serialize_session(profile, next_session))

        return Response({"error": "Сессия не найдена"}, status=status.HTTP_404_NOT_FOUND)


class CoachGroupsView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request):
        tenant = get_active_client(request.user)
        groups = (
            CoachGroup.objects
            .filter(tenant=tenant)
            .annotate(member_count=Count("members"))
            .order_by("created_at", "id")
        )
        return Response([_serialize_group(group) for group in groups])

    def post(self, request):
        tenant = get_active_client(request.user)
        serializer = CoachGroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = CoachGroup.objects.create(
            tenant=tenant,
            name=serializer.validated_data["name"].strip(),
        )
        return Response(_serialize_group(group, member_count=0), status=status.HTTP_201_CREATED)


class CoachGroupDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return [IsTenantOwnerOrEditor()]

    def get(self, request, group_id: int):
        tenant = get_active_client(request.user)
        group = (
            CoachGroup.objects
            .filter(id=group_id, tenant=tenant)
            .annotate(member_count=Count("members"))
            .prefetch_related("members", "tasks")
            .first()
        )
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        members = list(group.members.order_by("created_at", "id"))
        contact_ids = [member.contact_id for member in members]
        contacts = {
            int(contact.id): contact
            for contact in MapContact.objects.filter(id__in=contact_ids)
        }
        profiles = {
            profile.contact_id: profile
            for profile in (
                ContactCoachingProfile.objects
                .filter(tenant=tenant, contact_id__in=contact_ids)
                .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            )
        }
        done_index = _build_group_step_done_index(int(group.id), [int(member.contact_id) for member in members])

        payload_members = []
        for member in members:
            contact = contacts.get(int(member.contact_id))
            if contact is None:
                continue
            payload_members.append(_serialize_group_member(contact, profiles.get(int(member.contact_id))))

        payload_tasks = [
            _serialize_group_task(task, done_index)
            for task in group.tasks.order_by("created_at", "id")
        ]

        return Response(
            {
                "group": _serialize_group(group),
                "members": payload_members,
                "tasks": payload_tasks,
            }
        )

    def delete(self, request, group_id: int):
        tenant = get_active_client(request.user)
        group = CoachGroup.objects.filter(id=group_id, tenant=tenant).first()
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            tasks = list(group.tasks.select_related("group").all())
            for task in tasks:
                _delete_group_task_steps(task)
            group.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachGroupMembersView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, group_id: int):
        tenant = get_active_client(request.user)
        group = CoachGroup.objects.filter(id=group_id, tenant=tenant).first()
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachGroupMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        contact_id = int(serializer.validated_data["clientId"])
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        _, created = CoachGroupMember.objects.get_or_create(group=group, contact_id=contact_id)
        if not created:
            return Response({"error": "Контакт уже в группе"}, status=status.HTTP_400_BAD_REQUEST)

        profile = _get_profile(int(tenant.id), contact_id)
        return Response(_serialize_group_member(contact, profile), status=status.HTTP_201_CREATED)


class CoachGroupMembersBulkView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, group_id: int):
        tenant = get_active_client(request.user)
        group = CoachGroup.objects.filter(id=group_id, tenant=tenant).first()
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachGroupMembersBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requested_ids = [int(contact_id) for contact_id in serializer.validated_data["clientIds"]]
        contact_ids = list(dict.fromkeys(requested_ids))
        contacts = {
            int(contact.id): contact
            for contact in (
                MapContact.objects
                .filter(id__in=contact_ids)
                .filter(id__in=_tenant_contact_ids_queryset(int(tenant.id)))
            )
        }
        if len(contacts) != len(contact_ids):
            return Response({"error": "Часть контактов не найдена"}, status=status.HTTP_404_NOT_FOUND)

        existing_ids = set(
            group.members
            .filter(contact_id__in=contact_ids)
            .values_list("contact_id", flat=True)
        )
        create_ids = [contact_id for contact_id in contact_ids if contact_id not in existing_ids]
        if not create_ids:
            return Response([])

        CoachGroupMember.objects.bulk_create(
            [CoachGroupMember(group=group, contact_id=contact_id) for contact_id in create_ids],
            ignore_conflicts=True,
        )
        profiles = {
            profile.contact_id: profile
            for profile in (
                ContactCoachingProfile.objects
                .filter(tenant=tenant, contact_id__in=create_ids)
                .prefetch_related("goal_rows__competency_links", "goal_rows__group")
            )
        }

        payload = [
            _serialize_group_member(contacts[contact_id], profiles.get(contact_id))
            for contact_id in create_ids
        ]
        return Response(payload, status=status.HTTP_201_CREATED)


class CoachGroupMemberDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def delete(self, request, group_id: int, client_id: int):
        tenant = get_active_client(request.user)
        group = CoachGroup.objects.filter(id=group_id, tenant=tenant).first()
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        member = group.members.filter(contact_id=client_id).first()
        if member is None:
            return Response({"error": "Участник не найден"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            tasks_queryset = group.tasks.select_related("group")
            try:
                tasks = list(tasks_queryset.filter(step_refs__contains=[{"contactId": client_id}]))
            except NotSupportedError:
                tasks = list(tasks_queryset.all())

            changed_tasks: list[CoachGroupTask] = []
            now = timezone.now()
            for task in tasks:
                next_refs = []
                changed = False
                removed_task_ids: list[int] = []
                for ref in _group_task_refs(task):
                    try:
                        ref_contact_id = int(ref.get("contactId"))
                    except (TypeError, ValueError):
                        next_refs.append(ref)
                        continue
                    if ref_contact_id == client_id:
                        task_id = str(ref.get("taskId") or "")
                        if task_id.isdigit():
                            removed_task_ids.append(int(task_id))
                        changed = True
                    else:
                        next_refs.append(ref)

                if changed:
                    if removed_task_ids:
                        CRMTask.objects.filter(
                            id__in=removed_task_ids,
                            source=COACHING_TASK_SOURCE,
                            contact_id=client_id,
                        ).delete()
                    task.step_refs = next_refs
                    task.updated_at = now
                    changed_tasks.append(task)

            if changed_tasks:
                CoachGroupTask.objects.bulk_update(changed_tasks, ["step_refs", "updated_at"])

            profile = _get_profile(int(tenant.id), client_id)
            _drop_group_goal_if_no_tasks(profile, group_goal_id(int(group.id)))

            member.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachGroupTasksView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, group_id: int):
        tenant = get_active_client(request.user)
        group = CoachGroup.objects.filter(id=group_id, tenant=tenant).first()
        if group is None:
            return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachGroupTaskCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        members = list(group.members.order_by("created_at", "id"))
        if not members:
            return Response({"error": "В группе нет участников"}, status=status.HTTP_400_BAD_REQUEST)

        due_date = serializer.validated_data.get("dueDate")
        due_date_value = due_date.isoformat() if due_date else ""
        step_refs: list[dict] = []

        with transaction.atomic():
            for member in members:
                profile = _get_or_create_profile(int(tenant.id), int(member.contact_id))
                goal = _ensure_group_goal(profile, group)
                created_task = create_coaching_task(
                    contact_id=int(member.contact_id),
                    goal_id=str(goal.public_id or ""),
                    title=serializer.validated_data["text"].strip(),
                    due_date=due_date_value,
                    tenant_timezone=tenant.timezone,
                    history_note=CREATE_HISTORY_NOTE,
                )
                step_refs.append(
                    {
                        "contactId": int(member.contact_id),
                        "goalId": str(goal.public_id or ""),
                        "taskId": str(created_task.id),
                    }
                )

            task = CoachGroupTask.objects.create(
                group=group,
                text=serializer.validated_data["text"].strip(),
                due_date=due_date,
                step_refs=step_refs,
            )

        done_index = _build_group_step_done_index(int(group.id), [int(member.contact_id) for member in members])
        return Response(_serialize_group_task(task, done_index), status=status.HTTP_201_CREATED)


class CoachGroupTaskDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def delete(self, request, group_id: int, task_id: int):
        tenant = get_active_client(request.user)
        task = (
            CoachGroupTask.objects
            .select_related("group")
            .filter(id=task_id, group_id=group_id, group__tenant=tenant)
            .first()
        )
        if task is None:
            return Response({"error": "Задание не найдено"}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            _delete_group_task_steps(task)
            task.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachingContactInviteView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        invite = (
            InviteLink.objects
            .filter(tenant=tenant, contact_id=int(contact.id), used_at__isnull=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            .order_by("-created_at", "-id")
            .first()
        )
        if invite is None:
            InviteLink.objects.filter(
                tenant=tenant,
                contact_id=int(contact.id),
                used_at__isnull=True,
            ).filter(expires_at__isnull=False, expires_at__lte=now).delete()
            invite = InviteLink.objects.create(
                tenant=tenant,
                contact_id=int(contact.id),
            )

        return Response(_serialize_invite_link(invite, request), status=status.HTTP_200_OK)

    def delete(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        InviteLink.objects.filter(
            tenant=tenant,
            contact_id=int(contact.id),
            used_at__isnull=True,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CoachingOnboardingView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        tenant = get_active_client(request.user)
        serializer = CoachingOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_contact_id = serializer.validated_data.get("clientId") or ""
        try:
            contact_id = int(raw_contact_id)
        except (TypeError, ValueError):
            return Response({"error": "Некорректный clientId"}, status=status.HTTP_400_BAD_REQUEST)

        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        profile.intention = serializer.validated_data.get("intention") or ""
        profile.wheel = serializer.validated_data.get("wheel") or []
        profile.save()
        return Response({"ok": True})
