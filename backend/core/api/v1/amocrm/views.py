import json
import logging
from typing import Any

from django.core import signing
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.v1.crm.views import ZavodClientRequiredMixin
from core.models import AmoCRMAccount, AmoCRMLogEntry, CRMClient
from core.services.crm.amocrm import (
    AMO_OAUTH_STATE_SALT,
    AmoCRMConfigError,
    AmoCRMService,
    log_amocrm_event,
    normalize_amocrm_domain,
    parse_amocrm_webhook_payload,
)
from core.tasks.amocrm import (
    process_amocrm_contacts_webhook_task,
    resync_all_crm_clients_to_amocrm_task,
    sync_crm_client_to_amocrm_contact_task,
)

logger = logging.getLogger(__name__)


class AmoCRMZavodClientMixin(ZavodClientRequiredMixin):
    permission_classes = [IsAuthenticated]

    def require_zavod_client(self):
        zavod_client = self.get_zavod_client()
        if not zavod_client:
            raise AmoCRMConfigError("У пользователя нет связанного Zavod клиента")
        return zavod_client

    def _json_body(self, request) -> dict[str, Any]:
        if isinstance(getattr(request, "data", None), dict):
            return request.data
        try:
            raw = (request.body or b"").decode("utf-8").strip()
            return json.loads(raw) if raw else {}
        except Exception:  # noqa: BLE001
            return {}

    def _parse_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        return default


