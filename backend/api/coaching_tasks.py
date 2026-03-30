from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from core.models import CRMTask, CRMTaskHistory


COACHING_TASK_SOURCE = "coaching"
OPERATOR_TASK_SOURCE = "operator"
COACHING_DONE_STATUSES = {"done", "checked"}
COACHING_OPEN_STATUSES = {"open", "in_progress"}
COACHING_PENDING_STATUS = "pending"
COACHING_OVERDUE_STATUS = "overdue"

CREATE_HISTORY_NOTE = "Создано коучем"
EDIT_HISTORY_NOTE = "Обновлено коучем"
COACH_DONE_HISTORY_NOTE = "Коуч отметил задачу выполненной"
COACH_REOPEN_HISTORY_NOTE = "Коуч вернул задачу в работу"
CLIENT_EDIT_HISTORY_NOTE = "Клиент обновил задачу"
CLIENT_DONE_HISTORY_NOTE = "Клиент отметил задачу выполненной"
CLIENT_REOPEN_HISTORY_NOTE = "Клиент вернул задачу в работу"


@dataclass(frozen=True)
class CoachingTaskUpdate:
    title: str | None = None
    due_date: str | None = None
    is_milestone: bool | None = None
    milestone_note: str | None = None
    status: str | None = None
    done_at: datetime | None = None
    history_note: str | None = None


def _tenant_zoneinfo(timezone_name: str | None) -> ZoneInfo:
    raw = str(timezone_name or "").strip()
    if raw:
        try:
            return ZoneInfo(raw)
        except ZoneInfoNotFoundError:
            pass
    return ZoneInfo("UTC")


