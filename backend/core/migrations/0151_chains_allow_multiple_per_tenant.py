from django.db import migrations


FORWARD_SQL = """
drop index if exists chains.uniq_chains_tenant;
create unique index if not exists uniq_chains_tenant_name
    on chains.chains(tenant_id, name);
"""

REVERSE_SQL = """
drop index if exists chains.uniq_chains_tenant_name;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0150_referralfirstpayment"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
