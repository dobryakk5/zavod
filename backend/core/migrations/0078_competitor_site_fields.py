from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0077_competitor_site"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitorsite",
            name="home_title",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="home_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="services_url",
            field=models.CharField(blank=True, default="", max_length=700),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="prices_url",
            field=models.CharField(blank=True, default="", max_length=700),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="ai_is_competitor",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="ai_one_liner",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="ai_pricing",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="competitorsite",
            name="last_analyzed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

