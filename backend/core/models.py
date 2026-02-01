from django.db import models
from django.conf import settings
from django.utils import timezone
import re
import uuid
from typing import Dict, List


class Client(models.Model):
    SYSTEM_SLUG = "system"
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
    slug = models.SlugField(unique=True)
    timezone = models.CharField(max_length=64, default="Europe/Helsinki")

    # AI Analysis settings
    ai_analysis_channel_url = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="AI Анализ канала",
        help_text="URL канала для AI анализа (например: https://t.me/example_channel)"
    )
    ai_analysis_channel_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Тип канала",
        help_text="Тип канала для анализа (например: telegram, instagram, youtube)"
    )
    project_telegram_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Telegram проекта",
        help_text="Ссылка или @username Telegram канала проекта"
    )
    project_instagram_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Instagram проекта",
        help_text="Ссылка или @username Instagram аккаунта проекта"
    )
    project_youtube_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="YouTube проекта",
        help_text="Ссылка или ID YouTube канала проекта"
    )
    plan = models.ForeignKey(
        "PaymentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)

    # Business description
    avatar = models.TextField(
        blank=True,
        verbose_name="Аватар клиента",
        help_text="Портрет целевой аудитории (например: 'Мама двоих детей, работает удалённо, хочет больше времени для себя')"
    )
    pains = models.TextField(
        blank=True,
        verbose_name="Боли",
        help_text="Проблемы и боли целевой аудитории (например: 'нет времени на себя, стресс, лишний вес, низкая самооценка')"
    )
    desires = models.TextField(
        blank=True,
        verbose_name="Хотелки",
        help_text="Желания и цели аудитории (например: 'похудеть к лету, научиться танцевать, найти хобби, познакомиться с новыми людьми')"
    )
    objections = models.TextField(
        blank=True,
        verbose_name="Возражения/страхи",
        help_text="Страхи и возражения аудитории (например: 'дорого, нет времени, боюсь выглядеть глупо, не получится')"
    )
    expert_books = models.TextField(
        blank=True,
        verbose_name="Книги экспертов",
        help_text="Подборка книг для целевой аудитории (по одна на строку)"
    )
    base_video_prompt = models.TextField(
        blank=True,
        verbose_name="Base video prompt",
        help_text="Базовые инструкции для AI генерации промпта видео (инструкции для режиссера)"
    )
    add_video_prompt = models.TextField(
        blank=True,
        verbose_name="Additional video prompt",
        help_text="Дополнительные инструкции для генерации видео (клиентские пожелания)"
    )
    video_prompt = models.TextField(
        blank=True,
        verbose_name="Video prompt (deprecated)",
        help_text="Устаревшее поле. Используйте base_video_prompt и add_video_prompt"
    )
    last_image_generation_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Последняя генерация изображения",
        help_text="Время запуска последней генерации изображения"
    )
    last_video_generation_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Последняя генерация видео",
        help_text="Время запуска последней генерации видео"
    )

    # Telegram settings
    telegram_client_channel = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Канал клиента",
        help_text="Telegram канал клиента для публикации (например: @my_channel или -1001234567890)"
    )
    telegram_api_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Telegram API ID (получить на my.telegram.org)"
    )
    telegram_api_hash = models.CharField(
        max_length=255,
        blank=True,
        help_text="Telegram API Hash (получить на my.telegram.org)"
    )
    telegram_source_channels = models.TextField(
        default="@rian_ru, @tjournal",
        blank=True,
        help_text="Список Telegram каналов для сбора контента через запятую (например: @rian_ru, @tjournal, @meduza)"
    )

    # RSS settings
    rss_source_feeds = models.TextField(
        blank=True,
        help_text="Список RSS/Atom фидов для сбора контента через запятую (например: https://lenta.ru/rss, https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml)"
    )

    # YouTube settings
    youtube_api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="YouTube Data API v3 ключ (получить в Google Cloud Console)"
    )
    youtube_source_channels = models.TextField(
        blank=True,
        help_text="Список YouTube каналов для сбора контента через запятую (например: UC_x5XG1OV2P6uZZ5FSM9Ttw, UCMCgOm8GZkHp8zJ6l0_fGxA или @channel_handle)"
    )

    # Instagram settings
    instagram_access_token = models.TextField(
        blank=True,
        help_text="Instagram Graph API токен доступа"
    )
    instagram_source_accounts = models.TextField(
        blank=True,
        help_text="Список Instagram аккаунтов для сбора контента через запятую (например: username1, username2)"
    )

    # VKontakte settings
    vkontakte_access_token = models.TextField(
        blank=True,
        help_text="VKontakte API токен доступа (получить на vk.com/dev)"
    )
    vkontakte_source_groups = models.TextField(
        blank=True,
        help_text="Список VK групп/пабликов для сбора контента через запятую (например: apiclub, thecode)"
    )
    tgstat_channels = models.JSONField(
        default=list,
        blank=True,
        help_text="Список избранных TGStat каналов (id)",
    )

    def get_telegram_source_channels_list(self):
        """Парсит telegram_source_channels в список каналов."""
        if not self.telegram_source_channels:
            return []
        channels = re.split(r"[,\s]+", self.telegram_source_channels)
        return [ch.strip() for ch in channels if ch and ch.strip()]

    def get_rss_source_feeds_list(self):
        """Парсит rss_source_feeds в список URL фидов."""
        if not self.rss_source_feeds:
            return []
        feeds = re.split(r"[,\s]+", self.rss_source_feeds)
        return [feed.strip() for feed in feeds if feed and feed.strip()]

    def get_youtube_source_channels_list(self):
        """Парсит youtube_source_channels в список ID каналов."""
        if not self.youtube_source_channels:
            return []
        channels = re.split(r"[,\s]+", self.youtube_source_channels)
        return [ch.strip() for ch in channels if ch and ch.strip()]

    def get_instagram_source_accounts_list(self):
        """Парсит instagram_source_accounts в список аккаунтов."""
        if not self.instagram_source_accounts:
            return []
        accounts = re.split(r"[,\s]+", self.instagram_source_accounts)
        return [acc.strip() for acc in accounts if acc and acc.strip()]

    def get_vkontakte_source_groups_list(self):
        """Парсит vkontakte_source_groups в список групп."""
        if not self.vkontakte_source_groups:
            return []
        groups = re.split(r"[,\s]+", self.vkontakte_source_groups)
        return [grp.strip() for grp in groups if grp and grp.strip()]

    def __str__(self):
        return self.name

    def get_brand_display_name(self) -> str:
        """Возвращает пользовательское название бренда с запасным вариантом."""
        return (self.brand_name or self.name or "").strip()

    @property
    def is_system(self) -> bool:
        return self.slug == self.SYSTEM_SLUG

    @classmethod
    def get_system_client(cls):
        client, _ = cls.objects.get_or_create(
            slug=cls.SYSTEM_SLUG,
            defaults={
                "name": "System Templates",
                "timezone": "UTC",
            },
        )
        return client

    @classmethod
    def _get_default_video_prompt_client(cls):
        """
        Возвращает клиента, чьи настройки видео-промптов используются как дефолтные.
        """
        default_client_id = getattr(settings, "DEFAULT_VIDEO_PROMPT_CLIENT_ID", 3)
        if not default_client_id:
            return None
        try:
            default_client_id = int(default_client_id)
        except (TypeError, ValueError):
            return None
        if default_client_id <= 0:
            return None
        return cls.objects.filter(pk=default_client_id).only(
            "id",
            "base_video_prompt",
            "add_video_prompt",
            "video_prompt",
        ).first()

    def get_video_prompt_template(self) -> str:
        """
        Return additional video instructions (client-specific) with graceful fallbacks.

        Base/creative инструкции приходят из base_video_prompt, а здесь хранятся
        технические пожелания для финального промпта.
        """
        if self.add_video_prompt and self.add_video_prompt.strip():
            return self.add_video_prompt.strip()

        # Fallback to old video_prompt field for backward compatibility
        if self.video_prompt and self.video_prompt.strip():
            return self.video_prompt.strip()

        default_client = self._get_default_video_prompt_client()
        if default_client and default_client.pk != self.pk:
            if default_client.add_video_prompt and default_client.add_video_prompt.strip():
                return default_client.add_video_prompt.strip()
            if default_client.video_prompt and default_client.video_prompt.strip():
                return default_client.video_prompt.strip()

        # Final fallback to system-level defaults (если заданы)
        from .system_settings import get_video_prompt_instructions
        return get_video_prompt_instructions().strip()

    def get_base_video_prompt_instructions(self) -> str:
        """Return base instructions for AI video prompt generation."""
        if self.base_video_prompt and self.base_video_prompt.strip():
            return self.base_video_prompt.strip()

        default_client = self._get_default_video_prompt_client()
        if default_client and default_client.pk != self.pk:
            inherited_instructions = (default_client.base_video_prompt or "").strip()
            if inherited_instructions:
                return inherited_instructions

        # Default instructions for AI prompt generation
        return """Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. На входе у тебя текст поста.

1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.
2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.
3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.
4. Не добавляй хештеги, кавычки и технические команды."""


