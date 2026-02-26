from django.db import migrations


SQL = """
alter table map.kb_documents
    add column if not exists document_type text;

update map.kb_documents
set document_type = 'page'
where document_type is null or btrim(document_type) = '';

alter table map.kb_documents
    alter column document_type set default 'page';

alter table map.kb_documents
    alter column document_type set not null;

alter table map.products
    add column if not exists digital_product_document_id bigint;

create index if not exists idx_products_digital_product_document_id
    on map.products (digital_product_document_id);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'fk_products_digital_product_document'
          and conrelid = 'map.products'::regclass
    ) then
        alter table map.products
            add constraint fk_products_digital_product_document
            foreign key (digital_product_document_id)
            references map.kb_documents (id)
            on delete set null;
    end if;
end;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0165_product_kb_link_fields"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]
