from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0135_map_contacts_telegram_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE SCHEMA IF NOT EXISTS map;

            CREATE TABLE IF NOT EXISTS map.crm_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                color VARCHAR(7) NOT NULL,
                created_at TIMESTAMP DEFAULT now(),
                updated_at TIMESTAMP DEFAULT now()
            );

            INSERT INTO map.crm_categories (id, name, description, color)
            VALUES
                (1, 'VIP', 'Премиум клиенты', '#FFD700'),
                (2, 'Стандарт', 'Регулярные клиенты', '#4A90E2'),
                (3, 'Новички', 'Клиенты на пробном периоде', '#50C878'),
                (4, 'Потенциальные', 'Лиды в воронке продаж', '#FFA500')
            ON CONFLICT (id) DO NOTHING;

            SELECT setval(
                pg_get_serial_sequence('map.crm_categories', 'id'),
                COALESCE((SELECT MAX(id) FROM map.crm_categories), 1),
                true
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS map.crm_categories;
            """,
        ),
    ]