class ChannelAnalysis(models.Model):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="channel_analyses")
    channel_url = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=50)
    task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    progress = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    share_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    share_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.client.name} – {self.channel_type} analysis ({self.status})"


class ProjectChannelAnalysisRun(models.Model):
    STATUS_PENDING = ChannelAnalysis.STATUS_PENDING
    STATUS_IN_PROGRESS = ChannelAnalysis.STATUS_IN_PROGRESS
    STATUS_COMPLETED = ChannelAnalysis.STATUS_COMPLETED
    STATUS_FAILED = ChannelAnalysis.STATUS_FAILED

    STATUS_CHOICES = ChannelAnalysis.STATUS_CHOICES

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="project_channel_runs")
    task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    progress = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "status", "-created_at"], name="pcr_client_status_created_idx"),
        ]

    def __str__(self):
        return f"{self.client.name} – project channel run ({self.status})"


class ProjectChannelPostStat(models.Model):
    run = models.ForeignKey(ProjectChannelAnalysisRun, on_delete=models.CASCADE, related_name="post_stats")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="project_channel_post_stats")
    channel_type = models.CharField(max_length=50)
    channel_identifier = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=500, blank=True)
    published_at = models.DateTimeField(blank=True, null=True)
    views = models.PositiveIntegerField(default=0)
    reactions = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("run", "channel_type", "channel_identifier", "external_id")
        indexes = [
            models.Index(
                fields=["client", "channel_type", "channel_identifier", "external_id"],
                name="pcps_client_channel_post_idx",
            ),
            models.Index(fields=["run"], name="pcps_run_idx"),
        ]

    def __str__(self):
        return f"{self.client.name} – {self.channel_type} post {self.external_id}"


class WebsiteScan(models.Model):
    STATUS_PENDING = ChannelAnalysis.STATUS_PENDING
    STATUS_IN_PROGRESS = ChannelAnalysis.STATUS_IN_PROGRESS
    STATUS_COMPLETED = ChannelAnalysis.STATUS_COMPLETED
    STATUS_FAILED = ChannelAnalysis.STATUS_FAILED

    STATUS_CHOICES = ChannelAnalysis.STATUS_CHOICES

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="website_scans")
    base_url = models.CharField(max_length=500, help_text="Base website URL (e.g. https://example.com)")
    task_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    progress = models.PositiveIntegerField(default=0)
    max_depth = models.PositiveIntegerField(default=3)
    max_pages = models.PositiveIntegerField(default=100)
    pages_total = models.PositiveIntegerField(blank=True, null=True)
    robots_url = models.CharField(max_length=700, blank=True)
    robots_txt = models.TextField(blank=True)
    sitemap_urls = models.JSONField(default=list, blank=True)
    mind_map_id = models.IntegerField(blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "status", "-created_at"], name="ws_client_status_created_idx"),
        ]

    def __str__(self):
        return f"[{self.client.slug}] WebsiteScan {self.base_url} ({self.status})"


class CompetitorSite(models.Model):
    """
    Deduplicated competitor sites collected from Google search results.
    Stored per-client and unique by domain.
    """

    MANUAL_CATEGORY_CHOICES = (
        ("competitor", "Competitor"),
        ("informational", "Informational"),
        ("indirect", "Indirect"),
        ("other", "Other"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="competitor_sites")
    domain = models.CharField(max_length=255)
    base_url = models.CharField(max_length=500, blank=True, default="")
    first_seen_query = models.CharField(max_length=512, blank=True, default="")
    last_seen_query = models.CharField(max_length=512, blank=True, default="")
    home_title = models.CharField(max_length=512, blank=True, default="")
    home_text = models.TextField(blank=True, default="")
    services_url = models.CharField(max_length=700, blank=True, default="")
    prices_url = models.CharField(max_length=700, blank=True, default="")
    ai_is_competitor = models.BooleanField(blank=True, null=True)
    ai_one_liner = models.TextField(blank=True, default="")
    ai_pricing = models.TextField(blank=True, default="")
    last_analyzed_at = models.DateTimeField(blank=True, null=True)
    analysis_status = models.CharField(max_length=20, blank=True, default="pending")
    analysis_error = models.TextField(blank=True, default="")
    task_id = models.CharField(max_length=255, blank=True, default="")
    manual_category = models.CharField(max_length=32, blank=True, null=True, choices=MANUAL_CATEGORY_CHOICES)
    manual_is_competitor = models.BooleanField(blank=True, null=True)
    manual_marked_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(fields=["client", "domain"], name="uniq_competitor_site_client_domain"),
        ]
        indexes = [
            models.Index(fields=["client", "domain"], name="comp_site_client_domain_idx"),
            models.Index(fields=["client", "-updated_at"], name="comp_site_client_updated_idx"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.client.slug}:{self.domain}"


class WebsiteScanPage(models.Model):
    scan = models.ForeignKey(WebsiteScan, on_delete=models.CASCADE, related_name="pages")
    url = models.CharField(max_length=700)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        blank=True,
        null=True,
    )
    depth = models.PositiveIntegerField(default=0)
    status_code = models.IntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=255, blank=True)
    title = models.TextField(blank=True)
    meta_description = models.TextField(blank=True)
    headings = models.JSONField(default=dict, blank=True)
    wordstats = models.JSONField(default=list, blank=True)
    cluster_level_1 = models.CharField(max_length=255, blank=True, default="")
    cluster_level_2 = models.CharField(max_length=255, blank=True, default="")
    cluster_level_3 = models.CharField(max_length=255, blank=True, default="")
    cluster_source = models.CharField(max_length=32, blank=True, default="")
    can_fetch_all = models.BooleanField(default=True)
    can_fetch_googlebot = models.BooleanField(default=True)
    is_helper = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=["scan", "url"], name="core_ws_unique_scan_url"),
        ]
        indexes = [
            models.Index(fields=["scan", "depth"], name="core_ws_scan_depth_idx"),
            models.Index(fields=["scan", "parent"], name="core_ws_scan_parent_idx"),
        ]

    def __str__(self):
        return f"{self.url} (depth={self.depth})"


class WebsiteScanPageContent(models.Model):
    page = models.OneToOneField(WebsiteScanPage, on_delete=models.CASCADE, related_name="content")
    content_text = models.TextField(blank=True)
    content_html = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"Content for {self.page_id}"


