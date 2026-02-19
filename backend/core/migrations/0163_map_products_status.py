from django.db import migrations


SQL = """
alter table map.products
    add column if not exists status varchar(16);

update map.products
set status = 'active'
where status is null;

alter table map.products
    alter column status set default 'draft';

alter table map.products
    alter column status set not null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'chk_products_status'
          and conrelid = 'map.products'::regclass
    ) then
        alter table map.products
            add constraint chk_products_status
            check (status in ('draft', 'active'));
    end if;
end;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0162_referral_code_types"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]

