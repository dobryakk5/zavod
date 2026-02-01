from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0133_map_crm_event_notifications"),
    ]

    operations = [
        migrations.AlterField(
            model_name="client",
            name="timezone",
            field=models.CharField(default="Europe/Moscow", max_length=64),
        ),
    ]
