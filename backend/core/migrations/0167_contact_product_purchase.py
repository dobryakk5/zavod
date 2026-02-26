from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0166_unmanaged_product_kb_columns_sql"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactProductPurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contact_id", models.BigIntegerField(db_index=True, verbose_name="ID контакта (map.contact)")),
                ("product_id", models.BigIntegerField(db_index=True, verbose_name="ID продукта (map.products)")),
                ("product_name", models.CharField(blank=True, default="", max_length=255, verbose_name="Название продукта")),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Сумма покупки")),
                ("currency", models.CharField(default="RUB", max_length=3, verbose_name="Валюта")),
                ("paid_at", models.DateTimeField(blank=True, null=True, verbose_name="Дата оплаты")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="contact_product_purchases",
                        to="core.client",
                        verbose_name="Клиент",
                    ),
                ),
                (
                    "last_payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="contact_product_purchases",
                        to="core.yookassapayment",
                        verbose_name="Последний платеж YooKassa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Покупка цифрового продукта контактом",
                "verbose_name_plural": "Покупки цифровых продуктов контактами",
                "ordering": ("-paid_at", "-updated_at", "-id"),
            },
        ),
        migrations.AddConstraint(
            model_name="contactproductpurchase",
            constraint=models.UniqueConstraint(
                fields=("client", "contact_id", "product_id"),
                name="uniq_contact_product_purchase",
            ),
        ),
        migrations.AddIndex(
            model_name="contactproductpurchase",
            index=models.Index(fields=("client", "contact_id"), name="idx_cpp_client_contact"),
        ),
        migrations.AddIndex(
            model_name="contactproductpurchase",
            index=models.Index(fields=("client", "product_id"), name="idx_cpp_client_product"),
        ),
    ]
