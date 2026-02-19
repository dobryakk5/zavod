from django.db import migrations


SQL = """
ALTER TABLE map.user_tenant_binding
    ADD COLUMN IF NOT EXISTS provider varchar(16),
    ADD COLUMN IF NOT EXISTS provider_user_id varchar(255);

UPDATE map.user_tenant_binding
SET provider = 'telegram'
WHERE provider IS NULL OR provider = '';

UPDATE map.user_tenant_binding
SET provider_user_id = telegram_chat_id::text
WHERE (provider_user_id IS NULL OR provider_user_id = '')
  AND telegram_chat_id IS NOT NULL;

ALTER TABLE map.user_tenant_binding
    ALTER COLUMN provider SET DEFAULT 'telegram',
    ALTER COLUMN provider SET NOT NULL,
    ALTER COLUMN provider_user_id SET NOT NULL,
    ALTER COLUMN telegram_chat_id DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_tenant_binding_provider_unique
    ON map.user_tenant_binding(provider, provider_user_id, tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_tenant_binding_provider_active
    ON map.user_tenant_binding(provider, provider_user_id, is_active);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0159_rag_kb_chunks"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]
