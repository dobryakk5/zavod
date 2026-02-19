from django.db import migrations


FORWARD_SQL = """
ALTER TABLE map.kb_documents
    ADD COLUMN IF NOT EXISTS index_status text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS indexed_at timestamptz,
    ADD COLUMN IF NOT EXISTS index_error text;

CREATE INDEX IF NOT EXISTS idx_kb_documents_index_status
    ON map.kb_documents(index_status);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_kb_documents_index_status'
    ) THEN
        ALTER TABLE map.kb_documents
            ADD CONSTRAINT chk_kb_documents_index_status
            CHECK (index_status IN ('pending', 'indexing', 'indexed', 'skipped', 'failed'));
    END IF;
END $$;

UPDATE map.kb_documents d
SET
    index_status = 'indexed',
    indexed_at = COALESCE(d.indexed_at, d.updated_at),
    index_error = NULL
WHERE EXISTS (
    SELECT 1 FROM map.kb_chunks c WHERE c.document_id = d.id
)
  AND d.index_status = 'pending';
"""


REVERSE_SQL = """
ALTER TABLE map.kb_documents
    DROP CONSTRAINT IF EXISTS chk_kb_documents_index_status;

DROP INDEX IF EXISTS idx_kb_documents_index_status;

ALTER TABLE map.kb_documents
    DROP COLUMN IF EXISTS index_error,
    DROP COLUMN IF EXISTS indexed_at,
    DROP COLUMN IF EXISTS index_status;
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
        ("core", "0160_user_tenant_binding_provider"),
    ]

    operations = [
        migrations.RunPython(_apply_schema, reverse_code=_revert_schema),
    ]
