from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0196_project_team_invite_email_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoachGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coach_groups",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(fields=["tenant", "created_at"], name="idx_coach_group_tenant_created"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CoachGroupTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=500)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("step_refs", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="core.coachgroup",
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(fields=["group", "created_at"], name="idx_coach_group_task"),
                ],
            },
        ),
        migrations.CreateModel(
            name="CoachGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contact_id", models.IntegerField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="core.coachgroup",
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
                "indexes": [
                    models.Index(fields=["group", "contact_id"], name="idx_coach_group_member"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("group", "contact_id"), name="uniq_coach_group_member"),
                ],
            },
        ),
    ]
