import re
import uuid
from typing import List

from django.conf import settings
from django.db import models
from django.db.models import Q


class Client(models.Model):
    SYSTEM_SLUG = "system"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_VK = "vk"
    CHANNEL_EMAIL = "email"
    CHANNEL_CHOICES = (
        (CHANNEL_TELEGRAM, "Telegram"),
        (CHANNEL_VK, "ВКонтакте"),
        (CHANNEL_EMAIL, "Email"),
    )

    name = models.CharField(max_length=255)
    brand_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Название бренда",
        help_text="Используется при упоминании бренда в постах",
    )
    niche = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Ниша",
        help_text='Например "пиццерия" или "школа психологии"',
    )
    product_service = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Продукт/услуга",
        help_text='Например "доставка пиццы" или "онлайн-курс по йоге"',
    )
    client_page_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Настройки публичной страницы клиента",
        help_text="Конфигурация блоков, выбранного продукта и шаблона страницы /c/[client_id]",
    )
    client_page_content = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Контент публичной страницы клиента",
        help_text="Rich-text контент (TipTap JSON) для страницы /c/[client_id]",
    )
    slug = models.SlugField(unique=True)
    timezone = models.CharField(max_length=64, default="Europe/Moscow")
    custom_domain = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Свой домен клиента (например, Vasya.com)",
    )
    domain_verified = models.BooleanField(
        default=False,
        help_text="Домен подтвержден через DNS-проверку",
    )
    preferred_channel = models.CharField(
        max_length=32,
        choices=CHANNEL_CHOICES,
        null=True,
        blank=True,
        help_text="Предпочтительный канал связи с клиентом",
    )

    # --- AI Analysis settings ---
    ai_analysis_channel_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="AI Анализ канала",
        help_text="URL канала для AI анализа (например: https://t.me/example_channel)",
    )
    ai_analysis_channel_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Тип канала",
        help_text="Тип канала для анализа (например: telegram, instagram, youtube)",
    )
    project_telegram_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Telegram проекта",
        help_text="Ссылка или @username Telegram канала проекта",
    )
    project_instagram_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Instagram проекта",
        help_text="Ссылка или @username Instagram аккаунта проекта",
    )
    project_youtube_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="YouTube проекта",
        help_text="Ссылка или ID YouTube канала проекта",
    )

    # --- Payment plan ---
    plan = models.ForeignKey(
        "PaymentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)

    # --- YooKassa мульти-мерчант ---
    uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="UUID клиента",
    )
    # Вариант A: OAuth-токен (рекомендуется)
    yookassa_oauth_token = models.CharField(
        max_length=1000,
        blank=True,
        null=True,
        verbose_name="YooKassa OAuth-токен",
        help_text="Заполняется автоматически при подключении через OAuth",
    )
    yookassa_connected = models.BooleanField(
        default=False,
        verbose_name="YooKassa подключена",
        help_text="True если клиент успешно подключил свой YooKassa-магазин",
    )
    # Вариант B: ручные ключи (альтернатива OAuth)
    yookassa_shop_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="YooKassa Shop ID",
        help_text="ID магазина из личного кабинета YooKassa",
    )
    yookassa_secret_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="YooKassa Secret Key",
        help_text="Секретный ключ из личного кабинета YooKassa",
    )
    yookassa_return_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="YooKassa Return URL",
        help_text="Если пусто — генерируется автоматически как /payments/return/<uuid>/",
    )
    tbank_connected = models.BooleanField(
        default=False,
        verbose_name="T-Bank подключен",
        help_text="True если клиент сохранил ключи T-Bank для приема платежей",
    )
    tbank_terminal_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="T-Bank Terminal Key",
        help_text="TerminalKey из личного кабинета T-Bank",
    )
    tbank_secret_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="T-Bank Secret Key",
        help_text="SecretKey из личного кабинета T-Bank",
    )
    tbank_test_mode = models.BooleanField(
        default=False,
        verbose_name="T-Bank тестовый режим",
        help_text="Используются тестовые ключи TinkoffBankTest",
    )

    # --- Описание бизнеса и аудитории ---
    avatar = models.TextField(
        blank=True,
        verbose_name="Аватар клиента",
        help_text="Портрет целевой аудитории (например: 'Мама двоих детей, работает удалённо, хочет больше времени для себя')",
    )
    pains = models.TextField(
        blank=True,
        verbose_name="Боли",
        help_text="Проблемы и боли целевой аудитории (например: 'нет времени на себя, стресс, лишний вес, низкая самооценка')",
    )
    desires = models.TextField(
        blank=True,
        verbose_name="Хотелки",
        help_text="Желания и цели аудитории (например: 'похудеть к лету, научиться танцевать, найти хобби')",
    )
    objections = models.TextField(
        blank=True,
        verbose_name="Возражения/страхи",
        help_text="Страхи и возражения аудитории (например: 'дорого, нет времени, боюсь выглядеть глупо')",
    )
    expert_books = models.TextField(
        blank=True,
        verbose_name="Книги экспертов",
        help_text="Подборка книг для целевой аудитории (по одной на строку)",
    )

    # --- Видео-промпты ---
    base_video_prompt = models.TextField(
        blank=True,
        verbose_name="Base video prompt",
        help_text="Базовые инструкции для AI генерации промпта видео (инструкции для режиссёра)",
    )
    add_video_prompt = models.TextField(
        blank=True,
        verbose_name="Additional video prompt",
        help_text="Дополнительные инструкции для генерации видео (клиентские пожелания)",
    )
    video_prompt = models.TextField(
        blank=True,
        verbose_name="Video prompt (deprecated)",
        help_text="Устаревшее поле. Используйте base_video_prompt и add_video_prompt",
    )
    last_image_generation_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Последняя генерация изображения",
        help_text="Время запуска последней генерации изображения",
    )
    last_video_generation_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Последняя генерация видео",
        help_text="Время запуска последней генерации видео",
    )

    # --- Telegram ---
    telegram_client_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Канал клиента",
        help_text="Telegram канал клиента для публикации (например: @my_channel или -1001234567890)",
    )
    telegram_api_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Telegram API ID (получить на my.telegram.org)",
    )
    telegram_api_hash = models.CharField(
        max_length=255,
        blank=True,
        help_text="Telegram API Hash (получить на my.telegram.org)",
    )
    telegram_source_channels = models.TextField(
        default="@rian_ru, @tjournal",
        blank=True,
        help_text="Список Telegram каналов для сбора контента через запятую (например: @rian_ru, @tjournal, @meduza)",
    )

    # --- RSS ---
    rss_source_feeds = models.TextField(
        blank=True,
        help_text="Список RSS/Atom фидов для сбора контента через запятую",
    )

    # --- YouTube ---
    youtube_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="YouTube Data API v3 ключ (получить в Google Cloud Console)",
    )
    youtube_source_channels = models.TextField(
        blank=True,
        help_text="Список YouTube каналов через запятую (ID или @handle)",
    )

    # --- Instagram ---
    instagram_access_token = models.TextField(
        blank=True,
        help_text="Instagram Graph API токен доступа",
    )
    instagram_source_accounts = models.TextField(
        blank=True,
        help_text="Список Instagram аккаунтов через запятую",
    )

    # --- VKontakte ---
    vkontakte_access_token = models.TextField(
        blank=True,
        help_text="VKontakte API токен доступа (получить на vk.com/dev)",
    )
    vkontakte_source_groups = models.TextField(
        blank=True,
        help_text="Список VK групп/пабликов через запятую (например: apiclub, thecode)",
    )

    tgstat_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Список избранных TGStat каналов (id)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    # --- Helpers for comma-separated source fields ---

    @staticmethod
    def _parse_comma_separated(value: str) -> List[str]:
        """Разбивает строку с разделителями-запятыми/пробелами в список непустых элементов."""
        if not value:
            return []
        return [item.strip() for item in re.split(r"[,\s]+", value) if item.strip()]

    def get_telegram_source_channels_list(self) -> List[str]:
        return self._parse_comma_separated(self.telegram_source_channels)

    def get_rss_source_feeds_list(self) -> List[str]:
        return self._parse_comma_separated(self.rss_source_feeds)

    def get_youtube_source_channels_list(self) -> List[str]:
        return self._parse_comma_separated(self.youtube_source_channels)

    def get_instagram_source_accounts_list(self) -> List[str]:
        return self._parse_comma_separated(self.instagram_source_accounts)

    def get_vkontakte_source_groups_list(self) -> List[str]:
        return self._parse_comma_separated(self.vkontakte_source_groups)

    # --- Brand / system helpers ---

    def get_brand_display_name(self) -> str:
        """Возвращает название бренда с запасным вариантом."""
        return (self.brand_name or self.name or "").strip()

    @property
    def is_system(self) -> bool:
        return self.slug == self.SYSTEM_SLUG

    @classmethod
    def get_system_client(cls) -> "Client":
        client, _ = cls.objects.get_or_create(
            slug=cls.SYSTEM_SLUG,
            defaults={"name": "System Templates", "timezone": "UTC"},
        )
        return client

    # --- Video prompt helpers ---

    @classmethod
    def _get_default_video_prompt_client(cls) -> "Client | None":
        """Возвращает клиента, чьи видео-промпты используются как дефолтные."""
        default_client_id = getattr(settings, "DEFAULT_VIDEO_PROMPT_CLIENT_ID", 3)
        if not default_client_id:
            return None
        try:
            default_client_id = int(default_client_id)
        except (TypeError, ValueError):
            return None
        if default_client_id <= 0:
            return None
        return (
            cls.objects
            .filter(pk=default_client_id)
            .only("id", "base_video_prompt", "add_video_prompt", "video_prompt")
            .first()
        )

    def get_video_prompt_template(self) -> str:
        """Дополнительные видео-инструкции (клиентские), с цепочкой fallback."""
        if self.add_video_prompt and self.add_video_prompt.strip():
            return self.add_video_prompt.strip()
        if self.video_prompt and self.video_prompt.strip():
            return self.video_prompt.strip()
        default_client = self._get_default_video_prompt_client()
        if default_client and default_client.pk != self.pk:
            if default_client.add_video_prompt and default_client.add_video_prompt.strip():
                return default_client.add_video_prompt.strip()
            if default_client.video_prompt and default_client.video_prompt.strip():
                return default_client.video_prompt.strip()
        from .system import get_video_prompt_instructions
        return get_video_prompt_instructions().strip()

    def get_base_video_prompt_instructions(self) -> str:
        """Базовые инструкции для AI-генерации видео-промпта."""
        if self.base_video_prompt and self.base_video_prompt.strip():
            return self.base_video_prompt.strip()
        default_client = self._get_default_video_prompt_client()
        if default_client and default_client.pk != self.pk:
            inherited = (default_client.base_video_prompt or "").strip()
            if inherited:
                return inherited
        return (
            "Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. "
            "На входе у тебя текст поста.\n\n"
            "1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.\n"
            "2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.\n"
            "3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.\n"
            "4. Не добавляй хештеги, кавычки и технические команды."
        )


class UserTenantRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=(
            ("owner", "Owner"),
            ("editor", "Editor"),
            ("viewer", "Viewer"),
        ),
    )

    class Meta:
        unique_together = ("user", "client")

    def __str__(self):
        return f"{self.user} @ {self.client} ({self.role})"


class UserActiveClientPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_client_preference",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_user_preferences",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} -> {self.client or 'none'}"


class ProjectTeamInvite(models.Model):
    class Provider(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        VK = "vk", "VK"

    class Role(models.TextChoices):
        EDITOR = "editor", "Editor"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="team_invites",
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_team_invites",
    )
    accepted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_team_invites",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices)
    account_handle_raw = models.CharField(max_length=255)
    account_handle_normalized = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EDITOR)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = (
            models.Index(
                fields=("provider", "account_handle_normalized"),
                name="idx_team_invite_prov_handle",
            ),
            models.Index(fields=("client", "status"), name="idx_team_invite_client_status"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("client", "provider", "account_handle_normalized"),
                condition=Q(status="pending"),
                name="uniq_team_invite_pending_handle",
            ),
        )

    def __str__(self):
        return (
            f"{self.client} invite {self.provider}:{self.account_handle_normalized} "
            f"({self.status})"
        )
