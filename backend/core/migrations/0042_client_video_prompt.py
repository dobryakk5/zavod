from django.db import migrations, models


def copy_system_video_prompt(apps, schema_editor):
    Client = apps.get_model("core", "Client")
    SystemSetting = apps.get_model("core", "SystemSetting")

    try:
        system_setting = SystemSetting.objects.first()
        default_prompt = (system_setting.video_prompt_instructions or "").strip() if system_setting else ""
    except Exception:
        default_prompt = ""

    if not default_prompt:
        return

    Client.objects.filter(video_prompt="").update(video_prompt=default_prompt)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_alter_systemsetting_image_openrouter_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="video_prompt",
            field=models.TextField(
                blank=True,
                help_text="Инструкции для генерации видео, уникальные для этого клиента",
                verbose_name="Video prompt",
            ),
        ),
        migrations.RunPython(copy_system_video_prompt, migrations.RunPython.noop),
    ]
