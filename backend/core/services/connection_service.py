import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import Connection, SocialAccount

logger = logging.getLogger(__name__)


class ConnectionService:
    """Работа с OAuth-подключениями клиентов."""

    REFRESH_MARGIN = timedelta(minutes=10)

    def get_connection_for_schedule(self, schedule, provider: Optional[str] = None) -> Optional[Connection]:
        """Возвращает Connection для расписания, создавая его из SocialAccount при необходимости."""
        if schedule.connection_id:
            if provider and schedule.connection.provider != provider:
                logger.warning(
                    "Schedule %s has connection provider %s, expected %s",
                    schedule.id,
                    schedule.connection.provider,
                    provider,
                )
                return None
            return self.ensure_valid_token(schedule.connection)

        social_account = getattr(schedule, "social_account", None)
        if social_account:
            conn = self.ensure_from_social_account(social_account)
            if conn and schedule.connection_id != conn.id:
                schedule.connection = conn
                schedule.save(update_fields=["connection"])
            return conn

        return None

    def ensure_from_social_account(self, social_account: SocialAccount) -> Optional[Connection]:
        """Конвертирует SocialAccount в Connection (idempotent)."""
        provider = social_account.platform
        account_id, provider_user_id = self._extract_ids_from_social_account(social_account)
        name = social_account.name or account_id or provider_user_id or provider

        conn = (
            Connection.objects.filter(
                client=social_account.client,
                provider=provider,
                account_id=account_id or "",
            )
            .order_by("-updated_at")
            .first()
        )
        if conn:
            return conn

        with transaction.atomic():
            conn = Connection.objects.create(
                client=social_account.client,
                provider=provider,
                name=name,
                provider_user_id=provider_user_id or "",
                account_id=account_id or "",
                access_token=social_account.access_token or "",
                refresh_token=social_account.refresh_token or "",
                metadata=social_account.extra or {},
                status="active",
            )
        return conn

    def ensure_valid_token(self, connection: Connection) -> Connection:
        """Обновляет токен, если истёк или скоро истечёт."""
        if not connection:
            return connection

        if connection.provider == "instagram":
            return self._ensure_instagram_token(connection)
        if connection.provider == "youtube":
            return self._ensure_youtube_token(connection)
        return connection

    def _ensure_instagram_token(self, connection: Connection) -> Connection:
        if not connection.access_token:
            return connection
        if connection.expires_at and connection.expires_at - timezone.now() > self.REFRESH_MARGIN:
            return connection

        token = self._refresh_instagram_token(connection.access_token)
        if not token:
            return connection

        connection.access_token = token[0]
        connection.expires_at = token[1]
        connection.status = "active"
        connection.last_error = ""
        connection.save(update_fields=["access_token", "expires_at", "status", "last_error", "updated_at"])
        return connection

    def _refresh_instagram_token(self, access_token: str) -> Optional[Tuple[str, datetime]]:
        """
        Обновление long-lived токена Instagram.
        Использует Meta endpoint /refresh_access_token.
        """
        url = "https://graph.instagram.com/refresh_access_token"
        params = {"grant_type": "ig_refresh_token", "access_token": access_token}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in")
            if not new_token:
                return None
            expires_at = timezone.now() + timedelta(seconds=int(expires_in or 0)) if expires_in else None
            return new_token, expires_at
        except Exception as exc:  # noqa: BLE001
            logger.warning("Instagram token refresh failed: %s", exc)
            return None

    def _ensure_youtube_token(self, connection: Connection) -> Connection:
        if not connection.refresh_token:
            return connection
        if connection.expires_at and connection.expires_at - timezone.now() > self.REFRESH_MARGIN:
            return connection

        result = self._refresh_youtube_token(connection)
        if not result:
            return connection

        access_token, expires_at = result
        connection.access_token = access_token
        connection.expires_at = expires_at
        connection.status = "active"
        connection.last_error = ""
        connection.save(update_fields=["access_token", "expires_at", "status", "last_error", "updated_at"])
        return connection

    def _refresh_youtube_token(self, connection: Connection) -> Optional[Tuple[str, datetime]]:
        token_uri = getattr(settings, "YOUTUBE_TOKEN_URI", "https://oauth2.googleapis.com/token")
        client_id = (
            connection.metadata.get("client_id")
            if isinstance(connection.metadata, dict)
            else None
        ) or getattr(settings, "YOUTUBE_CLIENT_ID", getattr(settings, "GOOGLE_CLIENT_ID", None))
        client_secret = (
            connection.metadata.get("client_secret")
            if isinstance(connection.metadata, dict)
            else None
        ) or getattr(settings, "YOUTUBE_CLIENT_SECRET", getattr(settings, "GOOGLE_CLIENT_SECRET", None))

        if not client_id or not client_secret:
            logger.info("YouTube token refresh skipped: client_id/client_secret not configured")
            return None

        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": connection.refresh_token,
        }

        try:
            resp = requests.post(token_uri, data=payload, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in")
            if not new_token:
                return None
            expires_at = timezone.now() + timedelta(seconds=int(expires_in or 0)) if expires_in else None
            return new_token, expires_at
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube token refresh failed: %s", exc)
            connection.status = "error"
            connection.last_error = str(exc)
            connection.save(update_fields=["status", "last_error", "updated_at"])
            return None

    def _extract_ids_from_social_account(self, social_account: SocialAccount) -> tuple[str, str]:
        account_id = ""
        provider_user_id = ""
        extra = social_account.extra or {}
        if social_account.platform == "instagram":
            account_id = (
                extra.get("instagram_business_account_id")
                or extra.get("instagram_account_id")
                or extra.get("ig_user_id")
                or ""
            )
            provider_user_id = str(extra.get("page_id") or extra.get("user_id") or "")
        elif social_account.platform == "youtube":
            account_id = str(extra.get("channel_id") or extra.get("channel") or "")
            provider_user_id = str(extra.get("user_id") or "")
        return str(account_id), str(provider_user_id)
