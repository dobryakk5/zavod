from django.db import models

from .client import Client


class PostType(models.Model):
    """Справочник типов постов (системные и клиентские)."""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="post_types",
        null=True,
        blank=True,
        help_text="Оставьте пустым для системного типа, доступного всем клиентам",
    )
    value = models.CharField(max_length=50, help_text="Техническое название (например: selling, expert)")
    label = models.CharField(max_length=100, help_text="Отображаемое название (например: Продающий, Экспертный)")
    is_default = models.BooleanField(default=False, help_text="Предустановленный тип (создан автоматически)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "Post Type"
        verbose_name_plural = "Post Types"
        unique_together = [["client", "value"]]

    def __str__(self):
        prefix = f"[{self.client.slug}]" if self.client else "[Системный]"
        return f"{prefix} {self.label}"


class PostTone(models.Model):
    """Справочник тонов постов (системные и клиентские)."""

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="post_tones",
        null=True,
        blank=True,
        help_text="Оставьте пустым для системного тона, доступного всем клиентам",
    )
    value = models.CharField(max_length=50, help_text="Техническое название (например: professional, friendly)")
    label = models.CharField(max_length=100, help_text="Отображаемое название (например: Профессиональный, Дружественный)")
    is_default = models.BooleanField(default=False, help_text="Предустановленный тон (создан автоматически)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "Post Tone"
        verbose_name_plural = "Post Tones"
        unique_together = [["client", "value"]]

    def __str__(self):
        prefix = f"[{self.client.slug}]" if self.client else "[Системный]"
        return f"{prefix} {self.label}"


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
    """Шаблон для AI генерации контента с настройками стиля."""

    SUGGESTED_TYPES = ["selling", "expert", "trigger", "story"]
    SUGGESTED_TONES = ["professional", "friendly", "informative", "casual", "enthusiastic"]

    LANGUAGE_CHOICES = (
        ("ru", "Русский"),
        ("en", "English"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="content_templates")
    name = models.CharField(max_length=255, help_text="Название шаблона (например, 'Instagram пост')")

    type = models.CharField(max_length=50, default="selling")
    tone = models.CharField(max_length=50, default="professional")
    length = models.PositiveIntegerField(default=1200, help_text="Целевая длина поста в символах")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="ru")

    seo_prompt_template = models.TextField(
        verbose_name="SEO промпт",
        default="",
        help_text=(
            "Шаблон промпта для генерации на основе SEO ключевых фраз. "
            "Плейсхолдеры: {seo_keywords}, {topic_name}, {tone}, {length}, {language}, "
            "{type}, {avatar}, {pains}, {desires}, {objections}, {books}"
        ),
    )
    trend_prompt_template = models.TextField(
        verbose_name="Trend промпт",
        default="",
        help_text=(
            "Шаблон промпта для генерации на основе трендов. "
            "Плейсхолдеры: {trend_title}, {trend_description}, {trend_url}, {topic_name}, "
            "{tone}, {length}, {language}, {type}, {avatar}, {pains}, {desires}, {objections}"
        ),
    )
    additional_instructions = models.TextField(
        blank=True,
        help_text="Дополнительные инструкции для AI (например, 'Всегда упоминай бренд X')",
    )

    is_default = models.BooleanField(default=False, help_text="Использовать этот шаблон по умолчанию для клиента")
    include_hashtags = models.BooleanField(default=True, help_text="Генерировать хэштеги")
    max_hashtags = models.IntegerField(default=5, help_text="Максимальное количество хэштегов")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ContentTemplateManager()

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Content Template"
        verbose_name_plural = "Content Templates"
        unique_together = [["client", "name"]]

    def __str__(self):
        suffix = " [DEFAULT]" if self.is_default else ""
        return f"[{self.client.slug}] {self.name}{suffix}"

    def save(self, *args, **kwargs):
        if self.is_default:
            ContentTemplate.objects.filter(
                client=self.client, is_default=True
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
