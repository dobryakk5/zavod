from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0101_competitor_site_manual_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="channelanalysis",
            name="share_token",
            field=models.CharField(max_length=64, unique=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="channelanalysis",
            name="share_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
