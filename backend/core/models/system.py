from django.db import models


class SystemSetting(models.Model):
    """Глобальные настройки системы (singleton, pk=1)."""

    DEFAULT_AI_MODEL = "x-ai/grok-4.1-fast:free"
    DEFAULT_POST_AI_MODEL = DEFAULT_AI_MODEL
    DEFAULT_IMAGE_AI_MODEL = "google/gemini-2.5-flash-image"
    DEFAULT_IMAGE_TIMEOUT = 120
    DEFAULT_VIDEO_TIMEOUT = 600
    DEFAULT_PHOTO_PROMPT_INSTRUCTIONS = "Use people with Slavic appearance, fair skin, any age, any gender"
    DEFAULT_FALLBACK_AI_MODEL = "tngtech/deepseek-r1t2-chimera:free"

    IMAGE_GENERATION_METHODS = [
        ("openrouter", "OpenRouter API"),
        ("veo_photo", "VEO фото (Telegram бот)"),
        ("giga_photo", "Giga фото"),
    ]

    default_ai_model = models.CharField(
        max_length=255,
        default=DEFAULT_AI_MODEL,
        help_text="Модель OpenRouter по умолчанию для генерации контента",
    )
    post_ai_model = models.CharField(
        max_length=255,
        blank=True,
        default=DEFAULT_POST_AI_MODEL,
        help_text="Отдельная модель OpenRouter для генерации текстов постов",
    )
    fallback_ai_model = models.CharField(
        max_length=255,
        blank=True,
        default=DEFAULT_FALLBACK_AI_MODEL,
        help_text="Запасная модель OpenRouter, используется если основная недоступна",
    )
    image_generation_method = models.CharField(
        max_length=50,
        choices=IMAGE_GENERATION_METHODS,
        default="openrouter",
        help_text="Метод генерации изображений",
    )
    image_openrouter_model = models.CharField(
        max_length=255,
        default=DEFAULT_IMAGE_AI_MODEL,
        verbose_name="Image OpenRouter model",
        help_text="Модель OpenRouter для генерации изображений",
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
        help_text="Таймаут (в секундах) для генерации и скачивания изображений.",
    )
    video_generation_timeout = models.PositiveIntegerField(
        default=DEFAULT_VIDEO_TIMEOUT,
        help_text="Таймаут (в секундах) для генерации видео.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "SystemSetting":
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

    client = models.ForeignKey(
        "Client", on_delete=models.CASCADE, related_name="generation_events"
    )
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

    def __str__(self) -> str:
        return f"{self.client_id}:{self.event_type} ({self.created_at:%Y-%m-%d})"
