from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0155_crm_tasks_tables"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE map.crm_tasks
                ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 2;
            """,
            reverse_sql="""
            ALTER TABLE map.crm_tasks
                DROP COLUMN IF EXISTS priority;
            """,
        ),
    ]
