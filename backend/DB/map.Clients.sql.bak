-- 1. Клиенты
CREATE TABLE clients (
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

-- 3. Связь клиент ↔ теги
CREATE TABLE client_tags (
    client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (client_id, tag_id)
);

-- =====================================================
-- 1. Все теги конкретного клиента
-- =====================================================
CREATE OR REPLACE FUNCTION get_client_tags(p_client_id INTEGER)
RETURNS TABLE (
    client_name TEXT,
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
    FROM clients c
    JOIN client_tags ct ON ct.client_id = c.id
    JOIN tags t ON t.id = ct.tag_id
    WHERE c.id = p_client_id;
END;
$$;


-- =====================================================
-- 2. Клиенты по конкретному тегу
-- (цель / боль / опыт)
-- =====================================================
CREATE OR REPLACE FUNCTION get_clients_by_tag(
    p_tag_type TEXT,
    p_tag_value TEXT
)
RETURNS TABLE (
    client_id   INTEGER,
    client_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        c.id,
        c.name
    FROM clients c
    JOIN client_tags ct ON ct.client_id = c.id
    JOIN tags t ON t.id = ct.tag_id
    WHERE t.type = p_tag_type
      AND t.value = p_tag_value;
END;
$$;


-- =====================================================
-- 3. Статистика по тегам
-- (сколько клиентов на каждый тег)
-- =====================================================
CREATE OR REPLACE FUNCTION get_tag_statistics()
RETURNS TABLE (
    tag_type      TEXT,
    tag_value     TEXT,
    clients_count INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.type,
        t.value,
        COUNT(ct.client_id)::INTEGER AS clients_count
    FROM tags t
    LEFT JOIN client_tags ct ON ct.tag_id = t.id
    GROUP BY t.type, t.value
    ORDER BY t.type, clients_count DESC;
END;
$$;
