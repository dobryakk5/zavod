# Generated manually to add timestamps to Client model
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_add_crm_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]