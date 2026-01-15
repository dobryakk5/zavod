from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0096_article_wordstat_phrases"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=150)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="RUB", max_length=3)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Payment Plan",
                "verbose_name_plural": "Payment Plans",
                "ordering": ("sort_order", "name"),
            },
        ),
    ]
