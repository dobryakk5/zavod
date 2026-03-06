from django.db import migrations


FORWARD_SQL = """
CREATE SCHEMA IF NOT EXISTS chains;

CREATE TABLE IF NOT EXISTS chains.quizzes (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    BIGINT       NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    title        VARCHAR(255) NOT NULL DEFAULT 'Мой квиз',
    accent_color VARCHAR(7)   NOT NULL DEFAULT '#5b5ef4',
    is_published BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chains_quizzes_tenant
    ON chains.quizzes(tenant_id);

CREATE TABLE IF NOT EXISTS chains.quiz_screens (
    id            BIGSERIAL PRIMARY KEY,
    quiz_id        BIGINT        NOT NULL REFERENCES chains.quizzes(id) ON DELETE CASCADE,
    kind           VARCHAR(16)   NOT NULL
                   CHECK (kind IN ('intro', 'question', 'lead', 'result')),
    position       SMALLINT      NOT NULL CHECK (position >= 0),
    title          VARCHAR(500)  NOT NULL DEFAULT '',
    subtitle       VARCHAR(1000) NULL,
    question_type  VARCHAR(16)   NULL
                   CHECK (question_type IS NULL OR question_type IN ('single', 'multiple', 'rating', 'text', 'date', 'slider')),
    placeholder    VARCHAR(255)  NULL,
    min_val        SMALLINT      NULL,
    max_val        SMALLINT      NULL,
    max_rating     SMALLINT      NULL,
    is_required    BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (quiz_id, position)
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_screens_quiz_pos
    ON chains.quiz_screens(quiz_id, position);

CREATE TABLE IF NOT EXISTS chains.quiz_options (
    id          BIGSERIAL PRIMARY KEY,
    screen_id    BIGINT       NOT NULL REFERENCES chains.quiz_screens(id) ON DELETE CASCADE,
    label        VARCHAR(255) NOT NULL DEFAULT '',
    emoji        VARCHAR(32)  NOT NULL DEFAULT '',
    position     SMALLINT     NOT NULL CHECK (position >= 0),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (screen_id, position)
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_options_screen_pos
    ON chains.quiz_options(screen_id, position);

CREATE TABLE IF NOT EXISTS chains.quiz_leads (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     BIGINT       NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    quiz_id       BIGINT       NOT NULL REFERENCES chains.quizzes(id) ON DELETE CASCADE,
    contact_id    BIGINT       NULL REFERENCES map.contacts(id) ON DELETE SET NULL,
    name          VARCHAR(255) NULL,
    phone         VARCHAR(64)  NULL,
    email         VARCHAR(255) NULL,
    utm_source    VARCHAR(255) NULL,
    utm_medium    VARCHAR(255) NULL,
    utm_campaign  VARCHAR(255) NULL,
    ip            INET         NULL,
    user_agent    TEXT         NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_leads_quiz_date
    ON chains.quiz_leads(quiz_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_leads_contact_tenant
    ON chains.quiz_leads(contact_id, tenant_id);

CREATE TABLE IF NOT EXISTS chains.quiz_answers (
    id            BIGSERIAL PRIMARY KEY,
    lead_id       BIGINT      NOT NULL REFERENCES chains.quiz_leads(id) ON DELETE CASCADE,
    screen_id     BIGINT      NULL REFERENCES chains.quiz_screens(id) ON DELETE SET NULL,
    value_text    TEXT        NULL,
    value_number  SMALLINT    NULL,
    value_options BIGINT[]    NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_answers_lead
    ON chains.quiz_answers(lead_id);

CREATE INDEX IF NOT EXISTS idx_chains_quiz_answers_screen
    ON chains.quiz_answers(screen_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_quizzes_updated') THEN
        CREATE TRIGGER trg_chains_quizzes_updated
            BEFORE UPDATE ON chains.quizzes
            FOR EACH ROW
            EXECUTE FUNCTION chains.set_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_quiz_screens_updated') THEN
        CREATE TRIGGER trg_chains_quiz_screens_updated
            BEFORE UPDATE ON chains.quiz_screens
            FOR EACH ROW
            EXECUTE FUNCTION chains.set_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_chains_quiz_options_updated') THEN
        CREATE TRIGGER trg_chains_quiz_options_updated
            BEFORE UPDATE ON chains.quiz_options
            FOR EACH ROW
            EXECUTE FUNCTION chains.set_updated_at();
    END IF;
END $$;
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_chains_quiz_options_updated ON chains.quiz_options;
DROP TRIGGER IF EXISTS trg_chains_quiz_screens_updated ON chains.quiz_screens;
DROP TRIGGER IF EXISTS trg_chains_quizzes_updated ON chains.quizzes;

DROP INDEX IF EXISTS chains.idx_chains_quiz_answers_screen;
DROP INDEX IF EXISTS chains.idx_chains_quiz_answers_lead;
DROP INDEX IF EXISTS chains.idx_chains_quiz_leads_contact_tenant;
DROP INDEX IF EXISTS chains.idx_chains_quiz_leads_quiz_date;
DROP INDEX IF EXISTS chains.idx_chains_quiz_options_screen_pos;
DROP INDEX IF EXISTS chains.idx_chains_quiz_screens_quiz_pos;
DROP INDEX IF EXISTS chains.idx_chains_quizzes_tenant;

DROP TABLE IF EXISTS chains.quiz_answers;
DROP TABLE IF EXISTS chains.quiz_leads;
DROP TABLE IF EXISTS chains.quiz_options;
DROP TABLE IF EXISTS chains.quiz_screens;
DROP TABLE IF EXISTS chains.quizzes;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0177_chain_nodes_new_types"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
