-- Add duration_minutes to map.crm_event_types if missing
ALTER TABLE map.crm_event_types
    ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 60;

UPDATE map.crm_event_types
SET duration_minutes = 60
WHERE duration_minutes IS NULL;
