from django.db import migrations


SYSTEM_SLUG = "system"
SOURCE_CLIENT_ID = 3


def create_system_client_and_move_templates(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    ContentTemplate = apps.get_model("core", "ContentTemplate")

    system_client, _ = Client.objects.get_or_create(
        slug=SYSTEM_SLUG,
        defaults={
            "name": "System Templates",
            "timezone": "UTC",
        },
    )

    try:
        source_client = Client.objects.get(id=SOURCE_CLIENT_ID)
    except Client.DoesNotExist:
        return

    ContentTemplate.objects.filter(client=source_client).update(client=system_client)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_channelanalysis"),
    ]

    operations = [
        migrations.RunPython(create_system_client_and_move_templates, migrations.RunPython.noop),
    ]
