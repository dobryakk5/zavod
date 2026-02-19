from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0161_kb_documents_index_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="referralcode",
            name="code_type",
            field=models.CharField(
                choices=[("client", "Client"), ("contact", "Contact")],
                db_index=True,
                default="client",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="referralcode",
            name="contact_id",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AlterField(
            model_name="referralcode",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="referral_codes",
                to="core.client",
            ),
        ),
        migrations.AddConstraint(
            model_name="referralcode",
            constraint=models.CheckConstraint(
                check=(
                    (models.Q(code_type="client") & models.Q(contact_id__isnull=True))
                    | (models.Q(code_type="contact") & models.Q(contact_id__isnull=False))
                ),
                name="ref_code_type_contact_consistency",
            ),
        ),
        migrations.AddConstraint(
            model_name="referralcode",
            constraint=models.UniqueConstraint(
                condition=models.Q(code_type="client"),
                fields=("client", "code_type"),
                name="uniq_ref_code_client_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="referralcode",
            constraint=models.UniqueConstraint(
                condition=models.Q(code_type="contact"),
                fields=("client", "contact_id", "code_type"),
                name="uniq_ref_code_contact_type",
            ),
        ),
    ]
