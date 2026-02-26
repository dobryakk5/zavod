from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0167_contact_product_purchase"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactproductpurchase",
            name="service_package_mode",
            field=models.CharField(
                blank=True,
                default="",
                help_text="count | minutes; пусто если продукт не является пакетом услуг",
                max_length=16,
                verbose_name="Режим сервисного пакета",
            ),
        ),
        migrations.AddField(
            model_name="contactproductpurchase",
            name="service_package_name",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Название пакета услуг",
            ),
        ),
        migrations.AddField(
            model_name="contactproductpurchase",
            name="service_package_total_units",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Всего единиц в пакете услуг",
            ),
        ),
        migrations.AddField(
            model_name="contactproductpurchase",
            name="service_package_used_units",
            field=models.PositiveIntegerField(
                default=0,
                verbose_name="Израсходовано единиц в пакете услуг",
            ),
        ),
        migrations.CreateModel(
            name="ContactProductServiceUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contact_id", models.BigIntegerField(db_index=True, verbose_name="ID контакта (map.contact)")),
                ("event_id", models.BigIntegerField(db_index=True, unique=True, verbose_name="ID встречи (map.crm_events)")),
                (
                    "mode",
                    models.CharField(
                        choices=[("count", "По количеству встреч"), ("minutes", "По минутам")],
                        max_length=16,
                        verbose_name="Режим списания",
                    ),
                ),
                ("units", models.PositiveIntegerField(verbose_name="Списанные единицы (встречи/минуты)")),
                ("event_started_at", models.DateTimeField(blank=True, null=True, verbose_name="Начало встречи")),
                ("event_ended_at", models.DateTimeField(blank=True, null=True, verbose_name="Окончание встречи")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="contact_product_service_usages",
                        to="core.client",
                        verbose_name="Клиент",
                    ),
                ),
                (
                    "purchase",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="service_usages",
                        to="core.contactproductpurchase",
                        verbose_name="Покупка пакета",
                    ),
                ),
            ],
            options={
                "verbose_name": "Списание пакета услуг по встрече",
                "verbose_name_plural": "Списания пакетов услуг по встречам",
                "ordering": ("-updated_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="contactproductserviceusage",
            index=models.Index(fields=("client", "contact_id"), name="idx_cpsu_client_contact"),
        ),
        migrations.AddIndex(
            model_name="contactproductserviceusage",
            index=models.Index(fields=("purchase",), name="idx_cpsu_purchase"),
        ),
    ]
