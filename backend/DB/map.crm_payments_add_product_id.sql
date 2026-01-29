-- Add product_id to map.crm_payments if missing
ALTER TABLE map.crm_payments
    ADD COLUMN IF NOT EXISTS product_id BIGINT REFERENCES map.products(id) ON DELETE SET NULL;
