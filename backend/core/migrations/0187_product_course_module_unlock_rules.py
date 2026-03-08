from django.db import migrations


FORWARD_SQL = """
ALTER TABLE map.product_course_modules
    ADD COLUMN IF NOT EXISTS open_lessons_immediately BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS lesson_unlock_condition TEXT NOT NULL DEFAULT 'after_student_complete',
    ADD COLUMN IF NOT EXISTS unlock_delay_days INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS unlock_delay_hours INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS unlock_delay_minutes INT NOT NULL DEFAULT 0;

ALTER TABLE map.product_course_progress
    ADD COLUMN IF NOT EXISTS curator_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS curator_user_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_product_course_modules_unlock_condition'
          AND conrelid = 'map.product_course_modules'::regclass
    ) THEN
        ALTER TABLE map.product_course_modules
            ADD CONSTRAINT chk_product_course_modules_unlock_condition
            CHECK (
                lesson_unlock_condition IN (
                    'after_student_complete',
                    'after_curator_complete',
                    'after_timer'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_product_course_modules_delay_non_negative'
          AND conrelid = 'map.product_course_modules'::regclass
    ) THEN
        ALTER TABLE map.product_course_modules
            ADD CONSTRAINT chk_product_course_modules_delay_non_negative
            CHECK (
                unlock_delay_days >= 0
                AND unlock_delay_hours >= 0
                AND unlock_delay_minutes >= 0
            );
    END IF;
END
$$;
"""


REVERSE_SQL = """
ALTER TABLE map.product_course_progress
    DROP COLUMN IF EXISTS curator_user_id,
    DROP COLUMN IF EXISTS curator_completed_at;

ALTER TABLE map.product_course_modules
    DROP CONSTRAINT IF EXISTS chk_product_course_modules_delay_non_negative,
    DROP CONSTRAINT IF EXISTS chk_product_course_modules_unlock_condition,
    DROP COLUMN IF EXISTS unlock_delay_minutes,
    DROP COLUMN IF EXISTS unlock_delay_hours,
    DROP COLUMN IF EXISTS unlock_delay_days,
    DROP COLUMN IF EXISTS lesson_unlock_condition,
    DROP COLUMN IF EXISTS open_lessons_immediately;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0186_drop_legacy_product_kb_link"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
