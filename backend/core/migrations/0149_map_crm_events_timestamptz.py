from django.db import migrations


MAP_CRM_EVENTS_TO_TIMESTAMPTZ_SQL = """
create schema if not exists map;

alter table if exists map.crm_events
    alter column start_time type timestamptz using start_time at time zone 'UTC',
    alter column end_time type timestamptz using end_time at time zone 'UTC',
    alter column created_at type timestamptz using created_at at time zone 'UTC',
    alter column updated_at type timestamptz using updated_at at time zone 'UTC';
"""


MAP_CRM_EVENTS_TO_TIMESTAMP_SQL = """
create schema if not exists map;

alter table if exists map.crm_events
    alter column start_time type timestamp using start_time at time zone 'UTC',
    alter column end_time type timestamp using end_time at time zone 'UTC',
    alter column created_at type timestamp using created_at at time zone 'UTC',
    alter column updated_at type timestamp using updated_at at time zone 'UTC';
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0148_map_events_price_and_payment_event_link"),
    ]

    operations = [
        migrations.RunSQL(
            sql=MAP_CRM_EVENTS_TO_TIMESTAMPTZ_SQL,
            reverse_sql=MAP_CRM_EVENTS_TO_TIMESTAMP_SQL,
        ),
    ]
