from django.db import models

from .client import Client


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
        WordstatCluster, on_delete=models.SET_NULL, related_name="results", blank=True, null=True
    )
    phrase = models.TextField()
    count = models.PositiveIntegerField(default=0)
    result_type = models.CharField(max_length=20, choices=RESULT_TYPE_CHOICES, default="top_request")
    used_in_post = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-count", "phrase")
        indexes = [models.Index(fields=["query", "result_type", "count"])]
        verbose_name = "Wordstat Result"
        verbose_name_plural = "Wordstat Results"

    def __str__(self):
        return f"{self.phrase} ({self.count})"
