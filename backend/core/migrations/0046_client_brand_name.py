from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_add_hook_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='brand_name',
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name='Название бренда',
                help_text='Используется при упоминании бренда в постах',
            ),
        ),
    ]

