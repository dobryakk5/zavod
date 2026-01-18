from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember
from .utils import enforce_generation_limit, get_active_client
from core.generation_events import record_generation_event
from core.models import CompetitorSite, GenerationEvent
from core.services.website_ai_analyzer import analyze_websites_for_competitor_insights
from core.tasks.competitors import analyze_competitor_site_task

logger = logging.getLogger(__name__)


def _get_google_api_key() -> str:
    return (getattr(settings, "GOOGLE_API_KEY", "") or "").strip()


def _get_google_cse_id() -> str:
    return (getattr(settings, "GOOGLE_CSE_ID", "") or "").strip()


class GoogleCSESearchView(APIView):
    """
    Proxy for Google Custom Search JSON API (CSE).

    Keeps the API key on the backend; returns a normalized list of results.
    """

    permission_classes = [IsTenantMember]

    def get(self, request, *args, **kwargs):
        api_key = _get_google_api_key()
        cx = _get_google_cse_id()

        if not api_key:
            return Response(
                {"detail": "Не задан ключ Google API (env: Google_API_KEY / GOOGLE_API_KEY)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not cx:
            return Response(
                {"detail": "Не задан Google CSE ID (env: CSE_ID / GOOGLE_CSE_ID / GOOGLE_CX)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = str(request.query_params.get("q") or "").strip()
        if not query:
            raise ValidationError({"q": "Введите поисковый запрос"})

        client = get_active_client(request.user)
        limit_response = enforce_generation_limit(client, GenerationEvent.EVENT_GOOGLE_QUERY)
        if limit_response:
            return limit_response

        try:
            num = int(request.query_params.get("num") or 10)
        except (TypeError, ValueError):
            num = 10
        num = max(1, min(num, 10))

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": num,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
        except requests.RequestException:
            logger.warning("Google CSE request failed (network)", exc_info=True)
            return Response(
                {"detail": "Не удалось связаться с Google Custom Search"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = None

            error_message = None
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    error_message = error.get("message")

            logger.warning(
                "Google CSE returned %s for q=%r payload=%r body=%r",
                response.status_code,
                query,
                payload,
                (response.text or "")[:2000],
            )
            return Response(
                {"detail": error_message or "Google вернул ошибку", "status_code": response.status_code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        try:
            data = response.json()
        except ValueError:
            return Response(
                {"detail": "Google вернул некорректный JSON"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        results: list[dict] = []
        for idx, item in enumerate((data or {}).get("items", []) or [], start=1):
            try:
                results.append(
                    {
                        "position": idx,
                        "title": item["title"],
                        "url": item["link"],
                        "domain": item.get("displayLink") or "",
                        "snippet": item.get("snippet") or "",
                    }
                )
            except Exception:
                continue

        record_generation_event(
            client,
            GenerationEvent.EVENT_GOOGLE_QUERY,
            meta={"query": query},
        )

        return Response({"query": query, "results": results})


class GoogleCompetitorsAnalyzeView(APIView):
    """
    Analyze competitor websites (homepage + pricing/services pages) via default AI model.

    Input: { "urls": ["https://example.com/page", ...], "max_sites": 5, "max_pages_per_site": 4 }
    """

    permission_classes = [IsTenantMember]

    def post(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, dict) else {}
        urls = data.get("urls") or []
        if not isinstance(urls, list):
            raise ValidationError({"urls": "Ожидается массив URL"})
        urls = [str(u or "").strip() for u in urls if str(u or "").strip()]
        if not urls:
            raise ValidationError({"urls": "Передайте хотя бы один URL"})

        try:
            max_sites = int(data.get("max_sites") or 5)
        except (TypeError, ValueError):
            max_sites = 5
        max_sites = max(1, min(max_sites, 10))

        # Per spec: only 3 pages per site (home + services + prices)
        max_pages_per_site = 3

        results = analyze_websites_for_competitor_insights(
            urls,
            max_sites=max_sites,
            max_pages_per_site=max_pages_per_site,
        )

        payload = []
        for item in results:
            payload.append(
                {
                    "input_url": item.input_url,
                    "base_url": item.base_url,
                    "is_competitor": item.is_competitor,
                    "one_liner": item.one_liner,
                    "offers": item.offers,
                    "pricing": item.pricing,
                    "home_title": item.home_title,
                    "home_text": item.home_text,
                    "services_url": item.services_url,
                    "prices_url": item.prices_url,
                    "evidence_urls": item.evidence_urls,
                    "error": item.error,
                }
            )

        return Response({"results": payload})


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
        domain = (parsed.netloc or "").strip().lower()
    except Exception:
        domain = raw.strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain.endswith("."):
        domain = domain[:-1]
    return domain


def _root_domain(value: str) -> str:
    domain = _normalize_domain(value)
    if not domain:
        return ""
    parts = [part for part in domain.split(".") if part]
    if len(parts) <= 2:
        return domain
    return ".".join(parts[-2:])


def _root_domain_query(roots: list[str]) -> Q:
    query = Q()
    for root in roots:
        if not root:
            continue
        query |= Q(domain=root) | Q(domain__iendswith=f".{root}")
    return query


def _origin_from_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
    return ""


MANUAL_COMPETITOR_CATEGORIES = {"competitor", "informational", "indirect", "other"}


def _manual_category_from_site(site: CompetitorSite) -> str | None:
    if getattr(site, "manual_category", None):
        return site.manual_category
    if site.manual_is_competitor is True:
        return "competitor"
    if site.manual_is_competitor is False:
        return "other"
    return None


def _manual_is_competitor_from_category(category: str | None) -> bool | None:
    if category == "competitor":
        return True
    if category in {"informational", "indirect", "other"}:
        return False
    return None


class GoogleCompetitorsStoreView(APIView):
    """
    Persist competitor sites (deduplicated by domain per client).

    Input: { "query": "...", "results": [{ "url": "...", "domain": "example.com" }, ...] }
    """

    permission_classes = [IsTenantMember]

    def post(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, dict) else {}
        query = str(data.get("query") or "").strip()[:512]
        results = data.get("results") or []
        if not isinstance(results, list):
            raise ValidationError({"results": "Ожидается массив результатов Google"})

        client = get_active_client(request.user)

        domains_seen: set[str] = set()
        created = 0
        updated = 0

        for item in results[:50]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            display_domain = str(item.get("domain") or "").strip()

            normalized_domain = _normalize_domain(display_domain) or _normalize_domain(url)
            domain = _root_domain(normalized_domain)
            if not domain:
                continue
            if domain in domains_seen:
                continue
            domains_seen.add(domain)

            base_url = _origin_from_url(url) or f"https://{domain}/"

            existing = CompetitorSite.objects.filter(client=client).filter(
                Q(domain=domain) | Q(domain__iendswith=f".{domain}")
            ).order_by("-updated_at").first()

            if existing:
                obj = existing
                was_created = False
            else:
                try:
                    obj = CompetitorSite.objects.create(
                        client=client,
                        domain=domain,
                        base_url=base_url,
                        first_seen_query=query,
                        last_seen_query=query,
                    )
                    was_created = True
                except IntegrityError:
                    obj = CompetitorSite.objects.filter(client=client, domain=domain).first()
                    was_created = False

            if not obj:
                continue

            if was_created:
                created += 1
                continue

            fields_to_update: list[str] = []
            if query and obj.last_seen_query != query:
                obj.last_seen_query = query
                fields_to_update.append("last_seen_query")
            if base_url and (not obj.base_url or obj.base_url != base_url):
                obj.base_url = base_url
                fields_to_update.append("base_url")
            if fields_to_update:
                obj.updated_at = timezone.now()
                fields_to_update.append("updated_at")
                obj.save(update_fields=fields_to_update)
                updated += 1

        return Response(
            {
                "success": True,
                "query": query,
                "domains_seen": len(domains_seen),
                "created": created,
                "updated": updated,
            }
        )


class GoogleCompetitorsSitesView(APIView):
    """
    List stored competitor sites for the active client.
    """

    permission_classes = [IsTenantMember]

    def get(self, request, *args, **kwargs):
        client = get_active_client(request.user)
        qs = CompetitorSite.objects.filter(client=client).order_by("-updated_at")[:200]
        payload = []
        for row in qs:
            payload.append(
                {
                    "domain": row.domain,
                    "base_url": row.base_url,
                    "first_seen_query": row.first_seen_query,
                    "last_seen_query": row.last_seen_query,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
        return Response({"results": payload})


class GoogleCompetitorsResolveView(APIView):
    """
    One-shot flow:
    1) accept Google results (query + urls/domains/titles)
    2) check CompetitorSite cache by domain
    3) analyze only new/unknown (fetch home+services+prices, AI summary)
    4) return unified "Google results" list enriched with homepage text and cached analysis
    """

    permission_classes = [IsTenantMember]

    def post(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, dict) else {}
        query = str(data.get("query") or "").strip()[:512]
        results = data.get("results") or []
        if not isinstance(results, list):
            raise ValidationError({"results": "Ожидается массив результатов Google"})

        client = get_active_client(request.user)

        try:
            max_results = int(data.get("max_results") or 10)
        except (TypeError, ValueError):
            max_results = 10
        max_results = max(1, min(max_results, 10))

        enriched: list[dict] = []
        domains_in_request: list[str] = []
        incoming_rows: list[dict] = []
        domains_seen: set[str] = set()

        for idx, item in enumerate(results[:max_results], start=1):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            display_domain = str(item.get("domain") or "").strip()
            if not url and not display_domain:
                continue
            normalized_domain = _normalize_domain(display_domain) or _normalize_domain(url)
            root_domain = _root_domain(normalized_domain)
            if not root_domain:
                continue
            if root_domain in domains_seen:
                continue
            domains_seen.add(root_domain)
            base_url = _origin_from_url(url) or f"https://{root_domain}/"
            incoming_rows.append(
                {
                    "position": idx,
                    "title": title,
                    "url": url or base_url,
                    "domain": root_domain,
                    "base_url": base_url,
                }
            )
            domains_in_request.append(root_domain)

        existing_rows = {}
        if domains_in_request:
            root_query = _root_domain_query(domains_in_request)
            for row in CompetitorSite.objects.filter(client=client).filter(root_query).order_by("-updated_at"):
                root = _root_domain(row.domain)
                if not root:
                    continue
                if root not in existing_rows:
                    existing_rows[root] = row

        # Ensure all domains are persisted (dedupe constraint handles repeats).
        for row in incoming_rows:
            domain = row["domain"]
            base_url = row["base_url"]
            obj = existing_rows.get(domain)
            if obj:
                if query and obj.last_seen_query != query:
                    obj.last_seen_query = query
                if not obj.first_seen_query and query:
                    obj.first_seen_query = query
                if base_url and (not obj.base_url or obj.base_url != base_url):
                    obj.base_url = base_url
                obj.updated_at = timezone.now()
                obj.save(update_fields=["last_seen_query", "first_seen_query", "base_url", "updated_at"])
                continue

            try:
                obj = CompetitorSite.objects.create(
                    client=client,
                    domain=domain,
                    base_url=base_url,
                    first_seen_query=query,
                    last_seen_query=query,
                )
            except IntegrityError:
                obj = CompetitorSite.objects.filter(client=client, domain=domain).first()
            if obj:
                existing_rows[domain] = obj

        scheduled = 0

        def _enqueue(site_id: int) -> None:
            try:
                async_result = analyze_competitor_site_task.delay(site_id)
                CompetitorSite.objects.filter(id=site_id).update(
                    task_id=str(async_result.id),
                    updated_at=timezone.now(),
                )
            except Exception:
                logger.warning("Failed to enqueue competitor analysis: site_id=%s", site_id, exc_info=True)

        # Analyze only those without cached homepage text + AI decision, but do it via Celery.
        for row in incoming_rows:
            domain = row["domain"]
            initial_obj = existing_rows.get(domain)
            if not initial_obj:
                enriched.append(
                    {
                        **row,
                        "cached": False,
                        "analysis_status": "failed",
                        "analysis_error": "missing_db_row",
                        "last_seen_query": query,
                        "manual_category": None,
                        "manual_is_competitor": None,
                        "is_competitor": False,
                        "one_liner": "",
                        "pricing": "",
                        "home_title": "",
                        "home_text": "",
                        "services_url": None,
                        "prices_url": None,
                    }
                )
                continue

            # Lock the row to avoid double-enqueue across concurrent requests.
            with transaction.atomic():
                obj = CompetitorSite.objects.select_for_update().get(id=initial_obj.id)
                cached = bool(
                    (obj.home_text or "").strip()
                    and obj.ai_is_competitor is not None
                    and (obj.ai_one_liner or "").strip()
                )

                if cached and obj.analysis_status != "completed":
                    obj.analysis_status = "completed"
                    obj.analysis_error = ""
                    obj.task_id = obj.task_id or ""
                    obj.updated_at = timezone.now()
                    obj.save(update_fields=["analysis_status", "analysis_error", "updated_at"])

                manual_category = _manual_category_from_site(obj)
                manual_is_competitor = _manual_is_competitor_from_category(manual_category)
                needs_analysis = not cached and manual_category is None
                can_enqueue = obj.analysis_status != "in_progress"
                not_enqueued_yet = not (obj.task_id or "").strip()

                if needs_analysis and can_enqueue and not_enqueued_yet:
                    # (Re)queue analysis. Reset status to pending.
                    obj.analysis_status = "pending"
                    obj.analysis_error = ""
                    obj.updated_at = timezone.now()
                    obj.save(update_fields=["analysis_status", "analysis_error", "updated_at"])
                    transaction.on_commit(lambda site_id=obj.id: _enqueue(int(site_id)))
                    scheduled += 1

            enriched.append(
                {
                    **row,
                    "cached": cached,
                    "analysis_status": obj.analysis_status or ("completed" if cached else "pending"),
                    "analysis_error": obj.analysis_error or "",
                    "last_seen_query": obj.last_seen_query or query,
                    "manual_category": manual_category,
                    "manual_is_competitor": manual_is_competitor,
                    "is_competitor": (
                        bool(manual_is_competitor)
                        if manual_is_competitor is not None
                        else (bool(obj.ai_is_competitor) if obj.ai_is_competitor is not None else False)
                    ),
                    "one_liner": obj.ai_one_liner or ("В очереди на анализ" if obj.analysis_status in {"pending", "in_progress"} else ""),
                    "pricing": obj.ai_pricing or "",
                    "home_title": obj.home_title or "",
                    "home_text": obj.home_text or "",
                    "services_url": obj.services_url or None,
                    "prices_url": obj.prices_url or None,
                }
            )

        return Response({"query": query, "scheduled": scheduled, "results": enriched})


class GoogleCompetitorsCachedView(APIView):
    """
    Return previously stored competitor sites for a given query (no Google call).
    If query is empty, return latest sites for the client.

    GET ?q=...
    """

    permission_classes = [IsTenantMember]

    def get(self, request, *args, **kwargs):
        query = str(request.query_params.get("q") or "").strip()[:512]

        client = get_active_client(request.user)
        qs = CompetitorSite.objects.filter(client=client)
        if query:
            qs = qs.filter(last_seen_query=query)
        qs = qs.order_by("-updated_at", "id")

        results: list[dict] = []
        seen_roots: set[str] = set()
        for site in qs:
            root = _root_domain(site.domain)
            if not root or root in seen_roots:
                continue
            seen_roots.add(root)
            manual_category = _manual_category_from_site(site)
            manual_is_competitor = _manual_is_competitor_from_category(manual_category)
            is_competitor = (
                bool(manual_is_competitor)
                if manual_is_competitor is not None
                else (bool(site.ai_is_competitor) if site.ai_is_competitor is not None else False)
            )
            results.append(
                {
                    "position": len(results) + 1,
                    "title": site.home_title or root,
                    "url": site.base_url or f"https://{root}/",
                    "domain": root,
                    "base_url": site.base_url or f"https://{root}/",
                    "cached": True,
                    "analysis_status": site.analysis_status or "pending",
                    "analysis_error": site.analysis_error or "",
                    "last_seen_query": site.last_seen_query,
                    "manual_category": manual_category,
                    "manual_is_competitor": manual_is_competitor,
                    "is_competitor": is_competitor,
                    "one_liner": site.ai_one_liner or "",
                    "pricing": site.ai_pricing or "",
                    "home_title": site.home_title or "",
                    "home_text": site.home_text or "",
                    "services_url": site.services_url or None,
                    "prices_url": site.prices_url or None,
                }
            )
            if len(results) >= 50:
                break

        return Response({"query": query, "results": results})


class GoogleCompetitorsMarkView(APIView):
    """
    Manually mark a domain as competitor / informational / indirect / other (overrides AI).
    Input: { "domain": "example.com", "category": "competitor|informational|indirect|other|null" }
    """

    permission_classes = [IsTenantMember]

    def post(self, request, *args, **kwargs):
        data = request.data if isinstance(request.data, dict) else {}
        raw_domain = _normalize_domain(str(data.get("domain") or ""))
        domain = _root_domain(raw_domain)
        if not domain:
            raise ValidationError({"domain": "Введите домен"})

        manual_category = None
        raw_category = data.get("category", None)
        if raw_category is not None:
            raw_text = str(raw_category or "").strip().lower()
            if not raw_text:
                manual_category = None
            elif raw_text in MANUAL_COMPETITOR_CATEGORIES:
                manual_category = raw_text
            else:
                raise ValidationError({"category": "Ожидается competitor/informational/indirect/other/null"})
        else:
            value = data.get("is_competitor")
            if value is None:
                manual_category = None
            elif isinstance(value, bool):
                manual_category = "competitor" if value else "indirect"
            elif str(value).strip().lower() in {"true", "1", "yes"}:
                manual_category = "competitor"
            elif str(value).strip().lower() in {"false", "0", "no"}:
                manual_category = "indirect"
            else:
                raise ValidationError({"is_competitor": "Ожидается true/false/null"})

        client = get_active_client(request.user)
        qs = CompetitorSite.objects.filter(client=client).filter(
            Q(domain=domain) | Q(domain__iendswith=f".{domain}")
        )
        if not qs.exists():
            raise ValidationError({"domain": "Домен не найден в базе. Сначала выполните поиск."})

        manual_is_competitor = _manual_is_competitor_from_category(manual_category)
        now = timezone.now()
        qs.update(
            manual_category=manual_category,
            manual_is_competitor=manual_is_competitor,
            manual_marked_at=now,
            updated_at=now,
        )

        return Response(
            {
                "success": True,
                "domain": domain,
                "manual_category": manual_category,
                "manual_is_competitor": manual_is_competitor,
            }
        )
