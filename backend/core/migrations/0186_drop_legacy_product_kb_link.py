from django.db import migrations


FORWARD_SQL = """
ALTER TABLE map.products
    DROP CONSTRAINT IF EXISTS fk_products_digital_product_document;

DROP INDEX IF EXISTS map.idx_products_digital_product_document_id;
DROP INDEX IF EXISTS idx_products_digital_product_document_id;

ALTER TABLE map.products
    DROP COLUMN IF EXISTS digital_product_document_id;
"""


REVERSE_SQL = """
ALTER TABLE map.products
    ADD COLUMN IF NOT EXISTS digital_product_document_id BIGINT;

CREATE INDEX IF NOT EXISTS idx_products_digital_product_document_id
    ON map.products (digital_product_document_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE constraint_schema = 'map'
          AND table_name = 'products'
          AND constraint_name = 'fk_products_digital_product_document'
    ) THEN
        ALTER TABLE map.products
            ADD CONSTRAINT fk_products_digital_product_document
            FOREIGN KEY (digital_product_document_id)
            REFERENCES map.kb_documents (id)
            ON DELETE SET NULL;
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0185_product_course_lms_schema"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
