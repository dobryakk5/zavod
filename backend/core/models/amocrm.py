import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .client import Client
from .crm import CRMClient


class AmoCRMAccount(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_ERROR = "error"
    STATUS_REVOKED = "revoked"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ERROR, "Error"),
        (STATUS_REVOKED, "Revoked"),
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="amocrm_accounts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="amocrm_accounts_created",
    )

    subdomain = models.CharField(max_length=255, db_index=True)
    base_domain = models.CharField(max_length=255, unique=True, help_text="Например example.amocrm.ru")
    account_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    account_name = models.CharField(max_length=255, blank=True)

    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    scope = models.JSONField(default=list, blank=True)

    webhook_secret = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    webhook_registered_at = models.DateTimeField(null=True, blank=True)
    webhook_last_error = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "amocrm_accounts"
        ordering = ("-updated_at",)
        constraints = (
            models.UniqueConstraint(fields=("client", "subdomain"), name="uq_amocrm_acc_cli_subd"),
        )
        indexes = (
            models.Index(fields=("client", "status"), name="ix_amocrm_acc_cli_stat"),
        )

    def __str__(self) -> str:
        suffix = f" @ {self.client.slug}" if self.client_id else ""
        return f"amoCRM {self.base_domain}{suffix}"

    @property
    def is_access_token_expired(self) -> bool:
        if not self.expires_at:
            return True
        return self.expires_at <= timezone.now()


class AmoCRMContactMapping(models.Model):
    account = models.ForeignKey(
        AmoCRMAccount,
        on_delete=models.CASCADE,
        related_name="contact_mappings",
    )
    crm_client = models.ForeignKey(
        CRMClient,
        on_delete=models.CASCADE,
        related_name="amocrm_mappings",
    )
    amo_contact_id = models.BigIntegerField()
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_webhook_at = models.DateTimeField(null=True, blank=True)
    sync_hash = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "amocrm_contact_mappings"
        ordering = ("-updated_at",)
        constraints = (
            models.UniqueConstraint(fields=("account", "crm_client"), name="uq_amocrm_map_acc_cli"),
            models.UniqueConstraint(fields=("account", "amo_contact_id"), name="uq_amocrm_map_acc_amo"),
        )
        indexes = (
            models.Index(fields=("account", "last_synced_at"), name="ix_amocrm_map_acc_sync"),
        )

    def __str__(self) -> str:
        return f"{self.account_id}:{self.crm_client_id}->{self.amo_contact_id}"


class AmoCRMLogEntry(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"

    STATUS_QUEUED = "queued"
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_SKIPPED = "skipped"

    LEVEL_CHOICES = (
        (LEVEL_INFO, "Info"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_ERROR, "Error"),
    )
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_ERROR, "Error"),
        (STATUS_SKIPPED, "Skipped"),
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="amocrm_logs",
    )
    account = models.ForeignKey(
        AmoCRMAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    crm_client = models.ForeignKey(
        CRMClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="amocrm_logs",
    )
    mapping = models.ForeignKey(
        AmoCRMContactMapping,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )

    source = models.CharField(max_length=32, help_text="oauth|sync|webhook|resync")
    action = models.CharField(max_length=64, help_text="Конкретное действие")
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "amocrm_log_entries"
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("client", "created_at"), name="ix_amocrm_log_cli_ct"),
            models.Index(fields=("account", "created_at"), name="ix_amocrm_log_acc_ct"),
            models.Index(fields=("level", "status"), name="ix_amocrm_log_lvl_stat"),
        )

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.level}/{self.status} {self.action}"
