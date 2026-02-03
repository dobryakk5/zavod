from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0134_alter_client_timezone_default"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE map.contacts
                ADD COLUMN IF NOT EXISTS tg_user_id bigint,
                ADD COLUMN IF NOT EXISTS tg_username text,
                ADD COLUMN IF NOT EXISTS tg_connected_at date;
            """,
            reverse_sql="""
            ALTER TABLE map.contacts
                DROP COLUMN IF EXISTS tg_connected_at,
                DROP COLUMN IF EXISTS tg_username,
                DROP COLUMN IF EXISTS tg_user_id;
            """,
        ),
    ]
