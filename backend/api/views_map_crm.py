from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import TelegramTask, UserTenantBinding
from core.services.tenant_service import TenantService

from .permissions import IsTenantMember, IsTenantOwnerOrEditor
from .utils import get_active_client

User = get_user_model()
UTC_TZ = ZoneInfo("UTC")


def _map_schema() -> str:
    """Get the map schema name from environment or default to 'map'."""
    schema = os.getenv("MAP_SCHEMA", "map").strip()
    if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        return "map"
    return schema


def _coerce_int(value: Any, field_name: str) -> int:
    """Validate and convert value to integer."""
    if value is None or value == "":
        raise ValidationError({field_name: "Поле обязательно."})
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: "Нужно число."})


def _coerce_text(value: Any, field_name: str) -> str:
    """Validate and convert value to text."""
    text = str(value or "").strip()
    if not text:
        raise ValidationError({field_name: "Поле обязательно."})
    return text


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if value is None or value == "":
        raise ValidationError({field_name: "Поле обязательно."})
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            raise ValidationError({field_name: "Поле обязательно."})
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValidationError({field_name: f"Некорректная дата: {exc}"}) from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(UTC_TZ)


def _coerce_datetime_utc(value: Any, field_name: str) -> datetime:
    return _parse_datetime(value, field_name)


def _coerce_datetime_utc_optional(value: Any, field_name: str) -> datetime | None:
    if value is None or value == "":
        return None
    return _coerce_datetime_utc(value, field_name)


def _coerce_positive_float_optional(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        raw_value: Any = text.replace(",", ".")
    else:
        raw_value = value
    try:
        numeric = float(raw_value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: "Нужно число."})
    if numeric <= 0:
        raise ValidationError({field_name: "Значение должно быть больше 0."})
    return numeric


def _upsert_event_payment(
    schema: str,
    event_id: int,
    contact_id: int,
    amount: float,
    title: str,
    planned_at: datetime | None,
) -> int | None:
    description = f"Оплата встречи: {title}".strip() or "Оплата встречи"

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, status
            FROM {schema}.crm_payments
            WHERE event_id = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            [event_id],
        )
        existing = cursor.fetchone()

        if existing:
            payment_id, payment_status = existing
            # Не изменяем завершённые/ошибочные платежи автоматически.
            if payment_status == "pending":
                cursor.execute(
                    f"""
                    UPDATE {schema}.crm_payments
                    SET
                        contact_id = %s,
                        amount = %s,
                        currency = %s,
                        description = %s,
                        planned_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    [contact_id, amount, "RUB", description, planned_at, payment_id],
                )
            return int(payment_id)

        cursor.execute(
            f"""
            INSERT INTO {schema}.crm_payments
                (contact_id, event_id, product_id, amount, currency, status, payment_method, transaction_id, description, planned_at, paid_at)
            VALUES
                (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, NULL)
            RETURNING id
            """,
            [contact_id, event_id, amount, "RUB", "pending", "", "", description, planned_at],
        )
        created = cursor.fetchone()
        return int(created[0]) if created else None


def _serialize_datetime_utc(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC_TZ)
        return value.astimezone(UTC_TZ)
    return value


def _fetch_all(cursor) -> List[Dict[str, Any]]:
    """Convert cursor results to list of dictionaries."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def _column_exists(schema: str, table: str, column: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = %s
            LIMIT 1
            """,
            [schema, table, column],
        )
        return cursor.fetchone() is not None

def _normalize_tag_ids(value: Any) -> List[int]:
    if not value:
        return []
    return [int(item) for item in value]


def _serialize_contact_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize contact row from database to API format."""
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "category_id": row.get("category_id"),
        "status": row.get("status") or "active",
        "photo_url": row.get("photo_url") or "",
        "notes": row.get("notes") or "",
        "parent_id": row.get("parent_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "tags": {
            "goal": _normalize_tag_ids(row.get("goal_tags")),
            "pain": _normalize_tag_ids(row.get("pain_tags")),
            "experience": _normalize_tag_ids(row.get("experience_tags")),
        },
    }


def _serialize_tag_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize tag row from database to API format."""
    return {
        "id": row.get("id"),
        "type": row.get("type") or "",
        "value": row.get("value") or "",
        "created_at": row.get("created_at"),
    }


def _serialize_contact_tag_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize contact-tag relation with description."""
    return {
        "contact_id": row.get("contact_id"),
        "tag_id": row.get("tag_id"),
        "type": row.get("type") or "",
        "value": row.get("value") or "",
        "description": row.get("description") or "",
    }


