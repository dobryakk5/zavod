from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import OperationalError, ProgrammingError, transaction
from django.utils import timezone

from core.models import EmailAuthToken

_MAGIC_LINK_TTL = 15 * 60


class EmailAuthStorageUnavailableError(RuntimeError):
    """Raised when email auth persistence is unavailable in the current database."""


def normalize_email_address(value: str) -> str:
    return str(value or "").strip().lower()


def build_frontend_url(request) -> str:
    frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if frontend_url:
        return frontend_url

    origin = str(request.headers.get("Origin", "") or "").strip().rstrip("/")
    if origin:
        return origin

    return request.build_absolute_uri("/").rstrip("/")


def issue_email_auth_token(email: str) -> EmailAuthToken:
    normalized_email = normalize_email_address(email)
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(seconds=_MAGIC_LINK_TTL)

    try:
        with transaction.atomic():
            EmailAuthToken.objects.filter(email=normalized_email).delete()
            return EmailAuthToken.objects.create(
                email=normalized_email,
                token=token,
                expires_at=expires_at,
            )
    except (ProgrammingError, OperationalError) as exc:
        raise EmailAuthStorageUnavailableError("Email auth token storage is unavailable") from exc


def build_magic_link_url(request, token: str) -> str:
    return f"{build_frontend_url(request)}/auth/email/verify?token={token}"


def send_email_login_link(email: str, magic_url: str) -> None:
    send_mail(
        subject="Вход в личный кабинет",
        message=(
            "Для входа перейдите по ссылке. Она действительна 15 минут:\n\n"
            f"{magic_url}\n\n"
            "Если вы не запрашивали вход, просто проигнорируйте это письмо."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalize_email_address(email)],
        fail_silently=False,
    )


def send_team_invite_email(email: str, magic_url: str, *, project_name: str, inviter_name: str) -> None:
    send_mail(
        subject=f"Приглашение в команду {project_name}",
        message=(
            f"{inviter_name} пригласил(а) вас в команду проекта «{project_name}».\n\n"
            "Для входа и активации доступа перейдите по ссылке:\n"
            f"{magic_url}\n\n"
            "Ссылка одноразовая и действует 15 минут."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[normalize_email_address(email)],
        fail_silently=False,
    )
