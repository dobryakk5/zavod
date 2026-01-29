-- 1. Контакты
CREATE TABLE contacts (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT now()
);

-- 2. Теги (цели / боли / опыт)
CREATE TABLE tags (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('goal', 'pain', 'experience')),
    value       TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT now(),
    UNIQUE (type, value)
);

-- 3. Связь контакт ↔ теги
CREATE TABLE contact_tags (
    contact_id  INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (contact_id, tag_id)
);

-- =====================================================
-- 1. Все теги конкретного контакта
-- =====================================================
DROP FUNCTION IF EXISTS get_contact_tags(INTEGER);

CREATE OR REPLACE FUNCTION get_contact_tags(p_contact_id INTEGER)
RETURNS TABLE (
    contact_name TEXT,
    tag_type    TEXT,
    tag_value   TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.name,
        t.type,
        t.value
    FROM contacts c
    JOIN contact_tags ct ON ct.contact_id = c.id
    JOIN tags t ON t.id = ct.tag_id
    WHERE c.id = p_contact_id;
END;
$$;


-- =====================================================
-- 2. Контакты по конкретному тегу
-- (цель / боль / опыт)
-- =====================================================
DROP FUNCTION IF EXISTS get_contacts_by_tag(TEXT, TEXT);

CREATE OR REPLACE FUNCTION get_contacts_by_tag(
    p_tag_type TEXT,
    p_tag_value TEXT
)
RETURNS TABLE (
    contact_id   INTEGER,
    contact_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        c.id,
        c.name
    FROM contacts c
    JOIN contact_tags ct ON ct.contact_id = c.id
    JOIN tags t ON t.id = ct.tag_id
    WHERE t.type = p_tag_type
      AND t.value = p_tag_value;
END;
$$;


-- =====================================================
-- 3. Статистика по тегам
-- (сколько контактов на каждый тег)
-- =====================================================
DROP FUNCTION IF EXISTS get_tag_statistics();

CREATE OR REPLACE FUNCTION get_tag_statistics()
RETURNS TABLE (
    tag_type      TEXT,
    tag_value     TEXT,
    contacts_count INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.type,
        t.value,
        COUNT(ct.contact_id)::INTEGER AS contacts_count
    FROM tags t
    LEFT JOIN contact_tags ct ON ct.tag_id = t.id
    GROUP BY t.type, t.value
    ORDER BY t.type, contacts_count DESC;
END;
$$;