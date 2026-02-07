from django.db import migrations


UPDATE_EDGES_SQL = """
ALTER TABLE chains.chain_edges
    ADD COLUMN IF NOT EXISTS source_port_id varchar(64);

DO $$
DECLARE
    con record;
BEGIN
    FOR con IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'chain_edges'
          AND c.contype = 'u'
          AND pg_get_constraintdef(c.oid) ILIKE '%source_node_id%'
          AND pg_get_constraintdef(c.oid) ILIKE '%target_node_id%'
    LOOP
        EXECUTE format('ALTER TABLE chains.chain_edges DROP CONSTRAINT IF EXISTS %I', con.conname);
    END LOOP;
END $$;

ALTER TABLE chains.chain_edges
    ADD CONSTRAINT chain_edges_source_port_unique
    UNIQUE (source_node_id, source_port_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0141_chains_router_node"),
    ]

    operations = [
        migrations.RunSQL(sql=UPDATE_EDGES_SQL, reverse_sql=""),
    ]
