from django.db import migrations


FORWARD_SQL = """
ALTER TABLE map.product_course_lessons
    DROP COLUMN IF EXISTS video_provider;
"""


REVERSE_SQL = """
ALTER TABLE map.product_course_lessons
    ADD COLUMN IF NOT EXISTS video_provider TEXT
    CHECK (video_provider IN ('youtube', 'rutube', 'vk') OR video_provider IS NULL);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0189_drop_product_course_events_payload"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
