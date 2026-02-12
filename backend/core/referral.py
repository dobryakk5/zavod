# core/referral.py
# Реферальные модели и утилиты

import secrets
import string
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.models.client import Client


class ReferralCode(models.Model):
    """
    Реферальный код пользователя.
    Создаётся ТОЛЬКО по запросу через API — не автоматически.
    Формат кода: ref_XXXXXXXX  (префикс отличает от tenant deeplink base64).
    """

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="referral_code",
    )
    code = models.CharField(max_length=24, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    # Статистика (денормализация для скорости)
    total_referrals = models.PositiveIntegerField(default=0)
    successful_referrals = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_codes"

    def __str__(self) -> str:
        return f"{self.client_id} → {self.code}"

    # ------------------------------------------------------------------
    # Утилиты кода
    # ------------------------------------------------------------------

    @staticmethod
    def generate_code(length: int = 8) -> str:
        """
        Генерирует уникальный код с префиксом ref_.
        Пример: ref_A3BK92XZ
        """
        chars = string.ascii_uppercase + string.digits
        while True:
            random_part = "".join(secrets.choice(chars) for _ in range(length))
            code = f"ref_{random_part}"
            if not ReferralCode.objects.filter(code=code).exists():
                return code

    @staticmethod
    def is_referral_code(start_param: str) -> bool:
        """
        Проверяет является ли параметр /start реферальным кодом.
        Реферальные коды начинаются с 'ref_'.
        Все остальное — tenant deeplink (base64 от TenantService).
        """
        return bool(start_param and start_param.startswith("ref_"))

    def get_telegram_link(self, bot_username: str | None = None) -> str:
        """Возвращает Telegram deep link для приглашения."""
        username = bot_username or getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        if not username:
            raise ValueError("TELEGRAM_BOT_USERNAME не настроен")
        return f"https://t.me/{username}?start={self.code}"


class Referral(models.Model):
    """
    Запись о факте перехода по реферальной ссылке.
    referrer  — кто пригласил (владелец ReferralCode)
    referee   — кто перешёл (новый Client, появляется после регистрации)
    """

    STATUS_PENDING = "pending"
    STATUS_REGISTERED = "registered"
    STATUS_REWARDED = "rewarded"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает регистрации"),
        (STATUS_REGISTERED, "Зарегистрировался"),
        (STATUS_REWARDED, "Награда выдана"),
        (STATUS_EXPIRED, "Истёк срок"),
    ]

    referral_code = models.ForeignKey(
        ReferralCode,
        on_delete=models.CASCADE,
        related_name="referrals",
    )
    referrer = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="referrals_sent",
    )
    # referee появляется когда новый клиент завершил регистрацию
    referee = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals_received",
    )

    # Telegram-данные приглашённого (до создания Client)
    invited_telegram_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    invited_telegram_username = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # Временны́е метки
    created_at = models.DateTimeField(auto_now_add=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "referrals"
        indexes = [
            models.Index(fields=["referrer", "status"], name="referral_referrer_status_idx"),
            models.Index(fields=["invited_telegram_id"], name="referral_tg_id_idx"),
        ]

    def __str__(self) -> str:
        return f"Referral {self.referral_code.code}: {self.referrer_id} → {self.referee_id}"

    def mark_registered(self, referee_client: Client) -> None:
        """Вызывается когда приглашённый завершил привязку."""
        self.referee = referee_client
        self.status = self.STATUS_REGISTERED
        self.registered_at = timezone.now()
        self.save(update_fields=["referee", "status", "registered_at"])

        self.referral_code.total_referrals = models.F("total_referrals") + 1
        self.referral_code.save(update_fields=["total_referrals"])

    def mark_rewarded(self) -> None:
        """Вызывается когда награда выдана обоим."""
        self.status = self.STATUS_REWARDED
        self.rewarded_at = timezone.now()
        self.save(update_fields=["status", "rewarded_at"])

        self.referral_code.successful_referrals = models.F("successful_referrals") + 1
        self.referral_code.save(update_fields=["successful_referrals"])

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() > self.expires_at)


def apply_free_month(*, client: Client) -> None:
    """
    Начисляет клиенту +1 месяц к `plan_expires_at`.

    Правило:
    - если тариф активен (plan_expires_at > now) → продлеваем от даты окончания
    - иначе → продлеваем от текущего момента
    """
    now = timezone.now()
    base_date = client.plan_expires_at if client.plan_expires_at and client.plan_expires_at > now else now
    client.plan_expires_at = base_date + relativedelta(months=1)
    client.save(update_fields=["plan_expires_at"])


@transaction.atomic
def reward_referral_month(*, referrer: Client, referee: Client) -> None:
    """
    Выдаёт бонус обоим: +1 бесплатный месяц.

    Если у приглашённого нет тарифа — наследуем тариф пригласившего (если есть).
    """
    if referee.plan_id is None and referrer.plan_id is not None:
        referee.plan = referrer.plan
        referee.save(update_fields=["plan"])

    apply_free_month(client=referrer)
    apply_free_month(client=referee)

