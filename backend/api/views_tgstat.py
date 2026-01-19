from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence

from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember
from .utils import get_active_client


SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _tgstat_schema() -> str:
    schema = os.getenv("TGSTAT_SCHEMA", "map").strip()
    if not schema or not SCHEMA_RE.match(schema):
        return "map"
    return schema


def _fetch_all(cursor) -> List[Dict[str, Any]]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


class TgstatCategoryListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, slug, title, url
                FROM {schema}.tgstat_categories
                ORDER BY title ASC
                """
            )
            data = _fetch_all(cursor)
        return Response(data)


class TgstatTagListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        raw_category = (
            request.query_params.get("category_id")
            or request.query_params.get("category")
            or ""
        )
        category_slug = str(raw_category).strip()
        if not category_slug:
            return Response(
                {"error": "category is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            if category_slug.isdigit():
                cursor.execute(
                    f"""
                    SELECT t.slug, t.title, t.url, t.category_slug, t.more_channels_count
                    FROM {schema}.tgstat_tags t
                    WHERE t.category_id = %s
                    ORDER BY t.title ASC
                    """,
                    [int(category_slug)],
                )
            else:
                cursor.execute(
                    f"""
                    SELECT slug, title, url, category_slug, more_channels_count
                    FROM {schema}.tgstat_tags
                    WHERE category_slug = %s
                    ORDER BY title ASC
                    """,
                    [category_slug],
                )
            data = _fetch_all(cursor)
        return Response(data)


class TgstatChannelListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        tag_slug = (request.query_params.get("tag") or "").strip()
        raw_category = (
            request.query_params.get("category_id")
            or request.query_params.get("category")
            or ""
        )
        category_slug = str(raw_category).strip()
        if not tag_slug and not category_slug:
            return Response(
                {"error": "tag or category is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            if tag_slug:
                cursor.execute(
                    f"""
                    SELECT id, tag_slug, tag_id, username, title, subscribers, url
                    FROM {schema}.tgstat_tag_channels
                    WHERE tag_slug = %s
                    ORDER BY subscribers DESC NULLS LAST, title ASC
                    """,
                    [tag_slug],
                )
            else:
                if category_slug.isdigit():
                    cursor.execute(
                        f"""
                        SELECT ch.id, ch.tag_slug, ch.tag_id, ch.username, ch.title, ch.subscribers, ch.url
                        FROM {schema}.tgstat_tag_channels ch
                        WHERE ch.category_id = %s
                        ORDER BY ch.subscribers DESC NULLS LAST, ch.title ASC
                        """,
                        [int(category_slug)],
                    )
                else:
                    cursor.execute(
                        f"""
                        SELECT ch.id, ch.tag_slug, ch.tag_id, ch.username, ch.title, ch.subscribers, ch.url
                        FROM {schema}.tgstat_tag_channels ch
                        JOIN {schema}.tgstat_categories c ON c.id = ch.category_id
                        WHERE c.slug = %s
                        ORDER BY ch.subscribers DESC NULLS LAST, ch.title ASC
                        """,
                        [category_slug],
                    )
            data = _fetch_all(cursor)
        return Response(data)


def _normalize_tgstat_ids(raw_ids: Sequence[Any]) -> List[int]:
    ids: List[int] = []
    for item in raw_ids:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value > 0:
            ids.append(value)
    return ids


class TgstatFavoritesView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        client = get_active_client(request.user)
        stored_ids = _normalize_tgstat_ids(client.tgstat_channels or [])
        if not stored_ids:
            return Response([])

        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, tag_slug, tag_id, username, title, subscribers, url
                FROM {schema}.tgstat_tag_channels
                WHERE id = ANY(%s)
                ORDER BY array_position(%s::bigint[], id)
                """,
                [stored_ids, stored_ids],
            )
            data = _fetch_all(cursor)
        return Response(data)

    def post(self, request):
        client = get_active_client(request.user)
        payload = request.data or {}

        channel_id = payload.get("channel_id")
        tag_slug = (payload.get("tag_slug") or "").strip()
        username = (payload.get("username") or "").strip().lstrip("@")

        resolved_id = None
        if channel_id is not None:
            try:
                resolved_id = int(channel_id)
            except (TypeError, ValueError):
                return Response(
                    {"error": "channel_id must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif tag_slug and username:
            schema = _tgstat_schema()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id
                    FROM {schema}.tgstat_tag_channels
                    WHERE tag_slug = %s AND username = %s
                    """,
                    [tag_slug, username],
                )
                row = cursor.fetchone()
            if row:
                resolved_id = row[0]
            else:
                return Response(
                    {"error": "channel not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {"error": "channel_id or (tag_slug, username) is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id
                FROM {schema}.tgstat_tag_channels
                WHERE id = %s
                """,
                [resolved_id],
            )
            if cursor.fetchone() is None:
                return Response(
                    {"error": "channel not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        stored_ids = _normalize_tgstat_ids(client.tgstat_channels or [])
        if resolved_id not in stored_ids:
            stored_ids.append(resolved_id)
            client.tgstat_channels = stored_ids
            client.save(update_fields=["tgstat_channels"])

        return Response({"success": True, "tgstat_channels": stored_ids})

    def delete(self, request):
        client = get_active_client(request.user)
        payload = request.data or {}
        channel_id = payload.get("channel_id") or request.query_params.get("channel_id")
        if channel_id is None:
            return Response(
                {"error": "channel_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "channel_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stored_ids = _normalize_tgstat_ids(client.tgstat_channels or [])
        if channel_id in stored_ids:
            stored_ids = [value for value in stored_ids if value != channel_id]
            client.tgstat_channels = stored_ids
            client.save(update_fields=["tgstat_channels"])

        return Response({"success": True, "tgstat_channels": stored_ids})
