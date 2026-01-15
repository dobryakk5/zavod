from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from base64 import b64decode
from datetime import datetime

import requests
from django.conf import settings
import logging
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsTenantMember
from .utils import get_active_client
from core.models import Client, PaymentPlan

logger = logging.getLogger(__name__)
User = get_user_model()

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
    logger.info("yookassa: plan applied client_id=%s plan=%s expires_at=%s", client_id, plan.code, expires_at)


class YooKassaCreatePaymentView(APIView):
    permission_classes = [IsTenantMember]

    def post(self, request):
        client = get_active_client(request.user)
        user = request.user
        shop_id = settings.YOOKASSA_SHOP_ID
        secret_key = settings.YOOKASSA_SECRET_KEY
        api_url = settings.YOOKASSA_API_URL

        if not shop_id or not secret_key:
            logger.error("yookassa: credentials are missing")
            return Response(
                {"detail": "YooKassa credentials are not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        amount_raw = request.data.get("amount")
        currency = request.data.get("currency", "RUB")
        description = (request.data.get("description") or "Payment").strip()
        return_url = request.data.get("return_url") or settings.YOOKASSA_RETURN_URL
        metadata = request.data.get("metadata")
        plan_id = request.data.get("plan_id") or request.data.get("plan")
        if isinstance(metadata, dict) and not plan_id:
            plan_id = metadata.get("plan")
        is_dev = _is_dev_user(user)
        plan = None

        logger.info(
            "yookassa: create payment requested amount=%s currency=%s return_url=%s plan_id=%s is_dev=%s",
            amount_raw,
            currency,
            return_url,
            plan_id,
            is_dev,
        )

        if not return_url:
            logger.warning("yookassa: return_url is missing")
            return Response(
                {"detail": "return_url is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_dev:
            if not plan_id:
                logger.warning("yookassa: missing plan_id")
                return Response(
                    {"detail": "Plan is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plan = PaymentPlan.objects.filter(code=plan_id, is_active=True).first()
            if not plan:
                logger.warning("yookassa: unknown plan_id=%s", plan_id)
                return Response(
                    {"detail": "Unknown plan."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            amount = plan.amount
            currency = plan.currency or "RUB"
            description = f"Оплата тарифа {plan.name}"
        else:
            try:
                amount = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError):
                logger.warning("yookassa: invalid amount=%s", amount_raw)
                return Response(
                    {"detail": "Invalid amount."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if amount <= 0:
                logger.warning("yookassa: non-positive amount=%s", amount)
                return Response(
                    {"detail": "Amount must be greater than zero."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
        }

        if metadata_payload:
            payload["metadata"] = metadata_payload

        try:
            response = requests.post(
                api_url,
                json=payload,
                auth=(shop_id, secret_key),
                headers={
                    "Idempotence-Key": idempotence_key,
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.exception("yookassa: request failed idempotence_key=%s", idempotence_key)
            return Response(
                {"detail": f"YooKassa request failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if response.status_code not in (200, 201):
            logger.error(
                "yookassa: error status=%s idempotence_key=%s body=%s",
                response.status_code,
                idempotence_key,
                response.text,
            )
            return Response(
                {
                    "detail": "YooKassa returned an error.",
                    "status_code": response.status_code,
                    "body": response.text,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        confirmation = data.get("confirmation") or {}

        logger.info(
            "yookassa: payment created id=%s status=%s idempotence_key=%s",
            data.get("id"),
            data.get("status"),
            idempotence_key,
        )
        response_payload = dict(data)
        response_payload["confirmation_url"] = confirmation.get("confirmation_url")

        return Response(response_payload, status=status.HTTP_201_CREATED)


class YooKassaPaymentStatusView(APIView):
    permission_classes = [IsTenantMember]

    def get(self, request, payment_id: str):
        client = get_active_client(request.user)
        user = request.user
        shop_id = settings.YOOKASSA_SHOP_ID
        secret_key = settings.YOOKASSA_SECRET_KEY
        api_url = settings.YOOKASSA_API_URL.rstrip("/")

        if not shop_id or not secret_key:
            logger.error("yookassa: credentials are missing for status")
            return Response(
                {"detail": "YooKassa credentials are not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not payment_id:
            return Response(
                {"detail": "payment_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response = requests.get(
                f"{api_url}/{payment_id}",
                auth=(shop_id, secret_key),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.exception("yookassa: status request failed payment_id=%s", payment_id)
            return Response(
                {"detail": f"YooKassa request failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if response.status_code != 200:
            logger.error(
                "yookassa: status error payment_id=%s status=%s body=%s",
                payment_id,
                response.status_code,
                response.text,
            )
            return Response(
                {
                    "detail": "YooKassa returned an error.",
                    "status_code": response.status_code,
                    "body": response.text,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        metadata = data.get("metadata") or {}
        mismatches = []
        if metadata:
            if "client_id" in metadata and str(metadata.get("client_id")) != str(client.id):
                mismatches.append("client_id")
            if "telegram_id" in metadata and str(metadata.get("telegram_id")) != str(client.slug):
                mismatches.append("telegram_id")
            if "telegram_user_id" in metadata and str(metadata.get("telegram_user_id")) != str(user.id):
                mismatches.append("telegram_user_id")

        if mismatches:
            logger.warning(
                "yookassa: status mismatch payment_id=%s fields=%s",
                payment_id,
                ",".join(mismatches),
            )
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        logger.info(
            "yookassa: status payment_id=%s status=%s paid=%s",
            payment_id,
            data.get("status"),
            data.get("paid"),
        )

        return Response(data, status=status.HTTP_200_OK)


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


class YooKassaWebhookView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def _is_authorized(self, request) -> bool:
        expected_secret = settings.YOOKASSA_WEBHOOK_SECRET
        authorization = request.headers.get("Authorization", "")

        if expected_secret:
            if authorization == expected_secret or authorization == f"Bearer {expected_secret}":
                return True

            if authorization.startswith("Basic "):
                try:
                    decoded = b64decode(authorization.split(" ", 1)[1]).decode("utf-8")
                except Exception:
                    return False
                if decoded in {f"{expected_secret}:", f":{expected_secret}"}:
                    return True

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

    def post(self, request):
        if not self._is_authorized(request):
            logger.warning("yookassa: webhook unauthorized")
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}
        event = payload.get("event")
        payment = payload.get("object") or {}
        payment_id = payment.get("id")
        payment_status = payment.get("status")
        paid = payment.get("paid")
        metadata = payment.get("metadata") or {}

        logger.info(
            "yookassa: webhook event=%s payment_id=%s status=%s paid=%s metadata=%s",
            event,
            payment_id,
            payment_status,
            paid,
            metadata,
        )

        try:
            _apply_payment_plan(payment)
        except Exception:
            logger.exception("yookassa: failed to apply plan payment_id=%s", payment_id)

        try:
            _send_payment_confirmation(payment)
        except Exception:
            logger.exception("yookassa: failed to send payment email payment_id=%s", payment_id)

        return Response({"ok": True}, status=status.HTTP_200_OK)
