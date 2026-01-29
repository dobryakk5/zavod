-- Add planned_at to map.crm_payments if missing
ALTER TABLE map.crm_payments
    ADD COLUMN IF NOT EXISTS planned_at TIMESTAMP;
