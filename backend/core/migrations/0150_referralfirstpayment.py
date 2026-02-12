from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0149_map_crm_events_timestamptz"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferralFirstPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("currency", models.CharField(default="RUB", max_length=3)),
                ("plan_code", models.CharField(blank=True, max_length=100)),
                ("paid_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "referral",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="first_payment",
                        to="core.referral",
                    ),
                ),
                (
                    "referrer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_first_payments_received",
                        to="core.client",
                    ),
                ),
                (
                    "referee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_first_payment_made",
                        to="core.client",
                    ),
                ),
                (
                    "yookassa_payment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="referral_first_payment",
                        to="core.yookassapayment",
                    ),
                ),
            ],
            options={"db_table": "referral_first_payments"},
        ),
        migrations.AddIndex(
            model_name="referralfirstpayment",
            index=models.Index(fields=["referrer", "-paid_at"], name="rfp_referrer_paid_idx"),
        ),
        migrations.AddIndex(
            model_name="referralfirstpayment",
            index=models.Index(fields=["referee"], name="rfp_referee_idx"),
        ),
    ]
