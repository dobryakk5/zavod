from django.db import migrations


MAP_CRM_EVENTS_PRICE_AND_PAYMENT_EVENT_LINK_SQL = """
create schema if not exists map;

alter table if exists map.crm_events
    add column if not exists price numeric(10, 2);

alter table if exists map.crm_payments
    add column if not exists event_id bigint references map.crm_events(id) on delete set null;

create index if not exists idx_map_payments_event_id
    on map.crm_payments(event_id);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0147_referralcode_referral"),
    ]

    operations = [
        migrations.RunSQL(sql=MAP_CRM_EVENTS_PRICE_AND_PAYMENT_EVENT_LINK_SQL, reverse_sql=""),
    ]
