from django.db import models

from ._mixins import TaskStatusMixin
from .client import Client


class ChannelAnalysis(TaskStatusMixin):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="channel_analyses")
    channel_url = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=50)
    result = models.JSONField(default=dict, blank=True)
    share_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    share_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.client.name} – {self.channel_type} analysis ({self.status})"


class ProjectChannelAnalysisRun(TaskStatusMixin):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="project_channel_runs")
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["client", "status", "-created_at"],
                name="pcr_client_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.client.name} – project channel run ({self.status})"


class ProjectChannelPostStat(models.Model):
    run = models.ForeignKey(
        ProjectChannelAnalysisRun, on_delete=models.CASCADE, related_name="post_stats"
    )
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="project_channel_post_stats"
    )
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


class WeeklySourceReport(TaskStatusMixin):
    """Еженедельный отчёт по источнику контента."""

    SOURCE_CHOICES = (
        ("telegram", "Telegram"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("rss", "RSS"),
        ("vkontakte", "VKontakte"),
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
    summary = models.TextField(blank=True, help_text="Короткий отчёт от AI по источнику за неделю")
    links = models.JSONField(default=list, blank=True, help_text="Ссылки на посты/материалы за неделю")

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


class WeeklySourceBatch(TaskStatusMixin):
    """Подборка недельных отчётов (запуск)."""

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="weekly_source_batches")
    week_start = models.DateField(help_text="Дата начала недели (понедельник)")

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
            models.UniqueConstraint(
                fields=["client", "week_start"],
                name="core_weekly_sales_client_week_unique",
            ),
        ]

    def __str__(self):
        return f"[{self.client.slug}] Продажи {self.week_start}"


class WeeklyContentStrategy(models.Model):
    """Контент-стратегия по неделям."""

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="weekly_content_strategies"
    )
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
            models.UniqueConstraint(
                fields=["client", "week_start"],
                name="core_weekly_content_strategy_client_week_unique",
            ),
        ]

    def __str__(self):
        return f"[{self.client.slug}] Контент-стратегия {self.week_start}"
