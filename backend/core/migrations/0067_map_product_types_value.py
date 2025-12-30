from django.db import migrations


SQL = """
alter table map.product_types
add column if not exists value text;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0066_map_product_types_goal"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=""),
    ]

