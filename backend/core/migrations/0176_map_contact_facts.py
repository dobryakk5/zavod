from django.db import migrations


FORWARD_SQL = """
CREATE SCHEMA IF NOT EXISTS map;

CREATE TABLE IF NOT EXISTS map.contact_facts (
    id            BIGSERIAL PRIMARY KEY,
    contact_id    INTEGER      NOT NULL,
    tenant_id     INTEGER      NOT NULL,
    category      VARCHAR(32)  NOT NULL,
    fact_type     VARCHAR(64)  NOT NULL,
    fact_value    TEXT         NOT NULL,
    source        VARCHAR(32)  NOT NULL DEFAULT 'ai_chat',
    session_id    BIGINT       NULL REFERENCES chains.chain_sessions(id) ON DELETE SET NULL,
    confidence    SMALLINT     NOT NULL DEFAULT 2
                  CHECK (confidence BETWEEN 1 AND 3),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN map.contact_facts.category IS
    'purchase | context | environment | attitude | constraints';
COMMENT ON COLUMN map.contact_facts.fact_type IS
    'Конкретный тип внутри категории: pain, desire, objection, role, company, ...';
COMMENT ON COLUMN map.contact_facts.confidence IS
    '1=низкая (AI предположил), 2=средняя (явно сказал), 3=высокая (подтвердил действием)';
COMMENT ON COLUMN map.contact_facts.source IS
    'ai_chat | booking | manual | import';

CREATE INDEX IF NOT EXISTS idx_contact_facts_contact
    ON map.contact_facts(contact_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_contact_facts_category
    ON map.contact_facts(tenant_id, category, fact_type);

CREATE INDEX IF NOT EXISTS idx_contact_facts_active
    ON map.contact_facts(contact_id, tenant_id, is_active)
    WHERE is_active = TRUE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_contact_facts_updated'
    ) THEN
        CREATE TRIGGER trg_contact_facts_updated
            BEFORE UPDATE ON map.contact_facts
            FOR EACH ROW
            EXECUTE FUNCTION map.set_updated_at();
    END IF;
END $$;
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_contact_facts_updated ON map.contact_facts;
DROP INDEX IF EXISTS map.idx_contact_facts_active;
DROP INDEX IF EXISTS map.idx_contact_facts_category;
DROP INDEX IF EXISTS map.idx_contact_facts_contact;
DROP TABLE IF EXISTS map.contact_facts;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0174_map_crm_deals_and_payment_link"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