class WeeklySourceReport(models.Model):
    """Еженедельный отчёт по источнику контента."""

    SOURCE_CHOICES = (
        ("telegram", "Telegram"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("rss", "RSS"),
        ("vkontakte", "VKontakte"),
    )

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="weekly_source_reports")
    batch = models.ForeignKey(
        "WeeklySourceBatch",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="Подборка, к которой относится отчёт",
    )
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_value = models.CharField(max_length=255, help_text="URL или идентификатор канала/фида")
    week_start = models.DateField(help_text="Дата начала недели (понедельник)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    summary = models.TextField(blank=True, help_text="Короткий отчёт от AI по источнику за неделю")
    links = models.JSONField(default=list, blank=True, help_text="Ссылки на посты/материалы за неделю")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Weekly Source Report"
        verbose_name_plural = "Weekly Source Reports"
        indexes = [
            models.Index(
                fields=["client", "source_type", "week_start"],
                name="core_weekly_client__84fb5e_idx",
            ),
        ]

    def __str__(self):
        return f"[{self.client.slug}] {self.source_type}: {self.source_value} ({self.week_start})"


class WeeklySourceBatch(models.Model):
    """Подборка недельных отчётов (запуск)."""

    STATUS_CHOICES = WeeklySourceReport.STATUS_CHOICES

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="weekly_source_batches")
    week_start = models.DateField(help_text="Дата начала недели (понедельник)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WeeklySourceReport.STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Weekly Source Batch"
        verbose_name_plural = "Weekly Source Batches"

    def __str__(self):
        return f"[{self.client.slug}] Подборка {self.week_start}"


class WeeklySalesPlan(models.Model):
    """План/факт продаж по неделям."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="weekly_sales_plans")
    week_start = models.DateField(help_text="Дата начала недели (понедельник)")
    cold_leads_plan = models.PositiveIntegerField(null=True, blank=True)
    cold_leads_fact = models.PositiveIntegerField(null=True, blank=True)
    hot_leads_plan = models.PositiveIntegerField(null=True, blank=True)
    hot_leads_fact = models.PositiveIntegerField(null=True, blank=True)
    sales_plan = models.PositiveIntegerField(null=True, blank=True)
    sales_fact = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-week_start",)
        verbose_name = "Weekly Sales Plan"
        verbose_name_plural = "Weekly Sales Plans"
        constraints = [
            models.UniqueConstraint(fields=["client", "week_start"], name="core_weekly_sales_client_week_unique"),
        ]

    def __str__(self):
        return f"[{self.client.slug}] Продажи {self.week_start}"


class WeeklyContentStrategy(models.Model):
    """Контент-стратегия по неделям."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="weekly_content_strategies")
    week_start = models.DateField(help_text="Дата начала недели (понедельник)")
    comment = models.TextField(blank=True, default="")
    wordstat_cluster_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-week_start",)
        verbose_name = "Weekly Content Strategy"
        verbose_name_plural = "Weekly Content Strategies"
        constraints = [
            models.UniqueConstraint(fields=["client", "week_start"], name="core_weekly_content_strategy_client_week_unique"),
        ]

    def __str__(self):
        return f"[{self.client.slug}] Контент-стратегия {self.week_start}"


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


class VkIntegration(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_PENDING = "pending"
    STATUS_ERROR = "error"
    STATUS_DISABLED = "disabled"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PENDING, "Pending"),
        (STATUS_ERROR, "Error"),
        (STATUS_DISABLED, "Disabled"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="vk_integrations")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vk_integrations",
    )
    group_id = models.BigIntegerField()
    group_name = models.CharField(max_length=255, blank=True)
    screen_name = models.CharField(max_length=255, blank=True)
    access_token = models.TextField()
    user_id = models.BigIntegerField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    last_published_at = models.DateTimeField(blank=True, null=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("client", "group_id")
        ordering = ("-updated_at",)

    def __str__(self):
        suffix = f" @ {self.client}" if self.client_id else ""
        return f"VK {self.group_id}{suffix}"


class SocialAccount(models.Model):
    PLATFORM_CHOICES = (
        ("instagram", "Instagram"),
        ("telegram", "Telegram"),
        ("youtube", "YouTube"),
        ("vkontakte", "VKontakte"),
        ("rss_zen", "RSS Zen"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=255, help_text="Имя/описание аккаунта, чтобы не путать")
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    extra = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client} – {self.platform} ({self.name})"


class Connection(models.Model):
    """OAuth подключение соцсети к клиенту."""

    PROVIDER_CHOICES = (
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("telegram", "Telegram"),
        ("vkontakte", "VKontakte"),
    )

    STATUS_CHOICES = (
        ("active", "Active"),
        ("revoked", "Revoked"),
        ("error", "Error"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="connections")
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=255, help_text="Человекочитаемое имя подключения", blank=True)
    provider_user_id = models.CharField(max_length=255, blank=True, help_text="ID пользователя у провайдера")
    account_id = models.CharField(max_length=255, blank=True, help_text="ID аккаунта/канала для публикации")
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    scopes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_connections",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_error = models.TextField(blank=True)

    class Meta:
        unique_together = (("client", "provider", "account_id"),)
        ordering = ("-updated_at",)

    def __str__(self):
        suffix = f" @ {self.client.slug}" if self.client_id else ""
        name = self.name or self.account_id or self.provider_user_id or "Connection"
        return f"{self.provider}: {name}{suffix}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())


class PostJob(models.Model):
    """Задача публикации для очереди."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="post_jobs")
    provider = models.CharField(max_length=30, choices=Connection.PROVIDER_CHOICES)
    connection = models.ForeignKey(
        Connection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_jobs",
    )
    schedule = models.ForeignKey(
        "Schedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="post_jobs",
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    remote_id = models.CharField(max_length=255, blank=True)
    remote_url = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.provider} job #{self.id} ({self.status})"


class Post(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),          # черновик, только что создан
        ("ready", "Ready"),          # AI сгенерировал, но человек не смотрел
        ("approved", "Approved"),    # человек утвердил
        ("scheduled", "Scheduled"),  # есть задания в Schedule
        ("published", "Published"),  # полностью выпущен
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="posts")

    # Связь с историей (если пост - часть истории)
    story = models.ForeignKey(
        "Story",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="posts",
        help_text="История, к которой относится этот пост"
    )
    template = models.ForeignKey(
        "ContentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        help_text="Шаблон, использованный для генерации поста"
    )
    episode_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Номер эпизода в истории"
    )

    title = models.CharField(max_length=255)
    hook_title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Цепляющий заголовок (для фото)",
        help_text="Короткий заголовок до 3 слов для нанесения на изображение"
    )
    text = models.TextField(blank=True)
    # пока без отдельной Media-модели – можно позже перейти на Wagtail Images/Documents
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    tags = models.JSONField(default=list, blank=True)          # ["ai", "instagram", ...]
    source_links = models.JSONField(default=list, blank=True)  # ["https://...", ...]
    wordstat_phrases_used = models.JSONField(
        default=list,
        blank=True,
        help_text="Какие избранные фразы Wordstat были использованы при генерации",
    )

    # Флаги для публикации контента
    publish_text = models.BooleanField(default=True, verbose_name="Публиковать текст", help_text="Включать текст в публикацию")
    publish_image = models.BooleanField(default=True, verbose_name="Публиковать изображение", help_text="Включать изображение в публикацию")
    publish_video = models.BooleanField(default=True, verbose_name="Публиковать видео", help_text="Включать видео в публикацию")

    generated_by = models.CharField(max_length=50, blank=True)  # openai / manual / ...
    regeneration_count = models.IntegerField(
        default=0,
        help_text="Количество регенераций текста"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_posts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"[{self.client.slug}] {self.title}"

    def get_primary_image(self):
        """Вернуть первое изображение по порядку."""
        return self.images.order_by("order", "id").first()

    def get_primary_video(self):
        """Вернуть первое видео по порядку."""
        return self.videos.order_by("order", "id").first()


class PostImage(models.Model):
    """Изображение поста (поддержка нескольких файлов)."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="post_images/")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Post Image"
        verbose_name_plural = "Post Images"

    def __str__(self):
        return f"Image #{self.id} for {self.post}"


class PostVideo(models.Model):
    """Видео поста (поддержка нескольких файлов)."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="videos")
    video = models.FileField(upload_to="post_videos/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        verbose_name = "Post Video"
        verbose_name_plural = "Post Videos"

    def __str__(self):
        return f"Video #{self.id} for {self.post}"


class VeoVideoExport(models.Model):
    """
    Архив выгруженных VEO-видео на Яндекс.Диск.

    Хранит путь на диске и текстовый фрагмент из ответа бота
    (от "Ваш запрос:" до "🎛️ Инструмент:").
    """

    disk_path = models.CharField(max_length=1024, unique=True)
    request_text = models.TextField(
        blank=True,
        help_text='Фрагмент ответа VEO: от "Ваш запрос:" до "🎛️ Инструмент:"',
    )

    telegram_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    telegram_message_date = models.DateTimeField(null=True, blank=True)
    bot_username = models.CharField(max_length=255, blank=True, db_index=True)
    source_url = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "VEO Video Export"
        verbose_name_plural = "VEO Video Exports"

    def __str__(self):
        return self.disk_path


class Schedule(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In progress"),
        ("published", "Published"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="schedules")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="schedules")
    social_account = models.ForeignKey(
        SocialAccount,
        on_delete=models.CASCADE,
        related_name="schedules",
        null=True,
        blank=True,
    )
    connection = models.ForeignKey(
        Connection,
        on_delete=models.SET_NULL,
        related_name="schedules",
        null=True,
        blank=True,
        help_text="Предпочтительное подключение для публикации",
    )

    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID поста в соцсети (если есть)",
    )
    log = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scheduled_at",)

    def __str__(self):
        target = self.connection or self.social_account
        return f"{self.post} -> {target} @ {self.scheduled_at} ({self.status})"


class Topic(models.Model):
    """Тема для сбора контента (например, 'студия танцев', 'технологии AI')"""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=255, help_text="Название темы (например, 'студия танцев')")
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Ключевые слова для поиска (например, ['танцы', 'хореография', 'dance'])"
    )
    is_active = models.BooleanField(default=True, help_text="Активна ли тема для автоматического сбора")

    # Источники для сбора контента
    use_google_trends = models.BooleanField(
        default=True,
        verbose_name="Google Trends",
        help_text="Искать тренды в Google Trends"
    )
    use_telegram = models.BooleanField(
        default=False,
        verbose_name="Telegram",
        help_text="Искать в Telegram каналах (требует настройки каналов в клиенте)"
    )
    use_rss = models.BooleanField(
        default=False,
        verbose_name="RSS",
        help_text="Искать в RSS фидах (требует настройки фидов в клиенте)"
    )
    use_youtube = models.BooleanField(
        default=False,
        verbose_name="YouTube",
        help_text="Искать в YouTube каналах (требует API ключ и настройки каналов)"
    )
    use_instagram = models.BooleanField(
        default=False,
        verbose_name="Instagram",
        help_text="Искать в Instagram аккаунтах (требует access token и настройки аккаунтов)"
    )
    use_vkontakte = models.BooleanField(
        default=False,
        verbose_name="VKontakte",
        help_text="Искать в VK группах/пабликах (требует access token и настройки групп)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Topic"
        verbose_name_plural = "Topics"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"

    def get_enabled_sources(self):
        """Возвращает список включенных источников"""
        sources = []
        if self.use_google_trends:
            sources.append('google_trends')
        if self.use_telegram:
            sources.append('telegram')
        if self.use_rss:
            sources.append('rss')
        if self.use_youtube:
            sources.append('youtube')
        if self.use_instagram:
            sources.append('instagram')
        if self.use_vkontakte:
            sources.append('vkontakte')
        return sources


class TrendItem(models.Model):
    """Найденный тренд или новость"""
    SOURCE_CHOICES = (
        ("google_trends", "Google Trends"),
        ("google_news_rss", "Google News RSS"),
        ("telegram", "Telegram"),
        ("youtube", "YouTube"),
        ("rss_feed", "RSS Feed"),
        ("instagram", "Instagram"),
        ("vkontakte", "VKontakte"),
        ("news_api", "News API"),
        ("manual", "Manual"),
    )

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="trend_items")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="trend_items")

    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=1000, blank=True)

    # Дополнительные метаданные
    relevance_score = models.IntegerField(
        default=0,
        help_text="Оценка релевантности (например, количество поисков для трендов)"
    )
    extra = models.JSONField(
        default=dict,
        blank=True,
        help_text="Дополнительные данные (автор, дата публикации, изображение и т.д.)"
    )

    # Использован ли этот тренд для генерации контента
    used_for_post = models.ForeignKey(
        Post,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_trends",
        help_text="Пост, созданный на основе этого тренда"
    )

    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-relevance_score", "-discovered_at")
        verbose_name = "Trend Item"
        verbose_name_plural = "Trend Items"

    def __str__(self):
        return f"[{self.source}] {self.title[:50]}"


class Story(models.Model):
    """История - серия связанных постов (мини-сериал)"""

    STATUS_CHOICES = (
        ("draft", "Draft"),                # черновик, только создана
        ("ready", "Ready"),                # эпизоды сгенерированы
        ("approved", "Approved"),          # модератор одобрил
        ("generating_posts", "Generating Posts"),  # создаются посты из эпизодов
        ("completed", "Completed"),        # все посты созданы и опубликованы
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="stories")
    trend_item = models.ForeignKey(
        "TrendItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stories",
        help_text="Тренд, на основе которого создана история"
    )
    template = models.ForeignKey(
        "ContentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Шаблон для генерации постов из эпизодов"
    )

    title = models.CharField(max_length=500, help_text="Общий заголовок истории")
    episodes = models.JSONField(
        default=list,
        help_text="Список эпизодов: [{'order': 1, 'title': '...'}, ...]"
    )
    episode_count = models.IntegerField(
        default=5,
        help_text="Количество эпизодов в истории"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    generated_by = models.CharField(
        max_length=50,
        default="openrouter-chimera",
        help_text="Модель AI, использованная для генерации"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_stories",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Story"
        verbose_name_plural = "Stories"

    def __str__(self):
        return f"[{self.client.slug}] {self.title}"

    def get_episodes_display(self):
        """Форматированный вывод списка эпизодов"""
        if not self.episodes:
            return "Нет эпизодов"
        return "\n".join([f"{ep['order']}. {ep['title']}" for ep in self.episodes])


class Article(models.Model):
    """Статья: скелет/структура для SEO-статьи по Wordstat запросу."""

    STATUS_CHOICES = (
        ("wordstat", "Wordstat"),
        ("context_suggested", "Context Suggested"),
        ("context_selected", "Context Selected"),
        ("outline_ready", "Outline Ready"),
        ("article_ready", "Article Ready"),
        ("result_edited", "Result Edited"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="articles")
    wordstat = models.CharField(max_length=500, help_text="Wordstat фраза / поисковый запрос")
    wordstat_phrases = models.JSONField(default=list, blank=True)

    options_why_now = models.JSONField(default=list, blank=True)
    options_solution = models.JSONField(default=list, blank=True)
    selected_why_now = models.JSONField(default=list, blank=True)
    selected_solution = models.JSONField(default=list, blank=True)

    tripwire_product_id = models.PositiveIntegerField(null=True, blank=True)
    tripwire_product_name = models.CharField(max_length=255, blank=True)
    lead_product_id = models.PositiveIntegerField(null=True, blank=True)
    lead_product_name = models.CharField(max_length=255, blank=True)

    seo_blocks = models.JSONField(default=dict, blank=True)

    outline_markdown = models.TextField(blank=True, help_text="Markdown-структура статьи без контента")
    result_html = models.TextField(blank=True, help_text="Итоговый HTML-текст статьи")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="wordstat")

    audience = models.TextField(blank=True, help_text="Целевая аудитория для промптов статьи")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_articles",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Article"
        verbose_name_plural = "Articles"

    def __str__(self):
        return f"[{self.client.slug}] {self.wordstat[:80]}"


class ArticleBlock(models.Model):
    """Атомарный SEO-блок статьи (1 H2 = 1 смысл)."""

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("blueprint_ready", "Blueprint Ready"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    )

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="blocks")
    order = models.PositiveIntegerField(default=0)
    block_key = models.CharField(max_length=120, help_text="Системный ключ блока (например: Блок «Типичные ошибки»)")

    h2_title = models.CharField(max_length=300, blank=True)
    subquery = models.CharField(max_length=300, blank=True)
    micro_intent = models.CharField(max_length=300, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    key_points = models.TextField(blank=True)

    prompt_template = models.TextField(
        blank=True,
        help_text="Корректировка (добавляется к системному промпту блока)",
    )
    prompt_is_custom = models.BooleanField(
        default=False,
        help_text="DEPRECATED: больше не используется (оставлено для совместимости).",
    )
    prompt_used = models.TextField(blank=True, help_text="Последний использованный промпт (рендер)")

    content = models.TextField(blank=True, help_text="Сгенерированный текст блока (2–3 абзаца)")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    regeneration_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "id")
        unique_together = (("article", "block_key"),)
        verbose_name = "Article Block"
        verbose_name_plural = "Article Blocks"

    def __str__(self):
        return f"[{self.article_id}] {self.block_key}"


class ArticleBlockPromptTemplate(models.Model):
    """Системный шаблон промпта для блоков статьи (общий для всех клиентов/статей)."""

    block_key = models.CharField(max_length=120, unique=True)
    prompt_template = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("block_key",)
        verbose_name = "Промпт блока статьи"
        verbose_name_plural = "Промпты блоков статьи"

    def __str__(self):
        return self.block_key


class Articles(ArticleBlockPromptTemplate):
    """Proxy-модель для Django Admin: список системных промптов по URL `/django-admin/core/articles/`."""

    class Meta:
        proxy = True
        verbose_name = "Промпт статьи"
        verbose_name_plural = "Промпты статей"


class PostType(models.Model):
    """Справочник типов постов (системные и клиентские)"""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="post_types",
        null=True,
        blank=True,
        help_text="Оставьте пустым для системного типа, доступного всем клиентам"
    )
    value = models.CharField(
        max_length=50,
        help_text="Техническое название (например: selling, expert)"
    )
    label = models.CharField(
        max_length=100,
        help_text="Отображаемое название (например: Продающий, Экспертный)"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Предустановленный тип (создан автоматически)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "Post Type"
        verbose_name_plural = "Post Types"
        unique_together = [["client", "value"]]

    def __str__(self):
        if self.client:
            return f"[{self.client.slug}] {self.label}"
        return f"[Системный] {self.label}"


class PostTone(models.Model):
    """Справочник тонов постов (системные и клиентские)"""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="post_tones",
        null=True,
        blank=True,
        help_text="Оставьте пустым для системного тона, доступного всем клиентам"
    )
    value = models.CharField(
        max_length=50,
        help_text="Техническое название (например: professional, friendly)"
    )
    label = models.CharField(
        max_length=100,
        help_text="Отображаемое название (например: Профессиональный, Дружественный)"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Предустановленный тон (создан автоматически)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "Post Tone"
        verbose_name_plural = "Post Tones"
        unique_together = [["client", "value"]]

    def __str__(self):
        if self.client:
            return f"[{self.client.slug}] {self.label}"
        return f"[Системный] {self.label}"


class ContentTemplateQuerySet(models.QuerySet):
    def for_client(self, client: Client, include_system: bool = True):
        conditions = []
        if client:
            conditions.append(models.Q(client=client))
        if include_system:
            conditions.append(models.Q(client__slug=Client.SYSTEM_SLUG))
        if not conditions:
            return self.none()

        combined = conditions[0]
        for condition in conditions[1:]:
            combined |= condition
        return self.filter(combined)

    def only_system(self):
        return self.filter(client__slug=Client.SYSTEM_SLUG)


class ContentTemplateManager(models.Manager):
    def get_queryset(self):
        return ContentTemplateQuerySet(self.model, using=self._db)

    def for_client(self, client: Client, include_system: bool = True):
        return self.get_queryset().for_client(client, include_system=include_system)

    def only_system(self):
        return self.get_queryset().only_system()


class ContentTemplate(models.Model):
    """Шаблон для AI генерации контента с настройками стиля"""

    # Suggested default types (not enforced - users can create custom types)
    SUGGESTED_TYPES = [
        "selling",      # Продающий
        "expert",       # Экспертный
        "trigger",      # Триггерный
        "story",        # История (мини-сериал)
    ]

    # Suggested default tones (not enforced - users can create custom tones)
    SUGGESTED_TONES = [
        "professional", # Профессиональный
        "friendly",     # Дружественный
        "informative",  # Информационный
        "casual",       # Непринуждённый
        "enthusiastic", # Восторженный
    ]

    LANGUAGE_CHOICES = (
        ("ru", "Русский"),
        ("en", "English"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="content_templates")
    name = models.CharField(max_length=255, help_text="Название шаблона (например, 'Instagram пост')")

    # Параметры стиля
    type = models.CharField(
        max_length=50,
        default="selling",
        help_text="Тип поста по структуре (продающий, экспертный, триггерный) или свой кастомный тип"
    )
    tone = models.CharField(
        max_length=50,
        default="professional",
        help_text="Тон контента или свой кастомный тон"
    )
    length = models.PositiveIntegerField(
        default=1200,
        help_text="Целевая длина поста в символах"
    )
    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default="ru",
        help_text="Язык контента"
    )

    # Кастомные промпт-шаблоны
    seo_prompt_template = models.TextField(
        verbose_name="SEO промпт",
        default="",
        help_text=(
            "Шаблон промпта для генерации на основе SEO ключевых фраз. "
            "Плейсхолдеры: {seo_keywords}, {topic_name}, {tone}, {length}, {language}, "
            "{type}, {avatar}, {pains}, {desires}, {objections}, {books}"
        )
    )
    trend_prompt_template = models.TextField(
        verbose_name="Trend промпт",
        default="",
        help_text=(
            "Шаблон промпта для генерации на основе трендов. "
            "Плейсхолдеры: {trend_title}, {trend_description}, {trend_url}, {topic_name}, {tone}, {length}, {language}, "
            "{type}, {avatar}, {pains}, {desires}, {objections}"
        )
    )

    # Дополнительные инструкции
    additional_instructions = models.TextField(
        blank=True,
        help_text="Дополнительные инструкции для AI (например, 'Всегда упоминай бренд X')"
    )

    # Настройки
    is_default = models.BooleanField(
        default=False,
        help_text="Использовать этот шаблон по умолчанию для клиента"
    )
    include_hashtags = models.BooleanField(
        default=True,
        help_text="Генерировать хэштеги"
    )
    max_hashtags = models.IntegerField(
        default=5,
        help_text="Максимальное количество хэштегов"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ContentTemplateManager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Content Template"
        verbose_name_plural = "Content Templates"
        unique_together = [["client", "name"]]

    def __str__(self):
        default_marker = " [DEFAULT]" if self.is_default else ""
        return f"[{self.client.slug}] {self.name}{default_marker}"

    def save(self, *args, **kwargs):
        # Если этот шаблон помечен как default, снять флаг с других шаблонов клиента
        if self.is_default:
            ContentTemplate.objects.filter(
                client=self.client,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def is_system(self) -> bool:
        client = getattr(self, "client", None)
        return bool(client and client.is_system)

    @classmethod
    def get_for_client_or_system(cls, client: Client, template_id: int):
        conditions = models.Q(client__slug=Client.SYSTEM_SLUG)
        if client:
            conditions |= models.Q(client=client)
        return cls.objects.get(models.Q(id=template_id) & conditions)

    @classmethod
    def get_default_for_client(cls, client: Client):
        if client:
            template = cls.objects.filter(client=client, is_default=True).first()
            if template:
                return template

        template = cls.objects.only_system().filter(is_default=True).first()
        if template:
            return template

        if client:
            template = cls.objects.filter(client=client).first()
            if template:
                return template

        return cls.objects.only_system().first()


class SEOKeywordSet(models.Model):
    """SEO подборка ключевых фраз для клиента (исторически могла относиться к теме)"""

    GROUP_TYPE_CHOICES = [
        ("seo_pains", "SEO Pains"),
        ("seo_desires", "SEO Desires"),
        ("seo_objections", "SEO Objections"),
        ("seo_avatar", "SEO Avatar"),
        ("seo_keywords", "SEO Keywords"),
    ]

    STATUS_CHOICES = (
        ("pending", "Ожидает генерации"),
        ("generating", "Генерируется"),
        ("completed", "Завершено"),
        ("failed", "Ошибка"),
    )

    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        related_name="seo_keyword_sets",
        null=True,
        blank=True,
        help_text="(опционально) Историческая связь с конкретной темой"
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="seo_keyword_sets")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Сгенерированные ключевые фразы по группам
    keyword_groups = models.JSONField(
        default=dict,
        blank=True,
        help_text="Группы SEO-фраз: commercial, general, informational и т.д."
    )

    # Устаревшее поле, оставлено для совместимости (будет удалено после миграции)
    keywords_text = models.TextField(
        blank=True,
        help_text="[DEPRECATED] Список ключевых SEO-фраз, сгенерированных AI"
    )

    group_type = models.CharField(
        max_length=32,
        choices=GROUP_TYPE_CHOICES,
        blank=True,
        default="",
        help_text="Тип SEO-группы (по умолчанию пусто для старых записей)"
    )
    keywords_list = models.JSONField(
        default=list,
        blank=True,
        help_text="Список ключевых фраз для группы (используется для новых генераций)"
    )

    # Дополнительные метаданные
    ai_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Модель AI, использованная для генерации (например, gpt-4)"
    )
    prompt_used = models.TextField(
        blank=True,
        help_text="Промпт, использованный для генерации"
    )
    error_log = models.TextField(
        blank=True,
        help_text="Лог ошибок, если генерация не удалась"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "SEO Keyword Set"
        verbose_name_plural = "SEO Keyword Sets"

    def __str__(self):
        topic_part = f" → {self.topic.name}" if self.topic else ""
        group_part = f" [{self.group_type}]" if self.group_type else ""
        return f"[{self.client.slug}] SEO{topic_part}{group_part} ({self.status})"

    def get_keyword_groups_for_generation(self) -> Dict[str, List[str]]:
        """
        Возвращает словарь групп ключей с очищенными значениями.
        Отдаёт приоритет keywords_list (новые записи) и дополняет keyword_groups для обратной совместимости.
        """

        def _clean(items) -> List[str]:
            cleaned: List[str] = []
            if isinstance(items, list):
                for keyword in items:
                    if isinstance(keyword, str):
                        trimmed = keyword.strip()
                        if trimmed:
                            cleaned.append(trimmed)
            return cleaned

        groups: Dict[str, List[str]] = {}
        primary_group_name = self.group_type or "seo_keywords"

        primary_keywords = _clean(self.keywords_list)
        if primary_keywords:
            groups[primary_group_name] = primary_keywords

        if isinstance(self.keyword_groups, dict):
            for group_name, keywords in self.keyword_groups.items():
                cleaned = _clean(keywords)
                if cleaned and group_name not in groups:
                    groups[str(group_name)] = cleaned

        return groups

    def get_flat_keywords(self) -> List[str]:
        """Плоский список всех ключевых фраз."""
        flat_keywords: List[str] = []
        for keywords in self.get_keyword_groups_for_generation().values():
            flat_keywords.extend(keywords)
        return flat_keywords


class ProjectSemanticSet(models.Model):
    """Семантика проекта, сгенерированная на основе книг экспертов."""

    SOURCE_EXPERT_BOOKS = "expert_books"

    SOURCE_CHOICES = (
        (SOURCE_EXPERT_BOOKS, "Expert books"),
    )

    STATUS_CHOICES = (
        ("pending", "Ожидает генерации"),
        ("generating", "Генерируется"),
        ("completed", "Завершено"),
        ("failed", "Ошибка"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_sets")
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=SOURCE_EXPERT_BOOKS)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    books_text = models.TextField(blank=True, help_text="Книги экспертов, использованные для генерации")
    keyword_groups = models.JSONField(default=dict, blank=True)
    keywords_list = models.JSONField(default=list, blank=True)

    ai_model = models.CharField(max_length=100, blank=True)
    prompt_used = models.TextField(blank=True)
    error_log = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Project Semantic Set"
        verbose_name_plural = "Project Semantic Sets"

    def __str__(self):
        return f"[{self.client.slug}] Semantics ({self.status})"

    def get_flat_keywords(self) -> List[str]:
        cleaned: List[str] = []
        seen = set()
        for keyword in self.keywords_list or []:
            if not isinstance(keyword, str):
                continue
            value = keyword.strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            cleaned.append(value)
        if cleaned:
            return cleaned
        flat_keywords: List[str] = []
        if isinstance(self.keyword_groups, dict):
            for _, keywords in self.keyword_groups.items():
                if not isinstance(keywords, list):
                    continue
                for keyword in keywords:
                    if not isinstance(keyword, str):
                        continue
                    value = keyword.strip()
                    if not value or value.lower() in seen:
                        continue
                    seen.add(value.lower())
                    flat_keywords.append(value)
        return flat_keywords


class SemanticGroup(models.Model):
    """Смысловые группы (карта ниши)."""

    SCOPE_CHOICES = (
        ("narrow", "Narrow"),
        ("normal", "Normal"),
        ("wide", "Wide"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    )

    SOURCE_CHOICES = (
        ("ai", "AI"),
        ("manual", "Manual"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_groups")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_books = models.JSONField(default=list, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        null=True,
        blank=True,
    )
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, blank=True, default="normal")
    expected_clusters = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "semantic_groups"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "status"], name="semgrp_client_status_idx"),
            models.Index(fields=["client", "created_at"], name="semgrp_client_created_idx"),
        ]
        verbose_name = "Semantic Group"
        verbose_name_plural = "Semantic Groups"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"


class SemanticCluster(models.Model):
    """SEO-кластеры (интент = страница)."""

    INTENT_CHOICES = (
        ("info", "Info"),
        ("commercial", "Commercial"),
        ("navigational", "Navigational"),
        ("brand", "Brand"),
    )

    STATUS_CHOICES = (
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("published", "Published"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_clusters")
    semantic_group = models.ForeignKey(
        SemanticGroup,
        on_delete=models.CASCADE,
        related_name="clusters",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    main_keyword = models.CharField(max_length=255, blank=True)
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, blank=True)
    user_goal = models.TextField(blank=True)
    cta = models.CharField(max_length=255, blank=True)
    priority = models.PositiveSmallIntegerField(null=True, blank=True)
    page_type = models.CharField(max_length=50, blank=True)
    url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    phrases = models.ManyToManyField(
        "SemanticPhrase",
        through="ClusterPhrase",
        related_name="clusters",
        blank=True,
    )

    class Meta:
        db_table = "clusters"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "semantic_group"], name="semclust_client_group_idx"),
            models.Index(fields=["client", "status"], name="semclust_client_status_idx"),
            models.Index(fields=["client", "intent"], name="semclust_client_intent_idx"),
        ]
        verbose_name = "Semantic Cluster"
        verbose_name_plural = "Semantic Clusters"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"


class WordstatPhrase(models.Model):
    """Нормализованные Wordstat-фразы (общие для всех клиентов)."""

    phrase = models.TextField(unique=True)
    frequency = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wordstat_phrases"
        ordering = ("phrase", "id")
        verbose_name = "Wordstat Phrase"
        verbose_name_plural = "Wordstat Phrases"

    def __str__(self):
        return self.phrase


class SemanticPhrase(models.Model):
    """Ключевые фразы и LSI."""

    TYPE_CHOICES = (
        ("key", "Key"),
        ("lsi", "LSI"),
        ("wordstat", "Wordstat"),
        ("association", "Association"),
    )

    SOURCE_CHOICES = (
        ("ai", "AI"),
        ("wordstat", "Wordstat"),
        ("gsc", "GSC"),
        ("manual", "Manual"),
        ("favorite", "Favorite"),
    )

    INTENT_CHOICES = SemanticCluster.INTENT_CHOICES

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="semantic_phrases")
    phrase = models.ForeignKey(
        WordstatPhrase,
        on_delete=models.CASCADE,
        related_name="semantic_phrases",
        null=True,
        blank=True,
    )
    raw_phrase = models.TextField(blank=True, null=True)
    normalized_phrase = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="key")
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="ai")
    competition = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "phrases"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "source"], name="semphr_client_source_idx"),
            models.Index(fields=["client", "phrase"], name="semphr_client_phrase_idx"),
        ]
        verbose_name = "Semantic Phrase"
        verbose_name_plural = "Semantic Phrases"

    def __str__(self):
        phrase_text = self.normalized_phrase or self.raw_phrase or (self.phrase.phrase if self.phrase_id else "")
        return f"[{self.client.slug}] {phrase_text[:80]}"


class ClusterPhrase(models.Model):
    """Связь кластеров с фразами (many-to-many)."""

    ROLE_CHOICES = (
        ("main", "Main"),
        ("support", "Support"),
        ("lsi", "LSI"),
    )

    ADDED_BY_CHOICES = (
        ("ai", "AI"),
        ("manual", "Manual"),
    )

    cluster = models.ForeignKey(SemanticCluster, on_delete=models.CASCADE, related_name="cluster_phrases")
    phrase = models.ForeignKey(SemanticPhrase, on_delete=models.CASCADE, related_name="cluster_phrases")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="support")
    weight = models.PositiveSmallIntegerField(null=True, blank=True)
    added_by = models.CharField(max_length=20, choices=ADDED_BY_CHOICES, default="ai")

    class Meta:
        db_table = "cluster_phrases"
        unique_together = ("cluster", "phrase")
        indexes = [
            models.Index(fields=["cluster", "role"], name="clphr_cluster_role_idx"),
            models.Index(fields=["phrase"], name="clphr_phrase_idx"),
        ]
        verbose_name = "Cluster Phrase"
        verbose_name_plural = "Cluster Phrases"

    def __str__(self):
        return f"{self.cluster_id} -> {self.phrase_id}"


class WordstatQuery(models.Model):
    """Сохранённый запрос Wordstat и его результаты для конкретного клиента."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="wordstat_queries")
    group_name = models.CharField(max_length=255, blank=True, default="")
    phrases = models.JSONField(default=list, blank=True)
    request_phrase = models.CharField(max_length=255)
    total_count = models.PositiveIntegerField(default=0)
    include_parent = models.BooleanField(default=False)
    regions = models.JSONField(default=list, blank=True)
    devices = models.JSONField(default=list, blank=True)

    user_login = models.CharField(max_length=255, blank=True)
    limit_per_second = models.PositiveIntegerField(null=True, blank=True)
    daily_limit = models.PositiveIntegerField(null=True, blank=True)
    daily_limit_remaining = models.PositiveIntegerField(null=True, blank=True)

    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["client", "created_at"]),
            models.Index(fields=["client", "request_phrase"]),
        ]
        verbose_name = "Wordstat Query"
        verbose_name_plural = "Wordstat Queries"

    def __str__(self):
        return f"[{self.client.slug}] Wordstat '{self.request_phrase}' ({self.total_count})"


