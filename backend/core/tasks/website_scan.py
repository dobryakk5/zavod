import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from ..models import Client, WebsiteScan
from ..services.website_scan_service import run_website_scan

logger = logging.getLogger(__name__)

def maybe_schedule_next_website_scan_for_client(client_id: int) -> int | None:
    """
    Ensure there is at most one running website scan per client.

    If nothing is running, pick the oldest pending scan and start it.
    """

    scan_id: int | None = None

    with transaction.atomic():
        # Per-tenant lock to avoid concurrent scheduling races.
        Client.objects.select_for_update().get(id=client_id)

        if WebsiteScan.objects.filter(client_id=client_id, status=WebsiteScan.STATUS_IN_PROGRESS).exists():
            return None

        next_scan = (
            WebsiteScan.objects.filter(client_id=client_id, status=WebsiteScan.STATUS_PENDING)
            .order_by("created_at", "id")
            .first()
        )
        if not next_scan:
            return None

        next_scan.status = WebsiteScan.STATUS_IN_PROGRESS
        next_scan.started_at = next_scan.started_at or timezone.now()
        next_scan.progress = 0
        next_scan.error = ""
        next_scan.pages_total = None
        next_scan.save(update_fields=["status", "started_at", "progress", "error", "pages_total", "updated_at"])
        scan_id = int(next_scan.id)

        def _schedule():
            try:
                async_result = run_website_scan_task.delay(scan_id)
                WebsiteScan.objects.filter(id=scan_id).update(task_id=str(async_result.id), updated_at=timezone.now())
            except Exception:
                logger.warning("Failed to enqueue WebsiteScan %s", scan_id, exc_info=True)

        transaction.on_commit(_schedule)

    return scan_id


@shared_task
def run_website_scan_task(scan_id: int):
    logger.info("WebsiteScan task start: id=%s", scan_id)
    client_id: int | None = None
    try:
        scan = WebsiteScan.objects.select_related("client").get(id=scan_id)
        client_id = int(scan.client_id)
        run_website_scan(scan_id)
    except WebsiteScan.DoesNotExist:
        logger.error("WebsiteScan %s not found", scan_id)
        return None
    except Exception as exc:
        logger.error("WebsiteScan %s failed: %s", scan_id, exc, exc_info=True)
        try:
            WebsiteScan.objects.filter(id=scan_id).update(
                status=WebsiteScan.STATUS_FAILED,
                error=str(exc),
                finished_at=timezone.now(),
                updated_at=timezone.now(),
            )
        except Exception:
            pass
        if client_id is not None:
            try:
                maybe_schedule_next_website_scan_for_client(client_id)
            except Exception:
                logger.warning("Failed to schedule next WebsiteScan for client %s", client_id, exc_info=True)
        return None

    if client_id is not None:
        try:
            maybe_schedule_next_website_scan_for_client(client_id)
        except Exception:
            logger.warning("Failed to schedule next WebsiteScan for client %s", client_id, exc_info=True)

    logger.info("WebsiteScan task done: id=%s", scan_id)
    return scan_id