def coaching_due_date_to_datetime(value: str | None, tenant_timezone: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    tenant_zone = _tenant_zoneinfo(tenant_timezone)
    return datetime.combine(parsed, time(hour=12, minute=0), tzinfo=tenant_zone)


def crm_due_at_to_coaching_due_date(value: datetime | None, tenant_timezone: str | None) -> str | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        aware = timezone.make_aware(value, timezone.get_current_timezone())
    else:
        aware = value
    tenant_zone = _tenant_zoneinfo(tenant_timezone)
    return aware.astimezone(tenant_zone).date().isoformat()


def coaching_task_done(task: CRMTask) -> bool:
    return str(task.status or "").strip().lower() in COACHING_DONE_STATUSES


def coaching_task_status(task: CRMTask, tenant_timezone: str | None, *, now: datetime | None = None) -> str:
    if coaching_task_done(task):
        return "done"
    due_date = crm_due_at_to_coaching_due_date(task.due_at, tenant_timezone)
    if due_date:
        today = timezone.localdate(now or timezone.now(), _tenant_zoneinfo(tenant_timezone))
        try:
            parsed_due = date.fromisoformat(due_date)
        except ValueError:
            parsed_due = None
        if parsed_due is not None and parsed_due < today:
            return COACHING_OVERDUE_STATUS
    return COACHING_PENDING_STATUS


def coaching_task_queryset(*, contact_id: int | None = None, goal_id: str | None = None):
    queryset = CRMTask.objects.filter(source=COACHING_TASK_SOURCE)
    if contact_id is not None:
        queryset = queryset.filter(contact_id=contact_id)
    if goal_id is not None:
        queryset = queryset.filter(goal_id=goal_id)
    return queryset


def serialize_coaching_step(task: CRMTask, *, tenant_timezone: str | None, goal_title: str = "") -> dict:
    return {
        "id": str(task.id),
        "text": str(task.title or ""),
        "done": coaching_task_done(task),
        "isMilestone": bool(task.is_milestone),
        "milestoneNote": str(task.milestone_note or ""),
        "doneAt": task.done_at.isoformat() if task.done_at else None,
        "dueDate": crm_due_at_to_coaching_due_date(task.due_at, tenant_timezone),
        "goalId": str(task.goal_id or ""),
        "goalTitle": goal_title,
        "clientId": int(task.contact_id or 0),
    }


def serialize_coaching_task(task: CRMTask, *, tenant_timezone: str | None, goal_title: str = "") -> dict:
    return {
        "id": str(task.id),
        "clientId": int(task.contact_id or 0),
        "goalId": str(task.goal_id or "").strip() or None,
        "goalTitle": goal_title,
        "sessionId": None,
        "text": str(task.title or ""),
        "status": coaching_task_status(task, tenant_timezone),
        "dueDate": crm_due_at_to_coaching_due_date(task.due_at, tenant_timezone),
        "doneAt": task.done_at.isoformat() if task.done_at else None,
        "createdAt": task.created_at.isoformat() if task.created_at else timezone.now().isoformat(),
    }


def coaching_milestone_created_at(task: CRMTask) -> datetime:
    return task.done_at or task.updated_at or task.created_at or timezone.now()


def serialize_coaching_milestone(task: CRMTask) -> dict:
    created_at = coaching_milestone_created_at(task)
    return {
        "id": str(task.id),
        "clientId": int(task.contact_id or 0),
        "goalId": str(task.goal_id or ""),
        "text": str(task.title or ""),
        "note": str(task.milestone_note or ""),
        "createdAt": created_at.isoformat(),
    }


def list_coaching_tasks_by_goal(
    contact_id: int,
    tenant_timezone: str | None,
    goal_titles_by_id: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    titles = goal_titles_by_id or {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for task in coaching_task_queryset(contact_id=contact_id).order_by("created_at", "id"):
        goal_id = str(task.goal_id or "")
        grouped[goal_id].append(
            serialize_coaching_step(
                task,
                tenant_timezone=tenant_timezone,
                goal_title=titles.get(goal_id, ""),
            )
        )
    for goal_id, items in grouped.items():
        items.sort(key=_coaching_step_sort_key)
    return grouped


def flatten_coaching_steps(
    contact_id: int,
    tenant_timezone: str | None,
    *,
    done: bool | None = None,
    goal_titles_by_id: dict[str, str] | None = None,
) -> list[dict]:
    titles = goal_titles_by_id or {}
    items: list[dict] = []
    for task in coaching_task_queryset(contact_id=contact_id).order_by("created_at", "id"):
        payload = serialize_coaching_step(
            task,
            tenant_timezone=tenant_timezone,
            goal_title=titles.get(str(task.goal_id or ""), ""),
        )
        if done is not None and bool(payload["done"]) is not done:
            continue
        items.append(payload)
    items.sort(key=_coaching_step_sort_key)
    return items


def list_coaching_task_payloads(contact_id: int, tenant_timezone: str | None, goal_titles_by_id: dict[str, str] | None = None) -> list[dict]:
    titles = goal_titles_by_id or {}
    items = [
        serialize_coaching_task(
            task,
            tenant_timezone=tenant_timezone,
            goal_title=titles.get(str(task.goal_id or ""), ""),
        )
        for task in coaching_task_queryset(contact_id=contact_id).order_by("created_at", "id")
    ]
    items.sort(key=_coaching_task_sort_key)
    return items


def list_coaching_milestones(contact_id: int) -> list[dict]:
    items = [
        serialize_coaching_milestone(task)
        for task in coaching_task_queryset(contact_id=contact_id)
        .filter(is_milestone=True)
        .order_by("id")
    ]
    items.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    return items


def completed_coaching_task_count_last_30_days(contact_id: int, today: date) -> int:
    since = today - timedelta(days=29)
    return coaching_task_queryset(contact_id=contact_id).filter(
        status__in=COACHING_DONE_STATUSES,
        done_at__date__gte=since,
        done_at__date__lte=today,
    ).count()


def has_overdue_coaching_task(contact_id: int, tenant_timezone: str | None, now: datetime) -> bool:
    today = timezone.localdate(now, _tenant_zoneinfo(tenant_timezone))
    for task in coaching_task_queryset(contact_id=contact_id).filter(status__in=COACHING_OPEN_STATUSES):
        due_date = crm_due_at_to_coaching_due_date(task.due_at, tenant_timezone)
        if not due_date:
            continue
        try:
            parsed_due = date.fromisoformat(due_date)
        except ValueError:
            continue
        if parsed_due < today:
            return True
    return False


def has_recent_coaching_milestone(contact_id: int, now: datetime) -> bool:
    week_ago = now - timedelta(days=7)
    for task in coaching_task_queryset(contact_id=contact_id).filter(is_milestone=True):
        if coaching_milestone_created_at(task) >= week_ago:
            return True
    return False


def group_task_done_index(task_ids_by_contact: Iterable[tuple[int, str]]) -> dict[tuple[int, str], bool]:
    result: dict[tuple[int, str], bool] = {}
    for contact_id, task_id in task_ids_by_contact:
        result[(contact_id, task_id)] = False
    if not result:
        return result

    task_ids = [int(task_id) for _, task_id in result.keys() if str(task_id).isdigit()]
    done_ids = set(
        CRMTask.objects.filter(id__in=task_ids, source=COACHING_TASK_SOURCE, status__in=COACHING_DONE_STATUSES)
        .values_list("id", flat=True)
    )
    for contact_id, task_id in list(result.keys()):
        result[(contact_id, task_id)] = int(task_id) in done_ids if str(task_id).isdigit() else False
    return result


def create_coaching_task(
    *,
    contact_id: int,
    goal_id: str,
    title: str,
    due_date: str | None,
    tenant_timezone: str | None,
    history_note: str = CREATE_HISTORY_NOTE,
) -> CRMTask:
    with transaction.atomic():
        task = CRMTask.objects.create(
            source=COACHING_TASK_SOURCE,
            contact_id=contact_id,
            goal_id=goal_id or None,
            title=title,
            description=None,
            status="open",
            priority=2,
            due_at=coaching_due_date_to_datetime(due_date, tenant_timezone),
            is_milestone=False,
            milestone_note="",
            done_at=None,
            created_by=0,
        )
        CRMTaskHistory.objects.create(
            task=task,
            note=history_note,
            status=task.status,
            created_by=0,
        )
        return task


def create_coaching_milestone(
    *,
    contact_id: int,
    goal_id: str | None,
    text: str,
    note: str = "",
    created_at: datetime | None = None,
    history_note: str = CREATE_HISTORY_NOTE,
) -> CRMTask:
    created_at_value = created_at or timezone.now()
    with transaction.atomic():
        task = CRMTask.objects.create(
            source=COACHING_TASK_SOURCE,
            contact_id=contact_id,
            goal_id=str(goal_id or "").strip() or None,
            title=text,
            description=None,
            status="done",
            priority=2,
            due_at=None,
            is_milestone=True,
            milestone_note=note,
            done_at=created_at_value,
            created_by=0,
            created_at=created_at_value,
            updated_at=created_at_value,
        )
        CRMTaskHistory.objects.create(
            task=task,
            note=history_note,
            status=task.status,
            created_by=0,
            created_at=created_at_value,
        )
        return task


def update_coaching_task(task: CRMTask, *, tenant_timezone: str | None, changes: CoachingTaskUpdate) -> CRMTask:
    update_fields: list[str] = []
    now = timezone.now()

    if changes.title is not None and task.title != changes.title:
        task.title = changes.title
        update_fields.append("title")
    if changes.due_date is not None:
        due_at = coaching_due_date_to_datetime(changes.due_date, tenant_timezone)
        if task.due_at != due_at:
            task.due_at = due_at
            update_fields.append("due_at")
    if changes.is_milestone is not None and bool(task.is_milestone) != bool(changes.is_milestone):
        task.is_milestone = bool(changes.is_milestone)
        update_fields.append("is_milestone")
    if changes.milestone_note is not None and str(task.milestone_note or "") != str(changes.milestone_note or ""):
        task.milestone_note = changes.milestone_note or ""
        update_fields.append("milestone_note")
    if changes.status is not None and str(task.status or "") != changes.status:
        task.status = changes.status
        update_fields.append("status")
    if changes.done_at is not None or (changes.status is not None and changes.done_at is None):
        if task.done_at != changes.done_at:
            task.done_at = changes.done_at
            update_fields.append("done_at")

    history_note = str(changes.history_note or "").strip()
    if not update_fields:
        return task

    task.updated_at = now
    update_fields.append("updated_at")
    with transaction.atomic():
        task.save(update_fields=update_fields)
        if history_note:
            CRMTaskHistory.objects.create(
                task=task,
                note=history_note,
                status=task.status,
                created_by=0,
            )
    return task


def _coaching_step_sort_key(step: dict) -> tuple[int, str, str]:
    due_date = str(step.get("dueDate") or "")
    done_at = str(step.get("doneAt") or "")
    return (1 if step.get("done") else 0, due_date or "9999", done_at or "9999")


def _coaching_task_sort_key(task: dict) -> tuple[int, str, str]:
    status = str(task.get("status") or COACHING_PENDING_STATUS)
    due_date = str(task.get("dueDate") or "")
    created_at = str(task.get("createdAt") or "")
    return (1 if status == "done" else 0, due_date or "9999", created_at)
