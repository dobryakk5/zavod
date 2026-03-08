from django.db import migrations


FORWARD_SQL = """
CREATE TABLE IF NOT EXISTS map.product_courses (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL UNIQUE REFERENCES map.products(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    cover_url TEXT,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_courses_owner
    ON map.product_courses(owner_id);
CREATE INDEX IF NOT EXISTS idx_product_courses_published
    ON map.product_courses(is_published);

CREATE TABLE IF NOT EXISTS map.product_course_modules (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES map.product_courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    cover_url TEXT,
    position INT NOT NULL DEFAULT 0,
    unlock_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_course_modules_course
    ON map.product_course_modules(course_id);
CREATE INDEX IF NOT EXISTS idx_product_course_modules_course_position
    ON map.product_course_modules(course_id, position, id);

CREATE TABLE IF NOT EXISTS map.product_course_lessons (
    id BIGSERIAL PRIMARY KEY,
    module_id BIGINT NOT NULL REFERENCES map.product_course_modules(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    position INT NOT NULL DEFAULT 0,
    is_preview BOOLEAN NOT NULL DEFAULT FALSE,
    unlock_at TIMESTAMPTZ,
    video_provider TEXT CHECK (video_provider IN ('youtube', 'rutube', 'vk') OR video_provider IS NULL),
    youtube_video_id TEXT,
    rutube_video_id TEXT,
    vk_owner_id TEXT,
    vk_video_id TEXT,
    vk_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_course_lessons_module
    ON map.product_course_lessons(module_id);
CREATE INDEX IF NOT EXISTS idx_product_course_lessons_module_position
    ON map.product_course_lessons(module_id, position, id);
CREATE INDEX IF NOT EXISTS idx_product_course_lessons_preview
    ON map.product_course_lessons(is_preview);

CREATE TABLE IF NOT EXISTS map.product_course_progress (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL,
    lesson_id BIGINT NOT NULL REFERENCES map.product_course_lessons(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uniq_product_course_progress UNIQUE (owner_id, contact_id, lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_product_course_progress_owner_contact
    ON map.product_course_progress(owner_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_product_course_progress_lesson
    ON map.product_course_progress(lesson_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'map' AND p.proname = 'set_updated_at'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_product_courses_updated'
        ) THEN
            CREATE TRIGGER trg_product_courses_updated
                BEFORE UPDATE ON map.product_courses
                FOR EACH ROW
                EXECUTE FUNCTION map.set_updated_at();
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_product_course_modules_updated'
        ) THEN
            CREATE TRIGGER trg_product_course_modules_updated
                BEFORE UPDATE ON map.product_course_modules
                FOR EACH ROW
                EXECUTE FUNCTION map.set_updated_at();
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_product_course_lessons_updated'
        ) THEN
            CREATE TRIGGER trg_product_course_lessons_updated
                BEFORE UPDATE ON map.product_course_lessons
                FOR EACH ROW
                EXECUTE FUNCTION map.set_updated_at();
        END IF;
    END IF;
END
$$;
"""


REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_product_course_lessons_updated ON map.product_course_lessons;
DROP TRIGGER IF EXISTS trg_product_course_modules_updated ON map.product_course_modules;
DROP TRIGGER IF EXISTS trg_product_courses_updated ON map.product_courses;

DROP TABLE IF EXISTS map.product_course_progress;
DROP TABLE IF EXISTS map.product_course_lessons;
DROP TABLE IF EXISTS map.product_course_modules;
DROP TABLE IF EXISTS map.product_courses;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0184_crm_tasks_due_at_and_notifications"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
