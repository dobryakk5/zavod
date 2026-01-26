from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0125_wordstat_normalize_phrases_prompt"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticphrase",
            name="comment",
            field=models.TextField(blank=True),
        ),
    ]
