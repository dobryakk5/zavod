from __future__ import annotations

import hashlib
import logging
import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from core.models import AmoCRMAccount, AmoCRMContactMapping, AmoCRMLogEntry, CRMClient

logger = logging.getLogger(__name__)


AMO_OAUTH_STATE_SALT = "amocrm-oauth-state"
WEBHOOK_CONTACT_ID_KEY_RE = re.compile(r"^contacts\[(add|update)\]\[(\d+)\]\[id\]$")
WEBHOOK_ACCOUNT_KEY_RE = re.compile(r"^account\[(?P<field>[^\]]+)\]$")
PHONE_STRIP_RE = re.compile(r"[^\d+]+")
DOMAIN_ALLOWED_SUFFIXES = (".amocrm.ru", ".kommo.com")


class AmoCRMConfigError(RuntimeError):
    pass


class AmoCRMAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, response_body: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def normalize_amocrm_domain(value: str) -> tuple[str, str]:
    raw = (value or "").strip().lower()
    if not raw:
        raise ValueError("Не указан subdomain amoCRM")

    if "://" in raw:
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path or "").strip().lower()
    else:
        host = raw.split("/", 1)[0]

    host = host.split(":", 1)[0].strip(".")
    if not host:
        raise ValueError("Не удалось определить домен amoCRM")

    if "." not in host:
        subdomain = host
        base_domain = f"{subdomain}.amocrm.ru"
        return subdomain, base_domain

    if not host.endswith(DOMAIN_ALLOWED_SUFFIXES):
        raise ValueError("Поддерживаются только домены amoCRM/Kommo")

    subdomain = host.split(".", 1)[0]
    if not subdomain:
        raise ValueError("Некорректный subdomain amoCRM")
    return subdomain, host


def parse_amocrm_referer(value: str) -> tuple[str, str]:
    if not value:
        raise ValueError("В callback отсутствует referer")
    return normalize_amocrm_domain(value)


def normalize_phone(value: str) -> str:
    if not value:
        return ""
    normalized = PHONE_STRIP_RE.sub("", value.strip())
    return normalized[:32]


def split_name(name: str, first_name: str = "", last_name: str = "") -> tuple[str, str]:
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    if first or last:
        return first or "", last or ""

    full = (name or "").strip()
    if not full:
        return "", ""
    parts = full.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _json_safe_payload(payload: Any, max_len: int = 4000) -> Any:
    if payload is None:
        return {}
    if isinstance(payload, (str, int, float, bool)):
        text = str(payload)
        return payload if len(text) <= max_len else {"truncated": True, "preview": text[:max_len], "len": len(text)}
    if isinstance(payload, (dict, list)):
        try:
            text = json_dumps_for_len(payload)
        except Exception:  # noqa: BLE001
            text = str(payload)
        if len(text) <= max_len:
            return payload
        return {"truncated": True, "preview": text[:max_len], "len": len(text)}
    try:
        text = str(payload)
    except Exception:  # noqa: BLE001
        return {"repr_error": True}
    return {"repr": text[:max_len], "truncated": len(text) > max_len, "len": len(text)}


