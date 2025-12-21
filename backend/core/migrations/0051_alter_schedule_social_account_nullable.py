from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_alter_socialaccount_platform"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schedule",
            name="social_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="schedules",
                to="core.socialaccount",
            ),
        ),
    ]

