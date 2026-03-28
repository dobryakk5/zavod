from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta
from uuid import uuid4

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ContactCoachingProfile, MapContact, UserTenantBinding

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .serializers_coaching import (
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


def _competencies_map(profile: ContactCoachingProfile) -> dict[str, dict]:
    competencies = profile.competencies if isinstance(profile.competencies, list) else []
    return {
        str(item.get("id") or ""): item
        for item in competencies
        if isinstance(item, dict) and item.get("id")
    }


def _goal_focus(profile: ContactCoachingProfile) -> str:
    goals = profile.goals if isinstance(profile.goals, list) else []
    active_goal = next((goal for goal in goals if isinstance(goal, dict) and goal.get("status") == "active" and goal.get("title")), None)
    if active_goal:
        return str(active_goal.get("title") or "")
    first_goal = next((goal for goal in goals if isinstance(goal, dict) and goal.get("title")), None)
    if first_goal:
        return str(first_goal.get("title") or "")
    competencies = profile.competencies if isinstance(profile.competencies, list) else []
    first_comp = next((comp for comp in competencies if isinstance(comp, dict) and comp.get("name")), None)
    if not isinstance(first_comp, dict):
        return ""
    return str(first_comp.get("name") or "")


def _profile_avg_progress(profile: ContactCoachingProfile) -> int:
    goals = [goal for goal in (profile.goals or []) if isinstance(goal, dict)]
    if not goals:
        return 0
    total = sum(int(goal.get("progress") or 0) for goal in goals)
    return round(total / len(goals))


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
    since = today - timedelta(days=29)
    completed = 0
    for goal in profile.goals or []:
        if not isinstance(goal, dict):
            continue
        for step in goal.get("steps") or []:
            if not isinstance(step, dict) or not step.get("done"):
                continue
            done_at = _parse_moment(str(step.get("doneAt") or ""))
            if done_at is None:
                continue
            done_day = timezone.localdate(done_at)
            if since <= done_day <= today:
                completed += 1
    return completed


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
    for task in _profile_items(profile, "tasks"):
        task_status = str(task.get("status") or "").strip().lower()
        if task_status == "done":
            continue
        if task_status == "overdue":
            return True

        due_moment = _parse_moment(str(task.get("dueDate") or ""))
        if due_moment is not None and due_moment < now:
            return True
    for goal in _profile_items(profile, "goals"):
        for step in goal.get("steps") or []:
            if not isinstance(step, dict) or step.get("done"):
                continue
            due_moment = _parse_moment(str(step.get("dueDate") or ""))
            if due_moment is not None and due_moment < now:
                return True
    return False


def _profile_has_recent_milestone(profile: ContactCoachingProfile, now: datetime) -> bool:
    week_ago = now - timedelta(days=7)
    for milestone in _profile_items(profile, "milestones"):
        created_at = _parse_moment(str(milestone.get("createdAt") or ""))
        if created_at is not None and created_at >= week_ago:
            return True
    return False


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


def _serialize_goal_for_edit(goal: dict, competencies_by_id: dict[str, dict]) -> dict:
    links = []
    for link in goal.get("competencyLinks") or []:
        if not isinstance(link, dict):
            continue
        competency_id = str(link.get("competencyId") or "")
        competency = competencies_by_id.get(competency_id, {})
        links.append(
            {
                "competencyId": competency_id,
                "competencyName": str(competency.get("name") or link.get("competencyName") or ""),
                "weight": round(float(link.get("weight") or 0) * 100),
            }
        )
    return {
        "id": str(goal.get("id") or ""),
        "title": str(goal.get("title") or ""),
        "progress": int(goal.get("progress") or 0),
        "horizon": str(goal.get("horizon") or "quarter"),
        "status": str(goal.get("status") or "active"),
        "competencyLinks": links,
        "steps": deepcopy(goal.get("steps") or []),
        "createdAt": str(goal.get("createdAt") or timezone.now().isoformat()),
    }


def _serialize_goal_for_list(goal: dict, competencies_by_id: dict[str, dict], contact_id: int) -> dict:
    links = []
    for link in goal.get("competencyLinks") or []:
        if not isinstance(link, dict):
            continue
        competency = competencies_by_id.get(str(link.get("competencyId") or ""), {})
        links.append(
            {
                "name": str(competency.get("name") or link.get("competencyName") or ""),
                "weight": float(link.get("weight") or 0),
            }
        )
    return {
        "id": str(goal.get("id") or ""),
        "clientId": str(contact_id),
        "title": str(goal.get("title") or ""),
        "progress": int(goal.get("progress") or 0),
        "horizon": str(goal.get("horizon") or "quarter"),
        "status": str(goal.get("status") or "active"),
        "competencies": links,
        "steps": deepcopy(goal.get("steps") or []),
        "createdAt": str(goal.get("createdAt") or timezone.now().isoformat()),
    }


def _serialize_goal_step(profile: ContactCoachingProfile, goal: dict, step: dict) -> dict:
    return {
        "id": str(step.get("id") or ""),
        "text": str(step.get("text") or ""),
        "done": bool(step.get("done")),
        "isMilestone": bool(step.get("isMilestone")),
        "milestoneNote": str(step.get("milestoneNote") or ""),
        "doneAt": str(step.get("doneAt") or "").strip() or None,
        "dueDate": str(step.get("dueDate") or "").strip() or None,
        "goalId": str(goal.get("id") or ""),
        "goalTitle": str(step.get("goalTitle") or goal.get("title") or ""),
        "clientId": int(profile.contact_id),
    }


def _goal_step_sort_key(step: dict) -> tuple[int, str, str]:
    due_date = str(step.get("dueDate") or "")
    done_at = str(step.get("doneAt") or "")
    return (1 if step.get("done") else 0, due_date or "9999", done_at or "9999")


def _flatten_profile_goal_steps(profile: ContactCoachingProfile, *, done: bool | None = None) -> list[dict]:
    flattened: list[dict] = []
    for goal in profile.goals or []:
        if not isinstance(goal, dict):
            continue
        for step in goal.get("steps") or []:
            if not isinstance(step, dict):
                continue
            payload = _serialize_goal_step(profile, goal, step)
            if done is not None and bool(payload["done"]) is not done:
                continue
            flattened.append(payload)
    flattened.sort(key=_goal_step_sort_key)
    return flattened


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
                "id": uuid4().hex,
                "clientId": contact_id,
                "goalId": "",
                "text": f"Рост компетенции {name} на {growth}%",
                "note": "",
                "createdAt": created_at,
            }
        )
    return milestones


