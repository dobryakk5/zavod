from django.db import migrations


def forwards(apps, schema_editor):
    CompetitorSite = apps.get_model("core", "CompetitorSite")
    CompetitorSite.objects.filter(manual_category="indirect").update(manual_category="other")


def backwards(apps, schema_editor):
    CompetitorSite = apps.get_model("core", "CompetitorSite")
    CompetitorSite.objects.filter(manual_category="other", manual_is_competitor=False).update(manual_category="indirect")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0102_competitor_site_manual_category_other"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
