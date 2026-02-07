from django.db import migrations


UPDATE_CHAIN_CONSTRAINTS_SQL = """
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
          AND t.relname = 'chain_nodes'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%node_type%'
    LOOP
        EXECUTE format('ALTER TABLE chains.chain_nodes DROP CONSTRAINT IF EXISTS %I', con.conname);
    END LOOP;
END $$;

ALTER TABLE chains.chain_nodes
    ADD CONSTRAINT chain_nodes_node_type_check
    CHECK (node_type in ('start', 'text', 'photo', 'buttons', 'router', 'timer'));
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0142_chains_router_ports"),
    ]

    operations = [
        migrations.RunSQL(sql=UPDATE_CHAIN_CONSTRAINTS_SQL, reverse_sql=""),
    ]
