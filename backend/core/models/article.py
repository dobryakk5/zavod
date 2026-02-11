from django.conf import settings
from django.db import models

from .client import Client


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
    """Proxy-модель для Django Admin."""

    class Meta:
        proxy = True
        verbose_name = "Промпт статьи"
        verbose_name_plural = "Промпты статей"
