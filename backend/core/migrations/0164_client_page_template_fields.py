from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0163_map_products_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="client_page_config",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Конфигурация блоков, выбранного продукта и шаблона страницы /c/[client_id]",
                verbose_name="Настройки публичной страницы клиента",
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="client_page_content",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Rich-text контент (TipTap JSON) для страницы /c/[client_id]",
                verbose_name="Контент публичной страницы клиента",
            ),
        ),
    ]
