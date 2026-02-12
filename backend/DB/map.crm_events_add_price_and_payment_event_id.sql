-- Add optional meeting price and meeting-payment link if missing
ALTER TABLE map.crm_events
    ADD COLUMN IF NOT EXISTS price DECIMAL(10,2);

ALTER TABLE map.crm_payments
    ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES map.crm_events(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_map_payments_event_id ON map.crm_payments(event_id);
