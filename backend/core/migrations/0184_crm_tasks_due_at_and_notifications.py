from django.db import migrations


MAP_CRM_TASKS_DUE_AT_AND_NOTIFICATIONS_SQL = """
create schema if not exists map;

alter table map.crm_tasks
    add column if not exists due_at timestamptz;

create index if not exists idx_crm_tasks_due_at
    on map.crm_tasks(due_at)
    where due_at is not null;

create table if not exists map.crm_task_notifications (
    id bigserial primary key,
    task_id bigint not null references map.crm_tasks(id) on delete cascade,
    telegram_chat_id bigint not null,
    reminder_type text not null,
    due_at timestamptz not null,
    sent_at timestamptz not null default now()
);

create unique index if not exists idx_crm_task_notifications_unique
    on map.crm_task_notifications(task_id, telegram_chat_id, reminder_type, due_at);

create index if not exists idx_crm_task_notifications_task
    on map.crm_task_notifications(task_id);

create index if not exists idx_crm_task_notifications_chat
    on map.crm_task_notifications(telegram_chat_id);

create index if not exists idx_crm_task_notifications_sent
    on map.crm_task_notifications(sent_at);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0183_merge_20260306_0001"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_CRM_TASKS_DUE_AT_AND_NOTIFICATIONS_SQL, reverse_sql=""),
    ]

