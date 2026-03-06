from django.db import migrations


FORWARD_SQL = """
ALTER TABLE chains.quiz_answers
    ADD COLUMN IF NOT EXISTS tenant_id BIGINT,
    ADD COLUMN IF NOT EXISTS quiz_id BIGINT,
    ADD COLUMN IF NOT EXISTS contact_id BIGINT;

DO $$
BEGIN
    IF to_regclass('chains.quiz_leads') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM information_schema.columns
           WHERE table_schema = 'chains'
             AND table_name = 'quiz_answers'
             AND column_name = 'lead_id'
       ) THEN
        UPDATE chains.quiz_answers qa
           SET tenant_id = COALESCE(qa.tenant_id, ql.tenant_id),
               quiz_id = COALESCE(qa.quiz_id, ql.quiz_id),
               contact_id = COALESCE(qa.contact_id, ql.contact_id)
          FROM chains.quiz_leads ql
         WHERE qa.lead_id = ql.id;
    END IF;
END $$;

UPDATE chains.quiz_answers qa
   SET quiz_id = qs.quiz_id
  FROM chains.quiz_screens qs
 WHERE qa.quiz_id IS NULL
   AND qa.screen_id = qs.id;

UPDATE chains.quiz_answers qa
   SET tenant_id = q.tenant_id
  FROM chains.quizzes q
 WHERE qa.tenant_id IS NULL
   AND qa.quiz_id = q.id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_answers'
          AND c.conname = 'quiz_answers_tenant_id_fkey'
    ) THEN
        ALTER TABLE chains.quiz_answers
            ADD CONSTRAINT quiz_answers_tenant_id_fkey
            FOREIGN KEY (tenant_id) REFERENCES public.core_client(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_answers'
          AND c.conname = 'quiz_answers_quiz_id_fkey'
    ) THEN
        ALTER TABLE chains.quiz_answers
            ADD CONSTRAINT quiz_answers_quiz_id_fkey
            FOREIGN KEY (quiz_id) REFERENCES chains.quizzes(id) ON DELETE CASCADE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_answers'
          AND c.conname = 'quiz_answers_contact_id_fkey'
    ) THEN
        ALTER TABLE chains.quiz_answers
            ADD CONSTRAINT quiz_answers_contact_id_fkey
            FOREIGN KEY (contact_id) REFERENCES map.contacts(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_chains_quiz_answers_quiz_date
    ON chains.quiz_answers(quiz_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_answers_contact_tenant
    ON chains.quiz_answers(contact_id, tenant_id);

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
          AND t.relname = 'quiz_answers'
          AND pg_get_constraintdef(c.oid) ILIKE '%lead_id%'
    LOOP
        EXECUTE format('ALTER TABLE chains.quiz_answers DROP CONSTRAINT IF EXISTS %I', con.conname);
    END LOOP;
END $$;

DROP INDEX IF EXISTS chains.idx_chains_quiz_answers_lead;
ALTER TABLE chains.quiz_answers DROP COLUMN IF EXISTS lead_id;

DROP INDEX IF EXISTS chains.idx_chains_quiz_leads_contact_tenant;
DROP INDEX IF EXISTS chains.idx_chains_quiz_leads_quiz_date;
DROP TABLE IF EXISTS chains.quiz_leads;
"""


REVERSE_SQL = """
-- One-way migration: `quiz_leads` table and `lead_id` relation are intentionally removed.
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0178_chains_quiz_builder_schema"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
