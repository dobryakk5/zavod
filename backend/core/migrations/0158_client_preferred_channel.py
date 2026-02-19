from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0157_user_social_account"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="preferred_channel",
            field=models.CharField(
                blank=True,
                choices=[("telegram", "Telegram"), ("vk", "ВКонтакте"), ("email", "Email")],
                help_text="Предпочтительный канал связи с клиентом",
                max_length=32,
                null=True,
            ),
        ),
    ]