def json_dumps_for_len(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def log_amocrm_event(
    *,
    client_id: int | None = None,
    account: AmoCRMAccount | None = None,
    crm_client: CRMClient | None = None,
    mapping: AmoCRMContactMapping | None = None,
    source: str,
    action: str,
    level: str = AmoCRMLogEntry.LEVEL_INFO,
    status: str = AmoCRMLogEntry.STATUS_SUCCESS,
    message: str = "",
    payload: Any | None = None,
    error_code: str = "",
    idempotency_key: str = "",
) -> None:
    if not client_id:
        if account and account.client_id:
            client_id = account.client_id
        elif crm_client and crm_client.zavod_client_id:
            client_id = crm_client.zavod_client_id
    if not client_id:
        logger.warning("Skip AmoCRM log write: client_id is unknown (%s/%s)", source, action)
        return

    try:
        AmoCRMLogEntry.objects.create(
            client_id=client_id,
            account=account,
            crm_client=crm_client,
            mapping=mapping,
            source=source,
            action=action,
            level=level,
            status=status,
            message=message or "",
            payload=_json_safe_payload(payload),
            error_code=error_code or "",
            idempotency_key=idempotency_key or "",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to write AmoCRM log entry (%s/%s)", source, action)


def parse_amocrm_webhook_payload(*, json_payload: dict[str, Any] | None = None, form_items: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    if json_payload is not None:
        contacts_obj = json_payload.get("contacts") or {}
        add_list = _extract_ids_from_contact_events(contacts_obj.get("add"))
        update_list = _extract_ids_from_contact_events(contacts_obj.get("update"))
        return {
            "account": json_payload.get("account") or {},
            "contacts": {
                "add": [{"id": cid} for cid in add_list],
                "update": [{"id": cid} for cid in update_list],
            },
            "meta": {"source_format": "json"},
        }

    add_ids: dict[int, int] = {}
    update_ids: dict[int, int] = {}
    account_data: dict[str, Any] = {}

    for key, value in form_items or []:
        m = WEBHOOK_CONTACT_ID_KEY_RE.match(key)
        if m:
            event_name, idx_raw = m.group(1), m.group(2)
            try:
                idx = int(idx_raw)
                cid = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if event_name == "add":
                add_ids[idx] = cid
            else:
                update_ids[idx] = cid
            continue

        am = WEBHOOK_ACCOUNT_KEY_RE.match(key)
        if am:
            account_data[am.group("field")] = value

    return {
        "account": account_data,
        "contacts": {
            "add": [{"id": add_ids[k]} for k in sorted(add_ids)],
            "update": [{"id": update_ids[k]} for k in sorted(update_ids)],
        },
        "meta": {"source_format": "form"},
    }


def _extract_ids_from_contact_events(value: Any) -> list[int]:
    if not value:
        return []
    items = value if isinstance(value, list) else []
    result: list[int] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            cid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        result.append(cid)
    return result


def webhook_contact_ids(payload: dict[str, Any]) -> list[int]:
    contacts_obj = payload.get("contacts") or {}
    ids = _extract_ids_from_contact_events(contacts_obj.get("add"))
    ids.extend(_extract_ids_from_contact_events(contacts_obj.get("update")))
    seen: set[int] = set()
    unique: list[int] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(cid)
    return unique


def crm_client_sync_hash(crm_client: CRMClient) -> str:
    payload = "|".join(
        [
            (crm_client.first_name or "").strip(),
            (crm_client.last_name or "").strip(),
            (crm_client.email or "").strip().lower(),
            normalize_phone(crm_client.phone or ""),
            (crm_client.status or "").strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_amocrm_contact_payload(crm_client: CRMClient) -> dict[str, Any]:
    full_name = " ".join(part for part in [crm_client.first_name or "", crm_client.last_name or ""] if part).strip()
    custom_fields_values: list[dict[str, Any]] = []

    if crm_client.phone:
        custom_fields_values.append(
            {
                "field_code": "PHONE",
                "values": [{"value": crm_client.phone, "enum_code": "WORK"}],
            }
        )
    if crm_client.email:
        custom_fields_values.append(
            {
                "field_code": "EMAIL",
                "values": [{"value": crm_client.email, "enum_code": "WORK"}],
            }
        )

    payload: dict[str, Any] = {
        "name": full_name or crm_client.email or crm_client.phone or f"Client {crm_client.id}",
        "first_name": (crm_client.first_name or "").strip(),
        "last_name": (crm_client.last_name or "").strip(),
    }
    if custom_fields_values:
        payload["custom_fields_values"] = custom_fields_values
    return payload


def extract_contact_custom_field(contact_data: dict[str, Any], field_code: str) -> str:
    for field in contact_data.get("custom_fields_values") or []:
        if not isinstance(field, dict):
            continue
        if (field.get("field_code") or "").upper() != field_code.upper():
            continue
        values = field.get("values") or []
        if not values:
            return ""
        first_value = values[0]
        if isinstance(first_value, dict):
            return str(first_value.get("value") or "").strip()
        return str(first_value or "").strip()
    return ""


def contact_custom_fields_values(contact_data: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in contact_data.get("custom_fields_values") or []:
        if isinstance(field, dict):
            result.append(field)
    return result


def filter_unknown_custom_fields(custom_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known_codes = {"PHONE", "EMAIL"}
    unknown: list[dict[str, Any]] = []
    for field in custom_fields:
        code = str(field.get("field_code") or "").upper()
        if code and code in known_codes:
            continue
        unknown.append(field)
    return unknown


def remote_contact_to_local_fields(contact_data: dict[str, Any]) -> dict[str, str]:
    first_name = str(contact_data.get("first_name") or "").strip()
    last_name = str(contact_data.get("last_name") or "").strip()
    name = str(contact_data.get("name") or "").strip()
    first_name, last_name = split_name(name, first_name=first_name, last_name=last_name)

    email = extract_contact_custom_field(contact_data, "EMAIL") or ""
    phone = extract_contact_custom_field(contact_data, "PHONE") or ""

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email.lower() if email else "",
        "phone": phone,
    }


class AmoCRMService:
    REQUEST_TIMEOUT = 20
    TOKEN_REFRESH_MARGIN = timedelta(minutes=2)

    def __init__(self) -> None:
        self.client_id = (
            getattr(settings, "AMOCRM_INTEGRATION_CLIENT_ID", "")
            or getattr(settings, "AMOCRM_CLIENT_ID", "")
        )
        self.client_secret = (
            getattr(settings, "AMOCRM_INTEGRATION_CLIENT_SECRET", "")
            or getattr(settings, "AMOCRM_CLIENT_SECRET", "")
        )
        self.redirect_uri = (
            getattr(settings, "AMOCRM_INTEGRATION_REDIRECT_URI", "")
            or getattr(settings, "AMOCRM_REDIRECT_URI", "")
        )
        self.webhook_public_base_url = (
            getattr(settings, "AMOCRM_WEBHOOK_PUBLIC_BASE_URL", "")
            or getattr(settings, "PUBLIC_BASE_URL", "")
        )

    def ensure_oauth_configured(self, *, require_redirect_uri: bool = False) -> None:
        missing: list[str] = []
        if not self.client_id:
            missing.append("AMOCRM_INTEGRATION_CLIENT_ID/AMOCRM_CLIENT_ID")
        if not self.client_secret:
            missing.append("AMOCRM_INTEGRATION_CLIENT_SECRET/AMOCRM_CLIENT_SECRET")
        if require_redirect_uri and not self.redirect_uri:
            missing.append("AMOCRM_INTEGRATION_REDIRECT_URI/AMOCRM_REDIRECT_URI")
        if missing:
            raise AmoCRMConfigError("Не настроен amoCRM OAuth: " + ", ".join(missing))

    def get_redirect_uri(self, request=None) -> str:
        if self.redirect_uri:
            return self.redirect_uri
        if request is None:
            raise AmoCRMConfigError("Не задан redirect_uri amoCRM и нет request для вычисления callback URL")
        return request.build_absolute_uri(reverse("amocrm-oauth-callback"))

    def build_authorize_url(self, *, subdomain_or_domain: str, state: str, request=None) -> str:
        self.ensure_oauth_configured(require_redirect_uri=False)
        _, base_domain = normalize_amocrm_domain(subdomain_or_domain)
        params = {
            "client_id": self.client_id,
            "state": state,
            "mode": "popup",
            "redirect_uri": self.get_redirect_uri(request),
        }
        return f"https://{base_domain}/oauth?{urlencode(params)}"

    def oauth_connect_account(
        self,
        *,
        code: str,
        referer: str,
        zavod_client_id: int,
        created_by_id: int | None = None,
        request=None,
    ) -> AmoCRMAccount:
        self.ensure_oauth_configured(require_redirect_uri=True)
        subdomain, base_domain = parse_amocrm_referer(referer)

        tokens = self._oauth_token_request(
            base_domain=base_domain,
            grant_payload={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.get_redirect_uri(request),
            },
        )

        expires_at = self._expires_at_from_tokens(tokens)
        scope = self._normalize_scope(tokens.get("scope"))

        with transaction.atomic():
            account = AmoCRMAccount.objects.filter(base_domain=base_domain).select_for_update().first()
            if account and account.client_id != zavod_client_id:
                raise AmoCRMConfigError("Этот аккаунт amoCRM уже подключен к другому клиенту Zavod")

            if not account:
                account = AmoCRMAccount(client_id=zavod_client_id, created_by_id=created_by_id)

            account.client_id = zavod_client_id
            if created_by_id and not account.created_by_id:
                account.created_by_id = created_by_id
            account.subdomain = subdomain
            account.base_domain = base_domain
            account.access_token = str(tokens.get("access_token") or "")
            account.refresh_token = str(tokens.get("refresh_token") or "")
            account.expires_at = expires_at
            account.scope = scope
            account.status = AmoCRMAccount.STATUS_ACTIVE
            account.last_error = ""
            metadata = account.metadata or {}
            metadata["oauth_referer"] = referer
            metadata["token_type"] = tokens.get("token_type") or "Bearer"
            account.metadata = metadata
            account.save()

        info = {}
        try:
            info = self.get_remote_account_info(account)
        except Exception as exc:  # noqa: BLE001
            account.status = AmoCRMAccount.STATUS_ERROR
            account.last_error = f"Не удалось получить данные аккаунта amoCRM: {exc}"
            account.save(update_fields=["status", "last_error", "updated_at"])
            log_amocrm_event(
                account=account,
                source="oauth",
                action="fetch_account_info",
                level=AmoCRMLogEntry.LEVEL_WARNING,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message=str(exc),
            )
            return account

        changed_fields = ["updated_at"]
        if info.get("id") is not None:
            account.account_id = info["id"]
            changed_fields.append("account_id")
        if info.get("name"):
            account.account_name = info["name"]
            changed_fields.append("account_name")
        if info.get("subdomain"):
            account.subdomain = info["subdomain"]
            changed_fields.append("subdomain")
        meta = account.metadata or {}
        meta["account_info_synced_at"] = timezone.now().isoformat()
        account.metadata = meta
        changed_fields.append("metadata")
        account.save(update_fields=list(dict.fromkeys(changed_fields)))

        log_amocrm_event(
            account=account,
            source="oauth",
            action="callback_connected",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message="Аккаунт amoCRM подключен",
            payload={
                "base_domain": account.base_domain,
                "account_id": account.account_id,
                "account_name": account.account_name,
            },
        )
        return account

    def _oauth_token_request(self, *, base_domain: str, grant_payload: dict[str, Any]) -> dict[str, Any]:
        self.ensure_oauth_configured(require_redirect_uri=False)
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            **grant_payload,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        url = f"https://{base_domain}/oauth2/access_token"
        try:
            resp = requests.post(url, json=payload, timeout=self.REQUEST_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            raise AmoCRMAPIError(f"Ошибка запроса к amoCRM OAuth: {exc}") from exc
        return self._parse_response_json(resp, context="oauth_token")

    def _expires_at_from_tokens(self, tokens: dict[str, Any]) -> timezone.datetime | None:
        try:
            expires_in = int(tokens.get("expires_in") or 0)
        except (TypeError, ValueError):
            expires_in = 0
        if not expires_in:
            return None
        return timezone.now() + timedelta(seconds=expires_in)

    def _normalize_scope(self, scope_value: Any) -> list[str]:
        if isinstance(scope_value, list):
            return [str(x) for x in scope_value if str(x).strip()]
        if isinstance(scope_value, str):
            parts = [item.strip() for item in re.split(r"[\s,]+", scope_value) if item.strip()]
            return parts
        return []

    def ensure_valid_access_token(self, account: AmoCRMAccount, *, force_refresh: bool = False) -> AmoCRMAccount:
        should_refresh = force_refresh
        if not should_refresh:
            if not account.access_token:
                should_refresh = True
            elif not account.expires_at:
                should_refresh = False
            else:
                should_refresh = account.expires_at - timezone.now() <= self.TOKEN_REFRESH_MARGIN
        if not should_refresh:
            return account
        return self.refresh_access_token(account)

    def refresh_access_token(self, account: AmoCRMAccount) -> AmoCRMAccount:
        if not account.refresh_token:
            raise AmoCRMConfigError("У аккаунта amoCRM нет refresh_token")

        try:
            tokens = self._oauth_token_request(
                base_domain=account.base_domain,
                grant_payload={
                    "grant_type": "refresh_token",
                    "refresh_token": account.refresh_token,
                    "redirect_uri": self.redirect_uri or None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            account.status = AmoCRMAccount.STATUS_ERROR
            account.last_error = f"Token refresh failed: {exc}"
            account.save(update_fields=["status", "last_error", "updated_at"])
            log_amocrm_event(
                account=account,
                source="oauth",
                action="refresh_token",
                level=AmoCRMLogEntry.LEVEL_ERROR,
                status=AmoCRMLogEntry.STATUS_ERROR,
                message=str(exc),
            )
            raise

        account.access_token = str(tokens.get("access_token") or account.access_token or "")
        account.refresh_token = str(tokens.get("refresh_token") or account.refresh_token or "")
        account.expires_at = self._expires_at_from_tokens(tokens)
        account.scope = self._normalize_scope(tokens.get("scope")) or (account.scope or [])
        account.status = AmoCRMAccount.STATUS_ACTIVE
        account.last_error = ""
        account.save(
            update_fields=["access_token", "refresh_token", "expires_at", "scope", "status", "last_error", "updated_at"]
        )
        log_amocrm_event(
            account=account,
            source="oauth",
            action="refresh_token",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message="Токен amoCRM обновлен",
        )
        return account

    def _api_request(
        self,
        account: AmoCRMAccount,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        retry_on_401: bool = True,
    ) -> Any:
        account = self.ensure_valid_access_token(account)
        url = f"https://{account.base_domain}{path}"
        headers = {
            "Authorization": f"Bearer {account.access_token}",
            "Accept": "application/json",
        }
        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=self.REQUEST_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            raise AmoCRMAPIError(f"Ошибка запроса к amoCRM API: {exc}") from exc

        if resp.status_code == 401 and retry_on_401:
            account = self.refresh_access_token(account)
            return self._api_request(
                account,
                method,
                path,
                params=params,
                json_body=json_body,
                retry_on_401=False,
            )
        return self._parse_response_json(resp, context=f"{method.upper()} {path}")

    def _parse_response_json(self, resp: requests.Response, *, context: str) -> Any:
        if resp.status_code >= 400:
            body: Any
            try:
                body = resp.json()
            except Exception:  # noqa: BLE001
                body = resp.text[:1000]
            raise AmoCRMAPIError(
                f"amoCRM API error ({context}): HTTP {resp.status_code}",
                status_code=resp.status_code,
                response_body=body,
            )
        if resp.status_code == 204 or not (resp.text or "").strip():
            return {}
        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise AmoCRMAPIError(f"amoCRM API вернул не-JSON ответ ({context}): {exc}") from exc

    def get_remote_account_info(self, account: AmoCRMAccount) -> dict[str, Any]:
        data = self._api_request(account, "GET", "/api/v4/account")
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "subdomain": data.get("subdomain"),
        }

    def get_contact(self, account: AmoCRMAccount, amo_contact_id: int) -> dict[str, Any]:
        return self._api_request(account, "GET", f"/api/v4/contacts/{amo_contact_id}")

    def create_contact(self, account: AmoCRMAccount, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._api_request(account, "POST", "/api/v4/contacts", json_body=[payload])
        contacts = ((data.get("_embedded") or {}).get("contacts") or []) if isinstance(data, dict) else []
        if not contacts:
            raise AmoCRMAPIError("amoCRM не вернул созданный контакт", response_body=data)
        if not isinstance(contacts[0], dict):
            raise AmoCRMAPIError("Некорректный ответ amoCRM при создании контакта", response_body=data)
        return contacts[0]

    def update_contact(self, account: AmoCRMAccount, amo_contact_id: int, payload: dict[str, Any]) -> None:
        self._api_request(account, "PATCH", f"/api/v4/contacts/{amo_contact_id}", json_body=payload)

    def list_webhooks(self, account: AmoCRMAccount) -> list[dict[str, Any]]:
        data = self._api_request(account, "GET", "/api/v4/webhooks")
        return ((data.get("_embedded") or {}).get("webhooks") or []) if isinstance(data, dict) else []

    def webhook_url_for_account(self, account: AmoCRMAccount, *, request=None, require_public: bool = False) -> str:
        path = reverse("amocrm-webhook", kwargs={"webhook_secret": str(account.webhook_secret)})
        base = (self.webhook_public_base_url or "").strip().rstrip("/")
        if base:
            return f"{base}{path}"
        if request is not None and not require_public:
            return request.build_absolute_uri(path)
        if require_public:
            raise AmoCRMConfigError("Не задан AMOCRM_WEBHOOK_PUBLIC_BASE_URL для регистрации вебхука")
        return path

    def ensure_contact_webhook_registered(self, account: AmoCRMAccount, *, request=None) -> str:
        destination = self.webhook_url_for_account(account, request=request, require_public=True)
        existing = []
        try:
            existing = self.list_webhooks(account)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cannot list amoCRM webhooks for %s: %s", account.id, exc)

        required_settings = {"add_contact", "update_contact"}
        for hook in existing:
            if not isinstance(hook, dict):
                continue
            if str(hook.get("destination") or "").rstrip("/") != destination.rstrip("/"):
                continue
            hook_settings = set(hook.get("settings") or [])
            if required_settings.issubset(hook_settings):
                account.webhook_registered_at = timezone.now()
                account.webhook_last_error = ""
                account.save(update_fields=["webhook_registered_at", "webhook_last_error", "updated_at"])
                return destination

        self._api_request(
            account,
            "POST",
            "/api/v4/webhooks",
            json_body={
                "destination": destination,
                "settings": ["add_contact", "update_contact"],
            },
        )
        account.webhook_registered_at = timezone.now()
        account.webhook_last_error = ""
        account.save(update_fields=["webhook_registered_at", "webhook_last_error", "updated_at"])
        log_amocrm_event(
            account=account,
            source="webhook",
            action="register_webhook",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message="Webhook amoCRM зарегистрирован",
            payload={"destination": destination},
        )
        return destination

    def get_active_account_for_client(self, *, zavod_client_id: int, account_id: int | None = None) -> AmoCRMAccount:
        qs = AmoCRMAccount.objects.filter(client_id=zavod_client_id)
        if account_id:
            qs = qs.filter(id=account_id)
        account = qs.order_by("-updated_at").first()
        if not account:
            raise AmoCRMConfigError("У клиента нет подключенного аккаунта amoCRM")
        if account.status == AmoCRMAccount.STATUS_REVOKED:
            raise AmoCRMConfigError("Аккаунт amoCRM отключен")
        return account

    def sync_crm_client_to_amocrm(self, *, account: AmoCRMAccount, crm_client: CRMClient, force: bool = False) -> dict[str, Any]:
        if crm_client.zavod_client_id != account.client_id:
            raise AmoCRMConfigError("CRMClient не принадлежит этому аккаунту amoCRM")

        payload_hash = crm_client_sync_hash(crm_client)
        mapping = AmoCRMContactMapping.objects.filter(account=account, crm_client=crm_client).first()
        if mapping and not force and mapping.sync_hash == payload_hash:
            log_amocrm_event(
                account=account,
                crm_client=crm_client,
                mapping=mapping,
                source="sync",
                action="contact_push",
                status=AmoCRMLogEntry.STATUS_SKIPPED,
                message="Изменений нет, синк пропущен",
            )
            return {"status": "skipped", "mapping_id": mapping.id, "amo_contact_id": mapping.amo_contact_id}

        payload = build_amocrm_contact_payload(crm_client)
        action = "create"
        remote_contact_id: int | None = mapping.amo_contact_id if mapping else None
        created_contact: dict[str, Any] | None = None

        if mapping and mapping.amo_contact_id:
            try:
                self.update_contact(account, mapping.amo_contact_id, payload)
                action = "update"
            except AmoCRMAPIError as exc:
                if exc.status_code == 404:
                    remote_contact_id = None
                    action = "recreate"
                else:
                    self._mark_sync_error(account, crm_client, exc, mapping=mapping)
                    raise

        if not remote_contact_id:
            created_contact = self.create_contact(account, payload)
            try:
                remote_contact_id = int(created_contact.get("id"))
            except (TypeError, ValueError) as exc:
                raise AmoCRMAPIError("amoCRM не вернул id созданного контакта", response_body=created_contact) from exc

        with transaction.atomic():
            mapping, _ = AmoCRMContactMapping.objects.select_for_update().get_or_create(
                account=account,
                crm_client=crm_client,
                defaults={"amo_contact_id": remote_contact_id},
            )
            if mapping.amo_contact_id != remote_contact_id:
                mapping.amo_contact_id = remote_contact_id
            mapping.sync_hash = payload_hash
            mapping.last_synced_at = timezone.now()
            metadata = mapping.metadata or {}
            metadata["last_push_action"] = action
            metadata["last_push_at"] = timezone.now().isoformat()
            if created_contact is not None:
                created_custom_fields = contact_custom_fields_values(created_contact)
                metadata["amo_contact_snapshot"] = {
                    "id": created_contact.get("id"),
                    "name": created_contact.get("name"),
                    "updated_at": created_contact.get("updated_at"),
                }
                metadata["amo_custom_fields_values"] = created_custom_fields
                metadata["amo_custom_fields_unknown"] = filter_unknown_custom_fields(created_custom_fields)
            mapping.metadata = metadata
            mapping.save()

            account.last_sync_at = timezone.now()
            account.status = AmoCRMAccount.STATUS_ACTIVE
            account.last_error = ""
            account.save(update_fields=["last_sync_at", "status", "last_error", "updated_at"])

        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            mapping=mapping,
            source="sync",
            action="contact_push",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message=f"Контакт синхронизирован в amoCRM ({action})",
            payload={"amo_contact_id": remote_contact_id, "action": action},
        )
        return {
            "status": "success",
            "action": action,
            "mapping_id": mapping.id,
            "amo_contact_id": remote_contact_id,
        }

    def _mark_sync_error(
        self,
        account: AmoCRMAccount,
        crm_client: CRMClient,
        exc: Exception,
        *,
        mapping: AmoCRMContactMapping | None = None,
    ) -> None:
        account.status = AmoCRMAccount.STATUS_ERROR
        account.last_error = str(exc)
        account.save(update_fields=["status", "last_error", "updated_at"])
        payload = exc.response_body if isinstance(exc, AmoCRMAPIError) else None
        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            mapping=mapping,
            source="sync",
            action="contact_push",
            level=AmoCRMLogEntry.LEVEL_ERROR,
            status=AmoCRMLogEntry.STATUS_ERROR,
            message=str(exc),
            payload=payload,
            error_code=str(getattr(exc, "status_code", "") or ""),
        )

    def process_contact_webhook(self, *, account: AmoCRMAccount, payload: dict[str, Any]) -> dict[str, Any]:
        contact_ids = webhook_contact_ids(payload)
        if not contact_ids:
            log_amocrm_event(
                account=account,
                source="webhook",
                action="contacts_update",
                status=AmoCRMLogEntry.STATUS_SKIPPED,
                message="Webhook не содержит contacts.add/update",
                payload=payload,
            )
            return {"status": "skipped", "processed": 0}

        processed = 0
        errors = 0
        for contact_id in contact_ids:
            try:
                self.sync_local_crm_client_from_amocrm_contact(account=account, amo_contact_id=contact_id)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception("amoCRM webhook sync failed for account=%s contact=%s", account.id, contact_id)
                log_amocrm_event(
                    account=account,
                    source="webhook",
                    action="contact_pull",
                    level=AmoCRMLogEntry.LEVEL_ERROR,
                    status=AmoCRMLogEntry.STATUS_ERROR,
                    message=str(exc),
                    payload={"amo_contact_id": contact_id},
                    error_code=str(getattr(exc, "status_code", "") or ""),
                    idempotency_key=f"{account.id}:{contact_id}",
                )

        status = "success" if errors == 0 else ("error" if processed == 0 else "partial")
        log_amocrm_event(
            account=account,
            source="webhook",
            action="contacts_update",
            status=AmoCRMLogEntry.STATUS_SUCCESS if errors == 0 else AmoCRMLogEntry.STATUS_ERROR,
            level=AmoCRMLogEntry.LEVEL_INFO if errors == 0 else AmoCRMLogEntry.LEVEL_WARNING,
            message=f"Webhook обработан: processed={processed}, errors={errors}",
            payload={"contact_ids": contact_ids, "processed": processed, "errors": errors},
        )
        return {"status": status, "processed": processed, "errors": errors}

    def sync_local_crm_client_from_amocrm_contact(self, *, account: AmoCRMAccount, amo_contact_id: int) -> CRMClient:
        remote = self.get_contact(account, amo_contact_id)
        local_fields = remote_contact_to_local_fields(remote)
        remote_custom_fields = contact_custom_fields_values(remote)
        remote_unknown_custom_fields = filter_unknown_custom_fields(remote_custom_fields)

        with transaction.atomic():
            mapping = (
                AmoCRMContactMapping.objects.select_for_update()
                .filter(account=account, amo_contact_id=amo_contact_id)
                .select_related("crm_client")
                .first()
            )
            crm_client = mapping.crm_client if mapping else None

            if crm_client and crm_client.zavod_client_id != account.client_id:
                raise AmoCRMConfigError("Найдена mapping запись с чужим tenant для amoCRM контакта")

            if crm_client is None:
                crm_client = self._find_local_crm_client_for_remote_contact(account, local_fields)

            if crm_client is None:
                crm_client = self._create_local_crm_client_from_remote(account, local_fields, amo_contact_id)
            else:
                self._update_local_crm_client_from_remote(account, crm_client, local_fields)

            if mapping is None:
                mapping = AmoCRMContactMapping.objects.create(
                    account=account,
                    crm_client=crm_client,
                    amo_contact_id=amo_contact_id,
                )
            else:
                changed = False
                if mapping.crm_client_id != crm_client.id:
                    mapping.crm_client = crm_client
                    changed = True
                if mapping.amo_contact_id != amo_contact_id:
                    mapping.amo_contact_id = amo_contact_id
                    changed = True
                if changed:
                    mapping.save(update_fields=["crm_client", "amo_contact_id", "updated_at"])

            mapping.last_webhook_at = timezone.now()
            metadata = mapping.metadata or {}
            metadata["last_pull_at"] = timezone.now().isoformat()
            metadata["amo_contact_snapshot"] = {
                "id": remote.get("id"),
                "name": remote.get("name"),
                "updated_at": remote.get("updated_at"),
            }
            metadata["amo_custom_fields_values"] = remote_custom_fields
            metadata["amo_custom_fields_unknown"] = remote_unknown_custom_fields
            mapping.metadata = metadata
            mapping.save(update_fields=["last_webhook_at", "metadata", "updated_at"])

        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            mapping=mapping,
            source="webhook",
            action="contact_pull",
            status=AmoCRMLogEntry.STATUS_SUCCESS,
            message="Локальный CRMClient обновлен из amoCRM webhook",
            payload={"amo_contact_id": amo_contact_id, "crm_client_id": crm_client.id},
            idempotency_key=f"{account.id}:{amo_contact_id}",
        )
        return crm_client

    def _find_local_crm_client_for_remote_contact(self, account: AmoCRMAccount, local_fields: dict[str, str]) -> CRMClient | None:
        email = (local_fields.get("email") or "").strip().lower()
        phone = (local_fields.get("phone") or "").strip()

        if email:
            candidate = CRMClient.objects.filter(email=email).first()
            if candidate:
                if candidate.zavod_client_id != account.client_id:
                    raise AmoCRMConfigError("Email контакта уже занят в другом tenant-е Zavod")
                return candidate

        if phone:
            candidate = CRMClient.objects.filter(zavod_client_id=account.client_id, phone=phone).first()
            if candidate:
                return candidate

            normalized_phone = normalize_phone(phone)
            if normalized_phone:
                # fallback для разных форматов записи телефона
                candidates = CRMClient.objects.filter(zavod_client_id=account.client_id).exclude(phone="")
                for item in candidates[:500]:
                    if normalize_phone(item.phone or "") == normalized_phone:
                        return item

        return None

    def _create_local_crm_client_from_remote(
        self,
        account: AmoCRMAccount,
        local_fields: dict[str, str],
        amo_contact_id: int,
    ) -> CRMClient:
        first_name = local_fields.get("first_name") or ""
        last_name = local_fields.get("last_name") or ""
        email = local_fields.get("email") or None
        phone = (local_fields.get("phone") or "")[:20]

        if not first_name and not last_name:
            first_name = f"amoCRM {amo_contact_id}"

        try:
            crm_client = CRMClient.objects.create(
                first_name=first_name[:100],
                last_name=last_name[:100],
                email=(email or "")[:254] or None,
                phone=phone,
                status="active",
                zavod_client_id=account.client_id,
            )
        except IntegrityError as exc:
            raise AmoCRMConfigError(f"Не удалось создать CRMClient из amoCRM контакта: {exc}") from exc
        return crm_client

    def _update_local_crm_client_from_remote(
        self,
        account: AmoCRMAccount,
        crm_client: CRMClient,
        local_fields: dict[str, str],
    ) -> None:
        if crm_client.zavod_client_id != account.client_id:
            raise AmoCRMConfigError("CRMClient принадлежит другому tenant-у")

        update_fields: list[str] = []

        first_name = (local_fields.get("first_name") or crm_client.first_name or "").strip()[:100]
        last_name = (local_fields.get("last_name") or crm_client.last_name or "").strip()[:100]
        phone = (local_fields.get("phone") or crm_client.phone or "").strip()[:20]
        email = (local_fields.get("email") or "").strip().lower()

        if first_name != crm_client.first_name:
            crm_client.first_name = first_name
            update_fields.append("first_name")
        if last_name != crm_client.last_name:
            crm_client.last_name = last_name
            update_fields.append("last_name")
        if phone != crm_client.phone:
            crm_client.phone = phone
            update_fields.append("phone")

        if email and email != (crm_client.email or "").lower():
            existing = CRMClient.objects.filter(email=email).exclude(id=crm_client.id).first()
            if existing and existing.zavod_client_id != account.client_id:
                raise AmoCRMConfigError("Нельзя обновить email: он уже используется в другом tenant-е Zavod")
            if existing and existing.zavod_client_id == account.client_id:
                raise AmoCRMConfigError("Нельзя обновить email: он уже используется другим локальным CRMClient")
            crm_client.email = email
            update_fields.append("email")

        if update_fields:
            crm_client.save(update_fields=update_fields + ["updated_at"])

    def resync_all_crm_clients(self, *, account: AmoCRMAccount, force: bool = True, limit: int | None = None) -> dict[str, int]:
        queryset = CRMClient.objects.filter(zavod_client_id=account.client_id).order_by("id")
        if limit:
            queryset = queryset[:limit]

        synced = 0
        skipped = 0
        failed = 0
        for crm_client in queryset:
            try:
                result = self.sync_crm_client_to_amocrm(account=account, crm_client=crm_client, force=force)
                if result.get("status") == "skipped":
                    skipped += 1
                else:
                    synced += 1
            except Exception:
                failed += 1
                logger.exception("AmoCRM resync failed for crm_client=%s", crm_client.id)

        log_amocrm_event(
            account=account,
            source="resync",
            action="resync_all_contacts",
            status=AmoCRMLogEntry.STATUS_SUCCESS if failed == 0 else AmoCRMLogEntry.STATUS_ERROR,
            level=AmoCRMLogEntry.LEVEL_INFO if failed == 0 else AmoCRMLogEntry.LEVEL_WARNING,
            message=f"Resync completed: synced={synced}, skipped={skipped}, failed={failed}",
            payload={"synced": synced, "skipped": skipped, "failed": failed},
        )
        return {"synced": synced, "skipped": skipped, "failed": failed}
