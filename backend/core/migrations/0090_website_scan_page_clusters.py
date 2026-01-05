from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0089_article_block_subquery_key_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="websitescanpage",
            name="cluster_level_1",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="websitescanpage",
            name="cluster_level_2",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="websitescanpage",
            name="cluster_level_3",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="websitescanpage",
            name="cluster_source",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
