from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_client_brand_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemsetting",
            name="photo_prompt_instructions",
            field=models.TextField(
                blank=True,
                default="Use people with Slavic appearance, fair skin, any age, any gender",
                help_text=(
                    "Дополнительные пожелания к промптам для генерации изображений. "
                    "Этот текст добавляется к базовым инструкциям при генерации фото."
                ),
            ),
            preserve_default=False,
        ),
    ]
