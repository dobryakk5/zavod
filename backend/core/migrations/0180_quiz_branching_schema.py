from django.db import migrations


FORWARD_SQL = """
ALTER TABLE chains.quiz_screens
    ADD COLUMN IF NOT EXISTS is_default_result BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE chains.quiz_options
    ADD COLUMN IF NOT EXISTS next_screen_id BIGINT,
    ADD COLUMN IF NOT EXISTS next_special VARCHAR(16);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_options'
          AND c.conname = 'quiz_options_next_screen_id_fkey'
    ) THEN
        ALTER TABLE chains.quiz_options
            ADD CONSTRAINT quiz_options_next_screen_id_fkey
            FOREIGN KEY (next_screen_id) REFERENCES chains.quiz_screens(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_options'
          AND c.conname = 'quiz_options_next_special_check'
    ) THEN
        ALTER TABLE chains.quiz_options
            ADD CONSTRAINT quiz_options_next_special_check
            CHECK (next_special IS NULL OR next_special IN ('__lead', '__end'));
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'chains'
          AND t.relname = 'quiz_options'
          AND c.conname = 'quiz_options_next_target_check'
    ) THEN
        ALTER TABLE chains.quiz_options
            ADD CONSTRAINT quiz_options_next_target_check
            CHECK (next_screen_id IS NULL OR next_special IS NULL);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS chains.quiz_result_rules (
    id          BIGSERIAL PRIMARY KEY,
    screen_id   BIGINT      NOT NULL REFERENCES chains.quiz_screens(id) ON DELETE CASCADE,
    position    SMALLINT    NOT NULL CHECK (position >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (screen_id, position)
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_result_rules_screen_pos
    ON chains.quiz_result_rules(screen_id, position);

CREATE TABLE IF NOT EXISTS chains.quiz_result_conditions (
    id          BIGSERIAL PRIMARY KEY,
    rule_id     BIGINT      NOT NULL REFERENCES chains.quiz_result_rules(id) ON DELETE CASCADE,
    screen_id   BIGINT      NOT NULL REFERENCES chains.quiz_screens(id) ON DELETE CASCADE,
    operator    VARCHAR(16) NOT NULL
               CHECK (operator IN ('includes', 'not_includes', 'gte', 'lte', 'equals')),
    value       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    position    SMALLINT    NOT NULL DEFAULT 0 CHECK (position >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (rule_id, position)
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_result_conditions_rule_pos
    ON chains.quiz_result_conditions(rule_id, position);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_result_conditions_screen
    ON chains.quiz_result_conditions(screen_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_quiz_result_rules_updated') THEN
        CREATE TRIGGER trg_chains_quiz_result_rules_updated
            BEFORE UPDATE ON chains.quiz_result_rules
            FOR EACH ROW
            EXECUTE FUNCTION chains.set_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_quiz_result_conditions_updated') THEN
        CREATE TRIGGER trg_chains_quiz_result_conditions_updated
            BEFORE UPDATE ON chains.quiz_result_conditions
            FOR EACH ROW
            EXECUTE FUNCTION chains.set_updated_at();
    END IF;
END $$;
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_chains_quiz_result_conditions_updated ON chains.quiz_result_conditions;
DROP TRIGGER IF EXISTS trg_chains_quiz_result_rules_updated ON chains.quiz_result_rules;

DROP INDEX IF EXISTS chains.idx_chains_quiz_result_conditions_screen;
DROP INDEX IF EXISTS chains.idx_chains_quiz_result_conditions_rule_pos;
DROP INDEX IF EXISTS chains.idx_chains_quiz_result_rules_screen_pos;

DROP TABLE IF EXISTS chains.quiz_result_conditions;
DROP TABLE IF EXISTS chains.quiz_result_rules;

ALTER TABLE chains.quiz_options DROP CONSTRAINT IF EXISTS quiz_options_next_target_check;
ALTER TABLE chains.quiz_options DROP CONSTRAINT IF EXISTS quiz_options_next_special_check;
ALTER TABLE chains.quiz_options DROP CONSTRAINT IF EXISTS quiz_options_next_screen_id_fkey;

ALTER TABLE chains.quiz_options
    DROP COLUMN IF EXISTS next_special,
    DROP COLUMN IF EXISTS next_screen_id;

ALTER TABLE chains.quiz_screens
    DROP COLUMN IF EXISTS is_default_result;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0179_quiz_answers_contact_based"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
