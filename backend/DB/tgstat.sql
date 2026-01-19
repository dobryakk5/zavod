CREATE TABLE "map".tgstat_categories (
	slug text NOT NULL,
	title text NOT NULL,
	url text NOT NULL,
	parsed_at timestamp DEFAULT now() NULL,
	id serial4 NOT NULL,
	CONSTRAINT tgstat_categories_pkey PRIMARY KEY (id),
	CONSTRAINT tgstat_categories_slug_uniq UNIQUE (slug)
);

CREATE TABLE "map".tgstat_tags (
	slug text NOT NULL,
	title text NOT NULL,
	url text NOT NULL,
	category_slug text NULL,
	more_channels_count int4 NULL,
	parsed_at timestamp DEFAULT now() NULL,
	id smallserial NOT NULL,
	category_id int4 NULL,
	CONSTRAINT tgstat_tags_id_unique UNIQUE (id),
	CONSTRAINT tgstat_tags_pkey PRIMARY KEY (slug),
	CONSTRAINT tgstat_tags_category_id_fkey FOREIGN KEY (category_id) REFERENCES "map".tgstat_categories(id) ON DELETE CASCADE
);
CREATE INDEX idx_tgstat_tags_category ON map.tgstat_tags USING btree (category_slug);
CREATE INDEX idx_tgstat_tags_category_id ON map.tgstat_tags USING btree (category_id);

CREATE TABLE "map".tgstat_tag_channels (
	tag_slug text NULL,
	username text NOT NULL,
	title text NULL,
	subscribers int4 NULL,
	url text NULL,
	parsed_at timestamp DEFAULT now() NULL,
	tag_id int2 NULL,
	id bigserial NOT NULL,
	category_id int4 NULL,
	CONSTRAINT tgstat_tag_channels_pkey PRIMARY KEY (id),
	CONSTRAINT tgstat_tag_channels_tag_id_fk FOREIGN KEY (tag_id) REFERENCES "map".tgstat_tags(id),
	CONSTRAINT tgstat_tag_channels_tag_slug_fkey FOREIGN KEY (tag_slug) REFERENCES "map".tgstat_tags(slug)
);
CREATE INDEX idx_tgstat_tag_channels_tag ON map.tgstat_tag_channels USING btree (tag_slug);
CREATE UNIQUE INDEX tgstat_tag_channels_tag_user_uidx ON map.tgstat_tag_channels USING btree (tag_slug, username);
CREATE INDEX idx_tgstat_tag_channels_category ON map.tgstat_tag_channels USING btree (category_id);
