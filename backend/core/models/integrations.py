from django.conf import settings
from django.db import models
from django.utils import timezone

from .client import Client


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
    name = models.CharField(max_length=255, blank=True, help_text="Человекочитаемое имя подключения")
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
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
