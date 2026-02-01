from django.db import migrations


MAP_CRM_EVENT_NOTIFICATIONS_SQL = """
-- Ensure schema exists (already created by 0061_map_schema, but keep idempotent)
create schema if not exists map;

create table if not exists map.crm_event_notifications (
    id bigserial primary key,
    event_id bigint not null,
    telegram_chat_id bigint not null,
    reminder_type text not null,
    sent_at timestamptz not null default now()
);

create unique index if not exists idx_crm_event_notifications_unique
    on map.crm_event_notifications(event_id, telegram_chat_id, reminder_type);

create index if not exists idx_crm_event_notifications_event
    on map.crm_event_notifications(event_id);

create index if not exists idx_crm_event_notifications_chat
    on map.crm_event_notifications(telegram_chat_id);

create index if not exists idx_crm_event_notifications_sent
    on map.crm_event_notifications(sent_at);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0132_map_user_tenant_binding"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_CRM_EVENT_NOTIFICATIONS_SQL, reverse_sql=""),
    ]
