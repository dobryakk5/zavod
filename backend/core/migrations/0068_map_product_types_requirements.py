from django.db import migrations


SQL = """
alter table map.product_types
add column if not exists requirements_name text,
add column if not exists requirements_packages text,
add column if not exists requirements_audience text,
add column if not exists requirements_transformation text,
add column if not exists requirements_metrics text,
add column if not exists requirements_method text,
add column if not exists requirements_lesson_format text,
add column if not exists requirements_program_modules text,
add column if not exists requirements_packaging text;
"""

REVERSE_SQL = """
alter table map.product_types
drop column if exists requirements_name,
drop column if exists requirements_packages,
drop column if exists requirements_audience,
drop column if exists requirements_transformation,
drop column if exists requirements_metrics,
drop column if exists requirements_method,
drop column if exists requirements_lesson_format,
drop column if exists requirements_program_modules,
drop column if exists requirements_packaging;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0067_map_product_types_value"),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=REVERSE_SQL),
    ]

