from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0062_client_products"),
    ]

    operations = [
        migrations.RenameField(
            model_name="clientproduct",
            old_name="title",
            new_name="product_type",
        ),
        migrations.RenameField(
            model_name="clientproduct",
            old_name="description",
            new_name="short_description",
        ),
        migrations.AddField(
            model_name="clientproduct",
            name="packages",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

