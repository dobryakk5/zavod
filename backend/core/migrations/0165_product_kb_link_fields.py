from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0164_client_page_template_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbdocument",
            name="document_type",
            field=models.TextField(default="page"),
        ),
        migrations.AddField(
            model_name="clientproduct",
            name="digital_product_document",
            field=models.ForeignKey(
                blank=True,
                db_column="digital_product_document_id",
                null=True,
                on_delete=models.SET_NULL,
                related_name="digital_product_links",
                to="core.kbdocument",
            ),
        ),
    ]
