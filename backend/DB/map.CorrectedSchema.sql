-- Corrected schema for map CRM tables
-- This fixes the foreign key reference issues in the original schema

-- Create the map schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS map;

-- Create contacts table (migrated from crm_clients)
CREATE TABLE IF NOT EXISTS map.contacts (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    email           VARCHAR(255),
    phone           VARCHAR(50),
    tg_user_id      BIGINT,
    tg_username     TEXT,
    tg_connected_at DATE,
    category_id     INTEGER,
    status          VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    photo_url       TEXT,
    notes           TEXT,
    parent_id       INTEGER REFERENCES map.contacts(id) ON DELETE SET NULL,
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);

-- Create tags table (goals, pains, experiences)
CREATE TABLE IF NOT EXISTS map.crm_tags (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('goal', 'pain', 'experience')),
    value       TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT now(),
    UNIQUE (type, value)
);

-- Create contact_tags table (relationship between contacts and tags)
-- FIXED: Reference the correct table name (map.crm_tags instead of map.tags)
CREATE TABLE IF NOT EXISTS map.contact_tags (
    contact_id  INTEGER NOT NULL REFERENCES map.contacts(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES map.crm_tags(id) ON DELETE CASCADE,  -- FIXED: was map.tags
    description TEXT,
    PRIMARY KEY (contact_id, tag_id)
);

-- Create event types table (migrated from crm_event_types)
CREATE TABLE IF NOT EXISTS map.crm_event_types (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    duration_minutes INTEGER DEFAULT 60,
    color           VARCHAR(7) NOT NULL, -- HEX цвет для UI
    created_at      TIMESTAMP DEFAULT now()
);

-- Create events table (migrated from crm_events)
-- FIXED: Reference the correct table name (map.crm_event_types instead of map.event_types)
CREATE TABLE IF NOT EXISTS map.crm_events (
    id              SERIAL PRIMARY KEY,
    contact_id      INTEGER NOT NULL REFERENCES map.contacts(id) ON DELETE CASCADE,
    event_type_id   INTEGER REFERENCES map.crm_event_types(id) ON DELETE SET NULL,  -- FIXED: was map.event_types
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    location        VARCHAR(255),
    status          VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    notes           TEXT,
    price           DECIMAL(10,2),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Create payments table (migrated from crm_payments)
CREATE TABLE IF NOT EXISTS map.crm_payments (
    id              SERIAL PRIMARY KEY,
    contact_id      INTEGER NOT NULL REFERENCES map.contacts(id) ON DELETE CASCADE,
    event_id        BIGINT REFERENCES map.crm_events(id) ON DELETE SET NULL,
    product_id      BIGINT REFERENCES map.products(id) ON DELETE SET NULL,
    amount          DECIMAL(10,2) NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'RUB',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'refunded')),
    payment_method  VARCHAR(50),
    transaction_id  VARCHAR(255),
    description     TEXT,
    planned_at      TIMESTAMP,
    paid_at         TIMESTAMP,
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);

