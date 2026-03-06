from __future__ import annotations

import hashlib
import logging
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
    CRMTask,
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
from core.tasks.chains import _send_telegram_message, _send_vk_message

from .authentication import CookieJWTAuthentication
from .views_payments import (
    _build_yookassa_request_kwargs,
    _get_yookassa_credentials,
    _yookassa_request,
)


logger = logging.getLogger(__name__)
crm_workflow_dispatcher = CRMWorkflowDispatcher()

PAYMENT_PROVIDER_YOOKASSA = YooKassaPayment.PROVIDER_YOOKASSA
PAYMENT_PROVIDER_TBANK = YooKassaPayment.PROVIDER_TBANK
SUPPORTED_PAYMENT_PROVIDERS = {PAYMENT_PROVIDER_YOOKASSA, PAYMENT_PROVIDER_TBANK}
TBANK_SUCCESS_STATUSES = {"CONFIRMED"}
TBANK_FAILED_STATUSES = {"REJECTED", "CANCELLED", "DEADLINE_EXPIRED"}


def _resolve_public_payment_provider(raw_value: object) -> str:
    provider = str(raw_value or PAYMENT_PROVIDER_YOOKASSA).strip().lower()
    if provider not in SUPPORTED_PAYMENT_PROVIDERS:
        return ""
    return provider


def _map_tbank_status_to_internal(status_value: object) -> str:
    status_raw = str(status_value or "").strip().upper()
    if status_raw in TBANK_SUCCESS_STATUSES:
        return YooKassaPayment.STATUS_SUCCEEDED
    if status_raw in TBANK_FAILED_STATUSES:
        return YooKassaPayment.STATUS_CANCELED
    return YooKassaPayment.STATUS_PENDING


def _generate_tbank_token(params: dict, secret_key: str) -> str:
    filtered = {
        key: value
        for key, value in params.items()
        if key not in {"Token", "Receipt", "DATA", "Items"}
        and not isinstance(value, (dict, list))
    }
    filtered["Password"] = secret_key
    token_source = "".join(str(value) for key, value in sorted(filtered.items()))
    return hashlib.sha256(token_source.encode("utf-8")).hexdigest()


def _get_tbank_credentials(client: Client) -> tuple[str, str]:
    terminal_key = str(getattr(client, "tbank_terminal_key", "") or "").strip()
    secret_key = str(getattr(client, "tbank_secret_key", "") or "").strip()
    if terminal_key and secret_key:
        return terminal_key, secret_key

    return (
        str(getattr(settings, "TBANK_TERMINAL_KEY", "") or "").strip(),
        str(getattr(settings, "TBANK_SECRET_KEY", "") or "").strip(),
    )


def _is_tbank_test_mode(client: Client, terminal_key: str, secret_key: str) -> bool:
    if bool(getattr(client, "tbank_test_mode", False)):
        return True
    return terminal_key == "TinkoffBankTest" or secret_key == "TinkoffBankTest"


def _tbank_request(endpoint: str, payload: dict, *, terminal_key: str, secret_key: str, timeout: int = 15) -> dict:
    prepared = dict(payload)
    prepared["TerminalKey"] = terminal_key
    prepared["Token"] = _generate_tbank_token(prepared, secret_key)

    session = requests.Session()
    session.trust_env = False
    try:
        response = session.post(
            f"{str(getattr(settings, 'TBANK_API_URL', 'https://securepay.tinkoff.ru/v2')).rstrip('/')}/{endpoint}",
            json=prepared,
            timeout=timeout,
        )
    finally:
        session.close()

    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("Invalid T-Bank response")
    return result


