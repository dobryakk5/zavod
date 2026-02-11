from typing import List

from django.conf import settings
from django.db import models

from .client import Client


class Topic(models.Model):
    """Тема для сбора контента (например, 'студия танцев', 'технологии AI')."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="topics")
    name = models.CharField(max_length=255, help_text="Название темы (например, 'студия танцев')")
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Ключевые слова для поиска (например, ['танцы', 'хореография', 'dance'])",
    )
    is_active = models.BooleanField(default=True, help_text="Активна ли тема для автоматического сбора")

    use_google_trends = models.BooleanField(default=True, verbose_name="Google Trends")
    use_telegram = models.BooleanField(default=False, verbose_name="Telegram")
    use_rss = models.BooleanField(default=False, verbose_name="RSS")
    use_youtube = models.BooleanField(default=False, verbose_name="YouTube")
    use_instagram = models.BooleanField(default=False, verbose_name="Instagram")
    use_vkontakte = models.BooleanField(default=False, verbose_name="VKontakte")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Topic"
        verbose_name_plural = "Topics"

    def __str__(self):
        return f"[{self.client.slug}] {self.name}"

    def get_enabled_sources(self) -> List[str]:
        return [
            source
            for source, flag in [
                ("google_trends", self.use_google_trends),
                ("telegram", self.use_telegram),
                ("rss", self.use_rss),
                ("youtube", self.use_youtube),
                ("instagram", self.use_instagram),
                ("vkontakte", self.use_vkontakte),
            ]
            if flag
        ]


class TrendItem(models.Model):
    """Найденный тренд или новость."""

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
    relevance_score = models.IntegerField(default=0)
    extra = models.JSONField(default=dict, blank=True)
    used_for_post = models.ForeignKey(
        "Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_trends",
        help_text="Пост, созданный на основе этого тренда",
    )
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-relevance_score", "-discovered_at")
        verbose_name = "Trend Item"
        verbose_name_plural = "Trend Items"

    def __str__(self):
        return f"[{self.source}] {self.title[:50]}"


class Story(models.Model):
    """История — серия связанных постов (мини-сериал)."""

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("approved", "Approved"),
        ("generating_posts", "Generating Posts"),
        ("completed", "Completed"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="stories")
    trend_item = models.ForeignKey(
        TrendItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stories",
        help_text="Тренд, на основе которого создана история",
    )
    template = models.ForeignKey(
        "ContentTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Шаблон для генерации постов из эпизодов",
    )
    title = models.CharField(max_length=500, help_text="Общий заголовок истории")
    episodes = models.JSONField(
        default=list,
        help_text="Список эпизодов: [{'order': 1, 'title': '...'}, ...]",
    )
    episode_count = models.IntegerField(default=5, help_text="Количество эпизодов в истории")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    generated_by = models.CharField(
        max_length=50,
        default="openrouter-chimera",
        help_text="Модель AI, использованная для генерации",
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

    def get_episodes_display(self) -> str:
        if not self.episodes:
            return "Нет эпизодов"
        return "\n".join(f"{ep['order']}. {ep['title']}" for ep in self.episodes)
