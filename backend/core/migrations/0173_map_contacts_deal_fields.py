from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0172_bitrix24_mvp"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE map.contacts
                ADD COLUMN IF NOT EXISTS deal_stage text NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS deal_amount numeric(10,2),
                ADD COLUMN IF NOT EXISTS deal_loss_reason_code text NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS deal_loss_reason_text text NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS deal_lost_at timestamptz;

            CREATE INDEX IF NOT EXISTS idx_map_contacts_deal_stage
                ON map.contacts (deal_stage);

            CREATE INDEX IF NOT EXISTS idx_map_contacts_deal_loss_reason_code
                ON map.contacts (deal_loss_reason_code);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS map.idx_map_contacts_deal_loss_reason_code;
            DROP INDEX IF EXISTS map.idx_map_contacts_deal_stage;

            ALTER TABLE map.contacts
                DROP COLUMN IF EXISTS deal_lost_at,
                DROP COLUMN IF EXISTS deal_loss_reason_text,
                DROP COLUMN IF EXISTS deal_loss_reason_code,
                DROP COLUMN IF EXISTS deal_amount,
                DROP COLUMN IF EXISTS deal_stage;
            """,
        ),
    ]
