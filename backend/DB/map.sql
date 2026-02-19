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
-- CRM tasks
-- =========================================
create table if not exists map.crm_tasks (
    id serial primary key,
    level_id integer references map.crm_level(id) on delete set null,
    title text not null,
    description text,
    status varchar(20) not null default 'open',
    priority integer not null default 2,
    created_by integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_crm_tasks_level_id
    on map.crm_tasks(level_id);

create index if not exists idx_crm_tasks_status
    on map.crm_tasks(status);

create table if not exists map.crm_task_history (
    id serial primary key,
    task_id integer not null references map.crm_tasks(id) on delete cascade,
    note text not null,
    status varchar(20),
    created_by integer not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists idx_crm_task_history_task_id
    on map.crm_task_history(task_id);

-- =========================================
-- User-tenant bindings
-- =========================================
create table if not exists map.user_tenant_binding (
    id bigserial primary key,

    tenant_id bigint not null
        references public.core_client(id)
        on delete cascade,

    provider varchar(16) not null default 'telegram',
    provider_user_id varchar(255) not null,
    telegram_chat_id bigint,
    contact_id integer references map.contacts(id) on delete set null,
    bound_at timestamptz not null default now(),
    is_active boolean not null default true
);

create unique index if not exists idx_user_tenant_binding_unique
    on map.user_tenant_binding(provider, provider_user_id, tenant_id);

create index if not exists idx_user_tenant_binding_user_active
    on map.user_tenant_binding(provider, provider_user_id, is_active);

create index if not exists idx_user_tenant_binding_user_bound
    on map.user_tenant_binding(provider, provider_user_id, bound_at desc);

create index if not exists idx_user_tenant_binding_telegram_chat
    on map.user_tenant_binding(telegram_chat_id);

create index if not exists idx_user_tenant_binding_tenant
    on map.user_tenant_binding(tenant_id);

create index if not exists idx_user_tenant_binding_contact
    on map.user_tenant_binding(contact_id);

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

    if not exists (select 1 from pg_trigger where tgname = 'trg_crm_tasks_updated') then
        create trigger trg_crm_tasks_updated
        before update on map.crm_tasks
        for each row execute function map.set_updated_at();
    end if;
end;
$$;

-- =========================================
-- Knowledge base
-- =========================================
create table if not exists map.kb_folders (
    id bigserial primary key,
    workspace_id bigint not null references public.core_client(id) on delete cascade,
    name text not null,
    parent_id bigint references map.kb_folders(id) on delete set null,
    created_by_id bigint references auth_user(id) on delete set null,
    position int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_kb_folders_workspace on map.kb_folders(workspace_id);
create index if not exists idx_kb_folders_parent on map.kb_folders(parent_id);
create index if not exists idx_kb_folders_position on map.kb_folders(position);

create table if not exists map.kb_documents (
    id bigserial primary key,
    workspace_id bigint not null references public.core_client(id) on delete cascade,
    folder_id bigint references map.kb_folders(id) on delete set null,
    parent_document_id bigint references map.kb_documents(id) on delete set null,
    title text not null,
    icon text,
    cover_image text,
    content jsonb not null default '{}'::jsonb,
    created_by_id bigint references auth_user(id) on delete set null,
    last_edited_by_id bigint references auth_user(id) on delete set null,
    is_published boolean not null default false,
    is_archived boolean not null default false,
    is_template boolean not null default false,
    index_status text not null default 'pending'
        check (index_status in ('pending', 'indexing', 'indexed', 'skipped', 'failed')),
    indexed_at timestamptz,
    index_error text,
    position int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_kb_documents_workspace on map.kb_documents(workspace_id);
create index if not exists idx_kb_documents_folder on map.kb_documents(folder_id);
create index if not exists idx_kb_documents_parent on map.kb_documents(parent_document_id);
create index if not exists idx_kb_documents_updated on map.kb_documents(updated_at);
create index if not exists idx_kb_documents_archived on map.kb_documents(is_archived);
create index if not exists idx_kb_documents_index_status on map.kb_documents(index_status);

create table if not exists map.kb_document_versions (
    id bigserial primary key,
    document_id bigint not null references map.kb_documents(id) on delete cascade,
    title text,
    content jsonb not null default '{}'::jsonb,
    created_by_id bigint references auth_user(id) on delete set null,
    created_at timestamptz not null default now(),
    version_number int not null default 1
);

create unique index if not exists idx_kb_document_versions_unique
    on map.kb_document_versions(document_id, version_number);
create index if not exists idx_kb_document_versions_document
    on map.kb_document_versions(document_id);

create table if not exists map.kb_comments (
    id bigserial primary key,
    document_id bigint not null references map.kb_documents(id) on delete cascade,
    parent_comment_id bigint references map.kb_comments(id) on delete cascade,
    content text not null,
    block_id text,
    created_by_id bigint references auth_user(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    is_resolved boolean not null default false
);

create index if not exists idx_kb_comments_document on map.kb_comments(document_id);
create index if not exists idx_kb_comments_parent on map.kb_comments(parent_comment_id);
create index if not exists idx_kb_comments_resolved on map.kb_comments(is_resolved);

create table if not exists map.kb_tags (
    id bigserial primary key,
    workspace_id bigint not null references public.core_client(id) on delete cascade,
    name text not null,
    color text,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_kb_tags_workspace_name
    on map.kb_tags(workspace_id, name);

create table if not exists map.kb_document_tags (
    id bigserial primary key,
    document_id bigint not null references map.kb_documents(id) on delete cascade,
    tag_id bigint not null references map.kb_tags(id) on delete cascade,
    created_at timestamptz not null default now()
);

create unique index if not exists idx_kb_document_tags_unique
    on map.kb_document_tags(document_id, tag_id);
create index if not exists idx_kb_document_tags_document
    on map.kb_document_tags(document_id);
create index if not exists idx_kb_document_tags_tag
    on map.kb_document_tags(tag_id);

create table if not exists map.kb_shares (
    id bigserial primary key,
    document_id bigint not null references map.kb_documents(id) on delete cascade,
    share_token text not null,
    permission text not null default 'view',
    password text,
    expires_at timestamptz,
    created_by_id bigint references auth_user(id) on delete set null,
    created_at timestamptz not null default now(),
    is_active boolean not null default true,
    visit_count int not null default 0,
    constraint chk_kb_shares_permission check (permission in ('view', 'comment', 'edit'))
);

create unique index if not exists idx_kb_shares_token on map.kb_shares(share_token);
create index if not exists idx_kb_shares_document on map.kb_shares(document_id);
create index if not exists idx_kb_shares_active on map.kb_shares(is_active);

create extension if not exists vector;
create extension if not exists pg_trgm;

create table if not exists map.kb_chunks (
    id bigserial primary key,
    document_id bigint not null references map.kb_documents(id) on delete cascade,
    workspace_id bigint not null references public.core_client(id) on delete cascade,
    chunk_index int not null,
    chunk_type text not null default 'text',
    content text not null,
    context text,
    content_vector vector(384),
    embedding_model text not null,
    ts_content tsvector,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_kb_chunks_type check (chunk_type in ('text', 'table', 'formula', 'code'))
);

create unique index if not exists idx_kb_chunks_doc_chunk on map.kb_chunks(document_id, chunk_index);
create index if not exists idx_kb_chunks_workspace on map.kb_chunks(workspace_id);
create index if not exists idx_kb_chunks_document on map.kb_chunks(document_id);
create index if not exists idx_kb_chunks_vector
    on map.kb_chunks
    using hnsw (content_vector vector_cosine_ops)
    with (m = 16, ef_construction = 64);
create index if not exists idx_kb_chunks_ts on map.kb_chunks using gin(ts_content);

create or replace function map.kb_chunks_update_ts_content() returns trigger as $$
begin
    new.ts_content := to_tsvector('russian', coalesce(new.content, '') || ' ' || coalesce(new.context, ''));
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_kb_chunks_ts_content on map.kb_chunks;
create trigger trg_kb_chunks_ts_content
    before insert or update on map.kb_chunks
    for each row execute function map.kb_chunks_update_ts_content();

do $$
begin
    if not exists (select 1 from pg_trigger where tgname = 'trg_kb_folders_updated') then
        create trigger trg_kb_folders_updated
        before update on map.kb_folders
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_kb_documents_updated') then
        create trigger trg_kb_documents_updated
        before update on map.kb_documents
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_kb_comments_updated') then
        create trigger trg_kb_comments_updated
        before update on map.kb_comments
        for each row execute function map.set_updated_at();
    end if;

    if not exists (select 1 from pg_trigger where tgname = 'trg_kb_chunks_updated') then
        create trigger trg_kb_chunks_updated
        before update on map.kb_chunks
        for each row execute function map.set_updated_at();
    end if;
end;
$$;