def _normalize_goals_for_storage(validated_goals: list[dict], existing_goals: list[dict]) -> list[dict]:
    existing_by_id = {
        str(goal.get("id") or ""): goal
        for goal in existing_goals
        if isinstance(goal, dict) and goal.get("id")
    }
    normalized = []
    for position, goal in enumerate(validated_goals):
        goal_id = str(goal["id"])
        previous = existing_by_id.get(goal_id, {})
        links = []
        for link in goal.get("competencyLinks") or []:
            links.append(
                {
                    "competencyId": str(link["competencyId"]),
                    "competencyName": str(link.get("competencyName") or ""),
                    "weight": round(float(link["weight"]), 4),
                }
            )
        steps = deepcopy(goal.get("steps") or previous.get("steps") or [])
        created_at = str(goal.get("createdAt") or previous.get("createdAt") or timezone.now().isoformat())
        normalized.append(
            {
                "id": goal_id,
                "title": goal["title"],
                "progress": int(goal["progress"]),
                "horizon": goal["horizon"],
                "status": goal["status"],
                "sortOrder": position,
                "competencyLinks": links,
                "steps": steps,
                "createdAt": created_at,
            }
        )
    return normalized


def _find_profile_goal(tenant_id: int, goal_id: str) -> tuple[ContactCoachingProfile, int] | tuple[None, None]:
    for profile in ContactCoachingProfile.objects.filter(tenant_id=tenant_id).order_by("id"):
        goals = profile.goals if isinstance(profile.goals, list) else []
        for index, goal in enumerate(goals):
            if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
                return profile, index
    return None, None


def _goal_response(profile: ContactCoachingProfile, goal_index: int) -> dict:
    competencies_by_id = _competencies_map(profile)
    goal = (profile.goals or [])[goal_index]
    return _serialize_goal_for_list(goal, competencies_by_id, profile.contact_id)


def _goal_title_for_task(profile: ContactCoachingProfile, goal_id: str | None) -> str:
    if not goal_id:
        return ""
    for goal in profile.goals or []:
        if isinstance(goal, dict) and str(goal.get("id") or "") == str(goal_id):
            return str(goal.get("title") or "")
    return ""


def _serialize_task(profile: ContactCoachingProfile, task: dict) -> dict:
    task_id = str(task.get("id") or "")
    goal_id = str(task.get("goalId") or "").strip() or None
    due_date = str(task.get("dueDate") or "").strip() or None
    done_at = str(task.get("doneAt") or "").strip() or None
    created_at = str(task.get("createdAt") or timezone.now().isoformat())
    status_value = str(task.get("status") or "pending").strip().lower()
    if status_value not in {"pending", "done", "overdue"}:
        status_value = "pending"

    if status_value != "done" and due_date:
        due_moment = _parse_moment(due_date)
        if due_moment is not None and due_moment < timezone.now():
            status_value = "overdue"

    return {
        "id": task_id,
        "clientId": int(task.get("clientId") or profile.contact_id),
        "goalId": goal_id,
        "goalTitle": str(task.get("goalTitle") or _goal_title_for_task(profile, goal_id)),
        "sessionId": str(task.get("sessionId") or "").strip() or None,
        "text": str(task.get("text") or ""),
        "status": status_value,
        "dueDate": due_date,
        "doneAt": done_at,
        "createdAt": created_at,
    }


