import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from core.models import CompetitorSite

logger = logging.getLogger(__name__)


@shared_task
def analyze_competitor_site_task(site_id: int) -> int | None:
    """
    Background competitor analysis:
    - fetch homepage
    - extract links to services/prices from homepage
    - fetch services+prices pages (max 3 pages total)
    - call AI and persist summary
    """
    try:
        with transaction.atomic():
            site = CompetitorSite.objects.select_for_update().get(id=site_id)
            if site.analysis_status == "in_progress":
                return site_id
            site.analysis_status = "in_progress"
            site.analysis_error = ""
            site.updated_at = timezone.now()
            site.save(update_fields=["analysis_status", "analysis_error", "updated_at"])
    except CompetitorSite.DoesNotExist:
        logger.warning("CompetitorSite %s not found", site_id)
        return None
    except Exception:
        logger.warning("Failed to lock CompetitorSite %s", site_id, exc_info=True)
        return None

    try:
        from core.services.website_ai_analyzer import analyze_website_for_competitor_insights

        analysis = analyze_website_for_competitor_insights(site.base_url or f"https://{site.domain}/", max_pages=3)
        with transaction.atomic():
            site = CompetitorSite.objects.select_for_update().get(id=site_id)
            site.home_title = (analysis.home_title or "")[:512]
            site.home_text = (analysis.home_text or "")[:60000]
            site.services_url = (analysis.services_url or "")[:700] if analysis.services_url else ""
            site.prices_url = (analysis.prices_url or "")[:700] if analysis.prices_url else ""
            site.ai_is_competitor = bool(analysis.is_competitor)
            site.ai_one_liner = (analysis.one_liner or "")[:4000]
            site.ai_pricing = (analysis.pricing or "")[:4000]
            site.last_analyzed_at = timezone.now()
            site.analysis_status = "completed"
            site.analysis_error = ""
            site.updated_at = timezone.now()
            site.save(
                update_fields=[
                    "home_title",
                    "home_text",
                    "services_url",
                    "prices_url",
                    "ai_is_competitor",
                    "ai_one_liner",
                    "ai_pricing",
                    "last_analyzed_at",
                    "analysis_status",
                    "analysis_error",
                    "updated_at",
                ]
            )
    except Exception as exc:
        logger.error("CompetitorSite analysis failed: id=%s err=%s", site_id, exc, exc_info=True)
        try:
            CompetitorSite.objects.filter(id=site_id).update(
                analysis_status="failed",
                analysis_error=str(exc),
                updated_at=timezone.now(),
            )
        except Exception:
            pass
        return None

    return site_id
