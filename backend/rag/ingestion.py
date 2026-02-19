from __future__ import annotations

import json
import logging
from typing import Iterable, Optional

from django.db import connection, transaction
from django.utils import timezone

from core.models import KbDocument

from .config import config
from .context_llm import generate_context_batch
from .embedder import embed_passages
from .tiptap_parser import ParsedChunk, parse_tiptap

logger = logging.getLogger(__name__)


def _set_document_index_state(
    document_id: int,
    *,
    status: str,
    error: str | None = None,
    indexed_at: object = None,
    update_indexed_at: bool = False,
) -> None:
    payload: dict[str, object] = {
        "index_status": status,
        "index_error": error,
    }
    if update_indexed_at:
        payload["indexed_at"] = indexed_at
    KbDocument.objects.filter(id=document_id).update(**payload)


def _vector_to_pg(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def split_text_chunk(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunk_size = max(1, config.chunk_size)
    step = max(1, chunk_size - max(0, config.chunk_overlap))
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        start += step
    return chunks


def prepare_chunks(parsed: list[ParsedChunk]) -> list[ParsedChunk]:
    result: list[ParsedChunk] = []
    for item in parsed:
        if item.chunk_type == "text":
            for part in split_text_chunk(item.content):
                result.append(ParsedChunk(content=part, chunk_type="text"))
        else:
            result.append(item)
    return result


def _as_tiptap_document(content: object) -> Optional[dict]:
    data = content
    if isinstance(content, str):
        raw = content.strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except ValueError:
            return None

    if not isinstance(data, dict):
        return None

    if data.get("type") == "doc" and isinstance(data.get("content"), list):
        return data

    if isinstance(data.get("content"), list):
        return {"type": "doc", "content": data["content"]}

    return None


def _build_embed_inputs(chunks: list[ParsedChunk], contexts: list[str]) -> list[str]:
    payload: list[str] = []
    for chunk, context in zip(chunks, contexts):
        context = (context or "").strip()
        if chunk.chunk_type in {"table", "formula"}:
            payload.append(context or chunk.content)
        else:
            merged = f"{context}\n{chunk.content}".strip() if context else chunk.content
            payload.append(merged)
    return payload


def index_document(document_id: int) -> dict:
    document = KbDocument.objects.filter(id=document_id).first()
    if document is None:
        return {"status": "missing", "document_id": document_id, "indexed_chunks": 0}

    _set_document_index_state(document.id, status="indexing", error=None)

    try:
        tiptap_doc = _as_tiptap_document(document.content)
        if tiptap_doc is None:
            logger.info("Skip RAG indexing for kb document %s: content is not tiptap JSON", document.id)
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM map.kb_chunks WHERE document_id = %s", [document.id])
            _set_document_index_state(
                document.id,
                status="skipped",
                error="Content is not valid tiptap JSON.",
                indexed_at=timezone.now(),
                update_indexed_at=True,
            )
            return {"status": "skipped", "document_id": document.id, "indexed_chunks": 0}

        parsed = parse_tiptap(tiptap_doc)
        chunks = prepare_chunks(parsed)
        if not chunks:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM map.kb_chunks WHERE document_id = %s", [document.id])
            _set_document_index_state(
                document.id,
                status="indexed",
                error=None,
                indexed_at=timezone.now(),
                update_indexed_at=True,
            )
            return {"status": "ok", "document_id": document.id, "indexed_chunks": 0}

        raw_text = " ".join(item.content for item in parsed if item.chunk_type == "text")
        contents = [item.content for item in chunks]
        chunk_types = [item.chunk_type for item in chunks]
        contexts = generate_context_batch(raw_text, contents, chunk_types)
        embed_inputs = _build_embed_inputs(chunks, contexts)
        vectors = embed_passages(embed_inputs)

        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding result length mismatch")

        params: list[tuple] = []
        for index, (chunk, context, vector) in enumerate(zip(chunks, contexts, vectors)):
            params.append(
                (
                    document.id,
                    document.workspace_id,
                    index,
                    chunk.chunk_type,
                    chunk.content,
                    context or None,
                    _vector_to_pg(vector),
                    config.e5_model_path,
                )
            )

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM map.kb_chunks WHERE document_id = %s", [document.id])
                cursor.executemany(
                    """
                    INSERT INTO map.kb_chunks
                        (document_id, workspace_id, chunk_index, chunk_type, content, context, content_vector, embedding_model)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s::vector, %s)
                    """,
                    params,
                )

        _set_document_index_state(
            document.id,
            status="indexed",
            error=None,
            indexed_at=timezone.now(),
            update_indexed_at=True,
        )
        return {
            "status": "ok",
            "document_id": document.id,
            "indexed_chunks": len(params),
        }
    except Exception as exc:
        logger.exception("RAG indexing failed for kb document %s", document.id)
        _set_document_index_state(
            document.id,
            status="failed",
            error=str(exc)[:2000],
            indexed_at=None,
            update_indexed_at=True,
        )
        return {
            "status": "failed",
            "document_id": document.id,
            "indexed_chunks": 0,
            "error": str(exc),
        }


def reindex_kb_documents(
    *,
    workspace_id: int | None = None,
    document_id: int | None = None,
    include_archived: bool = False,
    limit: int | None = None,
) -> dict:
    query = KbDocument.objects.all().order_by("id")
    if workspace_id is not None:
        query = query.filter(workspace_id=workspace_id)
    if document_id is not None:
        query = query.filter(id=document_id)
    if not include_archived:
        query = query.filter(is_archived=False)
    if limit is not None and limit > 0:
        query = query[:limit]

    total = 0
    indexed = 0
    skipped = 0
    missing = 0
    failed = 0

    for item in query:
        total += 1
        result = index_document(item.id)
        status = result.get("status")
        if status == "ok":
            indexed += 1
        elif status == "missing":
            missing += 1
        elif status == "failed":
            failed += 1
        else:
            skipped += 1

    return {
        "total": total,
        "indexed": indexed,
        "skipped": skipped,
        "missing": missing,
        "failed": failed,
    }
