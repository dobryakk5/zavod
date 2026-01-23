-- =========================================
-- Schema
-- =========================================
create schema if not exists map;

-- =========================================
-- Session helpers
-- =========================================
create or replace function map.current_client_id()
returns bigint as $$
declare
    raw_id text;
begin
    raw_id = current_setting('app.current_client_id', true);
    if raw_id is null or raw_id = '' then
        raise exception 'app.current_client_id is not set for this session';
    end if;

    return raw_id::bigint;
end;
$$ language plpgsql stable;

-- =========================================
-- Mind maps
-- =========================================
create table if not exists map.mind_maps (
    id bigserial primary key,

    owner_id bigint not null
        references public.core_client(id)
        on delete cascade,

    title text not null,
    description text,
    is_public boolean not null default false,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_mind_maps_owner
    on map.mind_maps(owner_id);

-- =========================================
-- Map members (multi-user access)
-- =========================================
create table if not exists map.mind_map_members (
    map_id bigint not null
        references map.mind_maps(id)
        on delete cascade,

    user_id bigint not null
        references auth_user(id)
        on delete cascade,

    role text not null
        check (role in ('owner', 'editor', 'viewer')),

    primary key (map_id, user_id)
);

create index if not exists idx_mind_map_members_user
    on map.mind_map_members(user_id);

-- =========================================
-- Nodes (UUID — client generated)
-- =========================================
create table if not exists map.mind_nodes (
    id uuid primary key,

    map_id bigint not null
        references map.mind_maps(id)
        on delete cascade,

    text text not null,
    color text,
    shape text default 'rect',
    meta jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_mind_nodes_map
    on map.mind_nodes(map_id);

create index if not exists idx_mind_nodes_meta
    on map.mind_nodes using gin(meta);

-- =========================================
-- Edges (server generated)
-- =========================================
create table if not exists map.mind_edges (
    id bigserial primary key,

    map_id bigint not null
        references map.mind_maps(id)
        on delete cascade,

    from_node_id uuid not null
        references map.mind_nodes(id)
        on delete cascade,

    to_node_id uuid not null
        references map.mind_nodes(id)
        on delete cascade,

    type text not null default 'default',
    label text,
    meta jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    constraint chk_no_self_edge
        check (from_node_id <> to_node_id)
);

create index if not exists idx_mind_edges_map
    on map.mind_edges(map_id);

create index if not exists idx_mind_edges_from
    on map.mind_edges(from_node_id);

create index if not exists idx_mind_edges_to
    on map.mind_edges(to_node_id);

-- =========================================
-- Node positions (layout)
-- =========================================
create table if not exists map.mind_node_positions (
    node_id uuid not null
        references map.mind_nodes(id)
        on delete cascade,

    layout_name text not null default 'default',

    x double precision not null,
    y double precision not null,

    primary key (node_id),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_mind_node_positions_layout
    on map.mind_node_positions(layout_name);

-- =========================================
-- Node properties (key/value) for rich cards
-- =========================================
create table if not exists map.mind_node_properties (
    id bigserial primary key,

    node_id uuid not null
        references map.mind_nodes(id)
        on delete cascade,

    title text not null,       -- e.g. "Past 7 days"
    value text not null,       -- e.g. "4.41K mins"
    delta text,                -- e.g. "0.43% ↑"
    order_index int not null default 0,
    meta jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_mind_node_properties_node
    on map.mind_node_properties(node_id);

-- =========================================
-- Telegram tasks
-- =========================================
create table if not exists map.telegram_tasks (
    id bigserial primary key,

    client_id bigint not null
        references public.core_client(id)
        on delete cascade,

    tg_name text not null,
    telegram_user_id bigint not null,
    telegram_message_id bigint,
    message_text text not null,

    received_at timestamptz not null default now()
);

create index if not exists idx_telegram_tasks_client_received
    on map.telegram_tasks(client_id, received_at desc);

-- =========================================
-- updated_at trigger
-- =========================================
create or replace function map.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'trg_mind_maps_updated') then
        create trigger trg_mind_maps_updated
        before update on map.mind_maps
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_mind_nodes_updated') then
        create trigger trg_mind_nodes_updated
        before update on map.mind_nodes
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_mind_node_positions_updated') then
        create trigger trg_mind_node_positions_updated
        before update on map.mind_node_positions
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_mind_node_properties_updated') then
        create trigger trg_mind_node_properties_updated
        before update on map.mind_node_properties
        for each row execute function map.set_updated_at();
    end if;
end;
$$;
