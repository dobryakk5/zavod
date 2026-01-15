from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0095_project_channel_analysis"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="wordstat_phrases",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
