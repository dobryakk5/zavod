from django.db import migrations


MAP_USER_TENANT_BINDING_SQL = """
-- Ensure schema exists (already created by 0061_map_schema, but keep idempotent)
create schema if not exists map;

create table if not exists map.user_tenant_binding (
    id bigserial primary key,
    tenant_id bigint not null references public.core_client(id) on delete cascade,
    telegram_chat_id bigint not null,
    contact_id integer references map.contacts(id) on delete set null,
    bound_at timestamptz not null default now(),
    is_active boolean not null default true
);

create unique index if not exists idx_user_tenant_binding_unique
    on map.user_tenant_binding(telegram_chat_id, tenant_id);

create index if not exists idx_user_tenant_binding_user_active
    on map.user_tenant_binding(telegram_chat_id, is_active);

create index if not exists idx_user_tenant_binding_user_bound
    on map.user_tenant_binding(telegram_chat_id, bound_at desc);

create index if not exists idx_user_tenant_binding_tenant
    on map.user_tenant_binding(tenant_id);

create index if not exists idx_user_tenant_binding_contact
    on map.user_tenant_binding(contact_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0131_merge_20260128_2057"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_USER_TENANT_BINDING_SQL, reverse_sql=""),
    ]
