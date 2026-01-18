from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0063_client_product_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientproduct",
            name="structure",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

