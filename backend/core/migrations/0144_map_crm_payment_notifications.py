from django.db import migrations


MAP_CRM_PAYMENT_NOTIFICATIONS_SQL = """
-- Ensure schema exists (already created by 0061_map_schema, but keep idempotent)
create schema if not exists map;

create table if not exists map.crm_payment_notifications (
    id bigserial primary key,
    payment_id bigint not null,
    telegram_chat_id bigint not null,
    reminder_type text not null,
    sent_at timestamptz not null default now()
);

create unique index if not exists idx_crm_payment_notifications_unique
    on map.crm_payment_notifications(payment_id, telegram_chat_id, reminder_type);

create index if not exists idx_crm_payment_notifications_payment
    on map.crm_payment_notifications(payment_id);

create index if not exists idx_crm_payment_notifications_chat
    on map.crm_payment_notifications(telegram_chat_id);

create index if not exists idx_crm_payment_notifications_sent
    on map.crm_payment_notifications(sent_at);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0143_chains_start_node"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_CRM_PAYMENT_NOTIFICATIONS_SQL, reverse_sql=""),
    ]

