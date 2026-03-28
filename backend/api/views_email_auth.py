from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, OperationalError, ProgrammingError
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import EmailAuthToken

from .email_auth import (
    EmailAuthStorageUnavailableError,
    build_magic_link_url,
    issue_email_auth_token,
    normalize_email_address,
    send_email_login_link,
)
from .views_accounts import COOKIE_MAX_AGE, REFRESH_COOKIE_MAX_AGE, set_token_cookie

User = get_user_model()

_RATE_LIMIT_MAX = 3
_RATE_LIMIT_WINDOW = 60 * 60


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
        email = normalize_email_address(request.data.get("email"))

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

        try:
            auth_token = issue_email_auth_token(email)
        except EmailAuthStorageUnavailableError:
            return Response(
                {"detail": "Вход по email временно недоступен. Нужно применить миграции на сервере."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        magic_url = build_magic_link_url(request, auth_token.token)
        send_email_login_link(email, magic_url)
        cache.set(rate_key, sends + 1, timeout=_RATE_LIMIT_WINDOW)

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
        except (ProgrammingError, OperationalError):
            return Response(
                {"detail": "Вход по email временно недоступен. Нужно применить миграции на сервере."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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