def _serialize_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize event row from database to API format."""
    return {
        "id": row.get("id"),
        "contact_id": row.get("contact_id"),
        "event_type_id": row.get("event_type_id"),
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "start_time": _serialize_datetime_utc(row.get("start_time")),
        "end_time": _serialize_datetime_utc(row.get("end_time")),
        "location": row.get("location") or "",
        "status": row.get("status") or "scheduled",
        "notes": row.get("notes") or "",
        "price": float(row.get("price")) if row.get("price") is not None else None,
        "created_at": _serialize_datetime_utc(row.get("created_at")),
        "updated_at": _serialize_datetime_utc(row.get("updated_at")),
    }


def _serialize_availability_event_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize availability event row from database to API format."""
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "start_time": _serialize_datetime_utc(row.get("start_time")),
        "duration_minutes": row.get("duration_minutes"),
        "repeat_type": row.get("repeat_type"),
        "created_at": _serialize_datetime_utc(row.get("created_at")),
        "updated_at": _serialize_datetime_utc(row.get("updated_at")),
    }


def _serialize_event_type_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize event type row from database to API format."""
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "description": row.get("description") or "",
        "duration_minutes": row.get("duration_minutes") or 60,
        "color": row.get("color") or "#4A90E2",
        "created_at": row.get("created_at"),
    }


def _serialize_category_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize category row from database to API format."""
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "description": row.get("description") or "",
        "color": row.get("color") or "#4A90E2",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _serialize_payment_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize payment row from database to API format."""
    return {
        "id": row.get("id"),
        "contact_id": row.get("contact_id"),
        "event_id": row.get("event_id"),
        "product_id": row.get("product_id"),
        "amount": float(row.get("amount")) if row.get("amount") else 0.0,
        "currency": row.get("currency") or "RUB",
        "status": row.get("status") or "pending",
        "payment_method": row.get("payment_method") or "",
        "transaction_id": row.get("transaction_id") or "",
        "description": row.get("description") or "",
        "planned_at": _serialize_datetime_utc(row.get("planned_at")),
        "paid_at": _serialize_datetime_utc(row.get("paid_at")),
        "created_at": _serialize_datetime_utc(row.get("created_at")),
        "updated_at": _serialize_datetime_utc(row.get("updated_at")),
    }


def _serialize_note_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize note row from database to API format."""
    return {
        "id": row.get("id"),
        "contact_id": row.get("contact_id"),
        "title": row.get("title") or "",
        "content": row.get("content") or "",
        "is_important": bool(row.get("is_important")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _fetch_contact(schema: str, contact_id: int) -> Dict[str, Any] | None:
    """Fetch a single contact by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                c.*,
                COALESCE((
                    SELECT ARRAY_AGG(t.id)
                    FROM {schema}.contact_tags ct
                    JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                    WHERE ct.contact_id = c.id AND t.type = 'goal'
                ), ARRAY[]::int[]) AS goal_tags,
                COALESCE((
                    SELECT ARRAY_AGG(t.id)
                    FROM {schema}.contact_tags ct
                    JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                    WHERE ct.contact_id = c.id AND t.type = 'pain'
                ), ARRAY[]::int[]) AS pain_tags,
                COALESCE((
                    SELECT ARRAY_AGG(t.id)
                    FROM {schema}.contact_tags ct
                    JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                    WHERE ct.contact_id = c.id AND t.type = 'experience'
                ), ARRAY[]::int[]) AS experience_tags
            FROM {schema}.contacts c
            WHERE c.id = %s
            """,
            [contact_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_contact_row(dict(zip(columns, row)))


def _fetch_tag(schema: str, tag_id: int) -> Dict[str, Any] | None:
    """Fetch a single tag by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                type,
                value,
                created_at
            FROM {schema}.crm_tags
            WHERE id = %s
            """,
            [tag_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_tag_row(dict(zip(columns, row)))


def _fetch_event(schema: str, event_id: int) -> Dict[str, Any] | None:
    """Fetch a single event by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                contact_id,
                event_type_id,
                title,
                description,
                start_time,
                end_time,
                location,
                status,
                notes,
                price,
                created_at,
                updated_at
            FROM {schema}.crm_events
            WHERE id = %s
            """,
            [event_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_event_row(dict(zip(columns, row)))


def _fetch_availability_event(schema: str, tenant_id: int, event_id: int) -> Dict[str, Any] | None:
    """Fetch a single availability event by tenant + ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                tenant_id,
                start_time,
                duration_minutes,
                repeat_type,
                created_at,
                updated_at
            FROM {schema}.events
            WHERE tenant_id = %s AND id = %s
            """,
            [tenant_id, event_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_availability_event_row(dict(zip(columns, row)))


def _fetch_event_type(schema: str, event_type_id: int) -> Dict[str, Any] | None:
    """Fetch a single event type by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                name,
                description,
                duration_minutes,
                color,
                created_at
            FROM {schema}.crm_event_types
            WHERE id = %s
            """,
            [event_type_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_event_type_row(dict(zip(columns, row)))


def _fetch_category(schema: str, category_id: int) -> Dict[str, Any] | None:
    """Fetch a single category by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                name,
                description,
                color,
                created_at,
                updated_at
            FROM {schema}.crm_categories
            WHERE id = %s
            """,
            [category_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_category_row(dict(zip(columns, row)))


def _fetch_payment(schema: str, payment_id: int) -> Dict[str, Any] | None:
    """Fetch a single payment by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                contact_id,
                event_id,
                product_id,
                amount,
                currency,
                status,
                payment_method,
                transaction_id,
                description,
                planned_at,
                paid_at,
                created_at,
                updated_at
            FROM {schema}.crm_payments
            WHERE id = %s
            """,
            [payment_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_payment_row(dict(zip(columns, row)))


def _fetch_note(schema: str, note_id: int) -> Dict[str, Any] | None:
    """Fetch a single note by ID from the specified schema."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                contact_id,
                title,
                content,
                is_important,
                created_at,
                updated_at
            FROM {schema}.crm_notes
            WHERE id = %s
            """,
            [note_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_note_row(dict(zip(columns, row)))


class ContactsListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    c.*,
                    COALESCE((
                        SELECT ARRAY_AGG(t.id)
                        FROM {schema}.contact_tags ct
                        JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                        WHERE ct.contact_id = c.id AND t.type = 'goal'
                    ), ARRAY[]::int[]) AS goal_tags,
                    COALESCE((
                        SELECT ARRAY_AGG(t.id)
                        FROM {schema}.contact_tags ct
                        JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                        WHERE ct.contact_id = c.id AND t.type = 'pain'
                    ), ARRAY[]::int[]) AS pain_tags,
                    COALESCE((
                        SELECT ARRAY_AGG(t.id)
                        FROM {schema}.contact_tags ct
                        JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                        WHERE ct.contact_id = c.id AND t.type = 'experience'
                    ), ARRAY[]::int[]) AS experience_tags
                FROM {schema}.contacts c
                ORDER BY c.name ASC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_contact_row(row))

        return Response(payload)

    def post(self, request):
        raw_name = request.data.get("name")
        if not raw_name:
            first = request.data.get("first_name")
            last = request.data.get("last_name")
            raw_name = " ".join(part for part in [first, last] if part).strip()
        name = _coerce_text(raw_name, "name")
        email = request.data.get("email", "")
        phone = request.data.get("phone", "")
        category_id = request.data.get("category_id")
        status_val = request.data.get("status", "active")
        photo_url = request.data.get("photo_url", "")
        notes = request.data.get("notes", "")
        parent_id = request.data.get("parent_id")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.contacts 
                (name, email, phone, category_id, status, photo_url, notes, parent_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [name, email, phone, category_id, status_val, photo_url, notes, parent_id],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать контакт."}, status=status.HTTP_400_BAD_REQUEST)

        contact_id = row[0]
        created = _fetch_contact(schema, int(contact_id))
        if not created:
            created = {
                "id": int(contact_id),
                "name": name,
                "email": email,
                "phone": phone,
                "category_id": category_id,
                "status": status_val,
                "photo_url": photo_url,
                "notes": notes,
                "parent_id": parent_id,
                "created_at": None,
                "updated_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class ContactDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        schema = _map_schema()
        contact = _fetch_contact(schema, int(contact_id))
        if not contact:
            return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(contact)

    def patch(self, request, contact_id: int):
        schema = _map_schema()
        updates = []
        params = []

        raw_name = request.data.get("name")
        if raw_name is None and ("first_name" in request.data or "last_name" in request.data):
            first = request.data.get("first_name")
            last = request.data.get("last_name")
            raw_name = " ".join(part for part in [first, last] if part).strip()
        if raw_name is not None:
            updates.append("name = %s")
            params.append(_coerce_text(raw_name, "name"))

        if "email" in request.data:
            updates.append("email = %s")
            params.append(request.data["email"])

        if "phone" in request.data:
            updates.append("phone = %s")
            params.append(request.data["phone"])

        if "category_id" in request.data:
            updates.append("category_id = %s")
            params.append(request.data["category_id"])

        if "status" in request.data:
            updates.append("status = %s")
            params.append(request.data["status"])

        if "photo_url" in request.data:
            updates.append("photo_url = %s")
            params.append(request.data["photo_url"])

        if "notes" in request.data:
            updates.append("notes = %s")
            params.append(request.data["notes"])

        if "parent_id" in request.data:
            updates.append("parent_id = %s")
            params.append(request.data["parent_id"])

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(contact_id)  # Add contact_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.contacts SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_contact(schema, int(contact_id))
        if not updated:
            return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, contact_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.contacts WHERE id = %s", [contact_id])
            if cursor.rowcount == 0:
                return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactTelegramLinkView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, contact_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT tg_username FROM {schema}.contacts WHERE id = %s",
                [contact_id],
            )
            row = cursor.fetchone()
            if row is None:
                return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)
            contact_tg_username = row[0]

        client = get_active_client(request.user)
        tenant_service = TenantService()
        try:
            link = tenant_service.generate_telegram_link(client.id, contact_id=contact_id)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        binding_qs = (
            UserTenantBinding.objects.filter(
                tenant=client,
                contact_id=contact_id,
                provider=UserTenantBinding.PROVIDER_TELEGRAM,
            )
            .order_by("-bound_at", "-id")
        )
        binding = binding_qs.filter(is_active=True).first() or binding_qs.first()

        telegram_chat_id = None
        tg_name = None
        is_connected = False
        if binding is not None:
            telegram_chat_id = binding.telegram_chat_id
            is_connected = bool(binding.is_active)
            if contact_tg_username:
                tg_name = contact_tg_username
            else:
                task = (
                    TelegramTask.objects.filter(
                        client=client,
                        telegram_user_id=telegram_chat_id,
                    )
                    .order_by("-received_at", "-id")
                    .first()
                )
                if task and task.tg_name:
                    tg_name = task.tg_name
                else:
                    tg_name = f"tg_{telegram_chat_id}"

        return Response(
            {
                "contact_id": int(contact_id),
                "tenant_id": client.id,
                "telegram_chat_id": telegram_chat_id,
                "tg_name": tg_name,
                "is_connected": is_connected,
                "link": link,
            }
        )


class TagsListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    type,
                    value,
                    created_at
                FROM {schema}.crm_tags
                ORDER BY type, value ASC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_tag_row(row))

        return Response(payload)

    def post(self, request):
        tag_type = _coerce_text(request.data.get("type"), "type")
        if tag_type not in ["goal", "pain", "experience"]:
            return Response({"error": "Недопустимый тип тега. Допустимые значения: goal, pain, experience."}, status=status.HTTP_400_BAD_REQUEST)
        
        value = _coerce_text(request.data.get("value"), "value")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_tags 
                (type, value)
                VALUES (%s, %s)
                RETURNING id
                """,
                [tag_type, value],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать тег."}, status=status.HTTP_400_BAD_REQUEST)

        tag_id = row[0]
        created = _fetch_tag(schema, int(tag_id))
        if not created:
            created = {
                "id": int(tag_id),
                "type": tag_type,
                "value": value,
                "created_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, tag_id: int):
        schema = _map_schema()
        tag = _fetch_tag(schema, int(tag_id))
        if not tag:
            return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(tag)

    def patch(self, request, tag_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "type" in request.data:
            tag_type = _coerce_text(request.data["type"], "type")
            if tag_type not in ["goal", "pain", "experience"]:
                return Response({"error": "Недопустимый тип тега. Допустимые значения: goal, pain, experience."}, status=status.HTTP_400_BAD_REQUEST)
            updates.append("type = %s")
            params.append(tag_type)

        if "value" in request.data:
            updates.append("value = %s")
            params.append(_coerce_text(request.data["value"], "value"))

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(tag_id)  # Add tag_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_tags SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_tag(schema, int(tag_id))
        if not updated:
            return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, tag_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_tags WHERE id = %s", [tag_id])
            if cursor.rowcount == 0:
                return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactTagsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsTenantMember()]
        return super().get_permissions()

    def get(self, request):
        contact_id = request.query_params.get("contact_id") or request.query_params.get("contactId")
        if contact_id is None:
            return Response({"error": "contact_id обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        contact_id = _coerce_int(contact_id, "contact_id")
        schema = _map_schema()
        has_description = _column_exists(schema, "contact_tags", "description")
        description_select = "ct.description" if has_description else "NULL AS description"

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    ct.contact_id,
                    ct.tag_id,
                    {description_select},
                    t.type,
                    t.value
                FROM {schema}.contact_tags ct
                JOIN {schema}.crm_tags t ON t.id = ct.tag_id
                WHERE ct.contact_id = %s
                ORDER BY t.type ASC, t.value ASC
                """,
                [contact_id],
            )
            rows = _fetch_all(cursor)

        payload = [_serialize_contact_tag_row(row) for row in rows]
        return Response(payload)

    def post(self, request):
        contact_id = _coerce_int(request.data.get("contact_id") or request.data.get("contactId"), "contact_id")
        tag_id = _coerce_int(request.data.get("tag_id") or request.data.get("tagId"), "tag_id")
        description = request.data.get("description")

        schema = _map_schema()
        has_description = _column_exists(schema, "contact_tags", "description")
        with connection.cursor() as cursor:
            # Check if contact exists
            cursor.execute(f"SELECT 1 FROM {schema}.contacts WHERE id = %s", [contact_id])
            if not cursor.fetchone():
                return Response({"error": "Контакт не найден."}, status=status.HTTP_404_NOT_FOUND)

            # Check if tag exists
            cursor.execute(f"SELECT 1 FROM {schema}.crm_tags WHERE id = %s", [tag_id])
            if not cursor.fetchone():
                return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)

            # Insert the relationship
            if has_description:
                cursor.execute(
                    f"""
                    INSERT INTO {schema}.contact_tags (contact_id, tag_id, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (contact_id, tag_id) DO UPDATE
                    SET description = COALESCE(EXCLUDED.description, {schema}.contact_tags.description)
                    """,
                    [contact_id, tag_id, description],
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO {schema}.contact_tags (contact_id, tag_id)
                    VALUES (%s, %s)
                    ON CONFLICT (contact_id, tag_id) DO NOTHING
                    """,
                    [contact_id, tag_id],
                )

        return Response({"success": True}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        contact_id = _coerce_int(request.data.get("contact_id") or request.data.get("contactId"), "contact_id")
        tag_id = _coerce_int(request.data.get("tag_id") or request.data.get("tagId"), "tag_id")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {schema}.contact_tags WHERE contact_id = %s AND tag_id = %s",
                [contact_id, tag_id],
            )
            if cursor.rowcount == 0:
                return Response({"error": "Связь между контактом и тегом не найдена."}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriesListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    name,
                    description,
                    color,
                    created_at,
                    updated_at
                FROM {schema}.crm_categories
                ORDER BY name ASC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_category_row(row))

        return Response(payload)

    def post(self, request):
        name = _coerce_text(request.data.get("name"), "name")
        description = request.data.get("description", "")
        color = _coerce_text(request.data.get("color") or "#4A90E2", "color")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_categories
                (name, description, color)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                [name, description, color],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать категорию."}, status=status.HTTP_400_BAD_REQUEST)

        category_id = row[0]
        created = _fetch_category(schema, int(category_id))
        if not created:
            created = {
                "id": int(category_id),
                "name": name,
                "description": description,
                "color": color,
                "created_at": None,
                "updated_at": None,
            }
        return Response(created, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, category_id: int):
        schema = _map_schema()
        category = _fetch_category(schema, int(category_id))
        if not category:
            return Response({"error": "Категория не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(category)

    def patch(self, request, category_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "name" in request.data:
            updates.append("name = %s")
            params.append(_coerce_text(request.data["name"], "name"))

        if "description" in request.data:
            updates.append("description = %s")
            params.append(request.data["description"])

        if "color" in request.data:
            updates.append("color = %s")
            params.append(_coerce_text(request.data["color"], "color"))

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(category_id)

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_categories SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Категория не найдена."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_category(schema, int(category_id))
        if not updated:
            return Response({"error": "Категория не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, category_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_categories WHERE id = %s", [category_id])
            if cursor.rowcount == 0:
                return Response({"error": "Категория не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventTypesListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    name,
                    description,
                    duration_minutes,
                    color,
                    created_at
                FROM {schema}.crm_event_types
                ORDER BY name ASC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_event_type_row(row))

        return Response(payload)

    def post(self, request):
        name = _coerce_text(request.data.get("name"), "name")
        description = request.data.get("description", "")
        duration_minutes = _coerce_int(request.data.get("duration_minutes", 60), "duration_minutes")
        color = _coerce_text(request.data.get("color"), "color")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_event_types 
                (name, description, duration_minutes, color)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                [name, description, duration_minutes, color],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать тип события."}, status=status.HTTP_400_BAD_REQUEST)

        event_type_id = row[0]
        created = _fetch_event_type(schema, int(event_type_id))
        if not created:
            created = {
                "id": int(event_type_id),
                "name": name,
                "description": description,
                "duration_minutes": duration_minutes,
                "color": color,
                "created_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class EventTypeDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, event_type_id: int):
        schema = _map_schema()
        event_type = _fetch_event_type(schema, int(event_type_id))
        if not event_type:
            return Response({"error": "Тип события не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(event_type)

    def patch(self, request, event_type_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "name" in request.data:
            updates.append("name = %s")
            params.append(_coerce_text(request.data["name"], "name"))

        if "description" in request.data:
            updates.append("description = %s")
            params.append(request.data["description"])

        if "duration_minutes" in request.data:
            updates.append("duration_minutes = %s")
            params.append(_coerce_int(request.data["duration_minutes"], "duration_minutes"))

        if "color" in request.data:
            updates.append("color = %s")
            params.append(_coerce_text(request.data["color"], "color"))

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(event_type_id)  # Add event_type_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_event_types SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Тип события не найден."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_event_type(schema, int(event_type_id))
        if not updated:
            return Response({"error": "Тип события не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, event_type_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_event_types WHERE id = %s", [event_type_id])
            if cursor.rowcount == 0:
                return Response({"error": "Тип события не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventsListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    contact_id,
                    event_type_id,
                    title,
                    description,
                    start_time,
                    end_time,
                    location,
                    status,
                    notes,
                    price,
                    created_at,
                    updated_at
                FROM {schema}.crm_events
                ORDER BY start_time DESC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_event_row(row))

        return Response(payload)

    def post(self, request):
        contact_id = _coerce_int(request.data.get("contact_id"), "contact_id")
        event_type_id = request.data.get("event_type_id")
        title = _coerce_text(request.data.get("title"), "title")
        description = request.data.get("description", "")
        start_time = _coerce_datetime_utc(request.data.get("start_time"), "start_time")
        end_time = _coerce_datetime_utc(request.data.get("end_time"), "end_time")
        location = request.data.get("location", "")
        status_val = request.data.get("status", "scheduled")
        notes = request.data.get("notes", "")
        price = _coerce_positive_float_optional(request.data.get("price"), "price")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_events 
                (contact_id, event_type_id, title, description, start_time, end_time, location, status, notes, price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [contact_id, event_type_id, title, description, start_time, end_time, location, status_val, notes, price],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать событие."}, status=status.HTTP_400_BAD_REQUEST)

        event_id = row[0]
        if price is not None:
            _upsert_event_payment(
                schema=schema,
                event_id=int(event_id),
                contact_id=contact_id,
                amount=price,
                title=title,
                planned_at=start_time,
            )

        created = _fetch_event(schema, int(event_id))
        if not created:
            created = {
                "id": int(event_id),
                "contact_id": contact_id,
                "event_type_id": event_type_id,
                "title": title,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "status": status_val,
                "notes": notes,
                "price": price,
                "created_at": None,
                "updated_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class EventDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, event_id: int):
        schema = _map_schema()
        event = _fetch_event(schema, int(event_id))
        if not event:
            return Response({"error": "Событие не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(event)

    def patch(self, request, event_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "contact_id" in request.data:
            updates.append("contact_id = %s")
            params.append(_coerce_int(request.data["contact_id"], "contact_id"))

        if "event_type_id" in request.data:
            updates.append("event_type_id = %s")
            params.append(request.data["event_type_id"])

        if "title" in request.data:
            updates.append("title = %s")
            params.append(_coerce_text(request.data["title"], "title"))

        if "description" in request.data:
            updates.append("description = %s")
            params.append(request.data["description"])

        if "start_time" in request.data:
            updates.append("start_time = %s")
            params.append(_coerce_datetime_utc(request.data["start_time"], "start_time"))

        if "end_time" in request.data:
            updates.append("end_time = %s")
            params.append(_coerce_datetime_utc(request.data["end_time"], "end_time"))

        if "location" in request.data:
            updates.append("location = %s")
            params.append(request.data["location"])

        if "status" in request.data:
            updates.append("status = %s")
            params.append(request.data["status"])

        if "notes" in request.data:
            updates.append("notes = %s")
            params.append(request.data["notes"])

        if "price" in request.data:
            updates.append("price = %s")
            params.append(_coerce_positive_float_optional(request.data["price"], "price"))

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(event_id)  # Add event_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_events SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Событие не найдено."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_event(schema, int(event_id))
        if not updated:
            return Response({"error": "Событие не найден."}, status=status.HTTP_404_NOT_FOUND)

        if "price" in request.data and updated.get("price") is not None:
            _upsert_event_payment(
                schema=schema,
                event_id=int(updated["id"]),
                contact_id=int(updated["contact_id"]),
                amount=float(updated["price"]),
                title=str(updated.get("title") or "Встреча"),
                planned_at=updated.get("start_time"),
            )
        return Response(updated)

    def delete(self, request, event_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_events WHERE id = %s", [event_id])
            if cursor.rowcount == 0:
                return Response({"error": "Событие не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvailabilityEventsListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        client = get_active_client(request.user)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    tenant_id,
                    start_time,
                    duration_minutes,
                    repeat_type,
                    created_at,
                    updated_at
                FROM {schema}.events
                WHERE tenant_id = %s
                ORDER BY start_time DESC
                """,
                [client.id],
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_availability_event_row(row))

        return Response(payload)

    def post(self, request):
        client = get_active_client(request.user)
        start_time = _coerce_datetime_utc(request.data.get("start_time"), "start_time")
        duration_minutes = _coerce_int(request.data.get("duration_minutes", 60), "duration_minutes")
        repeat_type = _coerce_int(request.data.get("repeat_type", 0), "repeat_type")
        if repeat_type not in {0, 1, 2, 3}:
            raise ValidationError({"repeat_type": "Недопустимое значение."})

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.events
                (tenant_id, start_time, duration_minutes, repeat_type)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                [client.id, start_time, duration_minutes, repeat_type],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать доступное время."}, status=status.HTTP_400_BAD_REQUEST)

        event_id = row[0]
        created = _fetch_availability_event(schema, client.id, int(event_id))
        if not created:
            created = {
                "id": int(event_id),
                "tenant_id": client.id,
                "start_time": start_time,
                "duration_minutes": duration_minutes,
                "repeat_type": repeat_type,
                "created_at": None,
                "updated_at": None,
            }
        return Response(created, status=status.HTTP_201_CREATED)


class AvailabilityEventDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, event_id: int):
        schema = _map_schema()
        client = get_active_client(request.user)
        event = _fetch_availability_event(schema, client.id, int(event_id))
        if not event:
            return Response({"error": "Доступное время не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(event)

    def patch(self, request, event_id: int):
        schema = _map_schema()
        client = get_active_client(request.user)
        updates = []
        params = []

        if "start_time" in request.data:
            updates.append("start_time = %s")
            params.append(_coerce_datetime_utc(request.data.get("start_time"), "start_time"))

        if "duration_minutes" in request.data:
            updates.append("duration_minutes = %s")
            params.append(_coerce_int(request.data.get("duration_minutes"), "duration_minutes"))

        if "repeat_type" in request.data:
            repeat_type = _coerce_int(request.data.get("repeat_type"), "repeat_type")
            if repeat_type not in {0, 1, 2, 3}:
                raise ValidationError({"repeat_type": "Недопустимое значение."})
            updates.append("repeat_type = %s")
            params.append(repeat_type)

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.extend([client.id, event_id])
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {schema}.events
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE tenant_id = %s AND id = %s
                """,
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Доступное время не найдено."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_availability_event(schema, client.id, int(event_id))
        if not updated:
            return Response({"error": "Доступное время не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, event_id: int):
        schema = _map_schema()
        client = get_active_client(request.user)
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {schema}.events WHERE tenant_id = %s AND id = %s",
                [client.id, event_id],
            )
            if cursor.rowcount == 0:
                return Response({"error": "Доступное время не найдено."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentsListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    contact_id,
                    event_id,
                    product_id,
                    amount,
                    currency,
                    status,
                    payment_method,
                    transaction_id,
                    description,
                    planned_at,
                    paid_at,
                    created_at,
                    updated_at
                FROM {schema}.crm_payments
                ORDER BY created_at DESC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_payment_row(row))

        return Response(payload)

    def post(self, request):
        contact_id = _coerce_int(request.data.get("contact_id"), "contact_id")
        event_id = request.data.get("event_id")
        if event_id is not None:
            event_id = _coerce_int(event_id, "event_id")
        product_id = request.data.get("product_id")
        if product_id is not None:
            product_id = _coerce_int(product_id, "product_id")
        amount = float(request.data.get("amount", 0))
        currency = request.data.get("currency", "RUB")
        status_val = request.data.get("status", "pending")
        payment_method = request.data.get("payment_method", "")
        transaction_id = request.data.get("transaction_id", "")
        description = request.data.get("description", "")
        planned_at = _coerce_datetime_utc_optional(request.data.get("planned_at"), "planned_at")
        paid_at = _coerce_datetime_utc_optional(request.data.get("paid_at"), "paid_at")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_payments 
                (contact_id, event_id, product_id, amount, currency, status, payment_method, transaction_id, description, planned_at, paid_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                [contact_id, event_id, product_id, amount, currency, status_val, payment_method, transaction_id, description, planned_at, paid_at],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать платеж."}, status=status.HTTP_400_BAD_REQUEST)

        payment_id = row[0]
        created = _fetch_payment(schema, int(payment_id))
        if not created:
            created = {
                "id": int(payment_id),
                "contact_id": contact_id,
                "event_id": event_id,
                "product_id": product_id,
                "amount": amount,
                "currency": currency,
                "status": status_val,
                "payment_method": payment_method,
                "transaction_id": transaction_id,
                "description": description,
                "planned_at": planned_at,
                "paid_at": paid_at,
                "created_at": None,
                "updated_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, payment_id: int):
        schema = _map_schema()
        payment = _fetch_payment(schema, int(payment_id))
        if not payment:
            return Response({"error": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(payment)

    def patch(self, request, payment_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "contact_id" in request.data:
            updates.append("contact_id = %s")
            params.append(_coerce_int(request.data["contact_id"], "contact_id"))

        if "product_id" in request.data:
            value = request.data["product_id"]
            params.append(_coerce_int(value, "product_id") if value is not None else None)
            updates.append("product_id = %s")

        if "event_id" in request.data:
            value = request.data["event_id"]
            params.append(_coerce_int(value, "event_id") if value is not None else None)
            updates.append("event_id = %s")

        if "amount" in request.data:
            updates.append("amount = %s")
            params.append(float(request.data["amount"]))

        if "currency" in request.data:
            updates.append("currency = %s")
            params.append(request.data["currency"])

        if "status" in request.data:
            updates.append("status = %s")
            params.append(request.data["status"])

        if "payment_method" in request.data:
            updates.append("payment_method = %s")
            params.append(request.data["payment_method"])

        if "transaction_id" in request.data:
            updates.append("transaction_id = %s")
            params.append(request.data["transaction_id"])

        if "description" in request.data:
            updates.append("description = %s")
            params.append(request.data["description"])

        if "planned_at" in request.data:
            updates.append("planned_at = %s")
            params.append(_coerce_datetime_utc_optional(request.data["planned_at"], "planned_at"))

        if "paid_at" in request.data:
            updates.append("paid_at = %s")
            params.append(_coerce_datetime_utc_optional(request.data["paid_at"], "paid_at"))

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(payment_id)  # Add payment_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_payments SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_payment(schema, int(payment_id))
        if not updated:
            return Response({"error": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, payment_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_payments WHERE id = %s", [payment_id])
            if cursor.rowcount == 0:
                return Response({"error": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotesListView(APIView):
    permission_classes = [IsTenantMember]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsTenantOwnerOrEditor()]
        return super().get_permissions()

    def get(self, request):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    id,
                    contact_id,
                    title,
                    content,
                    is_important,
                    created_at,
                    updated_at
                FROM {schema}.crm_notes
                ORDER BY created_at DESC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_note_row(row))

        return Response(payload)

    def post(self, request):
        contact_id = _coerce_int(request.data.get("contact_id"), "contact_id")
        title = _coerce_text(request.data.get("title"), "title")
        content = request.data.get("content", "")
        is_important = request.data.get("is_important", False)

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {schema}.crm_notes 
                (contact_id, title, content, is_important)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                [contact_id, title, content, is_important],
            )
            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать заметку."}, status=status.HTTP_400_BAD_REQUEST)

        note_id = row[0]
        created = _fetch_note(schema, int(note_id))
        if not created:
            created = {
                "id": int(note_id),
                "contact_id": contact_id,
                "title": title,
                "content": content,
                "is_important": bool(is_important),
                "created_at": None,
                "updated_at": None
            }
        return Response(created, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, note_id: int):
        schema = _map_schema()
        note = _fetch_note(schema, int(note_id))
        if not note:
            return Response({"error": "Заметка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(note)

    def patch(self, request, note_id: int):
        schema = _map_schema()
        updates = []
        params = []

        if "contact_id" in request.data:
            updates.append("contact_id = %s")
            params.append(_coerce_int(request.data["contact_id"], "contact_id"))

        if "title" in request.data:
            updates.append("title = %s")
            params.append(_coerce_text(request.data["title"], "title"))

        if "content" in request.data:
            updates.append("content = %s")
            params.append(request.data["content"])

        if "is_important" in request.data:
            updates.append("is_important = %s")
            params.append(request.data["is_important"])

        if not updates:
            return Response({"error": "Нет данных для обновления."}, status=status.HTTP_400_BAD_REQUEST)

        params.append(note_id)  # Add note_id for WHERE clause

        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.crm_notes SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s",
                params,
            )
            if cursor.rowcount == 0:
                return Response({"error": "Заметка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_note(schema, int(note_id))
        if not updated:
            return Response({"error": "Заметка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, note_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.crm_notes WHERE id = %s", [note_id])
            if cursor.rowcount == 0:
                return Response({"error": "Заметка не найдена."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