class AmoCRMOAuthStartView(AmoCRMZavodClientMixin, APIView):
    def get(self, request):
        return self._start(request)

    def post(self, request):
        return self._start(request)

    def _start(self, request):
        service = AmoCRMService()
        zavod_client = self.require_zavod_client()

        body = self._json_body(request)
        subdomain_value = (
            request.query_params.get("subdomain")
            or body.get("subdomain")
            or body.get("domain")
            or ""
        )
        if not subdomain_value:
            return Response({"error": "Параметр subdomain обязателен"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            subdomain, base_domain = normalize_amocrm_domain(subdomain_value)
            state_payload = {
                "client_id": zavod_client.id,
                "user_id": request.user.id,
                "nonce": get_random_string(16),
            }
            state = signing.dumps(state_payload, salt=AMO_OAUTH_STATE_SALT)
            authorize_url = service.build_authorize_url(
                subdomain_or_domain=base_domain,
                state=state,
                request=request,
            )
        except Exception as exc:  # noqa: BLE001
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_amocrm_event(
            client_id=zavod_client.id,
            source="oauth",
            action="oauth_start",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message="Сформирован URL для OAuth amoCRM",
            payload={"subdomain": subdomain, "base_domain": base_domain},
        )
        return Response(
            {
                "authorize_url": authorize_url,
                "subdomain": subdomain,
                "base_domain": base_domain,
            }
        )


class AmoCRMOAuthCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        code = (request.query_params.get("code") or "").strip()
        state = (request.query_params.get("state") or "").strip()
        referer = (request.query_params.get("referer") or "").strip()

        if not code:
            return Response({"error": "В callback отсутствует code"}, status=status.HTTP_400_BAD_REQUEST)
        if not state:
            return Response({"error": "В callback отсутствует state"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            state_payload = signing.loads(state, salt=AMO_OAUTH_STATE_SALT, max_age=15 * 60)
            zavod_client_id = int(state_payload["client_id"])
            created_by_id = int(state_payload["user_id"])
        except Exception as exc:  # noqa: BLE001
            return Response({"error": f"Некорректный state: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        service = AmoCRMService()
        try:
            account = service.oauth_connect_account(
                code=code,
                referer=referer,
                zavod_client_id=zavod_client_id,
                created_by_id=created_by_id,
                request=request,
            )
        except Exception as exc:  # noqa: BLE001
            log_amocrm_event(
                client_id=zavod_client_id,
                source="oauth",
                action="callback_connected",
                level=AmoCRMLogEntry.LEVEL_ERROR,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message=str(exc),
                payload={"referer": referer},
            )
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        webhook_status = "skipped"
        webhook_error = ""
        webhook_url = ""
        try:
            webhook_url = service.webhook_url_for_account(account, request=request, require_public=False)
            if service.webhook_public_base_url:
                webhook_url = service.ensure_contact_webhook_registered(account, request=request)
                webhook_status = "registered"
            else:
                webhook_status = "manual_required"
                account.webhook_last_error = "AMOCRM_WEBHOOK_PUBLIC_BASE_URL не задан, webhook нужно зарегистрировать вручную"
                account.save(update_fields=["webhook_last_error", "updated_at"])
        except Exception as exc:  # noqa: BLE001
            webhook_status = "error"
            webhook_error = str(exc)
            account.webhook_last_error = webhook_error
            account.save(update_fields=["webhook_last_error", "updated_at"])
            log_amocrm_event(
                account=account,
                source="webhook",
                action="register_webhook",
                level=AmoCRMLogEntry.LEVEL_WARNING,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message=webhook_error,
            )

        return Response(
            {
                "ok": True,
                "account": {
                    "id": account.id,
                    "base_domain": account.base_domain,
                    "subdomain": account.subdomain,
                    "account_id": account.account_id,
                    "account_name": account.account_name,
                    "status": account.status,
                },
                "webhook": {
                    "status": webhook_status,
                    "url": webhook_url,
                    "error": webhook_error,
                },
            }
        )


class AmoCRMWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, webhook_secret):
        account = AmoCRMAccount.objects.filter(webhook_secret=webhook_secret).first()
        if not account:
            return Response({"error": "Webhook endpoint not found"}, status=status.HTTP_404_NOT_FOUND)

        content_type = (request.content_type or "").lower()
        try:
            if "json" in content_type:
                raw = json.loads((request.body or b"{}").decode("utf-8") or "{}")
                if not isinstance(raw, dict):
                    raw = {}
                payload = parse_amocrm_webhook_payload(json_payload=raw)
            else:
                payload = parse_amocrm_webhook_payload(form_items=list(request.POST.items()))
        except Exception as exc:  # noqa: BLE001
            log_amocrm_event(
                account=account,
                source="webhook",
                action="receive",
                level=AmoCRMLogEntry.LEVEL_ERROR,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message=f"Ошибка парсинга webhook: {exc}",
            )
            return Response({"error": "Invalid webhook payload"}, status=status.HTTP_400_BAD_REQUEST)

        payload_account = payload.get("account") or {}
        payload_subdomain = str(payload_account.get("subdomain") or "").strip().lower()
        if payload_subdomain and payload_subdomain != (account.subdomain or "").strip().lower():
            log_amocrm_event(
                account=account,
                source="webhook",
                action="receive",
                level=AmoCRMLogEntry.LEVEL_WARNING,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message="Webhook subdomain mismatch",
                payload={"payload_subdomain": payload_subdomain, "expected": account.subdomain},
            )
            return Response({"error": "Webhook account mismatch"}, status=status.HTTP_403_FORBIDDEN)

        log_amocrm_event(
            account=account,
            source="webhook",
            action="receive",
            status=AmoCRMLogEntry.STATUS_QUEUED,
            message="Webhook поставлен в очередь",
            payload=payload,
        )
        async_result = process_amocrm_contacts_webhook_task.delay(account.id, payload)
        return Response({"queued": True, "task_id": async_result.id}, status=status.HTTP_202_ACCEPTED)


class AmoCRMAccountStatusView(AmoCRMZavodClientMixin, APIView):
    def get(self, request):
        zavod_client = self.require_zavod_client()
        account = AmoCRMAccount.objects.filter(client_id=zavod_client.id).order_by("-updated_at").first()
        if not account:
            return Response({"connected": False, "account": None})

        service = AmoCRMService()
        try:
            webhook_url = service.webhook_url_for_account(account, request=request, require_public=False)
        except Exception:
            webhook_url = ""

        return Response(
            {
                "connected": True,
                "account": {
                    "id": account.id,
                    "base_domain": account.base_domain,
                    "subdomain": account.subdomain,
                    "account_id": account.account_id,
                    "account_name": account.account_name,
                    "status": account.status,
                    "expires_at": account.expires_at,
                    "webhook_registered_at": account.webhook_registered_at,
                    "webhook_last_error": account.webhook_last_error,
                    "last_sync_at": account.last_sync_at,
                    "last_error": account.last_error,
                    "webhook_url": webhook_url,
                },
            }
        )


class AmoCRMLogsView(AmoCRMZavodClientMixin, APIView):
    def get(self, request):
        zavod_client = self.require_zavod_client()
        qs = AmoCRMLogEntry.objects.filter(client_id=zavod_client.id).select_related("account", "crm_client")

        level = (request.query_params.get("level") or "").strip()
        status_filter = (request.query_params.get("status") or "").strip()
        if level:
            qs = qs.filter(level=level)
        if status_filter:
            qs = qs.filter(status=status_filter)

        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 200))

        rows = []
        for item in qs[:limit]:
            rows.append(
                {
                    "id": item.id,
                    "created_at": item.created_at,
                    "source": item.source,
                    "action": item.action,
                    "level": item.level,
                    "status": item.status,
                    "message": item.message,
                    "error_code": item.error_code,
                    "account_id": item.account_id,
                    "crm_client_id": item.crm_client_id,
                    "payload": item.payload,
                }
            )
        return Response({"results": rows, "count": len(rows)})


class AmoCRMResyncAllView(AmoCRMZavodClientMixin, APIView):
    def post(self, request):
        service = AmoCRMService()
        zavod_client = self.require_zavod_client()
        body = self._json_body(request)

        try:
            account_id = int(body["account_id"]) if body.get("account_id") not in (None, "") else None
        except (TypeError, ValueError):
            return Response({"error": "account_id должен быть числом"}, status=status.HTTP_400_BAD_REQUEST)
        force = self._parse_bool(body.get("force"), default=True)
        try:
            limit = int(body["limit"]) if "limit" in body and body["limit"] not in (None, "") else None
        except (TypeError, ValueError):
            return Response({"error": "limit должен быть числом"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = service.get_active_account_for_client(zavod_client_id=zavod_client.id, account_id=account_id)
        except Exception as exc:  # noqa: BLE001
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_amocrm_event(
            account=account,
            source="resync",
            action="resync_all_contacts_request",
            status=AmoCRMLogEntry.STATUS_QUEUED,
            message="Ручной ресинк всех контактов поставлен в очередь",
            payload={"force": force, "limit": limit},
        )
        task = resync_all_crm_clients_to_amocrm_task.delay(account.id, force=force, limit=limit)
        return Response({"queued": True, "task_id": task.id, "account_id": account.id}, status=status.HTTP_202_ACCEPTED)


class AmoCRMResyncOneView(AmoCRMZavodClientMixin, APIView):
    def post(self, request, crm_client_id: int):
        service = AmoCRMService()
        zavod_client = self.require_zavod_client()
        body = self._json_body(request)
        try:
            account_id = int(body["account_id"]) if body.get("account_id") not in (None, "") else None
        except (TypeError, ValueError):
            return Response({"error": "account_id должен быть числом"}, status=status.HTTP_400_BAD_REQUEST)
        force = self._parse_bool(body.get("force"), default=True)

        crm_client = CRMClient.objects.filter(id=crm_client_id, zavod_client_id=zavod_client.id).first()
        if not crm_client:
            return Response({"error": "CRMClient не найден"}, status=status.HTTP_404_NOT_FOUND)

        try:
            account = service.get_active_account_for_client(zavod_client_id=zavod_client.id, account_id=account_id)
        except Exception as exc:  # noqa: BLE001
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            source="resync",
            action="resync_one_contact_request",
            status=AmoCRMLogEntry.STATUS_QUEUED,
            message="Ручной ресинк контакта поставлен в очередь",
            payload={"force": force},
        )
        task = sync_crm_client_to_amocrm_contact_task.delay(account.id, crm_client.id, force=force)
        return Response(
            {"queued": True, "task_id": task.id, "account_id": account.id, "crm_client_id": crm_client.id},
            status=status.HTTP_202_ACCEPTED,
        )
