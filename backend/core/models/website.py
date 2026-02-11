from django.db import models

from ._mixins import TaskStatusMixin
from .client import Client


class WebsiteScan(TaskStatusMixin):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="website_scans")
    base_url = models.CharField(max_length=500, help_text="Base website URL (e.g. https://example.com)")
    max_depth = models.PositiveIntegerField(default=3)
    max_pages = models.PositiveIntegerField(default=100)
    pages_total = models.PositiveIntegerField(blank=True, null=True)
    robots_url = models.CharField(max_length=700, blank=True)
    robots_txt = models.TextField(blank=True)
    sitemap_urls = models.JSONField(default=list, blank=True)
    mind_map_id = models.IntegerField(blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["client", "status", "-created_at"],
                name="ws_client_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"[{self.client.slug}] WebsiteScan {self.base_url} ({self.status})"


class WebsiteScanPage(models.Model):
    scan = models.ForeignKey(WebsiteScan, on_delete=models.CASCADE, related_name="pages")
    url = models.CharField(max_length=700)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, related_name="children", blank=True, null=True
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


class CompetitorSite(models.Model):
    """Дедуплицированные сайты конкурентов из результатов Google."""

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

    def __str__(self) -> str:
        return f"{self.client.slug}:{self.domain}"
