# core/views_referral.py
# API: create_code, my_code, delete_code, stats
# Связь User → Client через UserTenantRole (owner/editor)

import json
from urllib.parse import parse_qs, unquote, urlparse

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.authentication import CookieJWTAuthentication
from core.models import UserSocialAccount, UserTenantBinding, UserTenantRole
from core.referral import Referral, ReferralCode, reward_referral_month


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _authenticate_cookie_user(request):
    """
    Для обычных Django views вручную поднимаем JWT-аутентификацию
    (как в DRF), чтобы request.user не был AnonymousUser.
    """
    if request.user.is_authenticated:
        return request.user
    try:
        auth_result = CookieJWTAuthentication().authenticate(request)
    except Exception:
        return None
    if not auth_result:
        return None
    user, token = auth_result
    request.user = user
    request.auth = token
    return user


def _get_client_for_user(request):
    """
    Возвращает первый Client где request.user имеет роль owner/editor.
    """
    user = _authenticate_cookie_user(request)
    if not user:
        return None
    role = (
        UserTenantRole.objects.select_related("client")
        .filter(user=user, role__in=("owner", "editor"))
        .first()
    )
    return role.client if role else None


def _code_to_dict(code: ReferralCode) -> dict:
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    referral_url = f"https://t.me/{bot_username}?start={code.code}" if bot_username else ""
    return {
        "id": code.id,
        "code": code.code,
        "code_type": code.code_type,
        "contact_id": code.contact_id,
        "referral_url": referral_url,
        "is_active": code.is_active,
        "total_referrals": code.total_referrals,
        "successful_referrals": code.successful_referrals,
        "created_at": code.created_at.isoformat(),
    }


def _resolve_referral_kind(request) -> str:
    raw = (
        request.GET.get("type")
        or request.GET.get("kind")
        or request.GET.get("program")
        or ""
    ).strip().lower()
    if raw == ReferralCode.TYPE_CONTACT:
        return ReferralCode.TYPE_CONTACT
    return ReferralCode.TYPE_CLIENT


