from django.db import migrations


SQL = """
ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS source varchar(32);

UPDATE map.crm_tasks
SET source = 'operator'
WHERE source IS NULL OR trim(source) = '';

ALTER TABLE map.crm_tasks
  ALTER COLUMN source SET DEFAULT 'operator';

ALTER TABLE map.crm_tasks
  ALTER COLUMN source SET NOT NULL;

ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS goal_id varchar(128);

ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS is_milestone boolean;

UPDATE map.crm_tasks
SET is_milestone = FALSE
WHERE is_milestone IS NULL;

ALTER TABLE map.crm_tasks
  ALTER COLUMN is_milestone SET DEFAULT FALSE;

ALTER TABLE map.crm_tasks
  ALTER COLUMN is_milestone SET NOT NULL;

ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS milestone_note text;

ALTER TABLE map.crm_tasks
  ADD COLUMN IF NOT EXISTS done_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_crm_tasks_contact_source
  ON map.crm_tasks(contact_id, source);

CREATE INDEX IF NOT EXISTS idx_crm_tasks_source_goal
  ON map.crm_tasks(source, goal_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0198_coach_invite_links"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]
