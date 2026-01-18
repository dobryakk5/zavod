from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_rename_core_weekly_source_idx_core_weekly_client__84fb5e_idx"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS core_weeklysourcebatch (
                id BIGSERIAL PRIMARY KEY,
                week_start DATE NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                client_id BIGINT NOT NULL REFERENCES core_client(id)
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS core_weeklysourcebatch CASCADE;
            """,
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE core_weeklysourcereport
            ADD COLUMN IF NOT EXISTS batch_id BIGINT;

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'core_weeklysourcereport_batch_id_fkey'
                ) THEN
                    ALTER TABLE core_weeklysourcereport
                    ADD CONSTRAINT core_weeklysourcereport_batch_id_fkey
                    FOREIGN KEY (batch_id)
                    REFERENCES core_weeklysourcebatch(id)
                    DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE core_weeklysourcereport DROP CONSTRAINT IF EXISTS core_weeklysourcereport_batch_id_fkey;
            ALTER TABLE core_weeklysourcereport DROP COLUMN IF EXISTS batch_id;
            """,
        ),
    ]

