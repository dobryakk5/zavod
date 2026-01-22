from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Sequence

from django.db import connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.ai_generator import AIContentGenerator
from .permissions import IsTenantMember, IsTenantOwnerOrEditor
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


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _build_categories_payload(
    categories: List[Dict[str, Any]],
    tags: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tags_by_category_id: dict[int, list[dict[str, str]]] = defaultdict(list)
    for tag in tags:
        category_id = tag.get("category_id")
        if not isinstance(category_id, int):
            continue
        slug = str(tag.get("slug") or "").strip()
        title = str(tag.get("title") or "").strip()
        if not slug:
            continue
        tags_by_category_id[category_id].append(
            {
                "slug": slug,
                "title": title or slug,
            }
        )

    payload: List[Dict[str, Any]] = []
    for category in categories:
        payload.append(
            {
                "category_slug": str(category.get("slug") or "").strip(),
                "category_title": str(category.get("title") or "").strip(),
                "tags": tags_by_category_id.get(category.get("id"), []),
            }
        )
    return payload


def _normalize_tgstat_recommendations(
    raw_recommendations: Any,
    categories: List[Dict[str, Any]],
    tags: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not isinstance(raw_recommendations, list):
        return []

    categories_by_slug = {str(item.get("slug") or "").strip(): item for item in categories}
    categories_by_title = {
        _normalize_label(item.get("title")): item for item in categories if item.get("title")
    }

    tags_by_slug = {str(item.get("slug") or "").strip(): item for item in tags}
    tags_by_category_slug: dict[str, dict[str, Dict[str, Any]]] = defaultdict(dict)
    tags_by_title: dict[str, dict[str, Dict[str, Any]]] = defaultdict(dict)
    for tag in tags:
        category_slug = str(tag.get("category_slug") or "").strip()
        slug = str(tag.get("slug") or "").strip()
        title = str(tag.get("title") or "").strip()
        if not category_slug or not slug:
            continue
        tags_by_category_slug[category_slug][slug] = tag
        if title:
            tags_by_title[category_slug][_normalize_label(title)] = tag

    ordered_categories: List[str] = []
    normalized: Dict[str, Dict[str, Any]] = {}

    for item in raw_recommendations:
        if not isinstance(item, dict):
            continue

        category_slug = str(item.get("category_slug") or "").strip()
        if not category_slug:
            category_title = str(item.get("category_title") or item.get("category") or "").strip()
            if category_title:
                matched = categories_by_title.get(_normalize_label(category_title))
                if matched:
                    category_slug = str(matched.get("slug") or "").strip()

        if not category_slug or category_slug not in categories_by_slug:
            continue

        entry = normalized.get(category_slug)
        if entry is None:
            category = categories_by_slug[category_slug]
            entry = {
                "category_slug": category_slug,
                "category_title": str(category.get("title") or category_slug),
                "tags": [],
            }
            normalized[category_slug] = entry
            ordered_categories.append(category_slug)

        raw_tags = item.get("tags") or item.get("subcategories") or []
        if not isinstance(raw_tags, list):
            continue

        existing_slugs = {tag["slug"] for tag in entry["tags"] if isinstance(tag, dict) and tag.get("slug")}
        for raw_tag in raw_tags:
            tag_slug = ""
            tag_title = ""
            reason = None
            if isinstance(raw_tag, dict):
                tag_slug = str(raw_tag.get("slug") or "").strip()
                tag_title = str(raw_tag.get("title") or "").strip()
                reason = str(raw_tag.get("reason") or "").strip() or None
            else:
                tag_title = str(raw_tag).strip()
                if tag_title in tags_by_slug:
                    tag_slug = tag_title

            resolved = None
            if tag_slug:
                resolved = tags_by_category_slug.get(category_slug, {}).get(tag_slug)
                if not resolved:
                    candidate = tags_by_slug.get(tag_slug)
                    if candidate and str(candidate.get("category_slug") or "") == category_slug:
                        resolved = candidate
            if not resolved and tag_title:
                resolved = tags_by_title.get(category_slug, {}).get(_normalize_label(tag_title))
            if not resolved:
                continue

            resolved_slug = str(resolved.get("slug") or "").strip()
            if not resolved_slug or resolved_slug in existing_slugs:
                continue
            entry["tags"].append(
                {
                    "slug": resolved_slug,
                    "title": str(resolved.get("title") or resolved_slug),
                    "reason": reason,
                }
            )
            existing_slugs.add(resolved_slug)
            if len(entry["tags"]) >= 10:
                break

    return [normalized[slug] for slug in ordered_categories if normalized.get(slug) and normalized[slug]["tags"]]

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


class TgstatRecommendationsView(APIView):
    permission_classes = [IsTenantOwnerOrEditor]

    def post(self, request):
        client = get_active_client(request.user)
        niche = (client.niche or "").strip()
        product_service = (client.product_service or "").strip()

        missing_fields: list[str] = []
        if not niche:
            missing_fields.append("niche")
        if not product_service:
            missing_fields.append("product_service")
        if missing_fields:
            return Response(
                {"error": "Введите данные проекта", "missing_fields": missing_fields},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schema = _tgstat_schema()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, slug, title
                FROM {schema}.tgstat_categories
                ORDER BY title ASC
                """
            )
            categories = _fetch_all(cursor)
            cursor.execute(
                f"""
                SELECT slug, title, category_id, category_slug
                FROM {schema}.tgstat_tags
                ORDER BY title ASC
                """
            )
            tags = _fetch_all(cursor)

        if not categories or not tags:
            return Response(
                {"success": False, "error": "Нет данных TGStat для рекомендаций"},
                status=status.HTTP_404_NOT_FOUND,
            )

        categories_payload = _build_categories_payload(categories, tags)
        categories_json = json.dumps(categories_payload, ensure_ascii=False, separators=(",", ":"))

        try:
            generator = AIContentGenerator()
        except ValueError as exc:
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        result = generator.generate_tgstat_tag_recommendations(
            niche=niche,
            product_service=product_service,
            categories_json=categories_json,
            language="ru",
        )
        if not result.get("success"):
            return Response(
                {
                    "success": False,
                    "error": "Не удалось получить рекомендации",
                    "details": result.get("error"),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        recommendations = _normalize_tgstat_recommendations(
            result.get("recommendations"),
            categories,
            tags,
        )

        return Response(
            {
                "success": True,
                "niche": niche,
                "product_service": product_service,
                "recommendations": recommendations,
            }
        )
