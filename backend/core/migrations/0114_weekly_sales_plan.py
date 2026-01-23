from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0113_map_telegram_tasks"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklySalesPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start", models.DateField(help_text="Дата начала недели (понедельник)")),
                ("cold_leads_plan", models.PositiveIntegerField(blank=True, null=True)),
                ("cold_leads_fact", models.PositiveIntegerField(blank=True, null=True)),
                ("hot_leads_plan", models.PositiveIntegerField(blank=True, null=True)),
                ("hot_leads_fact", models.PositiveIntegerField(blank=True, null=True)),
                ("sales_plan", models.PositiveIntegerField(blank=True, null=True)),
                ("sales_fact", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="weekly_sales_plans",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "ordering": ("-week_start",),
                "verbose_name": "Weekly Sales Plan",
                "verbose_name_plural": "Weekly Sales Plans",
            },
        ),
        migrations.AddConstraint(
            model_name="weeklysalesplan",
            constraint=models.UniqueConstraint(fields=("client", "week_start"), name="core_weekly_sales_client_week_unique"),
        ),
    ]
