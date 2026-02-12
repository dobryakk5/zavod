# core/migrations/0147_referralcode_referral.py

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        # Замени на последнюю реальную миграцию в твоём проекте
        ("core", "0146_auto_previous"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferralCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("code", models.CharField(db_index=True, max_length=24, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("total_referrals", models.PositiveIntegerField(default=0)),
                ("successful_referrals", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_code",
                        to="core.client",
                    ),
                ),
            ],
            options={"db_table": "referral_codes"},
        ),
        migrations.CreateModel(
            name="Referral",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("invited_telegram_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("invited_telegram_username", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Ожидает регистрации"),
                            ("registered", "Зарегистрировался"),
                            ("rewarded", "Награда выдана"),
                            ("expired", "Истёк срок"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("registered_at", models.DateTimeField(blank=True, null=True)),
                ("rewarded_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "referral_code",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals",
                        to="core.referralcode",
                    ),
                ),
                (
                    "referrer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals_sent",
                        to="core.client",
                    ),
                ),
                (
                    "referee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referrals_received",
                        to="core.client",
                    ),
                ),
            ],
            options={"db_table": "referrals"},
        ),
        migrations.AddIndex(
            model_name="referral",
            index=models.Index(fields=["referrer", "status"], name="referral_referrer_status_idx"),
        ),
        migrations.AddIndex(
            model_name="referral",
            index=models.Index(fields=["invited_telegram_id"], name="referral_tg_id_idx"),
        ),
    ]
