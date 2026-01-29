-- Migrate map.contacts to single name field (safe for mixed schemas)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'name'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'email'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN email VARCHAR(255);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'phone'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN phone VARCHAR(50);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'category_id'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN category_id INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'status'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'photo_url'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN photo_url TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'notes'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN notes TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'parent_id'
    ) THEN
        ALTER TABLE map.contacts
            ADD COLUMN parent_id INTEGER REFERENCES map.contacts(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'created_at'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN created_at TIMESTAMP DEFAULT now();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE map.contacts ADD COLUMN updated_at TIMESTAMP DEFAULT now();
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name IN ('first_name', 'last_name')
    ) THEN
        EXECUTE $sql$
            UPDATE map.contacts
            SET name = TRIM(CONCAT_WS(' ', first_name, last_name))
            WHERE (name IS NULL OR name = '')
        $sql$;
    END IF;

    UPDATE map.contacts
    SET name = 'Без имени'
    WHERE name IS NULL OR name = '';

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'last_name'
    ) THEN
        ALTER TABLE map.contacts DROP COLUMN last_name;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'map'
          AND table_name = 'contacts'
          AND column_name = 'first_name'
    ) THEN
        ALTER TABLE map.contacts DROP COLUMN first_name;
    END IF;

    ALTER TABLE map.contacts ALTER COLUMN name SET NOT NULL;
END $$;
