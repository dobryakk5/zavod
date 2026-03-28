from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0194_contact_coaching_profile_tasks"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailAuthToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("token", models.CharField(db_index=True, max_length=100, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Email auth token",
                "verbose_name_plural": "Email auth tokens",
                "ordering": ["-created_at"],
            },
        ),
    ]
