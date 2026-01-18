from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0104_merge_channel_analysis_sharing_and_competitor_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="tgstat_channels",
            field=models.JSONField(blank=True, default=list, help_text="Список избранных TGStat каналов (id)"),
        ),
    ]
