from __future__ import annotations

from django.conf import settings
from django.core import signing
from django.http import HttpRequest

from core.models import InviteLink


COACH_INVITE_COOKIE = "coach_invite_session"
COACH_INVITE_COOKIE_SALT = "coach-invite-session"
COACH_INVITE_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def build_frontend_url(request: HttpRequest, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    frontend_base = str(getattr(settings, "PUBLIC_FRONTEND_BASE_URL", "") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = request.build_absolute_uri("/").rstrip("/")
    return f"{frontend_base}{normalized_path}"


def set_coach_invite_cookie(response, invite: InviteLink) -> None:
    payload = {
        "invite_id": int(invite.id),
        "tenant_id": int(invite.tenant_id),
        "contact_id": int(invite.contact_id),
    }
    signed_payload = signing.dumps(payload, salt=COACH_INVITE_COOKIE_SALT)
    response.set_cookie(
        COACH_INVITE_COOKIE,
        signed_payload,
        httponly=True,
        secure=not settings.DEBUG,
        samesite=getattr(settings, "JWT_COOKIE_SAMESITE", "Lax"),
        path="/",
    )


def resolve_coach_invite_contact_id(request: HttpRequest, client_id: int) -> int | None:
    raw_cookie = request.COOKIES.get(COACH_INVITE_COOKIE)
    if not raw_cookie:
        return None

    try:
        payload = signing.loads(
            raw_cookie,
            salt=COACH_INVITE_COOKIE_SALT,
            max_age=COACH_INVITE_COOKIE_MAX_AGE,
        )
    except signing.SignatureExpired:
        return None
    except signing.BadSignature:
        return None

    try:
        invite_id = int(payload.get("invite_id"))
        tenant_id = int(payload.get("tenant_id"))
        contact_id = int(payload.get("contact_id"))
    except (TypeError, ValueError):
        return None

    if tenant_id != int(client_id) or contact_id <= 0:
        return None

    invite = (
        InviteLink.objects
        .filter(
            id=invite_id,
            tenant_id=tenant_id,
            contact_id=contact_id,
            used_at__isnull=False,
        )
        .first()
    )
    if invite is None:
        return None

    return contact_id
