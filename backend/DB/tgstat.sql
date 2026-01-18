CREATE TABLE IF NOT EXISTS tgstat_categories (
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    parsed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tgstat_tags (
    id SMALLSERIAL UNIQUE,
    slug TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    category_slug TEXT REFERENCES tgstat_categories(slug),
    more_channels_count INTEGER,
    parsed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE tgstat_tag_channels (
    id BIGSERIAL PRIMARY KEY,

    tag_slug TEXT REFERENCES tgstat_tags(slug),
    tag_id SMALLINT REFERENCES tgstat_tags(id),
    username TEXT NOT NULL,
    title TEXT,
    subscribers INTEGER,
    url TEXT,
    parsed_at TIMESTAMP DEFAULT now(),

    UNIQUE (tag_slug, username)
);


CREATE INDEX IF NOT EXISTS idx_tgstat_tag_channels_tag
    ON tgstat_tag_channels(tag_slug);
