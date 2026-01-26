from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from django.db import IntegrityError, connection
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember, IsTenantOwnerOrEditor


SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TAG_TYPES = {"goal", "pain", "experience"}


def _map_schema() -> str:
    schema = os.getenv("MAP_SCHEMA", "map").strip()
    if not schema or not SCHEMA_RE.match(schema):
        return "map"
    return schema


def _fetch_all(cursor) -> List[Dict[str, Any]]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _coerce_int(value: Any, field_name: str) -> int:
    if value is None or value == "":
        raise ValidationError({field_name: "Поле обязательно."})
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: "Нужно число."})

def _coerce_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError({field_name: "Поле обязательно."})
    return text


def _validate_tag_type(value: Any) -> str:
    tag_type = str(value or "").strip().lower()
    if tag_type not in TAG_TYPES:
        raise ValidationError({"type": "Недопустимая категория."})
    return tag_type


def _normalize_tag_ids(value: Any) -> List[int]:
    if not value:
        return []
    return [int(item) for item in value]

def _serialize_client_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "tags": {
            "goal": _normalize_tag_ids(row.get("goal_tags")),
            "pain": _normalize_tag_ids(row.get("pain_tags")),
            "experience": _normalize_tag_ids(row.get("experience_tags")),
        },
    }


def _fetch_client(schema: str, client_id: int) -> Dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                c.id,
                c.name,
                COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'goal'), ARRAY[]::int[]) AS goal_tags,
                COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'pain'), ARRAY[]::int[]) AS pain_tags,
                COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'experience'), ARRAY[]::int[]) AS experience_tags
            FROM {schema}.clients c
            LEFT JOIN {schema}.client_tags ct ON ct.client_id = c.id
            LEFT JOIN {schema}.tags t ON t.id = ct.tag_id
            WHERE c.id = %s
            GROUP BY c.id, c.name
            """,
            [client_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return _serialize_client_row(dict(zip(columns, row)))


def _fetch_tag(schema: str, tag_id: int) -> Dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT id, type, value
            FROM {schema}.tags
            WHERE id = %s
            """,
            [tag_id],
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))


class ClientsListView(APIView):
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
                    c.id,
                    c.name,
                    COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'goal'), ARRAY[]::int[]) AS goal_tags,
                    COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'pain'), ARRAY[]::int[]) AS pain_tags,
                    COALESCE(ARRAY_AGG(t.id) FILTER (WHERE t.type = 'experience'), ARRAY[]::int[]) AS experience_tags
                FROM {schema}.clients c
                LEFT JOIN {schema}.client_tags ct ON ct.client_id = c.id
                LEFT JOIN {schema}.tags t ON t.id = ct.tag_id
                GROUP BY c.id, c.name
                ORDER BY c.name ASC
                """
            )
            rows = _fetch_all(cursor)

        payload = []
        for row in rows:
            payload.append(_serialize_client_row(row))

        return Response(payload)

    def post(self, request):
        name = _coerce_text(request.data.get("name"), "name")
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {schema}.clients (name) VALUES (%s) RETURNING id",
                [name],
            )
            row = cursor.fetchone()
        client_id = row[0] if row else None
        if not client_id:
            return Response({"error": "Не удалось создать клиента."}, status=status.HTTP_400_BAD_REQUEST)
        created = _fetch_client(schema, int(client_id))
        if not created:
            created = {"id": int(client_id), "name": name, "tags": {"goal": [], "pain": [], "experience": []}}
        return Response(created, status=status.HTTP_201_CREATED)


class ClientDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, client_id: int):
        name = _coerce_text(request.data.get("name"), "name")
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {schema}.clients SET name = %s WHERE id = %s",
                [name, client_id],
            )
            if cursor.rowcount == 0:
                return Response({"error": "Клиент не найден."}, status=status.HTTP_404_NOT_FOUND)

        updated = _fetch_client(schema, int(client_id))
        if not updated:
            return Response({"error": "Клиент не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(updated)

    def delete(self, request, client_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.clients WHERE id = %s", [client_id])
            if cursor.rowcount == 0:
                return Response({"error": "Клиент не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
                SELECT id, type, value
                FROM {schema}.tags
                ORDER BY type ASC, value ASC
                """
            )
            data = _fetch_all(cursor)
        return Response(data)

    def post(self, request):
        tag_type = _validate_tag_type(request.data.get("type"))
        value = _coerce_text(request.data.get("value"), "value")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT 1 FROM {schema}.tags WHERE type = %s AND value = %s",
                [tag_type, value],
            )
            if cursor.fetchone():
                return Response({"error": "Такой тег уже существует."}, status=status.HTTP_409_CONFLICT)

            try:
                cursor.execute(
                    f"INSERT INTO {schema}.tags (type, value) VALUES (%s, %s) RETURNING id, type, value",
                    [tag_type, value],
                )
            except IntegrityError:
                return Response({"error": "Такой тег уже существует."}, status=status.HTTP_409_CONFLICT)

            row = cursor.fetchone()

        if not row:
            return Response({"error": "Не удалось создать тег."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": row[0], "type": row[1], "value": row[2]}, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def patch(self, request, tag_id: int):
        schema = _map_schema()
        existing = _fetch_tag(schema, int(tag_id))
        if not existing:
            return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)

        next_type = existing.get("type")
        next_value = existing.get("value")

        if "type" in request.data:
            next_type = _validate_tag_type(request.data.get("type"))
        if "value" in request.data:
            next_value = _coerce_text(request.data.get("value"), "value")

        if next_type == existing.get("type") and next_value == existing.get("value"):
            return Response(existing)

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT 1
                FROM {schema}.tags
                WHERE type = %s AND value = %s AND id <> %s
                """,
                [next_type, next_value, tag_id],
            )
            if cursor.fetchone():
                return Response({"error": "Такой тег уже существует."}, status=status.HTTP_409_CONFLICT)

            try:
                cursor.execute(
                    f"UPDATE {schema}.tags SET type = %s, value = %s WHERE id = %s RETURNING id, type, value",
                    [next_type, next_value, tag_id],
                )
            except IntegrityError:
                return Response({"error": "Такой тег уже существует."}, status=status.HTTP_409_CONFLICT)

            row = cursor.fetchone()

        if not row:
            return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"id": row[0], "type": row[1], "value": row[2]})

    def delete(self, request, tag_id: int):
        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {schema}.tags WHERE id = %s", [tag_id])
            if cursor.rowcount == 0:
                return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientTagsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client_id = _coerce_int(request.data.get("clientId") or request.data.get("client_id"), "clientId")
        tag_id = _coerce_int(request.data.get("tagId") or request.data.get("tag_id"), "tagId")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {schema}.clients WHERE id = %s", [client_id])
            if cursor.fetchone() is None:
                return Response({"error": "Клиент не найден."}, status=status.HTTP_404_NOT_FOUND)

            cursor.execute(f"SELECT 1 FROM {schema}.tags WHERE id = %s", [tag_id])
            if cursor.fetchone() is None:
                return Response({"error": "Тег не найден."}, status=status.HTTP_404_NOT_FOUND)

            cursor.execute(
                f"""
                INSERT INTO {schema}.client_tags (client_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                [client_id, tag_id],
            )

        return Response({"success": True}, status=status.HTTP_200_OK)

    def delete(self, request):
        client_id = _coerce_int(request.data.get("clientId") or request.data.get("client_id"), "clientId")
        tag_id = _coerce_int(request.data.get("tagId") or request.data.get("tag_id"), "tagId")

        schema = _map_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {schema}.client_tags WHERE client_id = %s AND tag_id = %s",
                [client_id, tag_id],
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
