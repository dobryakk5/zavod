from django.db import migrations


CHAIN_SCHEMA_SQL = """
-- Ensure schema exists
create schema if not exists chains;

-- updated_at trigger function
create or replace function chains.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

-- Chains
create table if not exists chains.chains (
    id bigserial primary key,
    tenant_id bigint not null references public.core_client(id) on delete cascade,
    name varchar(255) not null,
    description text,
    status varchar(20) not null default 'draft'
        check (status in ('draft', 'active', 'paused', 'archived')),
    start_node_id bigint,
    created_at timestamp not null default now(),
    updated_at timestamp not null default now()
);

create unique index if not exists uniq_chains_tenant on chains.chains(tenant_id);
create index if not exists idx_chains_chains_tenant on chains.chains(tenant_id);
create index if not exists idx_chains_chains_status on chains.chains(tenant_id, status);

-- Chain nodes
create table if not exists chains.chain_nodes (
    id bigserial primary key,
    chain_id bigint not null references chains.chains(id) on delete cascade,
    node_type varchar(20) not null default 'text'
        check (node_type in ('text', 'photo', 'buttons')),
    payload jsonb not null,
    delay_seconds integer not null default 0 check (delay_seconds >= 0),
    pos_x float not null default 0,
    pos_y float not null default 0,
    created_at timestamp not null default now(),
    updated_at timestamp not null default now()
);

create index if not exists idx_chains_nodes_chain on chains.chain_nodes(chain_id);

-- Chain edges
create table if not exists chains.chain_edges (
    id bigserial primary key,
    chain_id bigint not null references chains.chains(id) on delete cascade,
    source_node_id bigint not null references chains.chain_nodes(id) on delete cascade,
    target_node_id bigint not null references chains.chain_nodes(id) on delete cascade,
    priority integer not null default 0,
    created_at timestamp not null default now(),
    updated_at timestamp not null default now(),
    unique (source_node_id, target_node_id)
);

create index if not exists idx_chains_edges_chain on chains.chain_edges(chain_id);
create index if not exists idx_chains_edges_source on chains.chain_edges(source_node_id, priority);
create index if not exists idx_chains_edges_target on chains.chain_edges(target_node_id);

-- Chain conditions
create table if not exists chains.chain_conditions (
    id bigserial primary key,
    edge_id bigint not null references chains.chain_edges(id) on delete cascade,
    condition_type varchar(30) not null
        check (condition_type in ('button_press', 'text_contains', 'text_regex', 'timeout', 'any_reply')),
    params jsonb not null default '{}'::jsonb,
    created_at timestamp not null default now()
);

create index if not exists idx_chains_conditions_edge on chains.chain_conditions(edge_id);
create index if not exists idx_chains_conditions_type on chains.chain_conditions(edge_id, condition_type);

-- FK for start node (after nodes exist)
alter table chains.chains
    add constraint fk_chains_start_node
    foreign key (start_node_id) references chains.chain_nodes(id) on delete set null;

-- Chain sessions
create table if not exists chains.chain_sessions (
    id bigserial primary key,
    user_id bigint not null,
    tenant_id bigint not null references public.core_client(id) on delete cascade,
    chain_id bigint not null references chains.chains(id) on delete cascade,
    current_node_id bigint references chains.chain_nodes(id) on delete set null,
    status varchar(20) not null default 'active'
        check (status in ('active', 'completed', 'paused', 'failed')),
    context jsonb not null default '{}'::jsonb,
    started_at timestamp not null default now(),
    last_activity_at timestamp not null default now(),
    completed_at timestamp,
    created_at timestamp not null default now(),
    updated_at timestamp not null default now()
);

create unique index if not exists uniq_chain_sessions_active
    on chains.chain_sessions(user_id, chain_id)
    where status = 'active';

create index if not exists idx_chains_sessions_user_status on chains.chain_sessions(user_id, status);
create index if not exists idx_chains_sessions_tenant on chains.chain_sessions(tenant_id, status);
create index if not exists idx_chains_sessions_chain on chains.chain_sessions(chain_id, status);
create index if not exists idx_chains_sessions_last_activity
    on chains.chain_sessions(last_activity_at)
    where status = 'active';

-- updated_at triggers
do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'trg_chains_chains_updated') then
        create trigger trg_chains_chains_updated
        before update on chains.chains
        for each row execute function chains.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_chains_chain_nodes_updated') then
        create trigger trg_chains_chain_nodes_updated
        before update on chains.chain_nodes
        for each row execute function chains.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_chains_chain_edges_updated') then
        create trigger trg_chains_chain_edges_updated
        before update on chains.chain_edges
        for each row execute function chains.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_chains_chain_sessions_updated') then
        create trigger trg_chains_chain_sessions_updated
        before update on chains.chain_sessions
        for each row execute function chains.set_updated_at();
    end if;
end;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0138_article_blueprint_prompts"),
    ]

    operations = [
        migrations.RunSQL(sql=CHAIN_SCHEMA_SQL, reverse_sql=""),
    ]
