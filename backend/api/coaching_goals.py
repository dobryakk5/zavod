from __future__ import annotations

from django.utils import timezone

from core.models import CoachingGoal, ContactCoachingProfile


GROUP_GOAL_ID_PREFIX = "group-"


def group_goal_id(group_id: int) -> str:
    return f"{GROUP_GOAL_ID_PREFIX}{group_id}"


def is_group_goal_public_id(public_id: str | None) -> bool:
    return str(public_id or "").startswith(GROUP_GOAL_ID_PREFIX)


def group_goal_title(group_name: str | None) -> str:
    name = str(group_name or "").strip()
    return f"Группа: {name}" if name else "Группа"


def goal_display_title(goal: CoachingGoal) -> str:
    if goal.goal_type == CoachingGoal.TYPE_GROUP:
        return group_goal_title(goal.group.name if goal.group_id and goal.group else goal.title)
    return str(goal.title or "")


def profile_goal_rows(profile: ContactCoachingProfile) -> list[CoachingGoal]:
    if not getattr(profile, "pk", None):
        return []
    return list(profile.goal_rows.all())


def competencies_map(profile: ContactCoachingProfile) -> dict[str, dict]:
    competencies = profile.competencies if isinstance(profile.competencies, list) else []
    return {
        str(item.get("id") or ""): item
        for item in competencies
        if isinstance(item, dict) and item.get("id")
    }


def goal_title_map(goals: list[CoachingGoal]) -> dict[str, str]:
    return {
        str(goal.public_id): goal_display_title(goal)
        for goal in goals
        if str(goal.public_id or "").strip()
    }


def goal_focus(goals: list[CoachingGoal], competencies: list[dict] | None) -> str:
    active_goal = next((goal for goal in goals if goal.status == CoachingGoal.STATUS_ACTIVE and goal_display_title(goal)), None)
    if active_goal is not None:
        return goal_display_title(active_goal)

    first_goal = next((goal for goal in goals if goal_display_title(goal)), None)
    if first_goal is not None:
        return goal_display_title(first_goal)

    items = competencies if isinstance(competencies, list) else []
    first_comp = next((comp for comp in items if isinstance(comp, dict) and comp.get("name")), None)
    if not isinstance(first_comp, dict):
        return ""
    return str(first_comp.get("name") or "")


def average_progress(goals: list[CoachingGoal]) -> int:
    if not goals:
        return 0
    return round(sum(int(goal.progress or 0) for goal in goals) / len(goals))


def goal_progress_for_payload(goal: CoachingGoal, steps: list[dict]) -> int:
    if goal.goal_type != CoachingGoal.TYPE_GROUP:
        return int(goal.progress or 0)
    if not steps:
        return 0
    done_count = sum(1 for step in steps if step.get("done"))
    return round((done_count / len(steps)) * 100)


def serialize_goal_for_edit(goal: CoachingGoal, competencies_by_id: dict[str, dict]) -> dict:
    links = []
    for index, link in enumerate(goal.competency_links.all()):
        competency_id = str(link.competency_id or "")
        competency = competencies_by_id.get(competency_id, {})
        links.append(
            {
                "competencyId": competency_id,
                "competencyName": str(competency.get("name") or link.competency_name or ""),
                "weight": round(float(link.weight or 0) * 100),
            }
        )
    return {
        "id": str(goal.public_id or ""),
        "title": goal_display_title(goal),
        "progress": int(goal.progress or 0),
        "horizon": str(goal.horizon or CoachingGoal.HORIZON_QUARTER),
        "status": str(goal.status or CoachingGoal.STATUS_ACTIVE),
        "competencyLinks": links,
        "steps": [],
        "createdAt": goal.created_at.isoformat() if goal.created_at else timezone.now().isoformat(),
    }


def serialize_goal_for_list(
    goal: CoachingGoal,
    contact_id: int,
    competencies_by_id: dict[str, dict],
    steps_by_goal_id: dict[str, list[dict]],
) -> dict:
    links = []
    for link in goal.competency_links.all():
        competency_id = str(link.competency_id or "")
        competency = competencies_by_id.get(competency_id, {})
        links.append(
            {
                "name": str(competency.get("name") or link.competency_name or ""),
                "weight": float(link.weight or 0),
            }
        )

    steps = list(steps_by_goal_id.get(str(goal.public_id or ""), []))
    return {
        "id": str(goal.public_id or ""),
        "clientId": str(contact_id),
        "title": goal_display_title(goal),
        "progress": goal_progress_for_payload(goal, steps),
        "horizon": str(goal.horizon or CoachingGoal.HORIZON_QUARTER),
        "status": str(goal.status or CoachingGoal.STATUS_ACTIVE),
        "competencies": links,
        "steps": steps,
        "createdAt": goal.created_at.isoformat() if goal.created_at else timezone.now().isoformat(),
    }


def serialize_public_goal(
    goal: CoachingGoal,
    profile: ContactCoachingProfile,
    competencies_by_id: dict[str, dict],
    steps_by_goal_id: dict[str, list[dict]],
) -> dict:
    links = []
    for link in goal.competency_links.all():
        competency_id = str(link.competency_id or "")
        competency = competencies_by_id.get(competency_id, {})
        links.append(
            {
                "competencyId": competency_id,
                "competencyName": str(competency.get("name") or link.competency_name or ""),
                "weight": float(link.weight or 0),
            }
        )

    steps = list(steps_by_goal_id.get(str(goal.public_id or ""), []))
    return {
        "id": str(goal.public_id or ""),
        "clientId": int(profile.contact_id),
        "title": goal_display_title(goal),
        "progress": goal_progress_for_payload(goal, steps),
        "horizon": str(goal.horizon or CoachingGoal.HORIZON_QUARTER),
        "status": str(goal.status or CoachingGoal.STATUS_ACTIVE),
        "competencyLinks": links,
        "steps": steps,
        "createdAt": goal.created_at.isoformat() if goal.created_at else timezone.now().isoformat(),
    }