class WordstatCluster(models.Model):
    """Кластеры для избранных Wordstat-фраз."""

    id = models.SmallAutoField(primary_key=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="wordstat_clusters")
    name = models.CharField(max_length=255)
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        indexes = [
            models.Index(fields=["client", "name"], name="ws_cluster_client_name_idx"),
        ]
        verbose_name = "Wordstat Cluster"
        verbose_name_plural = "Wordstat Clusters"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"


class WordstatResult(models.Model):
    """Отдельная фраза из выдачи Wordstat с частотностью."""

    RESULT_TYPE_CHOICES = (
        ("top_request", "Top request"),
        ("association", "Association"),
        ("favorite", "Favorite"),
        ("skip", "Skip"),
    )

    query = models.ForeignKey(WordstatQuery, on_delete=models.CASCADE, related_name="results")
    cluster = models.ForeignKey(
        WordstatCluster,
        on_delete=models.SET_NULL,
        related_name="results",
        blank=True,
        null=True,
    )
    phrase = models.TextField()
    count = models.PositiveIntegerField(default=0)
    result_type = models.CharField(max_length=20, choices=RESULT_TYPE_CHOICES, default="top_request")
    used_in_post = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-count", "phrase")
        indexes = [
            models.Index(fields=["query", "result_type", "count"]),
        ]
        verbose_name = "Wordstat Result"
        verbose_name_plural = "Wordstat Results"

    def __str__(self):
        return f"{self.phrase} ({self.count})"


