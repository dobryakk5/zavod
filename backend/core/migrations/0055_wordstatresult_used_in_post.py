from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0054_post_wordstat_phrases_used"),
    ]

    operations = [
        migrations.AddField(
            model_name="wordstatresult",
            name="used_in_post",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
