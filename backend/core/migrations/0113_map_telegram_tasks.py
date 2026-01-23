from django.db import migrations


MAP_TELEGRAM_TASKS_SQL = """
-- Ensure schema exists (already created by 0061_map_schema, but keep idempotent)
create schema if not exists map;

create table if not exists map.telegram_tasks (
    id bigserial primary key,
    client_id bigint not null references public.core_client(id) on delete cascade,
    tg_name text not null,
    telegram_user_id bigint not null,
    telegram_message_id bigint,
    message_text text not null,
    received_at timestamptz not null default now()
);

create index if not exists idx_telegram_tasks_client_received
    on map.telegram_tasks(client_id, received_at desc);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0112_project_semantic_set"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_TELEGRAM_TASKS_SQL, reverse_sql=""),
    ]
