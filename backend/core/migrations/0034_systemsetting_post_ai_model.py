from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_post_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsetting',
            name='post_ai_model',
            field=models.CharField(
                blank=True,
                default='x-ai/grok-4.1-fast:free',
                help_text='Отдельная модель OpenRouter для генерации текстов постов',
                max_length=255,
            ),
        ),
    ]
