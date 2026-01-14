from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0091_wordstat_clusters"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="result_html",
            field=models.TextField(blank=True, help_text="Итоговый HTML-текст статьи"),
        ),
    ]
