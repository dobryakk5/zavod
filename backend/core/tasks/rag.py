import logging

from celery import shared_task
from django.conf import settings

from core.models import KbDocument

logger = logging.getLogger(__name__)


@shared_task
def process_pending_kb_rag_indexing(limit: int | None = None) -> dict:
    logger.info("Beat tick process_pending_kb_rag_indexing: limit=%s", limit)
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

    # Import lazily to avoid pulling RAG pipeline at worker startup.
    from rag.ingestion import index_document

    candidate_ids = list(
        KbDocument.objects.filter(
            is_archived=False,
            index_status__in=["pending", "failed"],
        )
        .order_by("updated_at", "id")
        .values_list("id", flat=True)[:batch_size]
    )

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
