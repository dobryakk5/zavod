from django.db import migrations


MAP_PRODUCTS_SQL = """
-- Ensure schema exists (already created by 0061_map_schema, but keep idempotent)
create schema if not exists map;

-- Product types
create table if not exists map.product_types (
    id bigserial primary key,
    owner_id bigint not null references public.core_client(id) on delete cascade,
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_product_types_owner on map.product_types(owner_id);

-- Products
create table if not exists map.products (
    id bigserial primary key,
    owner_id bigint not null references public.core_client(id) on delete cascade,
    name text not null,
    product_type_id bigint references map.product_types(id) on delete set null,
    short_description text,
    packages jsonb not null default '[]'::jsonb,
    structure jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_products_owner on map.products(owner_id);
create index if not exists idx_products_type on map.products(product_type_id);

-- updated_at triggers (function map.set_updated_at() is defined in 0061_map_schema)
do $$
begin
    if exists (select 1 from pg_proc where proname = 'set_updated_at' and pronamespace = 'map'::regnamespace) then
        if not exists (select 1 from pg_trigger where tgname = 'trg_product_types_updated') then
            create trigger trg_product_types_updated
            before update on map.product_types
            for each row execute function map.set_updated_at();
        end if;

        if not exists (select 1 from pg_trigger where tgname = 'trg_products_updated') then
            create trigger trg_products_updated
            before update on map.products
            for each row execute function map.set_updated_at();
        end if;
    end if;
end;
$$;

-- Data migration (best-effort): copy legacy core_clientproduct into map.products
do $$
begin
    if to_regclass('public.core_clientproduct') is not null then
        insert into map.products (id, owner_id, name, short_description, packages, structure, created_at, updated_at)
        select
            p.id,
            p.owner_id,
            p.product_type as name,
            p.short_description,
            coalesce(p.packages::jsonb, '[]'::jsonb),
            coalesce(p.structure::jsonb, '{}'::jsonb),
            p.created_at,
            p.updated_at
        from public.core_clientproduct p
        where not exists (select 1 from map.products mp where mp.id = p.id);
    end if;
exception when undefined_column then
    -- Older schema may have different column names; ignore.
    null;
end;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0064_client_product_structure"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_PRODUCTS_SQL, reverse_sql=""),
    ]

