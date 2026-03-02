from django.db import migrations


FORWARD_SQL = """
CREATE SCHEMA IF NOT EXISTS map;

CREATE TABLE IF NOT EXISTS map.crm_deals (
    id BIGSERIAL PRIMARY KEY,
    contact_id BIGINT NOT NULL REFERENCES map.contacts(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'new_lead',
    amount NUMERIC(10, 2),
    currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
    description TEXT NOT NULL DEFAULT '',
    lost_reason_code TEXT NOT NULL DEFAULT '',
    lost_reason_text TEXT NOT NULL DEFAULT '',
    lost_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_map_crm_deals_contact_stage
    ON map.crm_deals(contact_id, stage);

CREATE INDEX IF NOT EXISTS idx_map_crm_deals_stage_created
    ON map.crm_deals(stage, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_map_crm_deals_product_id
    ON map.crm_deals(product_id);

ALTER TABLE map.crm_payments
    ADD COLUMN IF NOT EXISTS deal_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'crm_payments_deal_id_fkey'
    ) THEN
        ALTER TABLE map.crm_payments
            ADD CONSTRAINT crm_payments_deal_id_fkey
            FOREIGN KEY (deal_id)
            REFERENCES map.crm_deals(id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_map_payments_deal_id
    ON map.crm_payments(deal_id);
"""


REVERSE_SQL = """
DROP INDEX IF EXISTS map.idx_map_payments_deal_id;

ALTER TABLE map.crm_payments
    DROP CONSTRAINT IF EXISTS crm_payments_deal_id_fkey;

ALTER TABLE map.crm_payments
    DROP COLUMN IF EXISTS deal_id;

DROP INDEX IF EXISTS map.idx_map_crm_deals_product_id;
DROP INDEX IF EXISTS map.idx_map_crm_deals_stage_created;
DROP INDEX IF EXISTS map.idx_map_crm_deals_contact_stage;

DROP TABLE IF EXISTS map.crm_deals;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0173_map_contacts_deal_fields"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]

