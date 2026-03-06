from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0180_quiz_branching_schema"),
    ]

    operations = [
        migrations.AddField(
            model_name="yookassapayment",
            name="provider",
            field=models.CharField(
                choices=[("yookassa", "YooKassa"), ("tbank", "T-Bank")],
                default="yookassa",
                max_length=32,
                verbose_name="Платежный провайдер",
            ),
        ),
        migrations.AddIndex(
            model_name="yookassapayment",
            index=models.Index(fields=["provider", "client"], name="yk_provider_client_idx"),
        ),
    ]
