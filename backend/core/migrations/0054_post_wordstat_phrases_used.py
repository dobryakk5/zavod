from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_wordstatquery_phrases_and_group_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="wordstat_phrases_used",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Какие избранные фразы Wordstat были использованы при генерации",
            ),
        ),
    ]

