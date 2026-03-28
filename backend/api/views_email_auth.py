from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import EmailAuthToken

from .views_accounts import COOKIE_MAX_AGE, REFRESH_COOKIE_MAX_AGE, set_token_cookie

User = get_user_model()

_MAGIC_LINK_TTL = 15 * 60
_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW = 60 * 60


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _build_frontend_url(request) -> str:
    frontend_url = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if frontend_url:
        return frontend_url

    origin = str(request.headers.get("Origin", "") or "").strip().rstrip("/")
    if origin:
        return origin

    return request.build_absolute_uri("/").rstrip("/")


def _generate_unique_username(email: str) -> str:
    base_username = email[:150]
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix_text = f"-{suffix}"
        username = f"{base_username[: 150 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return username


class EmailMagicLinkSendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        email = _normalize_email(request.data.get("email"))

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"detail": "Укажите корректный email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rate_key = f"magic_link_rate:{email}"
        sends = int(cache.get(rate_key, 0) or 0)
        if sends >= _RATE_LIMIT_MAX:
            return Response(
                {"detail": "Слишком много запросов. Попробуйте через час."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        cache.set(rate_key, sends + 1, timeout=_RATE_LIMIT_WINDOW)

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(seconds=_MAGIC_LINK_TTL)

        with transaction.atomic():
            EmailAuthToken.objects.filter(email=email).delete()
            EmailAuthToken.objects.create(email=email, token=token, expires_at=expires_at)

        magic_url = f"{_build_frontend_url(request)}/auth/email/verify?token={token}"

        send_mail(
            subject="Вход в личный кабинет",
            message=(
                "Для входа перейдите по ссылке. Она действительна 15 минут:\n\n"
                f"{magic_url}\n\n"
                "Если вы не запрашивали вход, просто проигнорируйте это письмо."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({"detail": "Письмо отправлено."}, status=status.HTTP_200_OK)


class EmailMagicLinkVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: tuple = ()

    def post(self, request):
        token = str(request.data.get("token") or "").strip()
        if not token:
            return Response(
                {"detail": "Токен отсутствует."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            auth_token = EmailAuthToken.objects.get(token=token)
        except EmailAuthToken.DoesNotExist:
            return Response(
                {"detail": "Ссылка недействительна."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() > auth_token.expires_at:
            auth_token.delete()
            return Response(
                {"detail": "Ссылка устарела. Запросите новую."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = auth_token.email
        auth_token.delete()

        user = User.objects.filter(email__iexact=email).order_by("id").first()
        created = False
        if user is None:
            try:
                user = User.objects.create(
                    username=_generate_unique_username(email),
                    email=email,
                    is_active=True,
                )
                created = True
            except IntegrityError:
                user = User.objects.filter(email__iexact=email).order_by("id").first()

        if user is None:
            return Response(
                {"detail": "Не удалось создать пользователя."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not getattr(user, "is_active", True):
            return Response(
                {"detail": "Аккаунт деактивирован."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        response = Response(
            {"detail": "Успешный вход.", "created": created},
            status=status.HTTP_200_OK,
        )
        set_token_cookie(response, "access_token", str(refresh.access_token), COOKIE_MAX_AGE)
        set_token_cookie(response, "refresh_token", str(refresh), REFRESH_COOKIE_MAX_AGE)
        return response
