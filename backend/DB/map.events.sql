-- Create availability events table for tenant booking windows
CREATE TABLE IF NOT EXISTS map.events (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    duration_minutes smallint NOT NULL DEFAULT 60,
    repeat_type smallint NOT NULL DEFAULT 0 CHECK (repeat_type IN (0, 1, 2, 3)),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE map.events
    ALTER COLUMN repeat_type TYPE smallint USING repeat_type::smallint,
    ALTER COLUMN repeat_type SET DEFAULT 0;

ALTER TABLE map.events
    DROP CONSTRAINT IF EXISTS events_repeat_type_check;

ALTER TABLE map.events
    ADD CONSTRAINT events_repeat_type_check CHECK (repeat_type IN (0, 1, 2, 3));

CREATE INDEX IF NOT EXISTS idx_map_events_tenant_start
    ON map.events(tenant_id, start_time);

CREATE INDEX IF NOT EXISTS idx_map_events_tenant_repeat
    ON map.events(tenant_id, repeat_type);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_map_events_updated') THEN
        CREATE TRIGGER trg_map_events_updated
        BEFORE UPDATE ON map.events
        FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
    END IF;
END;
$$;