class SystemSetting(models.Model):
    """Глобальные настройки системы (singleton)."""

    DEFAULT_AI_MODEL = "x-ai/grok-4.1-fast:free"
    DEFAULT_POST_AI_MODEL = DEFAULT_AI_MODEL
    DEFAULT_IMAGE_AI_MODEL = "google/gemini-2.5-flash-image"
    DEFAULT_IMAGE_TIMEOUT = 120
    DEFAULT_VIDEO_TIMEOUT = 600
    DEFAULT_PHOTO_PROMPT_INSTRUCTIONS = (
        "Use people with Slavic appearance, fair skin, any age, any gender"
    )
    DEFAULT_FALLBACK_AI_MODEL = "tngtech/deepseek-r1t2-chimera:free"

    IMAGE_GENERATION_METHODS = [
        ('openrouter', 'OpenRouter API'),
        ('veo_photo', 'VEO фото (Telegram бот)'),
        ('giga_photo', 'Giga фото'),
    ]

    default_ai_model = models.CharField(
        max_length=255,
        default=DEFAULT_AI_MODEL,
        help_text="Модель OpenRouter по умолчанию для генерации контента (например, x-ai/grok-4.1-fast:free)"
    )
    post_ai_model = models.CharField(
        max_length=255,
        blank=True,
        default=DEFAULT_POST_AI_MODEL,
        help_text="Отдельная модель OpenRouter для генерации текстов постов"
    )
    fallback_ai_model = models.CharField(
        max_length=255,
        blank=True,
        default=DEFAULT_FALLBACK_AI_MODEL,
        help_text="Запасная модель OpenRouter, используется если основная недоступна"
    )
    image_generation_method = models.CharField(
        max_length=50,
        choices=IMAGE_GENERATION_METHODS,
        default='openrouter',
        help_text="Метод генерации изображений"
    )
    image_openrouter_model = models.CharField(
        max_length=255,
        default=DEFAULT_IMAGE_AI_MODEL,
        verbose_name="Image OpenRouter model",
        help_text="Модель OpenRouter для генерации изображений (например, google/gemini-2.5-flash-image)"
    )
    video_prompt_instructions = models.TextField(
        blank=True,
        help_text=(
            "Дополнительные пожелания к промптам для видео. "
            "Этот текст добавляется к базовым инструкциям при генерации видео."
        ),
    )
    photo_prompt_instructions = models.TextField(
        blank=True,
        default=DEFAULT_PHOTO_PROMPT_INSTRUCTIONS,
        help_text=(
            "Дополнительные пожелания к промптам для генерации изображений. "
            "Этот текст добавляется к базовым инструкциям при генерации фото."
        ),
    )
    image_generation_timeout = models.PositiveIntegerField(
        default=DEFAULT_IMAGE_TIMEOUT,
        help_text=(
            "Таймаут (в секундах) для генерации и скачивания изображений. "
            "После его истечения запрос прерывается и пользователю возвращается ошибка о таймауте."
        ),
    )
    video_generation_timeout = models.PositiveIntegerField(
        default=DEFAULT_VIDEO_TIMEOUT,
        help_text=(
            "Таймаут (в секундах) для генерации видео (включая ожидание ответа бота VEO/скачивание файлов). "
            "По истечении лимита процесс отменяется и появляется ошибка о таймауте."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    def save(self, *args, **kwargs):
        # Принудительно держим одну запись
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "default_ai_model": cls.DEFAULT_AI_MODEL,
                "post_ai_model": cls.DEFAULT_POST_AI_MODEL,
                "image_generation_method": "openrouter",
                "image_openrouter_model": cls.DEFAULT_IMAGE_AI_MODEL,
                "fallback_ai_model": cls.DEFAULT_FALLBACK_AI_MODEL,
                "image_generation_timeout": cls.DEFAULT_IMAGE_TIMEOUT,
                "video_generation_timeout": cls.DEFAULT_VIDEO_TIMEOUT,
                "photo_prompt_instructions": cls.DEFAULT_PHOTO_PROMPT_INSTRUCTIONS,
            },
        )
        return obj


