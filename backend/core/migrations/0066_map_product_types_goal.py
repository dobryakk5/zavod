from django.db import migrations


SQL = """
alter table map.product_types
add column if not exists goal text;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0065_map_products_schema"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]

