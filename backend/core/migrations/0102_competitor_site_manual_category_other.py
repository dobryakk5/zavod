from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0101_competitor_site_manual_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="competitorsite",
            name="manual_category",
            field=models.CharField(
                max_length=32,
                blank=True,
                null=True,
                choices=[
                    ("competitor", "Competitor"),
                    ("informational", "Informational"),
                    ("indirect", "Indirect"),
                    ("other", "Other"),
                ],
            ),
        ),
    ]