# ============================================================================
# Generator prompts
# ============================================================================

class GeneratorPrompt(models.Model):
    """Справочник промптов для генераторов контента (редактируется в админке)."""

    GROUP_POSTS = "posts"
    GROUP_SEO = "seo"
    GROUP_ARTICLES = "articles"
    GROUP_WORDSTAT = "wordstat"
    GROUP_PRODUCTS = "products"
    GROUP_MEDIA = "media"
    GROUP_SERVICE = "service"

    GROUP_CHOICES = [
        (GROUP_POSTS, "Посты"),
        (GROUP_SEO, "SEO"),
        (GROUP_ARTICLES, "Статьи"),
        (GROUP_WORDSTAT, "Wordstat"),
        (GROUP_PRODUCTS, "Продукты"),
        (GROUP_MEDIA, "Медиа"),
        (GROUP_SERVICE, "Служебные"),
    ]

    code = models.SlugField(max_length=120, unique=True)
    group = models.CharField(max_length=20, choices=GROUP_CHOICES, default=GROUP_POSTS)
    prompt = models.TextField()
    comment = models.TextField(blank=True, help_text="Где используется")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "Промпт генератора"
        verbose_name_plural = "Промпты"

    def __str__(self):
        return self.code


# ============================================================================
# Payment plans
# ============================================================================