def _task_sort_key(task: dict) -> tuple[int, str, str]:
    status = str(task.get("status") or "pending")
    due_date = str(task.get("dueDate") or "")
    created_at = str(task.get("createdAt") or "")
    return (1 if status == "done" else 0, due_date or "9999", created_at)


def _find_profile_task(tenant_id: int, task_id: str) -> tuple[ContactCoachingProfile, int] | tuple[None, None]:
    for profile in ContactCoachingProfile.objects.filter(tenant_id=tenant_id).order_by("id"):
        tasks = profile.tasks if isinstance(profile.tasks, list) else []
        for index, task in enumerate(tasks):
            if isinstance(task, dict) and str(task.get("id") or "") == task_id:
                return profile, index
    return None, None


def _adjust_competencies_for_goal(profile: ContactCoachingProfile, goal: dict, next_progress: int) -> None:
    previous_progress = int(goal.get("progress") or 0)
    delta = next_progress - previous_progress
    if delta == 0:
        return

    competencies = []
    for competency in profile.competencies or []:
        if not isinstance(competency, dict):
            continue
        link = next(
            (
                item for item in goal.get("competencyLinks") or []
                if isinstance(item, dict) and str(item.get("competencyId") or "") == str(competency.get("id") or "")
            ),
            None,
        )
        if link is None:
            competencies.append(competency)
            continue

        next_score = round(float(competency.get("score") or 0) + (delta * float(link.get("weight") or 0)))
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
            for profile in ContactCoachingProfile.objects.filter(tenant=tenant, contact_id__in=contact_ids)
        }

        all_goals = []
        today = timezone.localdate()
        sessions_today = 0
        completed_tasks = 0
        for profile in profiles.values():
            for goal in profile.goals or []:
                if isinstance(goal, dict):
                    all_goals.append(int(goal.get("progress") or 0))
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
            for profile in ContactCoachingProfile.objects.filter(tenant=tenant, contact_id__in=[int(contact.id) for contact in contacts])
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
        profile.competencies = next_competencies
        if new_milestones:
            existing_milestones = [item for item in (profile.milestones or []) if isinstance(item, dict)]
            profile.milestones = [*new_milestones, *existing_milestones]
        profile.save()
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

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        competencies_by_id = _competencies_map(profile)
        payload = [
            _serialize_goal_for_edit(goal, competencies_by_id)
            for goal in (profile.goals or [])
            if isinstance(goal, dict)
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
        existing_goals = profile.goals if isinstance(profile.goals, list) else []
        profile.goals = _normalize_goals_for_storage(serializer.validated_data, existing_goals)
        profile.save()

        competencies_by_id = _competencies_map(profile)
        payload = [_serialize_goal_for_edit(goal, competencies_by_id) for goal in profile.goals]
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
        competencies_by_id = _competencies_map(profile)
        goals = []
        for goal in profile.goals or []:
            if not isinstance(goal, dict):
                continue
            if horizon and str(goal.get("horizon") or "") != horizon:
                continue
            goals.append(_serialize_goal_for_list(goal, competencies_by_id, contact_id))
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
        profile, goal_index = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal_index is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        raw_progress = request.data.get("progress")
        try:
            next_progress = int(raw_progress)
        except (TypeError, ValueError):
            return Response({"error": "Некорректный progress"}, status=status.HTTP_400_BAD_REQUEST)
        if next_progress < 0 or next_progress > 100:
            return Response({"error": "Некорректный progress"}, status=status.HTTP_400_BAD_REQUEST)

        goals = list(profile.goals or [])
        goal = deepcopy(goals[goal_index])
        _adjust_competencies_for_goal(profile, goal, next_progress)
        goal["progress"] = next_progress
        goals[goal_index] = goal
        profile.goals = goals
        profile.save()
        return Response(_goal_response(profile, goal_index))


class ContactGoalStepsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request, goal_id: str):
        tenant = get_active_client(request.user)
        profile, goal_index = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal_index is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingGoalStepCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        goals = list(profile.goals or [])
        goal = deepcopy(goals[goal_index])
        steps = [step for step in (goal.get("steps") or []) if isinstance(step, dict)]
        step = {
            "id": uuid4().hex,
            "text": serializer.validated_data["text"],
            "done": False,
            "isMilestone": False,
            "milestoneNote": "",
            "doneAt": "",
            "dueDate": serializer.validated_data.get("dueDate") or "",
            "goalId": str(goal.get("id") or ""),
            "goalTitle": str(goal.get("title") or ""),
        }
        goal["steps"] = [*steps, step]
        goals[goal_index] = goal
        profile.goals = goals
        profile.save()
        return Response(_serialize_goal_step(profile, goal, step), status=status.HTTP_201_CREATED)


class ContactGoalStepDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, goal_id: str, step_id: str):
        tenant = get_active_client(request.user)
        profile, goal_index = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal_index is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingGoalStepUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response({"error": "Нет данных для обновления"}, status=status.HTTP_400_BAD_REQUEST)

        goals = list(profile.goals or [])
        goal = deepcopy(goals[goal_index])
        steps = list(goal.get("steps") or [])
        step_found = False
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            if str(step.get("id") or "") != step_id:
                continue
            next_step = {**step}
            if "text" in serializer.validated_data:
                next_step["text"] = serializer.validated_data["text"]
            if "dueDate" in serializer.validated_data:
                next_step["dueDate"] = serializer.validated_data["dueDate"]
            if "isMilestone" in serializer.validated_data:
                next_step["isMilestone"] = bool(serializer.validated_data["isMilestone"])
            if "done" in serializer.validated_data:
                done = bool(serializer.validated_data["done"])
                next_step["done"] = done
                next_step["doneAt"] = timezone.now().isoformat() if done else ""
            steps[index] = next_step
            step_found = True
            break
        if not step_found:
            return Response({"error": "Шаг не найден"}, status=status.HTTP_404_NOT_FOUND)

        goal["steps"] = steps
        goals[goal_index] = goal
        profile.goals = goals
        profile.save()
        return Response(_goal_response(profile, goal_index))

    def delete(self, request, goal_id: str, step_id: str):
        tenant = get_active_client(request.user)
        profile, goal_index = _find_profile_goal(int(tenant.id), goal_id)
        if profile is None or goal_index is None:
            return Response({"error": "Цель не найдена"}, status=status.HTTP_404_NOT_FOUND)

        goals = list(profile.goals or [])
        goal = deepcopy(goals[goal_index])
        previous_count = len(goal.get("steps") or [])
        goal["steps"] = [
            step
            for step in (goal.get("steps") or [])
            if isinstance(step, dict) and str(step.get("id") or "") != step_id
        ]
        if len(goal["steps"]) == previous_count:
            return Response({"error": "Шаг не найден"}, status=status.HTTP_404_NOT_FOUND)

        goals[goal_index] = goal
        profile.goals = goals
        profile.save()
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
        milestones = [item for item in (profile.milestones or []) if isinstance(item, dict)]
        milestones.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
        return Response(milestones)

    def post(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CoachingMilestoneCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        milestone = {
            "id": uuid4().hex,
            "clientId": contact_id,
            "goalId": serializer.validated_data.get("goalId") or "",
            "text": serializer.validated_data["text"],
            "note": serializer.validated_data.get("note") or "",
            "createdAt": timezone.now().isoformat(),
        }
        profile.milestones = [milestone, *[item for item in (profile.milestones or []) if isinstance(item, dict)]]
        profile.save()
        return Response(milestone, status=status.HTTP_201_CREATED)


class ContactTasksView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        tenant = get_active_client(request.user)
        contact = _tenant_contact_or_none(int(tenant.id), contact_id)
        if contact is None:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        profile = _get_or_create_profile(int(tenant.id), contact_id)
        tasks = [_serialize_task(profile, task) for task in (profile.tasks or []) if isinstance(task, dict)]
        tasks.sort(key=_task_sort_key)
        return Response(tasks)


class ContactTaskDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, task_id: str):
        tenant = get_active_client(request.user)
        profile, task_index = _find_profile_task(int(tenant.id), task_id)
        if profile is None or task_index is None:
            return Response({"error": "Задание не найдено"}, status=status.HTTP_404_NOT_FOUND)

        next_status = str(request.data.get("status") or "").strip().lower()
        if next_status not in {"pending", "done", "overdue"}:
            return Response({"error": "Некорректный status"}, status=status.HTTP_400_BAD_REQUEST)

        tasks = list(profile.tasks or [])
        task = deepcopy(tasks[task_index])
        task["status"] = next_status
        task["doneAt"] = timezone.now().isoformat() if next_status == "done" else ""
        task["clientId"] = int(task.get("clientId") or profile.contact_id)
        task["createdAt"] = str(task.get("createdAt") or timezone.now().isoformat())
        tasks[task_index] = task
        profile.tasks = tasks
        profile.save()
        return Response(_serialize_task(profile, task))


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
