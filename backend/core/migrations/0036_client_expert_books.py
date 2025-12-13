from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_systemsetting_image_generation_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='expert_books',
            field=models.TextField(
                blank=True,
                help_text='Подборка книг для целевой аудитории (по одна на строку)',
                verbose_name='Книги экспертов',
            ),
        ),
    ]