class PaymentPlan(models.Model):
    PERIOD_WEEK = "week"
    PERIOD_MONTH = "month"
    PERIOD_YEAR = "year"
    PERIOD_CHOICES = [
        (PERIOD_WEEK, "Неделя"),
        (PERIOD_MONTH, "Месяц"),
        (PERIOD_YEAR, "Год"),
    ]

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    period = models.CharField(max_length=8, choices=PERIOD_CHOICES, default=PERIOD_MONTH)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Plan"
        verbose_name_plural = "Payment Plans"
        ordering = ("sort_order", "name")

    def __str__(self):
        return f"{self.name} ({self.amount} {self.currency})"


# ============================================================================
# Generation events
# ============================================================================

class GenerationEvent(models.Model):
    EVENT_POST = "post"
    EVENT_ARTICLE_WRITE = "article_write"
    EVENT_ARTICLE_EVALUATE = "article_evaluate"
    EVENT_CHANNEL_ANALYSIS = "channel_analysis"
    EVENT_WEBSITE_ANALYSIS = "website_analysis"
    EVENT_WEEKLY_COLLECTION = "weekly_collection"
    EVENT_SEO_GROUP = "seo_group"
    EVENT_SEMANTIC_CLUSTERS = "semantic_clusters"
    EVENT_SEMANTIC_PHRASES = "semantic_phrases"
    EVENT_WORDSTAT_QUERY = "wordstat_query"
    EVENT_GOOGLE_QUERY = "google_query"
    EVENT_PRODUCT = "product"
    EVENT_PRODUCT_MAP = "product_map"
    EVENT_BOOK_SEARCH = "book_search"
    EVENT_BOOK_SEMANTICS = "book_semantics"

    EVENT_CHOICES = (
        (EVENT_POST, "Post generation"),
        (EVENT_ARTICLE_WRITE, "Article write"),
        (EVENT_ARTICLE_EVALUATE, "Article evaluate"),
        (EVENT_CHANNEL_ANALYSIS, "Channel analysis"),
        (EVENT_WEBSITE_ANALYSIS, "Website analysis"),
        (EVENT_WEEKLY_COLLECTION, "Weekly collections"),
        (EVENT_SEO_GROUP, "SEO groups"),
        (EVENT_SEMANTIC_CLUSTERS, "Semantic clusters"),
        (EVENT_SEMANTIC_PHRASES, "Semantic phrases"),
        (EVENT_WORDSTAT_QUERY, "Wordstat query"),
        (EVENT_GOOGLE_QUERY, "Google query"),
        (EVENT_PRODUCT, "Product generation"),
        (EVENT_PRODUCT_MAP, "Product map"),
        (EVENT_BOOK_SEARCH, "Book search"),
        (EVENT_BOOK_SEMANTICS, "Book semantics"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="generation_events")
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["client", "event_type", "-created_at"],
                name="gen_ev_client_type_created",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.client_id}:{self.event_type} ({self.created_at:%Y-%m-%d})"


