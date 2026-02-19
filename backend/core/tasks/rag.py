import logging

from celery import shared_task
from django.conf import settings
from django.db import connection

from core.models import KbDocument

logger = logging.getLogger(__name__)
RAG_INDEX_TASK_LOCK_KEY = 982451653


def _try_acquire_task_lock() -> bool:
    if connection.vendor != "postgresql":
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [RAG_INDEX_TASK_LOCK_KEY])
        row = cursor.fetchone()
    return bool(row and row[0])


def _release_task_lock() -> None:
    if connection.vendor != "postgresql":
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [RAG_INDEX_TASK_LOCK_KEY])
    except Exception:
        logger.exception("Failed to release RAG advisory lock")


@shared_task
def process_pending_kb_rag_indexing(limit: int | None = None) -> dict:
    logger.info("Beat tick process_pending_kb_rag_indexing: limit=%s", limit)
    lock_acquired = _try_acquire_task_lock()
    if not lock_acquired:
        logger.info("Beat tick process_pending_kb_rag_indexing skipped: previous run still active")
        return {"total": 0, "indexed": 0, "skipped": 0, "missing": 0, "failed": 0, "locked": True}

    try:
        if not getattr(settings, "RAG_INDEXING_ENABLED", True):
            logger.info("Beat tick process_pending_kb_rag_indexing skipped: RAG indexing disabled")
            return {
                "total": 0,
                "indexed": 0,
                "skipped": 0,
                "missing": 0,
                "failed": 0,
                "disabled": True,
            }

        batch_size = int(limit or getattr(settings, "RAG_INDEX_BATCH_SIZE", 25))
        if batch_size <= 0:
            logger.info("Beat tick process_pending_kb_rag_indexing skipped: batch_size=%s", batch_size)
            return {"total": 0, "indexed": 0, "skipped": 0, "missing": 0, "failed": 0}

        candidate_ids = list(
            KbDocument.objects.filter(
                is_archived=False,
                index_status__in=["pending", "failed"],
            )
            .order_by("updated_at", "id")
            .values_list("id", flat=True)[:batch_size]
        )

        if not candidate_ids:
            logger.info("Beat tick process_pending_kb_rag_indexing: no pending documents")
            return {"total": 0, "indexed": 0, "skipped": 0, "missing": 0, "failed": 0}

        # Import lazily only when there is actual indexing work.
        from rag.ingestion import index_document

        stats = {"total": len(candidate_ids), "indexed": 0, "skipped": 0, "missing": 0, "failed": 0}

        for document_id in candidate_ids:
            claimed = KbDocument.objects.filter(
                id=document_id,
                index_status__in=["pending", "failed"],
            ).update(index_status="indexing", index_error=None)
            if not claimed:
                continue

            result = index_document(document_id)
            status = result.get("status")
            if status == "ok":
                stats["indexed"] += 1
            elif status == "missing":
                stats["missing"] += 1
            elif status == "failed":
                stats["failed"] += 1
            else:
                stats["skipped"] += 1

        logger.info(
            "Beat tick process_pending_kb_rag_indexing done: total=%s indexed=%s skipped=%s missing=%s failed=%s",
            stats["total"],
            stats["indexed"],
            stats["skipped"],
            stats["missing"],
            stats["failed"],
        )

        return stats
    finally:
        _release_task_lock()