-- Create notes table (migrated from crm_notes)
CREATE TABLE IF NOT EXISTS map.crm_notes (
    id              SERIAL PRIMARY KEY,
    contact_id      INTEGER NOT NULL REFERENCES map.contacts(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    content         TEXT NOT NULL,
    is_important    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_map_contacts_category ON map.contacts(category_id);
CREATE INDEX IF NOT EXISTS idx_map_contacts_status ON map.contacts(status);
CREATE INDEX IF NOT EXISTS idx_map_contacts_parent ON map.contacts(parent_id);
CREATE INDEX IF NOT EXISTS idx_map_tags_type ON map.crm_tags(type);
CREATE INDEX IF NOT EXISTS idx_map_tags_value ON map.crm_tags(value);
CREATE INDEX IF NOT EXISTS idx_map_events_contact_start_time ON map.crm_events(contact_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_map_events_type ON map.crm_events(event_type_id);
CREATE INDEX IF NOT EXISTS idx_map_payments_contact_status ON map.crm_payments(contact_id, status);
CREATE INDEX IF NOT EXISTS idx_map_payments_status ON map.crm_payments(status);
CREATE INDEX IF NOT EXISTS idx_map_payments_event_id ON map.crm_payments(event_id);
CREATE INDEX IF NOT EXISTS idx_map_notes_contact_important ON map.crm_notes(contact_id, is_important DESC);
CREATE INDEX IF NOT EXISTS idx_map_contact_tags_contact ON map.contact_tags(contact_id);
CREATE INDEX IF NOT EXISTS idx_map_contact_tags_tag ON map.contact_tags(tag_id);

-- Create functions for the new schema
-- Function to get events for a specific contact
CREATE OR REPLACE FUNCTION map.get_contact_events(p_contact_id INTEGER)
RETURNS TABLE (
    contact_name TEXT,
    event_title TEXT,
    event_description TEXT,
    event_start_time TIMESTAMP,
    event_end_time TIMESTAMP,
    event_status VARCHAR(20),
    event_location VARCHAR(255),
    event_notes TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.name as contact_name,
        e.title,
        e.description,
        e.start_time,
        e.end_time,
        e.status,
        e.location,
        e.notes
    FROM map.contacts c
    JOIN map.crm_events e ON e.contact_id = c.id
    WHERE c.id = p_contact_id
    ORDER BY e.start_time DESC;
END;
$$;

-- Function to get payments for a specific contact
CREATE OR REPLACE FUNCTION map.get_contact_payments(p_contact_id INTEGER)
RETURNS TABLE (
    contact_name TEXT,
    payment_amount DECIMAL(10,2),
    payment_currency VARCHAR(3),
    payment_status VARCHAR(20),
    payment_method VARCHAR(50),
    payment_transaction_id VARCHAR(255),
    payment_description TEXT,
    payment_paid_at TIMESTAMP
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.name as contact_name,
        p.amount,
        p.currency,
        p.status,
        p.payment_method,
        p.transaction_id,
        p.description,
        p.paid_at
    FROM map.contacts c
    JOIN map.crm_payments p ON p.contact_id = c.id
    WHERE c.id = p_contact_id
    ORDER BY p.created_at DESC;
END;
$$;

-- Function to get notes for a specific contact
CREATE OR REPLACE FUNCTION map.get_contact_notes(p_contact_id INTEGER)
RETURNS TABLE (
    contact_name TEXT,
    note_title VARCHAR(255),
    note_content TEXT,
    note_is_important BOOLEAN,
    note_created_at TIMESTAMP
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.name as contact_name,
        n.title,
        n.content,
        n.is_important,
        n.created_at
    FROM map.contacts c
    JOIN map.crm_notes n ON n.contact_id = c.id
    WHERE c.id = p_contact_id
    ORDER BY n.created_at DESC;
END;
$$;

-- Function to get all contact information
CREATE OR REPLACE FUNCTION map.get_complete_contact_info(p_contact_id INTEGER)
RETURNS TABLE (
    contact_id INTEGER,
    contact_name TEXT,
    contact_events_count INTEGER,
    contact_payments_count INTEGER,
    contact_notes_count INTEGER,
    contact_tags_count INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name as contact_name,
        (SELECT COUNT(*) FROM map.crm_events e WHERE e.contact_id = c.id) AS contact_events_count,
        (SELECT COUNT(*) FROM map.crm_payments p WHERE p.contact_id = c.id) AS contact_payments_count,
        (SELECT COUNT(*) FROM map.crm_notes n WHERE n.contact_id = c.id) AS contact_notes_count,
        (SELECT COUNT(*) FROM map.contact_tags ct WHERE ct.contact_id = c.id) AS contact_tags_count
    FROM map.contacts c
    WHERE c.id = p_contact_id;
END;
$$;

-- Trigger function for updated_at fields
CREATE OR REPLACE FUNCTION map.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables that have updated_at
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'map_contacts_updated_at'
    ) THEN
        CREATE TRIGGER map_contacts_updated_at
            BEFORE UPDATE ON map.contacts
            FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'map_events_updated_at'
    ) THEN
        CREATE TRIGGER map_events_updated_at
            BEFORE UPDATE ON map.crm_events
            FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'map_payments_updated_at'
    ) THEN
        CREATE TRIGGER map_payments_updated_at
            BEFORE UPDATE ON map.crm_payments
            FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'map_notes_updated_at'
    ) THEN
        CREATE TRIGGER map_notes_updated_at
            BEFORE UPDATE ON map.crm_notes
            FOR EACH ROW EXECUTE FUNCTION map.set_updated_at();
    END IF;
END $$;
