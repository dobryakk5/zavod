from django.db import migrations


FORWARD_SQL = """
ALTER TABLE map.product_course_events
    DROP COLUMN IF EXISTS payload;
"""


REVERSE_SQL = """
ALTER TABLE map.product_course_events
    ADD COLUMN IF NOT EXISTS payload JSONB NOT NULL DEFAULT '{}'::jsonb;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0188_product_course_events_comments"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
