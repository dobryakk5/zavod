from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from base64 import b64decode
from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import HttpResponseRedirect
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember
from .utils import get_active_client
from core.models import Client, PaymentPlan, YooKassaPayment, MapCRMPayment  # добавлена YooKassaPayment
from core.services.referral_payment_service import handle_succeeded_payment

logger = logging.getLogger(__name__)
User = get_user_model()
PROMO_CODE_STARTER = "1free"


# ---------------------------------------------------------------------------
# Helpers (без изменений)
# ---------------------------------------------------------------------------

def _is_dev_user(user) -> bool:
    return getattr(user, "is_dev_user", False) or user.username == "dev_user"


def _normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    email = str(value).strip()
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def _get_payment_email(payment: dict) -> str | None:
    metadata = payment.get("metadata") or {}
    email = _normalize_email(metadata.get("email"))
    if email:
        return email

    user_id = metadata.get("telegram_user_id")
    if user_id:
        user = User.objects.filter(id=user_id).first()
        if user and user.email and not user.email.endswith("@telegram.local"):
            return _normalize_email(user.email)
    return None


def _send_payment_confirmation(payment: dict) -> None:
    if not payment:
        return
    if payment.get("status") != "succeeded" or not payment.get("paid"):
        return

    payment_id = payment.get("id")
    if not payment_id:
        return

    cache_key = f"yookassa:payment-email:{payment_id}"
    if cache.get(cache_key):
        return

    email = _get_payment_email(payment)
    if not email:
        logger.warning("yookassa: payment email missing payment_id=%s", payment_id)
        return

    amount = payment.get("amount") or {}
    value = amount.get("value", "")
    currency = amount.get("currency", "RUB")
    description = payment.get("description", "Оплата")

    subject = f"Оплата подтверждена: {value} {currency}"
    message = (
        "Здравствуйте!\n\n"
        "Мы получили подтверждение оплаты через YooKassa.\n"
        f"Платеж: {description}\n"
        f"Сумма: {value} {currency}\n"
        f"ID платежа: {payment_id}\n\n"
        "Спасибо!"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
    cache.set(cache_key, True, 60 * 60 * 24 * 7)
    logger.info("yookassa: payment email sent payment_id=%s", payment_id)


def _parse_payment_created_at(value: str | None) -> datetime:
    if not value:
        return timezone.now()
    try:
        cleaned = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone=timezone.utc)
        return parsed
    except ValueError:
        return timezone.now()


def _plan_delta(plan: PaymentPlan) -> relativedelta:
    if plan.period == PaymentPlan.PERIOD_WEEK:
        return relativedelta(weeks=1)
    if plan.period == PaymentPlan.PERIOD_YEAR:
        return relativedelta(years=1)
    return relativedelta(months=1)


def _apply_payment_plan(payment: dict) -> None:
    if payment.get("status") != "succeeded" or not payment.get("paid"):
        return

    metadata = payment.get("metadata") or {}
    client_id = metadata.get("client_id")
    plan_code = metadata.get("plan")
    if not client_id or not plan_code:
        logger.warning("yookassa: missing client_id/plan in metadata")
        return

    client = Client.objects.filter(id=client_id).first()
    plan = PaymentPlan.objects.filter(code=plan_code, is_active=True).first()
    if not client or not plan:
        logger.warning("yookassa: plan apply failed client_id=%s plan=%s", client_id, plan_code)
        return

    base_date = _parse_payment_created_at(payment.get("created_at"))
    if client.plan_id == plan.id and client.plan_expires_at and client.plan_expires_at > base_date:
        base_date = client.plan_expires_at

    expires_at = base_date + _plan_delta(plan)
    client.plan = plan
    client.plan_expires_at = expires_at
    client.save(update_fields=["plan", "plan_expires_at"])
    logger.info(
        "yookassa: plan applied client_id=%s plan=%s expires_at=%s",
        client_id, plan.code, expires_at,
    )


def _parse_payment_success_at(payment: dict) -> datetime:
    confirmed_at = payment.get("captured_at") or payment.get("paid_at") or payment.get("created_at")
    return _parse_payment_created_at(confirmed_at)


