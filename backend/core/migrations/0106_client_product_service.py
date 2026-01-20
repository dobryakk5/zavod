from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0105_client_tgstat_channels"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="product_service",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Например "доставка пиццы" или "онлайн-курс по йоге"',
                max_length=255,
                verbose_name="Продукт/услуга",
            ),
        ),
    ]
