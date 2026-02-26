from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Client,
    ClientProduct,
    ContactProductPurchase,
    KbDocumentShare,
    MapAvailabilityEvent,
    UserSocialAccount,
    UserTenantBinding,
    YooKassaPayment,
)
from core.services.contact_service_packages import (
    build_service_package_payload,
    grant_service_package_to_purchase,
)
from core.services.crm_workflow_dispatcher import CRMWorkflowDispatcher

from .authentication import CookieJWTAuthentication
from .views_payments import (
    _build_yookassa_request_kwargs,
    _get_yookassa_credentials,
    _yookassa_request,
)


crm_workflow_dispatcher = CRMWorkflowDispatcher()


def _resolve_product_price(product: ClientProduct) -> Decimal | None:
    packages = product.packages if isinstance(product.packages, list) else []
    for item in packages:
        raw_price = item.get("price") if isinstance(item, dict) else None
        try:
            price = Decimal(str(raw_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


def _build_client_page_return_url(client_id: int) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    path = f"/c/{client_id}"
    return f"{base_url}{path}" if base_url else path


def _build_kb_share_url(token: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    path = f"/kb/share/{token}"
    return f"{base_url}{path}" if base_url else path


def _issue_share_token() -> str:
    return secrets.token_hex(16)


def _get_or_create_active_share(document_id: int) -> KbDocumentShare:
    existing = (
        KbDocumentShare.objects
        .filter(document_id=document_id, is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .order_by("-created_at")
        .first()
    )
    if existing:
        return existing

    token = _issue_share_token()
    while KbDocumentShare.objects.filter(share_token=token).exists():
        token = _issue_share_token()
    return KbDocumentShare.objects.create(
        document_id=document_id,
        share_token=token,
        permission="view",
        is_active=True,
    )


def _parse_payment_timestamp(value: object) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return timezone.now()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone=dt_timezone.utc)
        return parsed
    except ValueError:
        return timezone.now()


def _authenticate_cookie_user_optional(request):
    current_user = getattr(request, "user", None)
    if current_user is not None and getattr(current_user, "is_authenticated", False):
        return current_user

    authenticator = CookieJWTAuthentication()
    try:
        auth_result = authenticator.authenticate(request)
    except Exception:
        return None

    if not auth_result:
        return None

    user, token = auth_result
    request.user = user
    request.auth = token
    return user


def _resolve_bound_contact_id_for_client(user, client_id: int) -> int | None:
    if not user or not getattr(user, "is_authenticated", False):
        return None

    social_accounts = list(
        UserSocialAccount.objects
        .filter(
            user=user,
            provider__in=(UserSocialAccount.PROVIDER_TELEGRAM, UserSocialAccount.PROVIDER_VK),
        )
        .values_list("provider", "provider_id")
    )
    if not social_accounts:
        return None

    candidates: list[UserTenantBinding] = []
    for provider, provider_id in social_accounts:
        if not provider_id:
            continue
        binding = (
            UserTenantBinding.objects
            .filter(
                provider=provider,
                provider_user_id=str(provider_id),
                tenant_id=client_id,
                is_active=True,
            )
            .order_by("-bound_at", "-id")
            .first()
        )
        if binding and binding.contact_id is not None:
            candidates.append(binding)

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item.bound_at or timezone.now(), item.id or 0), reverse=True)
    return int(candidates[0].contact_id) if candidates[0].contact_id is not None else None


def _resolve_request_contact_id_for_client(request, client_id: int) -> int | None:
    user = _authenticate_cookie_user_optional(request)
    return _resolve_bound_contact_id_for_client(user, client_id)


def _build_digital_product_delivery_payload(client: Client, product: ClientProduct | None) -> dict[str, object]:
    document = getattr(product, "digital_product_document", None)
    if document and document.workspace_id == client.id and not getattr(document, "is_archived", False):
        share = _get_or_create_active_share(document.id)
        return {
            "ready": True,
            "document_id": document.id,
            "document_title": document.title,
            "url": _build_kb_share_url(share.share_token),
        }
    return {
        "ready": False,
        "missing_product_page": True,
        "message": "Покажите информацию об оплате владельцу портала",
    }


def _record_contact_product_purchase(
    *,
    client: Client,
    yk_payment: YooKassaPayment,
    payment_payload: dict,
    fallback_contact_id: int | None = None,
) -> ContactProductPurchase | None:
    if payment_payload.get("status") != "succeeded" or not payment_payload.get("paid"):
        return None

    metadata = payment_payload.get("metadata") or {}
    if str(metadata.get("payment_kind") or "") != "digital_product":
        return None
    if str(metadata.get("client_id") or "") != str(client.id):
        return None

    try:
        product_id = int(str(metadata.get("product_id") or ""))
    except (TypeError, ValueError):
        return None
    if product_id <= 0:
        return None

    contact_id = None
    try:
        contact_id_raw = metadata.get("contact_id")
        if contact_id_raw not in (None, ""):
            contact_id = int(str(contact_id_raw))
    except (TypeError, ValueError):
        contact_id = None

    if contact_id is None and fallback_contact_id is not None:
        contact_id = int(fallback_contact_id)
    if contact_id is None or contact_id <= 0:
        return None

    product = (
        ClientProduct.objects
        .filter(owner_id=client.id, id=product_id)
        .only("id", "name", "packages")
        .first()
    )

    amount_value = (payment_payload.get("amount") or {}).get("value")
    try:
        amount = Decimal(str(amount_value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        amount = yk_payment.amount

    currency = str((payment_payload.get("amount") or {}).get("currency") or "RUB").strip().upper()[:3] or "RUB"
    paid_at = _parse_payment_timestamp(
        payment_payload.get("captured_at") or payment_payload.get("paid_at") or payment_payload.get("created_at")
    )
    product_name = (
        (getattr(product, "name", "") or "").strip()
        or str(metadata.get("product_name") or "").strip()[:255]
    )

    existing_purchase = (
        ContactProductPurchase.objects
        .filter(client=client, contact_id=contact_id, product_id=product_id)
        .only("id", "last_payment_id")
        .first()
    )
    already_processed_same_payment = bool(
        existing_purchase is not None
        and existing_purchase.last_payment_id == yk_payment.id
    )

    purchase, _ = ContactProductPurchase.objects.update_or_create(
        client=client,
        contact_id=contact_id,
        product_id=product_id,
        defaults={
            "product_name": product_name,
            "last_payment": yk_payment,
            "amount": amount,
            "currency": currency,
            "paid_at": paid_at,
        },
    )
    if not already_processed_same_payment:
        grant_service_package_to_purchase(purchase=purchase, product=product, top_up=True)
    return purchase


class PublicClientPageView(APIView):
    """Public read-only data for /c/<client_id> page."""

    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request, client_id: int):
        client = (
            Client.objects
            .filter(id=client_id)
            .values(
                "id",
                "name",
                "brand_name",
                "niche",
                "product_service",
                "timezone",
                "client_page_config",
                "client_page_content",
            )
            .first()
        )
        if not client:
            raise Http404("Клиент не найден")

        products = list(
            ClientProduct.objects
            .filter(owner_id=client_id)
            .values(
                "id",
                "name",
                "status",
                "short_description",
                "digital_product_document_id",
                "packages",
                "structure",
                "created_at",
                "updated_at",
            )
            .order_by("-updated_at")
        )

        availability_events = list(
            MapAvailabilityEvent.objects
            .filter(tenant_id=client_id)
            .values(
                "id",
                "tenant_id",
                "start_time",
                "duration_minutes",
                "repeat_type",
                "created_at",
                "updated_at",
            )
            .order_by("-start_time")
        )

        return Response(
            {
                "client": {
                    "id": client["id"],
                    "name": client.get("name") or "",
                },
                "settings": {
                    "brand_name": client.get("brand_name") or "",
                    "niche": client.get("niche") or "",
                    "product_service": client.get("product_service") or "",
                    "timezone": client.get("timezone") or "Europe/Moscow",
                    "client_page_config": client.get("client_page_config") or {},
                    "client_page_content": client.get("client_page_content") or {},
                },
                "products": products,
                "availability_events": availability_events,
                # Public mode intentionally does not expose tenant CRM events.
                # Frontend uses this endpoint for read-only rendering and gates booking by auth.
                "events": [],
            }
        )


class PublicClientPageBuyProductView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request, client_id: int):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            raise Http404("Клиент не найден")

        try:
            product_id = int(request.data.get("product_id"))
        except (TypeError, ValueError):
            return Response({"detail": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        product = (
            ClientProduct.objects
            .filter(owner_id=client_id, id=product_id, status=ClientProduct.STATUS_ACTIVE)
            .first()
        )
        if not product:
            return Response({"detail": "Продукт не найден или недоступен."}, status=status.HTTP_404_NOT_FOUND)

        amount = _resolve_product_price(product)
        if not amount:
            return Response({"detail": "Для продукта не указана цена."}, status=status.HTTP_400_BAD_REQUEST)

        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)
        if not secret_or_token:
            return Response(
                {"detail": "Оплата для этого клиента не настроена."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return_url = str(request.data.get("return_url") or "").strip() or _build_client_page_return_url(client_id)
        idempotence_key = str(uuid.uuid4())
        metadata_payload = {
            "payment_kind": "digital_product",
            "client_id": str(client.id),
            "client_slug": str(client.slug),
            "product_id": str(product.id),
            "product_name": (product.name or "").strip()[:128],
        }
        bound_contact_id = _resolve_request_contact_id_for_client(request, client_id)
        if bound_contact_id is None or bound_contact_id <= 0:
            return Response(
                {"detail": "Для покупки войдите как контакт через Telegram или VK."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        metadata_payload["contact_id"] = str(bound_contact_id)
        payload = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": f"Покупка продукта: {(product.name or '').strip() or f'#{product.id}'}",
            "metadata": metadata_payload,
        }
        request_kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, idempotence_key)

        try:
            response = _yookassa_request(
                "POST",
                settings.YOOKASSA_API_URL,
                json=payload,
                timeout=15,
                **request_kwargs,
            )
        except requests.RequestException as exc:
            return Response({"detail": f"YooKassa request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if response.status_code not in (200, 201):
            return Response(
                {"detail": "YooKassa returned an error.", "body": response.text, "status_code": response.status_code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        payment_id = str(data.get("id") or "").strip()
        confirmation = data.get("confirmation") or {}
        confirmation_url = str(confirmation.get("confirmation_url") or "").strip()

        if payment_id:
            YooKassaPayment.objects.get_or_create(
                payment_id=payment_id,
                defaults={
                    "client": client,
                    "status": str(data.get("status") or YooKassaPayment.STATUS_PENDING),
                    "amount": amount,
                    "plan_code": f"digital_product:{product.id}",
                },
            )

        return Response(
            {
                "id": payment_id,
                "status": data.get("status"),
                "payment_url": confirmation_url,
                "confirmation_url": confirmation_url,
                "product_id": product.id,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicClientPagePaymentStatusView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request, client_id: int):
        payment_id = str(request.query_params.get("payment_id") or "").strip()
        if not payment_id:
            return Response({"detail": "payment_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.filter(id=client_id).first()
        if not client:
            raise Http404("Клиент не найден")

        yk_payment = YooKassaPayment.objects.filter(payment_id=payment_id, client=client).first()
        if not yk_payment:
            return Response({"detail": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
        previous_payment_status = str(yk_payment.status or "")

        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)
        if not secret_or_token:
            return Response({"detail": "Оплата для этого клиента не настроена."}, status=status.HTTP_400_BAD_REQUEST)

        request_kwargs = _build_yookassa_request_kwargs(shop_id, secret_or_token, auth_type, str(uuid.uuid4()))
        request_kwargs["headers"].pop("Idempotence-Key", None)
        api_url = f"{settings.YOOKASSA_API_URL.rstrip('/')}/{payment_id}"

        try:
            response = _yookassa_request("GET", api_url, timeout=15, **request_kwargs)
        except requests.RequestException as exc:
            return Response({"detail": f"YooKassa request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        if response.status_code != 200:
            return Response(
                {"detail": "YooKassa returned an error.", "body": response.text, "status_code": response.status_code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = response.json()
        metadata = data.get("metadata") or {}
        if str(metadata.get("client_id") or "") != str(client.id):
            return Response({"detail": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
        if str(metadata.get("payment_kind") or "") != "digital_product":
            return Response({"detail": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)

        payment_status = str(data.get("status") or "")
        if yk_payment.status != payment_status and payment_status:
            yk_payment.status = payment_status
            yk_payment.save(update_fields=["status"])

        result: dict[str, object] = {
            "payment_id": payment_id,
            "status": payment_status,
            "paid": bool(data.get("paid")),
            "delivery": None,
        }

        if payment_status == "succeeded" and data.get("paid"):
            fallback_contact_id = _resolve_request_contact_id_for_client(request, client_id)
            _record_contact_product_purchase(
                client=client,
                yk_payment=yk_payment,
                payment_payload=data,
                fallback_contact_id=fallback_contact_id,
            )
            if previous_payment_status != "succeeded":
                metadata_contact_id = None
                try:
                    metadata_contact_raw = metadata.get("contact_id")
                    if metadata_contact_raw not in (None, ""):
                        metadata_contact_id = int(str(metadata_contact_raw))
                except (TypeError, ValueError):
                    metadata_contact_id = None
                crm_workflow_dispatcher.dispatch_payment_paid(
                    tenant_id=client.id,
                    contact_id=metadata_contact_id or fallback_contact_id,
                    payment_payload={
                        "payment_id": payment_id,
                        "status": payment_status,
                        "paid": bool(data.get("paid")),
                        "amount": (data.get("amount") or {}).get("value"),
                        "currency": (data.get("amount") or {}).get("currency"),
                        "provider": "yookassa",
                        "provider_payment_id": payment_id,
                    },
                )
            try:
                product_id = int(str(metadata.get("product_id")))
            except (TypeError, ValueError):
                product_id = None

            product = (
                ClientProduct.objects
                .select_related("digital_product_document")
                .filter(owner_id=client_id, id=product_id)
                .first()
                if product_id is not None
                else None
            )
            result["delivery"] = _build_digital_product_delivery_payload(client, product)

        return Response(result)


class PublicClientPagePurchasesView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request, client_id: int):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            raise Http404("Клиент не найден")

        contact_id = _resolve_request_contact_id_for_client(request, client_id)
        if contact_id is None:
            return Response(
                {"detail": "Войдите как контакт через Telegram или VK."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        purchases = list(
            ContactProductPurchase.objects
            .select_related("last_payment")
            .filter(client=client, contact_id=contact_id)
            .order_by("-paid_at", "-updated_at", "-id")
        )

        products_by_id = {
            int(product.id): product
            for product in (
                ClientProduct.objects
                .select_related("digital_product_document")
                .filter(owner_id=client.id, id__in=[item.product_id for item in purchases])
            )
        }

        items: list[dict[str, object]] = []
        for purchase in purchases:
            product = products_by_id.get(int(purchase.product_id))
            product_name = (
                ((product.name if product else "") or "").strip()
                or (purchase.product_name or "").strip()
                or f"Продукт #{purchase.product_id}"
            )
            items.append(
                {
                    "id": purchase.id,
                    "product_id": int(purchase.product_id),
                    "product_name": product_name,
                    "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
                    "amount": str(purchase.amount) if purchase.amount is not None else None,
                    "currency": purchase.currency or "RUB",
                    "payment_id": purchase.last_payment.payment_id if purchase.last_payment_id else None,
                    "delivery": _build_digital_product_delivery_payload(client, product),
                    "service_package": build_service_package_payload(purchase),
                }
            )

        return Response(
            {
                "contact_id": int(contact_id),
                "items": items,
            }
        )