def _mark_crm_payment_paid(payment: dict) -> None:
    if payment.get("status") != "succeeded" or not payment.get("paid"):
        return

    metadata = payment.get("metadata") or {}
    crm_payment_id = metadata.get("crm_payment_id")
    yookassa_payment_id = payment.get("id")

    crm_payment = None
    if crm_payment_id:
        try:
            crm_payment = MapCRMPayment.objects.filter(id=int(str(crm_payment_id))).first()
        except (TypeError, ValueError):
            crm_payment = None

    if not crm_payment and yookassa_payment_id:
        crm_payment = MapCRMPayment.objects.filter(transaction_id=str(yookassa_payment_id)).first()

    if not crm_payment:
        logger.info(
            "yookassa: crm payment not found for update yookassa_payment_id=%s crm_payment_id=%s",
            yookassa_payment_id,
            crm_payment_id,
        )
        return

    update_fields: list[str] = []
    if crm_payment.status != "paid":
        crm_payment.status = "paid"
        update_fields.append("status")

    paid_at = _parse_payment_success_at(payment)
    if not crm_payment.paid_at or crm_payment.paid_at != paid_at:
        crm_payment.paid_at = paid_at
        update_fields.append("paid_at")

    if yookassa_payment_id and crm_payment.transaction_id != str(yookassa_payment_id):
        crm_payment.transaction_id = str(yookassa_payment_id)
        update_fields.append("transaction_id")

    payment_method = (payment.get("payment_method") or {}).get("type")
    if payment_method and crm_payment.payment_method != str(payment_method):
        crm_payment.payment_method = str(payment_method)
        update_fields.append("payment_method")

    if update_fields:
        crm_payment.save(update_fields=update_fields)
        logger.info(
            "yookassa: crm payment marked as paid crm_payment_id=%s yookassa_payment_id=%s",
            crm_payment.id,
            yookassa_payment_id,
        )


# ---------------------------------------------------------------------------
# NEW: Multi-merchant helpers
# ---------------------------------------------------------------------------

def _get_yookassa_credentials(client: Client) -> tuple[str, str, str]:
    """
    Возвращает (shop_id, secret_key_or_token, auth_type) для клиента.
    auth_type: 'basic' или 'bearer'

    Приоритет:
      1. OAuth-токен клиента (bearer)
      2. Собственные shop_id/secret_key клиента (basic)
      3. Глобальные ключи из .env (basic, fallback)
    """
    if getattr(client, "yookassa_oauth_token", None):
        return "", client.yookassa_oauth_token, "bearer"

    if getattr(client, "yookassa_shop_id", None) and getattr(client, "yookassa_secret_key", None):
        return client.yookassa_shop_id, client.yookassa_secret_key, "basic"

    return settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY, "basic"


def _build_yookassa_request_kwargs(shop_id: str, secret_or_token: str, auth_type: str, idempotence_key: str) -> dict:
    """Собирает kwargs для requests с нужной авторизацией."""
    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json",
    }
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {secret_or_token}"
        return {"headers": headers}
    return {"auth": (shop_id, secret_or_token), "headers": headers}


def _get_client_return_url(client: Client) -> str:
    """Возвращает return_url для конкретного клиента."""
    if getattr(client, "yookassa_return_url", None):
        return client.yookassa_return_url
    base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    return f"{base}/payments/return/{client.uuid}/" if hasattr(client, "uuid") else settings.YOOKASSA_RETURN_URL


def _get_client_webhook_url(client: Client) -> str:
    """Возвращает уникальный webhook URL для конкретного клиента."""
    base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    return f"{base}/api/payments/webhook/{client.uuid}/"


def _register_client_webhooks(client: Client) -> None:
    """
    Регистрирует вебхуки в YooKassa для конкретного клиента.
    Вызывается после подключения OAuth или сохранения ручных ключей.
    """
    shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)

    if not secret_or_token:
        logger.warning("yookassa: cannot register webhooks — no credentials for client_id=%s", client.id)
        return

    webhook_url = _get_client_webhook_url(client)
    events = ["payment.succeeded", "payment.canceled", "payment.waiting_for_capture"]

    for event in events:
        idem_key = str(uuid.uuid4())
        kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, idem_key)
        try:
            resp = _yookassa_request(
                "POST",
                "https://api.yookassa.ru/v3/webhooks",
                json={"event": event, "url": webhook_url},
                timeout=10,
                **kwargs,
            )
            if resp.status_code in (200, 201):
                logger.info(
                    "yookassa: webhook registered client_id=%s event=%s url=%s",
                    client.id, event, webhook_url,
                )
            else:
                logger.warning(
                    "yookassa: webhook registration failed client_id=%s event=%s status=%s body=%s",
                    client.id, event, resp.status_code, resp.text,
                )
        except requests.RequestException:
            logger.exception("yookassa: webhook registration request failed client_id=%s event=%s", client.id, event)


