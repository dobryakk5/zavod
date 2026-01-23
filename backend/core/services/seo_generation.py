from datetime import timedelta

from django.utils import timezone

from ..models import SEOKeywordSet

SEO_GENERATION_TIMEOUT = timedelta(minutes=10)


def _inflight_queryset(client):
    return SEOKeywordSet.objects.filter(
        client=client,
        status__in=["pending", "generating"],
    )


def expire_stale_generations(client) -> int:
    cutoff = timezone.now() - SEO_GENERATION_TIMEOUT
    stale_qs = _inflight_queryset(client).filter(updated_at__lt=cutoff)
    count = stale_qs.count()
    if count:
        stale_qs.update(status="failed", error_log="Timed out after 10 minutes")
    return count


def has_active_generation(client) -> bool:
    expire_stale_generations(client)
    return _inflight_queryset(client).exists()


def cancel_active_generation(client, reason: str = "Canceled by user") -> int:
    qs = _inflight_queryset(client)
    count = qs.count()
    if count:
        qs.update(status="failed", error_log=reason)
    return count
