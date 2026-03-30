from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0197_coach_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="InviteLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("contact_id", models.IntegerField(db_index=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coach_invite_links",
                        to="core.client",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.AddIndex(
            model_name="invitelink",
            index=models.Index(fields=["tenant", "contact_id"], name="idx_coach_inv_tenant_contact"),
        ),
        migrations.AddIndex(
            model_name="invitelink",
            index=models.Index(fields=["used_at"], name="idx_coach_invite_used_at"),
        ),
    ]