# ============================================================================
# Client products
# ============================================================================

class ProductType(models.Model):
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="product_types")
    name = models.TextField()
    value = models.TextField(blank=True, null=True)
    goal = models.TextField(blank=True, null=True)
    requirements_name = models.TextField(blank=True, null=True)
    requirements_packages = models.TextField(blank=True, null=True)
    requirements_audience = models.TextField(blank=True, null=True)
    requirements_transformation = models.TextField(blank=True, null=True)
    requirements_metrics = models.TextField(blank=True, null=True)
    requirements_method = models.TextField(blank=True, null=True)
    requirements_lesson_format = models.TextField(blank=True, null=True)
    requirements_program_modules = models.TextField(blank=True, null=True)
    requirements_packaging = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."product_types'
        ordering = ("-updated_at",)

    def __str__(self):
        return self.name


class ClientProduct(models.Model):
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="products")
    name = models.TextField()
    product_type = models.ForeignKey(
        ProductType,
        on_delete=models.SET_NULL,
        db_column="product_type_id",
        related_name="products",
        blank=True,
        null=True,
    )
    short_description = models.TextField(blank=True, null=True)
    packages = models.JSONField(default=list, blank=True)
    structure = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."products'
        ordering = ("-updated_at",)

    def __str__(self):
        return self.name


# ============================================================================
# Mind map schema (map.* tables)
# ============================================================================

class MindMap(models.Model):
    owner = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="owner_id", related_name="mind_maps")
    title = models.TextField()
    description = models.TextField(blank=True, null=True)
    type = models.TextField(default="product")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_maps'

    def __str__(self):
        return self.title


class MindMapMember(models.Model):
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column="user_id")
    role = models.TextField()

    class Meta:
        managed = False
        db_table = 'map"."mind_map_members'
        unique_together = ("map", "user")


class MindNode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="nodes")
    text = models.TextField()
    color = models.TextField(blank=True, null=True)
    shape = models.TextField(blank=True, null=True)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_nodes'

    def __str__(self):
        return self.text


class MindEdge(models.Model):
    id = models.BigAutoField(primary_key=True)
    map = models.ForeignKey(MindMap, on_delete=models.CASCADE, db_column="map_id", related_name="edges")
    from_node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="from_node_id", related_name="edges_from")
    to_node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="to_node_id", related_name="edges_to")
    type = models.TextField(default="default")
    label = models.TextField(blank=True, null=True)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_edges'


class MindNodeProperty(models.Model):
    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(MindNode, on_delete=models.CASCADE, db_column="node_id", related_name="properties")
    title = models.TextField()
    value = models.TextField()
    delta = models.TextField(blank=True, null=True)
    order_index = models.IntegerField(default=0)
    meta = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_node_properties'


class MindNodePosition(models.Model):
    node = models.OneToOneField(MindNode, on_delete=models.CASCADE, db_column="node_id", primary_key=True, related_name="position")
    layout_name = models.TextField(default="default")
    x = models.FloatField()
    y = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'map"."mind_node_positions'


class UserTenantBinding(models.Model):
    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        db_column="tenant_id",
        related_name="telegram_user_bindings",
    )
    telegram_chat_id = models.BigIntegerField()
    contact_id = models.IntegerField(blank=True, null=True)
    bound_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = 'map"."user_tenant_binding'
        unique_together = ("telegram_chat_id", "tenant")
        ordering = ("-bound_at", "-id")

    def __str__(self):
        return f"{self.telegram_chat_id} -> {self.tenant_id}"


class TelegramTask(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, db_column="client_id", related_name="telegram_tasks")
    tg_name = models.TextField()
    telegram_user_id = models.BigIntegerField()
    telegram_message_id = models.BigIntegerField(blank=True, null=True)
    message_text = models.TextField()
    received_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'map"."telegram_tasks'
        ordering = ("-received_at", "-id")

    def __str__(self):
        return f"@{self.tg_name}: {self.message_text[:48]}"


# ==================== CRM MODELS ====================
from django.db import models
from django.contrib.auth.models import User
from core.models import Client  # Используем существующую модель клиента zavod


class ClientCategory(models.Model):
    """
    Категории клиентов
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, help_text="HEX цвет для UI")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_client_categories'

    def __str__(self):
        return self.name


class CRMClient(models.Model):
    """
    Клиент в CRM-системе
    """
    STATUS_CHOICES = [
        ('active', 'Активный'),
        ('inactive', 'Неактивный'),
        ('archived', 'В архиве'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(ClientCategory, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    photo_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Связь с клиентом zavod
    zavod_client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'crm_clients'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class EventType(models.Model):
    """
    Типы событий
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.IntegerField(default=60)
    color = models.CharField(max_length=7, help_text="HEX цвет для UI")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crm_event_types'

    def __str__(self):
        return self.name


class Event(models.Model):
    """
    События (встречи, консультации и т.д.)
    """
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
        ('no_show', 'Не явился'),
    ]

    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    event_type = models.ForeignKey(EventType, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_events'
        constraints = [
            models.CheckConstraint(check=models.Q(end_time__gt=models.F('start_time')), name='check_event_time')
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Проверяем, что end_time > start_time
        if self.end_time <= self.start_time:
            raise ValueError("Время окончания должно быть больше времени начала")
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Платежи
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('paid', 'Оплачено'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
    ]

    CURRENCY_CHOICES = [
        ('RUB', 'Рубль'),
        ('USD', 'Доллар'),
        ('EUR', 'Евро'),
    ]

    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Сумма платежа")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='RUB')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_payments'
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='check_positive_amount')
        ]

    def __str__(self):
        return f"{self.amount} {self.currency} - {self.status}"


class Note(models.Model):
    """
    Заметки о клиентах
    """
    client = models.ForeignKey(CRMClient, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    is_important = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_notes'

    def __str__(self):
        return self.title or f"Заметка от {self.created_at.date()}"


    Client.add_to_class('updated_at', models.DateTimeField(auto_now=True))
