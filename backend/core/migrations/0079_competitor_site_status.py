from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0078_competitor_site_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitorsite",
            name="analysis_status",
            field=models.CharField(blank=True, default="pending", max_length=20),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="analysis_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="task_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

