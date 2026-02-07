from django.db import migrations


MAP_KB_SCHEMA_SQL = """
-- Ensure schema exists
create schema if not exists map;

-- Folders
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

-- Documents
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
    position int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_kb_documents_workspace on map.kb_documents(workspace_id);
create index if not exists idx_kb_documents_folder on map.kb_documents(folder_id);
create index if not exists idx_kb_documents_parent on map.kb_documents(parent_document_id);
create index if not exists idx_kb_documents_updated on map.kb_documents(updated_at);
create index if not exists idx_kb_documents_archived on map.kb_documents(is_archived);

-- Document versions
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

-- Comments
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

-- Tags
create table if not exists map.kb_tags (
    id bigserial primary key,
    workspace_id bigint not null references public.core_client(id) on delete cascade,
    name text not null,
    color text,
    created_at timestamptz not null default now()
);
create unique index if not exists idx_kb_tags_workspace_name
    on map.kb_tags(workspace_id, name);

-- Document tags
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

-- Shares
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

-- updated_at triggers
-- map.set_updated_at() defined in 0061_map_schema

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
end $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0139_chains_schema"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_KB_SCHEMA_SQL, reverse_sql=""),
    ]
