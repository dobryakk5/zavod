from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_alter_wordstatresult_result_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socialaccount",
            name="platform",
            field=models.CharField(
                choices=[
                    ("instagram", "Instagram"),
                    ("telegram", "Telegram"),
                    ("youtube", "YouTube"),
                    ("rss_zen", "RSS Zen"),
                ],
                max_length=20,
            ),
        ),
    ]

