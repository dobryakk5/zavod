from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0128_semantic_phrase_raw_phrase"),
    ]

    operations = [
        migrations.AddField(
            model_name="semanticphrase",
            name="normalized_phrase",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="semanticphrase",
            name="phrase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="semantic_phrases",
                to="core.wordstatphrase",
            ),
        ),
    ]
