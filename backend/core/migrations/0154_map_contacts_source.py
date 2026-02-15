from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0153_chains_client_meeting_payment_conditions"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE map.contacts
                ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT '';
            """,
            reverse_sql="""
            ALTER TABLE map.contacts
                DROP COLUMN IF EXISTS source;
            """,
        ),
    ]
