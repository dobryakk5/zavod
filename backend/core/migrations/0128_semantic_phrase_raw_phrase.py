from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0127_wordstat_phrases_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticphrase",
            name="raw_phrase",
            field=models.TextField(blank=True, null=True),
        ),
    ]
