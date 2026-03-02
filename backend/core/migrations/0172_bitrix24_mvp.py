import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0171_amocrm_mvp"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Bitrix24Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("portal_domain", models.CharField(db_index=True, max_length=255)),
                ("member_id", models.CharField(db_index=True, max_length=64, unique=True)),
                ("account_name", models.CharField(blank=True, max_length=255)),
                ("client_endpoint", models.CharField(blank=True, max_length=512)),
                ("server_endpoint", models.CharField(blank=True, max_length=512)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("scope", models.JSONField(blank=True, default=list)),
                ("application_token", models.CharField(blank=True, max_length=255)),
                ("webhook_secret", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("webhook_registered_at", models.DateTimeField(blank=True, null=True)),
                ("webhook_last_error", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("error", "Error"), ("revoked", "Revoked")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bitrix24_accounts",
                        to="core.client",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bitrix24_accounts_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "bitrix24_accounts",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="bitrix24account",
            constraint=models.UniqueConstraint(fields=("client", "portal_domain"), name="uq_b24_acc_cli_portal"),
        ),
        migrations.AddIndex(
            model_name="bitrix24account",
            index=models.Index(fields=("client", "status"), name="ix_b24_acc_cli_stat"),
        ),
        migrations.CreateModel(
            name="Bitrix24ContactMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bitrix_contact_id", models.BigIntegerField()),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_webhook_at", models.DateTimeField(blank=True, null=True)),
                ("sync_hash", models.CharField(blank=True, max_length=64)),
                ("remote_updated_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contact_mappings",
                        to="core.bitrix24account",
                    ),
                ),
                (
                    "crm_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bitrix24_mappings",
                        to="core.crmclient",
                    ),
                ),
            ],
            options={
                "db_table": "bitrix24_contact_mappings",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="bitrix24contactmapping",
            constraint=models.UniqueConstraint(fields=("account", "crm_client"), name="uq_b24_map_acc_client"),
        ),
        migrations.AddConstraint(
            model_name="bitrix24contactmapping",
            constraint=models.UniqueConstraint(fields=("account", "bitrix_contact_id"), name="uq_b24_map_acc_contact"),
        ),
        migrations.AddIndex(
            model_name="bitrix24contactmapping",
            index=models.Index(fields=("account", "last_synced_at"), name="ix_b24_map_acc_sync"),
        ),
        migrations.CreateModel(
            name="Bitrix24LogEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(help_text="oauth|sync|webhook|resync", max_length=32)),
                ("action", models.CharField(help_text="Конкретное действие", max_length=64)),
                (
                    "level",
                    models.CharField(
                        choices=[("info", "Info"), ("warning", "Warning"), ("error", "Error")],
                        default="info",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("queued", "Queued"), ("success", "Success"), ("error", "Error"), ("skipped", "Skipped")],
                        default="success",
                        max_length=16,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("idempotency_key", models.CharField(blank=True, db_index=True, max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="core.bitrix24account",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bitrix24_logs",
                        to="core.client",
                    ),
                ),
                (
                    "crm_client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bitrix24_logs",
                        to="core.crmclient",
                    ),
                ),
                (
                    "mapping",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="core.bitrix24contactmapping",
                    ),
                ),
            ],
            options={
                "db_table": "bitrix24_log_entries",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="bitrix24logentry",
            index=models.Index(fields=("client", "created_at"), name="ix_b24_log_cli_ct"),
        ),
        migrations.AddIndex(
            model_name="bitrix24logentry",
            index=models.Index(fields=("account", "created_at"), name="ix_b24_log_acc_ct"),
        ),
        migrations.AddIndex(
            model_name="bitrix24logentry",
            index=models.Index(fields=("level", "status"), name="ix_b24_log_lvl_stat"),
        ),
        migrations.CreateModel(
            name="Bitrix24WebhookEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_name", models.CharField(max_length=64)),
                ("event_handler_id", models.CharField(blank=True, max_length=64)),
                ("remote_entity_id", models.BigIntegerField(blank=True, null=True)),
                ("ts", models.BigIntegerField(blank=True, null=True)),
                ("idempotency_key", models.CharField(max_length=160)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("received", "Received"),
                            ("processing", "Processing"),
                            ("done", "Done"),
                            ("failed", "Failed"),
                            ("ignored", "Ignored"),
                        ],
                        default="received",
                        max_length=16,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_events",
                        to="core.bitrix24account",
                    ),
                ),
            ],
            options={
                "db_table": "bitrix24_webhook_events",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="bitrix24webhookevent",
            constraint=models.UniqueConstraint(fields=("account", "idempotency_key"), name="uq_b24_evt_acc_idem"),
        ),
        migrations.AddIndex(
            model_name="bitrix24webhookevent",
            index=models.Index(fields=("account", "status", "created_at"), name="ix_b24_evt_acc_stat_ct"),
        ),
        migrations.AddIndex(
            model_name="bitrix24webhookevent",
            index=models.Index(fields=("account", "event_name", "remote_entity_id"), name="ix_b24_evt_acc_obj"),
        ),
    ]
