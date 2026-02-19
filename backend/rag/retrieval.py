from __future__ import annotations

from collections.abc import Iterable

from django.db import connection

from .config import config
from .embedder import embed_query


def _vector_to_pg(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def semantic_search_kb(query: str, workspace_id: int, top_k: int | None = None) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []

    top_k = max(1, int(top_k or config.top_k))
    query_vector = embed_query(query)
    if not query_vector:
        return []

    sql = """
    WITH vector_search AS (
        SELECT
            id,
            ROW_NUMBER() OVER (ORDER BY content_vector <=> %s::vector) AS rank
        FROM map.kb_chunks
        WHERE workspace_id = %s
          AND content_vector IS NOT NULL
        ORDER BY content_vector <=> %s::vector
        LIMIT %s
    ),
    bm25_search AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(ts_content, plainto_tsquery(%s::regconfig, %s)) DESC
            ) AS rank
        FROM map.kb_chunks
        WHERE workspace_id = %s
          AND ts_content @@ plainto_tsquery(%s::regconfig, %s)
        LIMIT %s
    ),
    rrf AS (
        SELECT
            COALESCE(v.id, b.id) AS id,
            COALESCE(1.0 / (v.rank + %s), 0) + COALESCE(1.0 / (b.rank + %s), 0) AS score
        FROM vector_search v
        FULL OUTER JOIN bm25_search b ON b.id = v.id
    )
    SELECT
        c.id AS chunk_id,
        c.document_id,
        c.chunk_index,
        c.chunk_type,
        c.content,
        c.context,
        d.title,
        d.is_archived,
        r.score
    FROM rrf r
    JOIN map.kb_chunks c ON c.id = r.id
    JOIN map.kb_documents d ON d.id = c.document_id
    WHERE d.is_archived = FALSE
    ORDER BY r.score DESC
    LIMIT %s
    """

    vector_literal = _vector_to_pg(query_vector)
    params = [
        vector_literal,
        workspace_id,
        vector_literal,
        top_k,
        config.ts_language,
        query,
        workspace_id,
        config.ts_language,
        query,
        top_k,
        config.rrf_k,
        config.rrf_k,
        top_k,
    ]

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]
