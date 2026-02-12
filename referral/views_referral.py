# core/views_referral.py
# API: create_code, my_code, delete_code, stats
# Связь User → Client через UserTenantRole (owner/editor)

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.models import UserTenantRole
from core.referral import Referral, ReferralCode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_for_user(request):
    """
    Возвращает первый Client где request.user имеет роль owner/editor.
    """
    if not request.user.is_authenticated:
        return None
    role = (
        UserTenantRole.objects
        .select_related("client")
        .filter(user=request.user, role__in=("owner", "editor"))
        .first()
    )
    return role.client if role else None


def _code_to_dict(code: ReferralCode) -> dict:
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    referral_url = f"https://t.me/{bot_username}?start={code.code}" if bot_username else ""
    return {
        "id": code.id,
        "code": code.code,
        "referral_url": referral_url,
        "is_active": code.is_active,
        "total_referrals": code.total_referrals,
        "successful_referrals": code.successful_referrals,
        "created_at": code.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /api/referral/create_code/
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def create_code(request):
    client = _get_client_for_user(request)
    if client is None:
        return JsonResponse({"error": "Не авторизован или нет доступного клиента"}, status=401)

    if ReferralCode.objects.filter(client=client).exists():
        return JsonResponse({"error": "Реферальный код уже существует"}, status=400)

    code = ReferralCode.objects.create(
        client=client,
        code=ReferralCode.generate_code(),
    )
    return JsonResponse(_code_to_dict(code), status=201)


# ---------------------------------------------------------------------------
# GET /api/referral/my_code/
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def my_code(request):
    client = _get_client_for_user(request)
    if client is None:
        return JsonResponse({"error": "Не авторизован или нет доступного клиента"}, status=401)

    try:
        code = ReferralCode.objects.get(client=client)
    except ReferralCode.DoesNotExist:
        return JsonResponse(
            {
                "error": "Реферальный код не создан",
                "detail": "Отправьте POST /api/referral/create_code/",
                "has_code": False,
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
    client = _get_client_for_user(request)
    if client is None:
        return JsonResponse({"error": "Не авторизован или нет доступного клиента"}, status=401)

    deleted, _ = ReferralCode.objects.filter(client=client).delete()
    if deleted == 0:
        return JsonResponse({"error": "Реферальный код не найден"}, status=404)

    return JsonResponse({"message": "Реферальный код удалён"})


# ---------------------------------------------------------------------------
# GET /api/referral/stats/
# ---------------------------------------------------------------------------

@require_http_methods(["GET"])
def stats(request):
    client = _get_client_for_user(request)
    if client is None:
        return JsonResponse({"error": "Не авторизован или нет доступного клиента"}, status=401)

    try:
        code = ReferralCode.objects.get(client=client)
    except ReferralCode.DoesNotExist:
        return JsonResponse(
            {
                "has_code": False,
                "error": "Реферальный код не создан",
                "detail": "Отправьте POST /api/referral/create_code/",
            }
        )

    qs = Referral.objects.filter(referrer=client)
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
    referral_url = f"https://t.me/{bot_username}?start={code.code}" if bot_username else ""

    return JsonResponse(
        {
            "has_code": True,
            "referral_code": code.code,
            "referral_url": referral_url,
            "total_referrals": qs.count(),
            "registered_referrals": qs.filter(
                status__in=[Referral.STATUS_REGISTERED, Referral.STATUS_REWARDED]
            ).count(),
            "pending_referrals": qs.filter(status=Referral.STATUS_PENDING).count(),
            "rewarded_referrals": qs.filter(status=Referral.STATUS_REWARDED).count(),
        }
    )
