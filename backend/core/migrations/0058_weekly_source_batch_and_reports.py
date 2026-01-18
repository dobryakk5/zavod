from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0057_connection_schedule_connection_postjob"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklySourceBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "week_start",
                    models.DateField(help_text="Дата начала недели (понедельник)"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_source_batches",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Weekly Source Batch",
                "verbose_name_plural": "Weekly Source Batches",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="WeeklySourceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("telegram", "Telegram"),
                            ("instagram", "Instagram"),
                            ("youtube", "YouTube"),
                            ("rss", "RSS"),
                            ("vkontakte", "VKontakte"),
                        ],
                        max_length=20,
                    ),
                ),
                ("source_value", models.CharField(help_text="URL или идентификатор канала/фида", max_length=255)),
                ("week_start", models.DateField(help_text="Дата начала недели (понедельник)")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("summary", models.TextField(blank=True, help_text="Короткий отчёт от AI по источнику за неделю")),
                ("links", models.JSONField(blank=True, default=list, help_text="Ссылки на посты/материалы за неделю")),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "batch",
                    models.ForeignKey(
                        blank=True,
                        help_text="Подборка, к которой относится отчёт",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports",
                        to="core.weeklysourcebatch",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_source_reports",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "verbose_name": "Weekly Source Report",
                "verbose_name_plural": "Weekly Source Reports",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(
                        fields=["client", "source_type", "week_start"],
                        name="core_weekly_client__84fb5e_idx",
                    )
                ],
            },
        ),
    ]