def _parse_digital_product_plan_code(plan_code: object) -> tuple[int | None, int | None, int | None]:
    raw = str(plan_code or "").strip()
    if not raw.startswith("digital_product:"):
        return None, None, None

    chunks = raw.split(":")
    if len(chunks) < 2:
        return None, None, None

    product_id: int | None = None
    contact_id: int | None = None
    package_index: int | None = None
    try:
        product_id = int(chunks[1])
    except (TypeError, ValueError):
        product_id = None

    index = 2
    while index + 1 < len(chunks):
        token = chunks[index]
        value = chunks[index + 1]
        if token == "contact":
            try:
                contact_id = int(value)
            except (TypeError, ValueError):
                contact_id = None
        elif token == "package":
            try:
                parsed_package_index = int(value)
                package_index = parsed_package_index if parsed_package_index >= 0 else None
            except (TypeError, ValueError):
                package_index = None
        index += 2

    return product_id, contact_id, package_index


def _resolve_product_price(product: ClientProduct, package_index: int | None = None) -> tuple[Decimal | None, dict | None, int | None]:
    packages = product.packages if isinstance(product.packages, list) else []
    if package_index is not None:
        if package_index < 0 or package_index >= len(packages):
            return None, None, None
        item = packages[package_index]
        if not isinstance(item, dict):
            return None, None, None
        raw_price = item.get("price")
        try:
            price = Decimal(str(raw_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None, None, None
        if price > 0:
            return price, item, package_index
        return None, None, None

    for index, item in enumerate(packages):
        raw_price = item.get("price") if isinstance(item, dict) else None
        try:
            price = Decimal(str(raw_price)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if price > 0 and isinstance(item, dict):
            return price, item, index
    return None, None, None


def _resolve_product_package_payload(product: ClientProduct | None, package_index: int | None) -> dict[str, object] | None:
    if product is None or package_index is None:
        return None

    raw_packages = product.packages if isinstance(product.packages, list) else []
    if package_index < 0 or package_index >= len(raw_packages):
        return None

    raw_package = raw_packages[package_index]
    if not isinstance(raw_package, dict):
        return None

    package_name = str(raw_package.get("name") or "").strip()
    package_description = str(raw_package.get("description") or "").strip()
    package_price: str | None = None
    try:
        parsed_price = Decimal(str(raw_package.get("price"))).quantize(Decimal("0.01"))
        if parsed_price > 0:
            package_price = f"{parsed_price:.2f}"
    except (InvalidOperation, TypeError, ValueError):
        package_price = None

    return {
        "index": int(package_index),
        "name": package_name or f"Пакет {package_index + 1}",
        "description": package_description,
        "price": package_price,
    }


def _infer_product_package_index_by_amount(product: ClientProduct | None, amount: Decimal | None) -> int | None:
    if product is None or amount is None:
        return None

    raw_packages = product.packages if isinstance(product.packages, list) else []
    matches: list[int] = []
    for index, raw_package in enumerate(raw_packages):
        if not isinstance(raw_package, dict):
            continue
        try:
            package_price = Decimal(str(raw_package.get("price"))).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if package_price > 0 and package_price == amount:
            matches.append(index)

    if len(matches) == 1:
        return matches[0]
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
) -> tuple[ContactProductPurchase | None, bool]:
    if payment_payload.get("status") != "succeeded" or not payment_payload.get("paid"):
        return None, False

    metadata = payment_payload.get("metadata") or {}
    if str(metadata.get("payment_kind") or "") != "digital_product":
        return None, False
    if str(metadata.get("client_id") or "") != str(client.id):
        return None, False

    try:
        product_id = int(str(metadata.get("product_id") or ""))
    except (TypeError, ValueError):
        return None, False
    if product_id <= 0:
        return None, False

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
        return None, False

    selected_package_index: int | None = None
    try:
        selected_package_index_raw = metadata.get("package_index")
        if selected_package_index_raw not in (None, ""):
            parsed_package_index = int(str(selected_package_index_raw))
            if parsed_package_index >= 0:
                selected_package_index = parsed_package_index
    except (TypeError, ValueError):
        selected_package_index = None

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
        grant_service_package_to_purchase(
            purchase=purchase,
            product=product,
            top_up=True,
            package_index=selected_package_index,
        )
    return purchase, (not already_processed_same_payment)


def _resolve_contact_binding_for_notification(*, client_id: int, contact_id: int | None) -> UserTenantBinding | None:
    if contact_id is None:
        return None
    try:
        contact_id_int = int(contact_id)
    except (TypeError, ValueError):
        return None
    if contact_id_int <= 0:
        return None

    return (
        UserTenantBinding.objects
        .filter(
            tenant_id=client_id,
            contact_id=contact_id_int,
            is_active=True,
            provider__in=(UserTenantBinding.PROVIDER_TELEGRAM, UserTenantBinding.PROVIDER_VK),
        )
        .order_by("-bound_at", "-id")
        .first()
    )


def _format_purchase_success_message(
    *,
    product: ClientProduct | None,
    amount: str | None,
    currency: str | None,
) -> str:
    product_name = (getattr(product, "name", "") or "").strip()
    structure = product.structure if isinstance(getattr(product, "structure", None), dict) else {}
    is_event = isinstance(structure.get("event"), dict)
    item_label = "мероприятие" if is_event else "товар"

    message_lines = [
        "Оплата прошла успешно.",
        f"Вы купили {item_label}{f': {product_name}' if product_name else ''}.",
    ]

    amount_label = ""
    try:
        parsed_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        if parsed_amount > 0:
            amount_label = f"{parsed_amount:.2f}"
    except (InvalidOperation, TypeError, ValueError):
        amount_label = ""
    currency_label = (str(currency or "RUB").strip().upper()[:3] or "RUB")
    if amount_label:
        message_lines.append(f"Сумма: {amount_label} {currency_label}")

    return "\n".join(message_lines)


def _notify_contact_purchase_success(
    *,
    client: Client,
    contact_id: int | None,
    product: ClientProduct | None,
    amount: str | None,
    currency: str | None,
) -> bool:
    binding = _resolve_contact_binding_for_notification(client_id=client.id, contact_id=contact_id)
    if binding is None:
        return False

    message_text = _format_purchase_success_message(
        product=product,
        amount=amount,
        currency=currency,
    )
    provider = str(getattr(binding, "provider", "") or "").strip().lower()
    provider_user_id = str(getattr(binding, "provider_user_id", "") or "").strip()
    if provider == UserTenantBinding.PROVIDER_TELEGRAM:
        chat_id_raw = provider_user_id
        if not chat_id_raw:
            telegram_chat_id = getattr(binding, "telegram_chat_id", None)
            if telegram_chat_id is not None:
                chat_id_raw = str(telegram_chat_id)
        try:
            chat_id = int(chat_id_raw)
        except (TypeError, ValueError):
            logger.warning(
                "purchase notification skipped: invalid telegram chat id client_id=%s contact_id=%s value=%r",
                client.id,
                contact_id,
                chat_id_raw,
            )
            return False
        return _send_telegram_message(chat_id, text=message_text)

    if provider == UserTenantBinding.PROVIDER_VK:
        if not provider_user_id:
            logger.warning(
                "purchase notification skipped: empty vk provider_user_id client_id=%s contact_id=%s",
                client.id,
                contact_id,
            )
            return False
        return _send_vk_message(
            tenant_id=client.id,
            vk_user_id=provider_user_id,
            text=message_text,
        )

    return False


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


class PublicClientPageTasksView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def get(self, request, client_id: int):
        client_exists = Client.objects.filter(id=client_id).exists()
        if not client_exists:
            raise Http404("Клиент не найден")

        contact_id = _resolve_request_contact_id_for_client(request, client_id)
        if contact_id is None or contact_id <= 0:
            return Response(
                {"detail": "Для просмотра заданий войдите как контакт через Telegram или VK."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        items = list(
            CRMTask.objects
            .filter(contact_id=int(contact_id))
            .values(
                "id",
                "contact_id",
                "title",
                "description",
                "status",
                "priority",
                "created_at",
                "updated_at",
            )
            .order_by("-updated_at", "-id")
        )

        return Response(
            {
                "contact_id": int(contact_id),
                "items": items,
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

        package_index: int | None = None
        package_index_raw = request.data.get("package_index")
        if package_index_raw not in (None, ""):
            try:
                parsed_package_index = int(package_index_raw)
            except (TypeError, ValueError):
                return Response({"detail": "package_index must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
            if parsed_package_index < 0:
                return Response({"detail": "package_index must be >= 0."}, status=status.HTTP_400_BAD_REQUEST)
            package_index = parsed_package_index

        product = (
            ClientProduct.objects
            .filter(owner_id=client_id, id=product_id, status=ClientProduct.STATUS_ACTIVE)
            .first()
        )
        if not product:
            return Response({"detail": "Продукт не найден или недоступен."}, status=status.HTTP_404_NOT_FOUND)

        amount, selected_package, resolved_package_index = _resolve_product_price(product, package_index=package_index)
        if amount is None:
            if package_index is None:
                return Response({"detail": "Для продукта не указана цена."}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Пакет не найден или у него не указана цена."}, status=status.HTTP_400_BAD_REQUEST)

        provider = _resolve_public_payment_provider(request.data.get("provider"))
        if not provider:
            return Response(
                {"detail": "Некорректный провайдер оплаты. Используйте yookassa или tbank."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return_url = str(request.data.get("return_url") or "").strip() or _build_client_page_return_url(client_id)
        metadata_payload: dict[str, str] = {
            "payment_kind": "digital_product",
            "client_id": str(client.id),
            "client_slug": str(client.slug),
            "product_id": str(product.id),
            "product_name": (product.name or "").strip()[:128],
        }
        if resolved_package_index is not None:
            metadata_payload["package_index"] = str(resolved_package_index)
        if isinstance(selected_package, dict):
            package_name = str(selected_package.get("name") or "").strip()
            if package_name:
                metadata_payload["package_name"] = package_name[:128]
        bound_contact_id = _resolve_request_contact_id_for_client(request, client_id)
        if bound_contact_id is None or bound_contact_id <= 0:
            return Response(
                {"detail": "Для покупки войдите как контакт через Telegram или VK."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        metadata_payload["contact_id"] = str(bound_contact_id)
        plan_code = f"digital_product:{product.id}:contact:{bound_contact_id}"
        if resolved_package_index is not None:
            plan_code = f"digital_product:{product.id}:package:{resolved_package_index}:contact:{bound_contact_id}"

        if provider == PAYMENT_PROVIDER_TBANK:
            terminal_key, secret_key = _get_tbank_credentials(client)
            if not terminal_key or not secret_key:
                return Response(
                    {"detail": "T-Bank для этого клиента не настроен."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            is_test_mode = _is_tbank_test_mode(client, terminal_key, secret_key)

            order_id = f"cp-{client.id}-{product.id}-{uuid.uuid4().hex[:16]}"
            payload = {
                "OrderId": order_id,
                "Amount": int(amount * 100),
                "Description": f"Покупка продукта: {(product.name or '').strip() or f'#{product.id}'}",
                "SuccessURL": return_url,
                "FailURL": return_url,
                "DATA": metadata_payload,
            }

            try:
                data = _tbank_request(
                    "Init",
                    payload,
                    terminal_key=terminal_key,
                    secret_key=secret_key,
                    timeout=15,
                )
            except requests.RequestException as exc:
                return Response({"detail": f"T-Bank request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
            except ValueError:
                return Response({"detail": "T-Bank returned invalid response."}, status=status.HTTP_502_BAD_GATEWAY)

            if not data.get("Success"):
                return Response(
                    {"detail": "T-Bank returned an error.", "body": data},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            payment_id = str(data.get("PaymentId") or "").strip()
            payment_url = str(data.get("PaymentURL") or "").strip()
            mapped_status = _map_tbank_status_to_internal(data.get("Status"))

            if payment_id:
                YooKassaPayment.objects.get_or_create(
                    payment_id=payment_id,
                    defaults={
                        "client": client,
                        "provider": PAYMENT_PROVIDER_TBANK,
                        "status": mapped_status,
                        "amount": amount,
                        "plan_code": plan_code,
                    },
                )

            return Response(
                {
                    "id": payment_id,
                    "status": mapped_status,
                    "provider": PAYMENT_PROVIDER_TBANK,
                    "test_mode": is_test_mode,
                    "payment_url": payment_url,
                    "confirmation_url": payment_url,
                    "product_id": product.id,
                },
                status=status.HTTP_201_CREATED,
            )

        shop_id, secret_or_token, auth_type = _get_yookassa_credentials(client)
        if not secret_or_token:
            return Response(
                {"detail": "Оплата для этого клиента не настроена."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        idempotence_key = str(uuid.uuid4())
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
                    "provider": PAYMENT_PROVIDER_YOOKASSA,
                    "status": str(data.get("status") or YooKassaPayment.STATUS_PENDING),
                    "amount": amount,
                    "plan_code": plan_code,
                },
            )

        return Response(
            {
                "id": payment_id,
                "status": data.get("status"),
                "provider": PAYMENT_PROVIDER_YOOKASSA,
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
        provider = str(getattr(yk_payment, "provider", PAYMENT_PROVIDER_YOOKASSA) or PAYMENT_PROVIDER_YOOKASSA).strip().lower()
        fallback_contact_id = _resolve_request_contact_id_for_client(request, client_id)

        metadata: dict[str, object] = {}
        amount_value: str | None = None
        currency_value = "RUB"
        payment_status = YooKassaPayment.STATUS_PENDING
        paid = False
        product_id: int | None = None
        metadata_contact_id: int | None = None
        is_test_mode = False

        if provider == PAYMENT_PROVIDER_TBANK:
            terminal_key, secret_key = _get_tbank_credentials(client)
            if not terminal_key or not secret_key:
                return Response({"detail": "T-Bank для этого клиента не настроен."}, status=status.HTTP_400_BAD_REQUEST)
            is_test_mode = _is_tbank_test_mode(client, terminal_key, secret_key)

            try:
                data = _tbank_request(
                    "GetState",
                    {"PaymentId": payment_id},
                    terminal_key=terminal_key,
                    secret_key=secret_key,
                    timeout=15,
                )
            except requests.RequestException as exc:
                return Response({"detail": f"T-Bank request failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
            except ValueError:
                return Response({"detail": "T-Bank returned invalid response."}, status=status.HTTP_502_BAD_GATEWAY)

            if not data.get("Success"):
                return Response({"detail": "T-Bank returned an error.", "body": data}, status=status.HTTP_502_BAD_GATEWAY)

            payment_status = _map_tbank_status_to_internal(data.get("Status"))
            paid = payment_status == YooKassaPayment.STATUS_SUCCEEDED

            amount_raw = data.get("Amount")
            try:
                amount_decimal = Decimal(str(amount_raw)) / Decimal("100")
                amount_value = f"{amount_decimal:.2f}"
            except (InvalidOperation, TypeError, ValueError):
                amount_value = f"{yk_payment.amount:.2f}" if yk_payment.amount is not None else None

            parsed_product_id, parsed_contact_id, parsed_package_index = _parse_digital_product_plan_code(yk_payment.plan_code)
            product_id = parsed_product_id
            metadata_contact_id = parsed_contact_id
            metadata = {
                "payment_kind": "digital_product",
                "client_id": str(client.id),
                "product_id": str(product_id) if product_id is not None else "",
                "contact_id": str(metadata_contact_id) if metadata_contact_id is not None else "",
            }
            if parsed_package_index is not None:
                metadata["package_index"] = str(parsed_package_index)
            payment_payload = {
                "id": payment_id,
                "status": payment_status,
                "paid": paid,
                "metadata": metadata,
                "amount": {"value": amount_value, "currency": currency_value},
            }
        else:
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

            payment_payload = response.json()
            metadata = payment_payload.get("metadata") or {}
            if str(metadata.get("client_id") or "") != str(client.id):
                return Response({"detail": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)
            if str(metadata.get("payment_kind") or "") != "digital_product":
                return Response({"detail": "Платеж не найден."}, status=status.HTTP_404_NOT_FOUND)

            payment_status = str(payment_payload.get("status") or YooKassaPayment.STATUS_PENDING)
            paid = bool(payment_payload.get("paid"))
            amount_value = str((payment_payload.get("amount") or {}).get("value") or "") or None
            currency_value = str((payment_payload.get("amount") or {}).get("currency") or "RUB").strip().upper() or "RUB"

            try:
                product_id = int(str(metadata.get("product_id")))
            except (TypeError, ValueError):
                product_id = None
            try:
                metadata_contact_raw = metadata.get("contact_id")
                if metadata_contact_raw not in (None, ""):
                    metadata_contact_id = int(str(metadata_contact_raw))
            except (TypeError, ValueError):
                metadata_contact_id = None

        if yk_payment.status != payment_status and payment_status:
            yk_payment.status = payment_status
            yk_payment.save(update_fields=["status"])

        result: dict[str, object] = {
            "payment_id": payment_id,
            "provider": provider,
            "status": payment_status,
            "paid": paid,
            "delivery": None,
        }
        if provider == PAYMENT_PROVIDER_TBANK:
            result["test_mode"] = is_test_mode

        if payment_status == YooKassaPayment.STATUS_SUCCEEDED and paid:
            purchase, purchase_was_new_payment = _record_contact_product_purchase(
                client=client,
                yk_payment=yk_payment,
                payment_payload=payment_payload,
                fallback_contact_id=fallback_contact_id,
            )
            if previous_payment_status != YooKassaPayment.STATUS_SUCCEEDED:
                crm_workflow_dispatcher.dispatch_payment_paid(
                    tenant_id=client.id,
                    contact_id=metadata_contact_id or fallback_contact_id,
                    payment_payload={
                        "payment_id": payment_id,
                        "status": payment_status,
                        "paid": paid,
                        "amount": amount_value,
                        "currency": currency_value,
                        "provider": provider,
                        "provider_payment_id": payment_id,
                    },
                )

            product = (
                ClientProduct.objects
                .select_related("digital_product_document")
                .filter(owner_id=client_id, id=product_id)
                .first()
                if product_id is not None
                else None
            )
            result["delivery"] = _build_digital_product_delivery_payload(client, product)
            if purchase_was_new_payment:
                contact_id_for_notification: int | None = None
                if purchase is not None and getattr(purchase, "contact_id", None) is not None:
                    try:
                        contact_id_for_notification = int(getattr(purchase, "contact_id"))
                    except (TypeError, ValueError):
                        contact_id_for_notification = None
                if contact_id_for_notification is None:
                    contact_id_for_notification = metadata_contact_id or fallback_contact_id

                _notify_contact_purchase_success(
                    client=client,
                    contact_id=contact_id_for_notification,
                    product=product,
                    amount=amount_value,
                    currency=currency_value,
                )

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
            selected_package_index: int | None = None
            if purchase.last_payment_id and purchase.last_payment:
                parsed_product_id, _, parsed_package_index = _parse_digital_product_plan_code(purchase.last_payment.plan_code)
                if parsed_product_id in (None, int(purchase.product_id)):
                    selected_package_index = parsed_package_index
            if selected_package_index is None:
                selected_package_index = _infer_product_package_index_by_amount(product, purchase.amount)
            package_payload = _resolve_product_package_payload(product, selected_package_index)
            items.append(
                {
                    "id": purchase.id,
                    "product_id": int(purchase.product_id),
                    "product_name": product_name,
                    "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
                    "amount": str(purchase.amount) if purchase.amount is not None else None,
                    "currency": purchase.currency or "RUB",
                    "payment_id": purchase.last_payment.payment_id if purchase.last_payment_id else None,
                    "package": package_payload,
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
