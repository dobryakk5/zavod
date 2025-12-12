from django.db import models
from django.conf import settings
from typing import Dict, List


class Client(models.Model):
    SYSTEM_SLUG = "system"
    name = models.CharField(max_length=255)
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

    def get_telegram_source_channels_list(self):
        """Парсит telegram_source_channels в список каналов."""
        if not self.telegram_source_channels:
            return []
        # Разделяем по запятой, убираем пробелы, фильтруем пустые
        channels = [ch.strip() for ch in self.telegram_source_channels.split(',')]
        return [ch for ch in channels if ch]

    def get_rss_source_feeds_list(self):
        """Парсит rss_source_feeds в список URL фидов."""
        if not self.rss_source_feeds:
            return []
        feeds = [feed.strip() for feed in self.rss_source_feeds.split(',')]
        return [feed for feed in feeds if feed]

    def get_youtube_source_channels_list(self):
        """Парсит youtube_source_channels в список ID каналов."""
        if not self.youtube_source_channels:
            return []
        channels = [ch.strip() for ch in self.youtube_source_channels.split(',')]
        return [ch for ch in channels if ch]

    def get_instagram_source_accounts_list(self):
        """Парсит instagram_source_accounts в список аккаунтов."""
        if not self.instagram_source_accounts:
            return []
        accounts = [acc.strip() for acc in self.instagram_source_accounts.split(',')]
        return [acc for acc in accounts if acc]

    def get_vkontakte_source_groups_list(self):
        """Парсит vkontakte_source_groups в список групп."""
        if not self.vkontakte_source_groups:
            return []
        groups = [grp.strip() for grp in self.vkontakte_source_groups.split(',')]
        return [grp for grp in groups if grp]

    def __str__(self):
        return self.name

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.client.name} – {self.channel_type} analysis ({self.status})"


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


class SocialAccount(models.Model):
    PLATFORM_CHOICES = (
        ("instagram", "Instagram"),
        ("telegram", "Telegram"),
        ("youtube", "YouTube"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=255, help_text="Имя/описание аккаунта, чтобы не путать")
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.client} – {self.platform} ({self.name})"


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
    text = models.TextField(blank=True)
    # пока без отдельной Media-модели – можно позже перейти на Wagtail Images/Documents
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    tags = models.JSONField(default=list, blank=True)          # ["ai", "instagram", ...]
    source_links = models.JSONField(default=list, blank=True)  # ["https://...", ...]

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


class Schedule(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In progress"),
        ("published", "Published"),
        ("failed", "Failed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="schedules")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="schedules")
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name="schedules")

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
        return f"{self.post} -> {self.social_account} @ {self.scheduled_at} ({self.status})"


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

    LENGTH_CHOICES = (
        ("short", "Короткий (500-1000 символов)"),
        ("medium", "Средний (1000-1500 символов)"),
        ("long", "Длинный (1500-2000 символов)"),
    )

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
    length = models.CharField(
        max_length=20,
        choices=LENGTH_CHOICES,
        default="medium",
        help_text="Длина поста"
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
            "{type}, {avatar}, {pains}, {desires}, {objections}"
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


class SystemSetting(models.Model):
    """Глобальные настройки системы (singleton)."""

    DEFAULT_AI_MODEL = "x-ai/grok-4.1-fast:free"
    DEFAULT_POST_AI_MODEL = DEFAULT_AI_MODEL
    DEFAULT_IMAGE_AI_MODEL = "google/gemini-2.5-flash-image"
    DEFAULT_IMAGE_TIMEOUT = 120
    DEFAULT_VIDEO_TIMEOUT = 600
    DEFAULT_FALLBACK_AI_MODEL = "tngtech/deepseek-r1t2-chimera:free"

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
    image_generation_model = models.CharField(
        max_length=255,
        default=DEFAULT_IMAGE_AI_MODEL,
        help_text="Модель OpenRouter для генерации изображений (например, google/gemini-2.5-flash-image)"
    )
    video_prompt_instructions = models.TextField(
        blank=True,
        help_text=(
            "Дополнительные пожелания к промптам для видео. "
            "Этот текст добавляется к базовым инструкциям при генерации видео."
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
                "image_generation_model": cls.DEFAULT_IMAGE_AI_MODEL,
                "fallback_ai_model": cls.DEFAULT_FALLBACK_AI_MODEL,
                "image_generation_timeout": cls.DEFAULT_IMAGE_TIMEOUT,
                "video_generation_timeout": cls.DEFAULT_VIDEO_TIMEOUT,
            },
        )
        return obj
