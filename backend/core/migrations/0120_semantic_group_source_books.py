from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0119_semantic_clusters_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticgroup",
            name="source_books",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
