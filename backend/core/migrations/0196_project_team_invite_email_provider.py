from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0195_email_auth_token"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectteaminvite",
            name="provider",
            field=models.CharField(
                choices=[("telegram", "Telegram"), ("vk", "VK"), ("email", "Email")],
                max_length=32,
            ),
        ),
    ]
