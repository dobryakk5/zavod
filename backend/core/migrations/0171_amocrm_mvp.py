import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0170_inbox_reply_message"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AmoCRMAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subdomain", models.CharField(db_index=True, max_length=255)),
                ("base_domain", models.CharField(help_text="Например example.amocrm.ru", max_length=255, unique=True)),
                ("account_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("account_name", models.CharField(blank=True, max_length=255)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("scope", models.JSONField(blank=True, default=list)),
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
                        related_name="amocrm_accounts",
                        to="core.client",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="amocrm_accounts_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "amocrm_accounts",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="amocrmaccount",
            constraint=models.UniqueConstraint(fields=("client", "subdomain"), name="uq_amocrm_acc_cli_subd"),
        ),
        migrations.AddIndex(
            model_name="amocrmaccount",
            index=models.Index(fields=("client", "status"), name="ix_amocrm_acc_cli_stat"),
        ),
        migrations.CreateModel(
            name="AmoCRMContactMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amo_contact_id", models.BigIntegerField()),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_webhook_at", models.DateTimeField(blank=True, null=True)),
                ("sync_hash", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contact_mappings",
                        to="core.amocrmaccount",
                    ),
                ),
                (
                    "crm_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="amocrm_mappings",
                        to="core.crmclient",
                    ),
                ),
            ],
            options={
                "db_table": "amocrm_contact_mappings",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="amocrmcontactmapping",
            constraint=models.UniqueConstraint(fields=("account", "crm_client"), name="uq_amocrm_map_acc_cli"),
        ),
        migrations.AddConstraint(
            model_name="amocrmcontactmapping",
            constraint=models.UniqueConstraint(fields=("account", "amo_contact_id"), name="uq_amocrm_map_acc_amo"),
        ),
        migrations.AddIndex(
            model_name="amocrmcontactmapping",
            index=models.Index(fields=("account", "last_synced_at"), name="ix_amocrm_map_acc_sync"),
        ),
        migrations.CreateModel(
            name="AmoCRMLogEntry",
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
                        to="core.amocrmaccount",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="amocrm_logs",
                        to="core.client",
                    ),
                ),
                (
                    "crm_client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="amocrm_logs",
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
                        to="core.amocrmcontactmapping",
                    ),
                ),
            ],
            options={
                "db_table": "amocrm_log_entries",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="amocrmlogentry",
            index=models.Index(fields=("client", "created_at"), name="ix_amocrm_log_cli_ct"),
        ),
        migrations.AddIndex(
            model_name="amocrmlogentry",
            index=models.Index(fields=("account", "created_at"), name="ix_amocrm_log_acc_ct"),
        ),
        migrations.AddIndex(
            model_name="amocrmlogentry",
            index=models.Index(fields=("level", "status"), name="ix_amocrm_log_lvl_stat"),
        ),
    ]
