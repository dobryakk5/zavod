from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0193_contact_coaching_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactcoachingprofile",
            name="tasks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
