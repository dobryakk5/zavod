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
    CHECK (node_type in ('text', 'photo', 'buttons', 'router', 'timer'));

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
          AND t.relname = 'chain_conditions'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%condition_type%'
    LOOP
        EXECUTE format('ALTER TABLE chains.chain_conditions DROP CONSTRAINT IF EXISTS %I', con.conname);
    END LOOP;
END $$;

ALTER TABLE chains.chain_conditions
    ADD CONSTRAINT chain_conditions_condition_type_check
    CHECK (condition_type in (
        'button_press',
        'text_contains',
        'text_regex',
        'timeout',
        'any_reply',
        'content_type',
        'has_media',
        'text_equals',
        'has_entities'
    ));
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0140_map_kb_schema"),
    ]

    operations = [
        migrations.RunSQL(sql=UPDATE_CHAIN_CONSTRAINTS_SQL, reverse_sql=""),
    ]
