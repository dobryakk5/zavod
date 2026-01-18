from django.db import migrations, models


def forwards(apps, schema_editor):
    CompetitorSite = apps.get_model("core", "CompetitorSite")
    for site in CompetitorSite.objects.exclude(manual_is_competitor__isnull=True).only("id", "manual_is_competitor"):
        if site.manual_is_competitor is True:
            category = "competitor"
        elif site.manual_is_competitor is False:
            category = "other"
        else:
            continue
        CompetitorSite.objects.filter(id=site.id).update(manual_category=category)


def backwards(apps, schema_editor):
    CompetitorSite = apps.get_model("core", "CompetitorSite")
    for site in CompetitorSite.objects.exclude(manual_category__isnull=True).only("id", "manual_category"):
        if site.manual_category == "competitor":
            manual_value = True
        elif site.manual_category in {"informational", "indirect", "other"}:
            manual_value = False
        else:
            manual_value = None
        CompetitorSite.objects.filter(id=site.id).update(manual_is_competitor=manual_value)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0100_generation_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitorsite",
            name="manual_category",
            field=models.CharField(
                max_length=32,
                blank=True,
                null=True,
                choices=[
                    ("competitor", "Competitor"),
                    ("informational", "Informational"),
                    ("indirect", "Indirect"),
                ],
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
