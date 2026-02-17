from django.db import migrations


CRM_TASKS_SQL = """
create schema if not exists map;

drop table if exists map.telegram_tasks;

create table if not exists map.crm_tasks (
  id          serial primary key,
  level_id    integer references map.crm_level(id) on delete set null,
  title       text not null,
  description text,
  status      varchar(20) not null default 'open',
  created_by  integer not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create table if not exists map.crm_task_history (
  id          serial primary key,
  task_id     integer not null references map.crm_tasks(id) on delete cascade,
  note        text not null,
  status      varchar(20),
  created_by  integer not null default 0,
  created_at  timestamptz not null default now()
);

create index if not exists idx_crm_tasks_level_id
  on map.crm_tasks(level_id);

create index if not exists idx_crm_tasks_status
  on map.crm_tasks(status);

create index if not exists idx_crm_task_history_task_id
  on map.crm_task_history(task_id);

create or replace function map.set_crm_tasks_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'trg_crm_tasks_updated') then
        create trigger trg_crm_tasks_updated
        before update on map.crm_tasks
        for each row execute function map.set_crm_tasks_updated_at();
    end if;
end;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0154_map_contacts_source"),
    ]

    operations = [
        migrations.RunSQL(sql=CRM_TASKS_SQL, reverse_sql=""),
    ]
