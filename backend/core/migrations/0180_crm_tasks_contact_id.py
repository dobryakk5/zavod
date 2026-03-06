from django.db import migrations


SQL = """
ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS contact_id integer;

CREATE INDEX IF NOT EXISTS idx_crm_tasks_contact_id
  ON map.crm_tasks(contact_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'crm_tasks_contact_id_fkey'
          AND conrelid = 'map.crm_tasks'::regclass
    ) THEN
        ALTER TABLE map.crm_tasks
            ADD CONSTRAINT crm_tasks_contact_id_fkey
            FOREIGN KEY (contact_id) REFERENCES map.contacts(id) ON DELETE SET NULL;
    END IF;
END;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0179_quiz_answers_contact_based"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]