def _yookassa_request(method: str, url: str, *, timeout: int = 30, **kwargs):
    """
    Выполняет HTTP-запрос к YooKassa без использования env-proxy.
    """
    session = requests.Session()
    session.trust_env = False
    try:
        return session.request(method=method, url=url, timeout=timeout, **kwargs)
    finally:
        session.close()


def _build_settings_redirect_url(**params: str) -> str:
    """Формирует URL возврата на вкладку оплаты в настройках."""
    site_url = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    query: dict[str, str] = {"tab": "payment"}
    for key, value in params.items():
        if value:
            query[key] = value
    return f"{site_url}/settings?{urlencode(query)}"


def _exchange_oauth_code(code: str, oauth_client_id: str, oauth_client_secret: str, client_uuid: str):
    """
    Обменивает OAuth code на token.

    Делаем повтор при сетевом сбое, чтобы переживать кратковременные проблемы сети.
    """
    token_url = getattr(settings, "YOOKASSA_OAUTH_TOKEN_URL", "https://yookassa.ru/oauth/v2/token")
    payload = {"grant_type": "authorization_code", "code": code}
    last_error: requests.RequestException | None = None

    for attempt in (1, 2):
        try:
            return _yookassa_request(
                "POST",
                token_url,
                auth=(oauth_client_id, oauth_client_secret),
                data=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "yookassa: oauth token exchange network error attempt=%s client_uuid=%s url=%s error=%s",
                attempt,
                client_uuid,
                token_url,
                exc,
            )

    if last_error:
        raise last_error

    raise requests.RequestException("OAuth token exchange failed without exception details")


# ---------------------------------------------------------------------------
# NEW: OAuth flow views
# ---------------------------------------------------------------------------

class YooKassaOAuthRedirectView(APIView):
    """
    Шаг 1: редиректит пользователя на страницу авторизации YooKassa.
    GET /payments/yookassa/connect/
    """
    permission_classes = [IsTenantMember]

    def get(self, request):
        client = get_active_client(request.user)
        client_id = getattr(settings, "YOOKASSA_CLIENT_ID", "")
        auth_base_url = getattr(settings, "YOOKASSA_OAUTH_AUTHORIZE_URL", "https://yookassa.ru/oauth/v2/authorize")

        if not client_id:
            return Response(
                {"detail": "YooKassa OAuth не настроен на сервере."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        auth_url = (
            f"{auth_base_url}"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&state={client.uuid}"  # используем UUID клиента как state для безопасности
        )
        return Response({"redirect_url": auth_url})


class YooKassaOAuthCallbackView(APIView):
    """
    Шаг 2: принимает code от YooKassa, обменивает на токен, регистрирует вебхуки.
    GET /payments/yookassa/callback/?code=...&state=<client_uuid>
    """
    permission_classes = [AllowAny]  # это публичный callback от YooKassa
    authentication_classes: list = []

    def get(self, request):
        code = request.GET.get("code")
        client_uuid = request.GET.get("state")

        if not code or not client_uuid:
            logger.warning("yookassa: oauth callback missing code or state")
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="invalid_params"))

        try:
            client = Client.objects.get(uuid=client_uuid)
        except (Client.DoesNotExist, ValueError):
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="client_not_found"))

        oauth_client_id = getattr(settings, "YOOKASSA_CLIENT_ID", "")
        oauth_client_secret = getattr(settings, "YOOKASSA_CLIENT_SECRET", "")

        if not oauth_client_id or not oauth_client_secret:
            logger.error("yookassa: oauth callback called but oauth credentials are not configured")
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="oauth_not_configured"))

        # Обмениваем code → OAuth-токен
        try:
            resp = _exchange_oauth_code(code, oauth_client_id, oauth_client_secret, str(client_uuid))
        except requests.RequestException:
            logger.exception("yookassa: oauth token exchange failed client_uuid=%s", client_uuid)
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="connection_failed"))

        if resp.status_code != 200:
            logger.error(
                "yookassa: oauth token exchange error status=%s body=%s client_uuid=%s",
                resp.status_code, resp.text, client_uuid,
            )
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="token_exchange_failed"))

        try:
            token_data = resp.json()
        except ValueError:
            logger.error("yookassa: oauth token exchange returned non-json body client_uuid=%s", client_uuid)
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="token_exchange_failed"))
        oauth_token = token_data.get("access_token")

        if not oauth_token:
            logger.error("yookassa: oauth response missing access_token client_uuid=%s", client_uuid)
            return HttpResponseRedirect(_build_settings_redirect_url(yookassa_error="missing_access_token"))

        # Сохраняем токен и помечаем клиента как подключённого
        client.yookassa_oauth_token = oauth_token
        client.yookassa_connected = True
        client.save(update_fields=["yookassa_oauth_token", "yookassa_connected"])

        logger.info("yookassa: oauth connected client_id=%s", client.id)

        # Автоматически регистрируем вебхуки для этого клиента
        _register_client_webhooks(client)

        # Редиректим обратно в настройки
        return HttpResponseRedirect(_build_settings_redirect_url(connected="true"))


