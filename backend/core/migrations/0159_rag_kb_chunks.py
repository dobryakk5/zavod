from django.db import migrations


FORWARD_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS map.kb_chunks (
    id bigserial PRIMARY KEY,
    document_id bigint NOT NULL REFERENCES map.kb_documents(id) ON DELETE CASCADE,
    workspace_id bigint NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    chunk_type text NOT NULL DEFAULT 'text',
    content text NOT NULL,
    context text,
    content_vector vector(384),
    embedding_model text NOT NULL,
    ts_content tsvector,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_kb_chunks_type CHECK (chunk_type IN ('text', 'table', 'formula', 'code'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_kb_chunks_doc_chunk
    ON map.kb_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_workspace ON map.kb_chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_document ON map.kb_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_vector
    ON map.kb_chunks
    USING hnsw (content_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_ts ON map.kb_chunks USING GIN(ts_content);

CREATE OR REPLACE FUNCTION map.kb_chunks_update_ts_content() RETURNS trigger AS $$
BEGIN
    NEW.ts_content := to_tsvector('russian', COALESCE(NEW.content, '') || ' ' || COALESCE(NEW.context, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_kb_chunks_ts_content ON map.kb_chunks;
CREATE TRIGGER trg_kb_chunks_ts_content
    BEFORE INSERT OR UPDATE ON map.kb_chunks
    FOR EACH ROW EXECUTE FUNCTION map.kb_chunks_update_ts_content();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'map' AND p.proname = 'set_updated_at'
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_kb_chunks_updated') THEN
            CREATE TRIGGER trg_kb_chunks_updated
                BEFORE UPDATE ON map.kb_chunks
                FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
        END IF;
    END IF;
END $$;
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_kb_chunks_updated ON map.kb_chunks;
DROP TRIGGER IF EXISTS trg_kb_chunks_ts_content ON map.kb_chunks;
DROP FUNCTION IF EXISTS map.kb_chunks_update_ts_content();
DROP TABLE IF EXISTS map.kb_chunks;
"""


def _apply_schema(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(FORWARD_SQL)


def _revert_schema(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0158_client_preferred_channel"),
    ]

    operations = [
        migrations.RunPython(_apply_schema, reverse_code=_revert_schema),
    ]

