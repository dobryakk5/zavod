from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0156_crm_tasks_priority"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSocialAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("telegram", "Telegram"), ("vk", "VK")], max_length=32)),
                ("provider_id", models.CharField(max_length=128)),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="social_accounts_auth", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="usersocialaccount",
            constraint=models.UniqueConstraint(fields=("provider", "provider_id"), name="uniq_user_social_provider_id"),
        ),
        migrations.AddConstraint(
            model_name="usersocialaccount",
            constraint=models.UniqueConstraint(fields=("user", "provider"), name="uniq_user_social_user_provider"),
        ),
        migrations.AddIndex(
            model_name="usersocialaccount",
            index=models.Index(fields=["provider", "provider_id"], name="idx_user_social_provider_id"),
        ),
        migrations.AddIndex(
            model_name="usersocialaccount",
            index=models.Index(fields=["user", "provider"], name="idx_user_social_user_provider"),
        ),
    ]
