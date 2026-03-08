from django.db import migrations


FORWARD_SQL = """
CREATE TABLE IF NOT EXISTS map.product_course_events (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL REFERENCES map.products(id) ON DELETE CASCADE,
    course_id BIGINT NOT NULL REFERENCES map.product_courses(id) ON DELETE CASCADE,
    module_id BIGINT NOT NULL REFERENCES map.product_course_modules(id) ON DELETE CASCADE,
    lesson_id BIGINT NOT NULL REFERENCES map.product_course_lessons(id) ON DELETE CASCADE,
    progress_id BIGINT REFERENCES map.product_course_progress(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    actor_user_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_course_events_event_type CHECK (
        event_type IN ('lesson_completed', 'lesson_accepted')
    ),
    CONSTRAINT chk_product_course_events_actor_role CHECK (
        actor_role IN ('student', 'curator', 'system')
    )
);

CREATE INDEX IF NOT EXISTS idx_product_course_events_owner_contact_created
    ON map.product_course_events(owner_id, contact_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_course_events_owner_lesson_created
    ON map.product_course_events(owner_id, lesson_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_course_events_type_created
    ON map.product_course_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS map.product_course_comments (
    id BIGSERIAL PRIMARY KEY,
    owner_id BIGINT NOT NULL REFERENCES public.core_client(id) ON DELETE CASCADE,
    contact_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL REFERENCES map.products(id) ON DELETE CASCADE,
    course_id BIGINT NOT NULL REFERENCES map.product_courses(id) ON DELETE CASCADE,
    module_id BIGINT NOT NULL REFERENCES map.product_course_modules(id) ON DELETE CASCADE,
    lesson_id BIGINT NOT NULL REFERENCES map.product_course_lessons(id) ON DELETE CASCADE,
    author_role TEXT NOT NULL,
    author_user_id BIGINT,
    channel TEXT NOT NULL DEFAULT 'courses',
    message_text TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_product_course_comments_author_role CHECK (
        author_role IN ('student', 'curator', 'system')
    ),
    CONSTRAINT chk_product_course_comments_channel CHECK (
        channel IN ('courses', 'telegram', 'vk', 'email')
    )
);

CREATE INDEX IF NOT EXISTS idx_product_course_comments_owner_contact_lesson_created
    ON map.product_course_comments(owner_id, contact_id, lesson_id, created_at);
CREATE INDEX IF NOT EXISTS idx_product_course_comments_owner_lesson_created
    ON map.product_course_comments(owner_id, lesson_id, created_at);
"""


REVERSE_SQL = """
DROP TABLE IF EXISTS map.product_course_comments;
DROP TABLE IF EXISTS map.product_course_events;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0187_product_course_module_unlock_rules"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