def _parse_positive_int(raw_value):
    if raw_value is None:
        return None
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _extract_referral_code_from_text(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    parsed_value = value
    try:
        url = urlparse(value)
        if url.scheme and url.netloc:
            start_values = parse_qs(url.query).get("start", [])
            if start_values:
                parsed_value = start_values[0]
    except Exception:
        parsed_value = value

    if "start=" in parsed_value and not parsed_value.lower().startswith("ref_"):
        tail = parsed_value.split("start=", 1)[1]
        parsed_value = tail.split("&", 1)[0]

    parsed_value = unquote(parsed_value).strip()
    lower = parsed_value.lower()
    if lower.startswith("ref_c"):
        return f"ref_c{parsed_value[5:].upper()}"
    if lower.startswith("ref_"):
        return f"ref_{parsed_value[4:].upper()}"
    return parsed_value


def _extract_referral_code_from_request(request) -> str:
    code = (request.POST.get("code") or "").strip()
    if not code:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            code = str(payload.get("code") or "").strip()
        except Exception:
            code = ""
    return _extract_referral_code_from_text(code)


def _get_telegram_identity_for_user(user):
    linked_telegram = (
        UserSocialAccount.objects.filter(
            user=user,
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    if not linked_telegram:
        return None, ""

    telegram_id = _parse_positive_int(linked_telegram.provider_id)
    extra = linked_telegram.extra_data if isinstance(linked_telegram.extra_data, dict) else {}
    username = str(extra.get("username") or user.username or "").strip()
    return telegram_id, username


def _get_contact_id_for_user_and_client(request, client) -> int | None:
    user = _authenticate_cookie_user(request)
    if not user:
        return None

    linked_telegram = (
        UserSocialAccount.objects.filter(
            user=user,
            provider=UserSocialAccount.PROVIDER_TELEGRAM,
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    telegram_id = (
        str(linked_telegram.provider_id)
        if linked_telegram and linked_telegram.provider_id
        else str(user.id)
    )

    binding = (
        UserTenantBinding.objects.filter(
            provider=UserTenantBinding.PROVIDER_TELEGRAM,
            provider_user_id=telegram_id,
            tenant_id=client.id,
            is_active=True,
        )
        .order_by("-bound_at", "-id")
        .first()
    )
    if not binding or binding.contact_id is None:
        return None

    try:
        value = int(binding.contact_id)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resolve_scope(request):
    client = _get_client_for_user(request)
    if client is None:
        return None, None, None, JsonResponse(
            {"error": "Не авторизован или нет доступного клиента"},
            status=401,
        )

    kind = _resolve_referral_kind(request)
    if kind == ReferralCode.TYPE_CONTACT:
        explicit_contact_id = _parse_positive_int(request.GET.get("contact_id"))
        if explicit_contact_id:
            return client, kind, explicit_contact_id, None

        contact_id = _get_contact_id_for_user_and_client(request, client)
        if not contact_id:
            return None, None, None, JsonResponse(
                {"error": "Для контактной реферальной программы не найден contact_id"},
                status=400,
            )
        return client, kind, contact_id, None

    return client, ReferralCode.TYPE_CLIENT, None, None


def _get_referral_code(client, code_type: str, contact_id: int | None) -> ReferralCode | None:
    qs = ReferralCode.objects.filter(client=client, code_type=code_type)
    if code_type == ReferralCode.TYPE_CONTACT:
        qs = qs.filter(contact_id=contact_id)
    else:
        qs = qs.filter(contact_id__isnull=True)
    return qs.order_by("-id").first()


def _serialize_referral_item(referral: Referral) -> dict:
    code = referral.referral_code
    return {
        "id": referral.id,
        "code": code.code,
        "code_type": code.code_type,
        "code_contact_id": code.contact_id,
        "status": referral.status,
        "invited_telegram_id": referral.invited_telegram_id,
        "invited_telegram_username": referral.invited_telegram_username,
        "created_at": referral.created_at.isoformat() if referral.created_at else None,
        "registered_at": referral.registered_at.isoformat() if referral.registered_at else None,
        "rewarded_at": referral.rewarded_at.isoformat() if referral.rewarded_at else None,
        "referee_client_id": referral.referee_id,
    }


def _get_referrals_queryset(client, code_type: str, code: ReferralCode | None):
    if code_type == ReferralCode.TYPE_CLIENT:
        return Referral.objects.filter(referrer=client)
    if code is None:
        return Referral.objects.none()
    return Referral.objects.filter(referral_code=code)


def _apply_referral_code_for_client(client, referral_code: ReferralCode, telegram_id: int | None, telegram_username: str):
    existing_other = (
        Referral.objects.filter(referee=client)
        .exclude(referral_code=referral_code)
        .exclude(status=Referral.STATUS_EXPIRED)
        .first()
    )
    if existing_other is not None:
        return None, JsonResponse({"error": "Реферальный код уже был применён ранее"}, status=400)

    referral = (
        Referral.objects.filter(referral_code=referral_code, referee=client)
        .order_by("-id")
        .first()
    )
    if referral is None:
        referral = Referral.objects.create(
            referral_code=referral_code,
            referrer=referral_code.client,
            invited_telegram_id=telegram_id,
            invited_telegram_username=telegram_username or "",
            expires_at=None,
        )
    return referral, None


def _apply_referral_code_for_contact(client, actor_contact_id: int | None, referral_code: ReferralCode, telegram_id: int | None, telegram_username: str):
    if client.id != referral_code.client_id:
        return None, JsonResponse({"error": "Контактный код можно применять только в рамках этого клиента"}, status=400)

    if actor_contact_id and referral_code.contact_id and actor_contact_id == referral_code.contact_id:
        return None, JsonResponse({"error": "Нельзя применить собственный реферальный код"}, status=400)

    if telegram_id is None:
        return None, JsonResponse({"error": "Не удалось определить Telegram-пользователя"}, status=400)

    existing_other = (
        Referral.objects.filter(
            invited_telegram_id=telegram_id,
            referral_code__code_type=ReferralCode.TYPE_CONTACT,
            referral_code__client_id=referral_code.client_id,
        )
        .exclude(referral_code=referral_code)
        .exclude(status=Referral.STATUS_EXPIRED)
        .first()
    )
    if existing_other is not None:
        return None, JsonResponse({"error": "Реферальный код уже был применён ранее"}, status=400)

    referral = (
        Referral.objects.filter(
            referral_code=referral_code,
            invited_telegram_id=telegram_id,
        )
        .order_by("-id")
        .first()
    )
    if referral is None:
        referral = Referral.objects.create(
            referral_code=referral_code,
            referrer=referral_code.client,
            invited_telegram_id=telegram_id,
            invited_telegram_username=telegram_username or "",
            expires_at=None,
        )
    return referral, None


# ---------------------------------------------------------------------------
# POST /api/referral/create_code/
# ---------------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["POST"])
def create_code(request):
    client, code_type, contact_id, scope_error = _resolve_scope(request)
    if scope_error is not None:
        return scope_error

    if _get_referral_code(client, code_type, contact_id) is not None:
        return JsonResponse({"error": "Реферальный код уже существует"}, status=400)

    code = ReferralCode.objects.create(
        client=client,
        code_type=code_type,
        contact_id=contact_id,
        code=ReferralCode.generate_code(code_type=code_type),
    )
    return JsonResponse(_code_to_dict(code), status=201)


@csrf_exempt
@require_http_methods(["POST"])
def apply_code(request):
    user = _authenticate_cookie_user(request)
    if not user:
        return JsonResponse({"error": "Не авторизован"}, status=401)

    client = _get_client_for_user(request)
    if client is None:
        return JsonResponse({"error": "Не авторизован или нет доступного клиента"}, status=401)

    code_raw = _extract_referral_code_from_request(request)
    if not code_raw:
        return JsonResponse({"error": "Укажите реферальный код"}, status=400)

    referral_code = (
        ReferralCode.objects.select_related("client")
        .filter(code=code_raw, is_active=True)
        .first()
    )
    if referral_code is None:
        return JsonResponse({"error": "Реферальный код не найден"}, status=404)

    actor_contact_id = _parse_positive_int(request.GET.get("contact_id"))
    if actor_contact_id is None:
        actor_contact_id = _get_contact_id_for_user_and_client(request, client)

    if referral_code.code_type == ReferralCode.TYPE_CLIENT and referral_code.client_id == client.id:
        return JsonResponse({"error": "Нельзя применить собственный реферальный код"}, status=400)

    telegram_id, telegram_username = _get_telegram_identity_for_user(user)

    if referral_code.code_type == ReferralCode.TYPE_CLIENT:
        referral, referral_error = _apply_referral_code_for_client(
            client,
            referral_code,
            telegram_id,
            telegram_username,
        )
    else:
        referral, referral_error = _apply_referral_code_for_contact(
            client,
            actor_contact_id,
            referral_code,
            telegram_id,
            telegram_username,
        )
    if referral_error is not None:
        return referral_error
    if referral is None:
        return JsonResponse({"error": "Не удалось применить код"}, status=400)

    if referral.status in {Referral.STATUS_REGISTERED, Referral.STATUS_REWARDED}:
        return JsonResponse(
            {
                "ok": True,
                "already_applied": True,
                "message": "Код уже был применён ранее.",
                "referral_type": referral.referral_code.code_type,
            }
        )

    try:
        with transaction.atomic():
            referral.mark_registered(client)
            if referral.referral_code.code_type == ReferralCode.TYPE_CLIENT and referral.referrer_id != client.id:
                reward_referral_month(referrer=referral.referrer, referee=client)
            referral.mark_rewarded()
    except Exception:
        return JsonResponse({"error": "Не удалось применить код. Попробуйте позже."}, status=500)

    return JsonResponse(
        {
            "ok": True,
            "already_applied": False,
            "message": "Код применён. Приглашение засчитано.",
            "referral_type": referral.referral_code.code_type,
        }
    )


# ---------------------------------------------------------------------------
# GET /api/referral/my_code/
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def my_code(request):
    client, code_type, contact_id, scope_error = _resolve_scope(request)
    if scope_error is not None:
        return scope_error

    code = _get_referral_code(client, code_type, contact_id)
    if code is None:
        return JsonResponse(
            {
                "error": "Реферальный код не создан",
                "detail": "Отправьте POST /api/referral/create_code/",
                "has_code": False,
                "referral_type": code_type,
            },
            status=404,
        )
    return JsonResponse(_code_to_dict(code))


# ---------------------------------------------------------------------------
# DELETE /api/referral/delete_code/
# ---------------------------------------------------------------------------


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_code(request):
    client, code_type, contact_id, scope_error = _resolve_scope(request)
    if scope_error is not None:
        return scope_error

    qs = ReferralCode.objects.filter(client=client, code_type=code_type)
    if code_type == ReferralCode.TYPE_CONTACT:
        qs = qs.filter(contact_id=contact_id)
    else:
        qs = qs.filter(contact_id__isnull=True)
    deleted, _ = qs.delete()
    if deleted == 0:
        return JsonResponse({"error": "Реферальный код не найден"}, status=404)

    return JsonResponse({"message": "Реферальный код удалён"})


# ---------------------------------------------------------------------------
# GET /api/referral/stats/
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
def stats(request):
    client, code_type, contact_id, scope_error = _resolve_scope(request)
    if scope_error is not None:
        return scope_error

    code = _get_referral_code(client, code_type, contact_id)
    if code is None:
        return JsonResponse(
            {
                "has_code": False,
                "error": "Реферальный код не создан",
                "detail": "Отправьте POST /api/referral/create_code/",
                "referral_type": code_type,
            }
        )

    qs = _get_referrals_queryset(client, code_type, code)
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    referral_url = f"https://t.me/{bot_username}?start={code.code}" if bot_username else ""
    invitations = [
        _serialize_referral_item(referral)
        for referral in qs.select_related("referral_code").order_by("-created_at", "-id")[:100]
    ]

    return JsonResponse(
        {
            "has_code": True,
            "referral_type": code_type,
            "referral_code": code.code,
            "referral_url": referral_url,
            "total_referrals": qs.count(),
            "registered_referrals": qs.filter(status__in=[Referral.STATUS_REGISTERED, Referral.STATUS_REWARDED]).count(),
            "pending_referrals": qs.filter(status=Referral.STATUS_PENDING).count(),
            "rewarded_referrals": qs.filter(status=Referral.STATUS_REWARDED).count(),
            "invitations": invitations,
        }
    )


@require_http_methods(["GET"])
def invitations(request):
    client, code_type, contact_id, scope_error = _resolve_scope(request)
    if scope_error is not None:
        return scope_error

    code = _get_referral_code(client, code_type, contact_id)
    if code_type == ReferralCode.TYPE_CONTACT and code is None:
        return JsonResponse(
            {
                "has_code": False,
                "referral_type": code_type,
                "items": [],
            }
        )

    qs = _get_referrals_queryset(client, code_type, code)
    items = [
        _serialize_referral_item(referral)
        for referral in qs.select_related("referral_code").order_by("-created_at", "-id")[:200]
    ]
    return JsonResponse(
        {
            "has_code": code is not None,
            "referral_type": code_type,
            "items": items,
        }
    )
