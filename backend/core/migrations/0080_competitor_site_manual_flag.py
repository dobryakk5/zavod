from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0079_competitor_site_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitorsite",
            name="manual_is_competitor",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="manual_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