class YooKassaOAuthDisconnectView(APIView):
    """
    Отключает YooKassa от клиента.
    POST /payments/yookassa/disconnect/
    """
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        client.yookassa_oauth_token = None
        client.yookassa_connected = False
        client.save(update_fields=["yookassa_oauth_token", "yookassa_connected"])
        logger.info("yookassa: oauth disconnected client_id=%s", client.id)
        return Response({"ok": True})


class YooKassaSaveCredentialsView(APIView):
    """
    Сохраняет ручные ключи клиента (альтернатива OAuth).
    POST /payments/yookassa/credentials/
    Body: { "shop_id": "...", "secret_key": "..." }
    """
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        shop_id = (request.data.get("shop_id") or "").strip()
        secret_key = (request.data.get("secret_key") or "").strip()

        if not shop_id or not secret_key:
            return Response(
                {"detail": "shop_id и secret_key обязательны."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверяем ключи запросом к YooKassa (GET /v3/me или любой тестовый вызов)
        try:
            check_resp = _yookassa_request(
                "GET",
                "https://api.yookassa.ru/v3/me",
                auth=(shop_id, secret_key),
                timeout=10,
            )
        except requests.RequestException:
            logger.exception("yookassa: credentials check failed client_id=%s", client.id)
            return Response({"detail": "Не удалось проверить ключи."}, status=status.HTTP_502_BAD_GATEWAY)

        if check_resp.status_code == 401:
            return Response(
                {"detail": "Неверный shop_id или secret_key."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client.yookassa_shop_id = shop_id
        client.yookassa_secret_key = secret_key
        client.yookassa_connected = True
        client.save(update_fields=["yookassa_shop_id", "yookassa_secret_key", "yookassa_connected"])

        logger.info("yookassa: manual credentials saved client_id=%s shop_id=%s", client.id, shop_id)

        # Автоматически регистрируем вебхуки
        _register_client_webhooks(client)

        return Response({"ok": True, "webhook_url": _get_client_webhook_url(client)})


# ---------------------------------------------------------------------------
# UPDATED: CreatePayment — теперь берёт ключи клиента
# ---------------------------------------------------------------------------

class YooKassaCreatePaymentView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        user = request.user
        api_url = settings.YOOKASSA_API_URL

        # ---- Берём ключи клиента (или глобальные как fallback) ----
        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)

        if not secret_or_token:
            logger.error("yookassa: credentials are missing for client_id=%s", client.id)
            return Response(
                {"detail": "YooKassa не подключена. Пожалуйста, настройте оплату в разделе настроек."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_raw = request.data.get("amount")
        currency = request.data.get("currency", "RUB")
        description = (request.data.get("description") or "Payment").strip()

        # return_url: сначала из запроса, потом клиентский, потом глобальный
        return_url = (
            request.data.get("return_url")
            or _get_client_return_url(client)
            or settings.YOOKASSA_RETURN_URL
        )

        metadata = request.data.get("metadata")
        plan_id = request.data.get("plan_id") or request.data.get("plan")
        if isinstance(metadata, dict) and not plan_id:
            plan_id = metadata.get("plan")
        is_dev = _is_dev_user(user)
        plan = None

        logger.info(
            "yookassa: create payment requested client_id=%s amount=%s plan_id=%s auth_type=%s is_dev=%s",
            client.id, amount_raw, plan_id, auth_type, is_dev,
        )

        if not return_url:
            return Response({"detail": "return_url is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_dev:
            if not plan_id:
                return Response({"detail": "Plan is required."}, status=status.HTTP_400_BAD_REQUEST)
            plan = PaymentPlan.objects.filter(code=plan_id, is_active=True).first()
            if not plan:
                return Response({"detail": "Unknown plan."}, status=status.HTTP_400_BAD_REQUEST)
            amount = plan.amount
            currency = plan.currency or "RUB"
            description = f"Оплата тарифа {plan.name}"
        else:
            try:
                amount = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError):
                return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
            if amount <= 0:
                return Response({"detail": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        idempotence_key = str(uuid.uuid4())
        metadata_payload: dict[str, str] = {
            "client_id": str(client.id),
            "client_slug": str(client.slug),
            "telegram_id": str(client.slug),
            "telegram_username": str(user.username),
            "telegram_user_id": str(user.id),
        }

        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if value is None:
                    continue
                metadata_payload[str(key)] = str(value)

        if plan_id:
            metadata_payload.setdefault("plan", str(plan_id))
        if plan:
            metadata_payload.setdefault("plan_name", plan.name)
            metadata_payload.setdefault("plan_period", plan.period)

        metadata_email = _normalize_email(metadata_payload.get("email"))
        if metadata_email and metadata_email != user.email:
            user.email = metadata_email
            user.save(update_fields=["email"])

        payload: dict[str, object] = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": metadata_payload,
        }

        request_kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, idempotence_key)

        try:
            response = _yookassa_request("POST", api_url, json=payload, timeout=15, **request_kwargs)
        except requests.RequestException as exc:
            logger.exception("yookassa: request failed idempotence_key=%s", idempotence_key)
            return Response({"detail": f"YooKassa request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if response.status_code not in (200, 201):
            logger.error(
                "yookassa: error status=%s idempotence_key=%s body=%s",
                response.status_code, idempotence_key, response.text,
            )
            return Response(
                {"detail": "YooKassa returned an error.", "status_code": response.status_code, "body": response.text},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        payment_id = data.get("id")
        confirmation = data.get("confirmation") or {}

        # ---- Сохраняем payment_id → client для надёжной идентификации в вебхуке ----
        if payment_id:
            YooKassaPayment.objects.get_or_create(
                payment_id=payment_id,
                defaults={"client": client, "status": "pending", "amount": amount},
            )

        logger.info(
            "yookassa: payment created id=%s status=%s client_id=%s auth_type=%s",
            payment_id, data.get("status"), client.id, auth_type,
        )

        response_payload = dict(data)
        response_payload["confirmation_url"] = confirmation.get("confirmation_url")
        return Response(response_payload, status=status.HTTP_201_CREATED)


class YooKassaCreatePaymentLinkView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        user = request.user
        api_url = settings.YOOKASSA_API_URL

        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)
        if not secret_or_token:
            logger.error("yookassa: credentials are missing for payment link client_id=%s", client.id)
            return Response(
                {"detail": "YooKassa не подключена. Пожалуйста, настройте оплату в разделе настроек."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_raw = request.data.get("amount")
        currency = str(request.data.get("currency") or "RUB").strip().upper() or "RUB"
        description = (request.data.get("description") or "Оплата").strip()
        return_url = (
            request.data.get("return_url")
            or _get_client_return_url(client)
            or settings.YOOKASSA_RETURN_URL
        )

        if not return_url:
            return Response({"detail": "return_url is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"detail": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        idempotence_key = str(uuid.uuid4())
        metadata_payload: dict[str, str] = {
            "client_id": str(client.id),
            "client_slug": str(client.slug),
            "telegram_id": str(client.slug),
            "telegram_username": str(user.username),
            "telegram_user_id": str(user.id),
            "payment_kind": "crm_payment_link",
        }

        raw_metadata = request.data.get("metadata")
        if isinstance(raw_metadata, dict):
            for key, value in raw_metadata.items():
                if value is None:
                    continue
                metadata_payload[str(key)] = str(value)

        metadata_email = _normalize_email(metadata_payload.get("email"))
        if metadata_email and metadata_email != user.email:
            user.email = metadata_email
            user.save(update_fields=["email"])

        payload: dict[str, object] = {
            "amount": {"value": f"{amount:.2f}", "currency": currency},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": metadata_payload,
        }

        request_kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, idempotence_key)

        try:
            response = _yookassa_request("POST", api_url, json=payload, timeout=15, **request_kwargs)
        except requests.RequestException as exc:
            logger.exception("yookassa: payment link request failed idempotence_key=%s", idempotence_key)
            return Response({"detail": f"YooKassa request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if response.status_code not in (200, 201):
            logger.error(
                "yookassa: payment link error status=%s idempotence_key=%s body=%s",
                response.status_code,
                idempotence_key,
                response.text,
            )
            return Response(
                {"detail": "YooKassa returned an error.", "status_code": response.status_code, "body": response.text},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        payment_id = data.get("id")
        confirmation = data.get("confirmation") or {}
        confirmation_url = confirmation.get("confirmation_url")

        if payment_id:
            YooKassaPayment.objects.get_or_create(
                payment_id=payment_id,
                defaults={
                    "client": client,
                    "status": str(data.get("status") or YooKassaPayment.STATUS_PENDING),
                    "amount": amount,
                },
            )

            crm_payment_id = metadata_payload.get("crm_payment_id")
            if crm_payment_id:
                try:
                    crm_payment = MapCRMPayment.objects.filter(id=int(str(crm_payment_id))).first()
                except (TypeError, ValueError):
                    crm_payment = None
                if crm_payment and crm_payment.transaction_id != str(payment_id):
                    crm_payment.transaction_id = str(payment_id)
                    crm_payment.save(update_fields=["transaction_id"])

        return Response(
            {
                "id": payment_id,
                "status": data.get("status"),
                "confirmation_url": confirmation_url,
                "payment_url": confirmation_url,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# UPDATED: PaymentStatus — теперь берёт ключи клиента
# ---------------------------------------------------------------------------

class YooKassaPaymentStatusView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, payment_id: str):
        client = get_active_client(request.user)
        user = request.user
        api_url = settings.YOOKASSA_API_URL.rstrip("/")

        if not payment_id:
            return Response({"detail": "payment_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Проверяем, что этот платёж действительно принадлежит данному клиенту
        yk_payment = YooKassaPayment.objects.filter(payment_id=payment_id, client=client).first()
        if not yk_payment:
            # Fallback: старая проверка по metadata (для платежей, созданных до миграции)
            logger.warning(
                "yookassa: payment_id=%s not found in YooKassaPayment for client_id=%s — falling back to metadata check",
                payment_id, client.id,
            )

        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)

        if not secret_or_token:
            return Response(
                {"detail": "YooKassa credentials are not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        request_kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, str(uuid.uuid4()))
        # Для GET-запроса Idempotence-Key не нужен
        request_kwargs["headers"].pop("Idempotence-Key", None)

        try:
            response = _yookassa_request("GET", f"{api_url}/{payment_id}", timeout=15, **request_kwargs)
        except requests.RequestException as exc:
            logger.exception("yookassa: status request failed payment_id=%s", payment_id)
            return Response({"detail": f"YooKassa request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if response.status_code != 200:
            logger.error(
                "yookassa: status error payment_id=%s status=%s body=%s",
                payment_id, response.status_code, response.text,
            )
            return Response(
                {"detail": "YooKassa returned an error.", "status_code": response.status_code, "body": response.text},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        metadata = data.get("metadata") or {}

        # Проверяем принадлежность платежа клиенту
        mismatches = []
        if not yk_payment:
            # Только если нет записи в YooKassaPayment — проверяем metadata
            if metadata:
                if "client_id" in metadata and str(metadata.get("client_id")) != str(client.id):
                    mismatches.append("client_id")
                if "telegram_id" in metadata and str(metadata.get("telegram_id")) != str(client.slug):
                    mismatches.append("telegram_id")
                if "telegram_user_id" in metadata and str(metadata.get("telegram_user_id")) != str(user.id):
                    mismatches.append("telegram_user_id")

        if mismatches:
            logger.warning("yookassa: status mismatch payment_id=%s fields=%s", payment_id, ",".join(mismatches))
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        if data.get("status") == "succeeded" and data.get("paid"):
            try:
                _apply_payment_plan(data)
                _mark_crm_payment_paid(data)
                if yk_payment:
                    yk_payment.status = "succeeded"
                    yk_payment.save(update_fields=["status"])
                    handle_succeeded_payment(yk_payment)
            except Exception:
                logger.exception("yookassa: failed to apply plan via status payment_id=%s", payment_id)

        logger.info(
            "yookassa: status payment_id=%s status=%s paid=%s",
            payment_id, data.get("status"), data.get("paid"),
        )
        return Response(data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# UPDATED: Webhook — изолирован по client_uuid в URL
# ---------------------------------------------------------------------------

class YooKassaWebhookView(APIView):
    """
    Вебхук привязан к конкретному клиенту через URL:
    POST /payments/webhook/<client_uuid>/

    Авторизация:
     - Если у клиента OAuth: проверяем, что payment_id есть в YooKassaPayment
     - Если у клиента ручные ключи: Basic auth = shop_id:secret_key
     - Fallback: глобальный YOOKASSA_WEBHOOK_SECRET
    """
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def _is_authorized(self, request, client: Client) -> bool:
        authorization = request.headers.get("Authorization", "")

        # 1. Глобальный webhook secret (fallback / legacy)
        expected_secret = getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "")
        if expected_secret:
            if authorization in {expected_secret, f"Bearer {expected_secret}"}:
                return True
            if authorization.startswith("Basic "):
                try:
                    decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
                except Exception:
                    return False
                if decoded in {f"{expected_secret}:", f":{expected_secret}"}:
                    return True

        # 2. Basic auth с ключами клиента
        if getattr(client, "yookassa_shop_id", None) and getattr(client, "yookassa_secret_key", None):
            if authorization.startswith("Basic "):
                try:
                    decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
                except Exception:
                    return False
                if decoded == f"{client.yookassa_shop_id}:{client.yookassa_secret_key}":
                    return True

        # 3. Basic auth с глобальными ключами
        global_shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
        global_secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", "")
        if global_shop_id and global_secret_key:
            if authorization.startswith("Basic "):
                try:
                    decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
                except Exception:
                    return False
                if decoded == f"{global_shop_id}:{global_secret_key}":
                    return True

        # 4. OAuth клиент: YooKassa не шлёт Basic auth — проверка только по payment_id (ниже в post)
        if getattr(client, "yookassa_oauth_token", None):
            return True  # авторизация будет через проверку payment_id в БД

        # 5. Нет ни одного настроенного варианта — пропускаем (legacy поведение)
        if not expected_secret and not global_shop_id:
            return True

        return False

    def post(self, request, client_uuid: str = None):
        # Если URL без client_uuid — legacy режим с глобальными ключами
        client = None
        if client_uuid:
            try:
                client = Client.objects.get(uuid=client_uuid)
            except (Client.DoesNotExist, ValueError):
                logger.warning("yookassa: webhook unknown client_uuid=%s", client_uuid)
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if client and not self._is_authorized(request, client):
            logger.warning("yookassa: webhook unauthorized client_id=%s", client.id if client else "—")
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        if not client and not self._legacy_is_authorized(request):
            logger.warning("yookassa: webhook unauthorized (legacy)")
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}
        event = payload.get("event")
        payment = payload.get("object") or {}
        payment_id = payment.get("id")
        payment_status = payment.get("status")
        paid = payment.get("paid")

        logger.info(
            "yookassa: webhook event=%s payment_id=%s status=%s paid=%s client_id=%s",
            event, payment_id, payment_status, paid, client.id if client else "global",
        )

        # Проверяем принадлежность платежа клиенту через БД (надёжно, не через metadata)
        if client and payment_id:
            yk_payment = YooKassaPayment.objects.filter(payment_id=payment_id, client=client).first()
            if not yk_payment:
                logger.warning(
                    "yookassa: webhook payment_id=%s does not belong to client_id=%s — ignoring",
                    payment_id, client.id,
                )
                # Возвращаем 200, чтобы YooKassa не ретраила, но ничего не применяем
                return Response({"ok": True}, status=status.HTTP_200_OK)

            if event == "payment.succeeded":
                yk_payment.status = "succeeded"
                yk_payment.save(update_fields=["status"])
                try:
                    handle_succeeded_payment(yk_payment)
                except Exception:
                    logger.exception("referral: failed to handle first payment payment_id=%s", payment_id)
            elif event == "payment.canceled":
                yk_payment.status = "canceled"
                yk_payment.save(update_fields=["status"])

        try:
            _apply_payment_plan(payment)
        except Exception:
            logger.exception("yookassa: failed to apply plan payment_id=%s", payment_id)

        try:
            _mark_crm_payment_paid(payment)
        except Exception:
            logger.exception("yookassa: failed to mark crm payment as paid payment_id=%s", payment_id)

        try:
            _send_payment_confirmation(payment)
        except Exception:
            logger.exception("yookassa: failed to send payment email payment_id=%s", payment_id)

        return Response({"ok": True}, status=status.HTTP_200_OK)

    def _legacy_is_authorized(self, request) -> bool:
        """Авторизация для старого /payments/webhook/ без client_uuid."""
        expected_secret = getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "")
        authorization = request.headers.get("Authorization", "")

        if expected_secret:
            if authorization in {expected_secret, f"Bearer {expected_secret}"}:
                return True
            if authorization.startswith("Basic "):
                try:
                    decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
                except Exception:
                    return False
                return decoded in {f"{expected_secret}:", f":{expected_secret}"}
            return False

        if authorization.startswith("Basic "):
            try:
                decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
            except Exception:
                return False
            if decoded == f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}":
                return True
            return False

        return True


# ---------------------------------------------------------------------------
# Остальные вьюхи (без изменений)
# ---------------------------------------------------------------------------

class PaymentPlanListView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        plans = PaymentPlan.objects.filter(is_active=True).order_by("sort_order", "name")
        data = [
            {
                "code": plan.code,
                "name": plan.name,
                "amount": f"{plan.amount:.2f}",
                "currency": plan.currency,
                "period": plan.period,
                "period_label": plan.get_period_display(),
                "description": plan.description or "",
            }
            for plan in plans
        ]
        return Response({"plans": data}, status=status.HTTP_200_OK)


class PaymentSubscriptionView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request):
        client = get_active_client(request.user)
        plan = client.plan
        expires_at = client.plan_expires_at
        now = timezone.now()

        if not plan or not expires_at or expires_at <= now:
            return Response(
                {
                    "plan_name": "Ознакомительный",
                    "plan_code": "trial",
                    "expires_at": None,
                    "is_active": False,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "plan_name": plan.name,
                "plan_code": plan.code,
                "expires_at": expires_at,
                "period": plan.period,
                "period_label": plan.get_period_display(),
                "is_active": True,
            },
            status=status.HTTP_200_OK,
        )


class PaymentPromoCodeApplyView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        raw_code = request.data.get("code") or request.data.get("promo_code")
        code = str(raw_code or "").strip().lower()

        if not code:
            return Response({"detail": "Промокод обязателен."}, status=status.HTTP_400_BAD_REQUEST)

        if code != PROMO_CODE_STARTER:
            return Response({"detail": "Промокод не найден."}, status=status.HTTP_400_BAD_REQUEST)

        plan = PaymentPlan.objects.filter(code="starter", is_active=True).first()
        if not plan:
            logger.error("promo: starter plan missing")
            return Response({"detail": "Тариф starter не настроен."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        now = timezone.now()
        if client.plan_id and client.plan_id != plan.id and client.plan_expires_at and client.plan_expires_at > now:
            until = timezone.localtime(client.plan_expires_at).strftime("%d.%m.%Y")
            return Response(
                {
                    "detail": (
                        f"У вас уже активный тариф {client.plan.name} до {until}. "
                        "Промокод можно применить после окончания."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_date = now
        if client.plan_id == plan.id and client.plan_expires_at and client.plan_expires_at > now:
            base_date = client.plan_expires_at

        expires_at = base_date + relativedelta(months=1)
        client.plan = plan
        client.plan_expires_at = expires_at
        client.save(update_fields=["plan", "plan_expires_at"])

        logger.info("promo: applied code=%s client_id=%s plan=%s expires_at=%s", code, client.id, plan.code, expires_at)

        return Response(
            {
                "success": True,
                "plan_code": plan.code,
                "plan_name": plan.name,
                "expires_at": expires_at,
                "message": "Промокод применен.",
            },
            status=status.HTTP_200_OK,
        )
