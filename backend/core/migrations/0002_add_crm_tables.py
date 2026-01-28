from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),  # Зависит от вашей последней миграции
    ]

    operations = [
        # Создание таблиц для CRM-функциональности
        migrations.RunSQL(
            """
            -- Таблица категорий клиентов
            CREATE TABLE IF NOT EXISTS crm_client_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                color VARCHAR(7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица клиентов
            CREATE TABLE IF NOT EXISTS crm_clients (
                id SERIAL PRIMARY KEY,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE,
                phone VARCHAR(20),
                category_id INTEGER REFERENCES crm_client_categories(id) ON DELETE SET NULL,
                status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
                photo_url TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица типов событий
            CREATE TABLE IF NOT EXISTS crm_event_types (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                color VARCHAR(7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица событий
            CREATE TABLE IF NOT EXISTS crm_events (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES crm_clients(id) ON DELETE CASCADE,
                event_type_id INTEGER REFERENCES crm_event_types(id) ON DELETE SET NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                location VARCHAR(255),
                status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT check_event_time CHECK (end_time > start_time)
            );

            -- Таблица платежей
            CREATE TABLE IF NOT EXISTS crm_payments (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES crm_clients(id) ON DELETE CASCADE,
                amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
                currency VARCHAR(3) DEFAULT 'RUB' NOT NULL,
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'refunded')),
                payment_method VARCHAR(50),
                transaction_id VARCHAR(255),
                description TEXT,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Таблица заметок
            CREATE TABLE IF NOT EXISTS crm_notes (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES crm_clients(id) ON DELETE CASCADE,
                title VARCHAR(255),
                content TEXT NOT NULL,
                is_important BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Индексы
            CREATE INDEX IF NOT EXISTS idx_crm_clients_category ON crm_clients(category_id);
            CREATE INDEX IF NOT EXISTS idx_crm_clients_status ON crm_clients(status);
            CREATE INDEX IF NOT EXISTS idx_crm_clients_email ON crm_clients(email);
            CREATE INDEX IF NOT EXISTS idx_crm_events_client ON crm_events(client_id);
            CREATE INDEX IF NOT EXISTS idx_crm_events_start_time ON crm_events(start_time);
            CREATE INDEX IF NOT EXISTS idx_crm_events_status ON crm_events(status);
            CREATE INDEX IF NOT EXISTS idx_crm_events_type ON crm_events(event_type_id);
            CREATE INDEX IF NOT EXISTS idx_crm_payments_client ON crm_payments(client_id);
            CREATE INDEX IF NOT EXISTS idx_crm_payments_status ON crm_payments(status);
            CREATE INDEX IF NOT EXISTS idx_crm_notes_client ON crm_notes(client_id);

            -- Триггеры для обновления времени
            CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER IF NOT EXISTS update_crm_clients_updated_at
                BEFORE UPDATE ON crm_clients
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER IF NOT EXISTS update_crm_categories_updated_at
                BEFORE UPDATE ON crm_client_categories
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER IF NOT EXISTS update_crm_events_updated_at
                BEFORE UPDATE ON crm_events
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER IF NOT EXISTS update_crm_payments_updated_at
                BEFORE UPDATE ON crm_payments
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER IF NOT EXISTS update_crm_notes_updated_at
                BEFORE UPDATE ON crm_notes
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            -- Начальные данные
            INSERT INTO crm_client_categories (name, description, color) 
            SELECT 'VIP', 'Премиум клиенты с индивидуальным подходом', '#FFD700'
            WHERE NOT EXISTS (SELECT 1 FROM crm_client_categories WHERE name = 'VIP');

            INSERT INTO crm_client_categories (name, description, color) 
            SELECT 'Стандарт', 'Регулярные клиенты', '#4A90E2'
            WHERE NOT EXISTS (SELECT 1 FROM crm_client_categories WHERE name = 'Стандарт');

            INSERT INTO crm_event_types (name, description, duration_minutes, color) 
            SELECT 'Индивидуальная сессия', 'Персональная коуч-сессия', 60, '#4A90E2'
            WHERE NOT EXISTS (SELECT 1 FROM crm_event_types WHERE name = 'Индивидуальная сессия');
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS crm_notes;
            DROP TABLE IF EXISTS crm_payments;
            DROP TABLE IF EXISTS crm_events;
            DROP TABLE IF EXISTS crm_event_types;
            DROP TABLE IF EXISTS crm_clients;
            DROP TABLE IF EXISTS crm_client_categories;
            
            DROP FUNCTION IF EXISTS update_updated_at_column();
            """
        ),
    ]