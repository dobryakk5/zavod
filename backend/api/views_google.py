from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember

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

        return Response({"query": query, "results": results})
