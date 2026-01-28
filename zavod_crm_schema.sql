-- Таблица категорий клиентов
CREATE TABLE client_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7), -- HEX цвет для UI
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица клиентов
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    category_id INTEGER REFERENCES client_categories(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    photo_url TEXT,
    notes TEXT,
    parent_id INTEGER REFERENCES clients(id) ON DELETE SET NULL, -- Связь с родительским клиентом
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для оптимизации поиска дочерних клиентов
CREATE INDEX idx_clients_parent ON clients(parent_id);

-- Таблица типов событий
CREATE TABLE event_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    duration_minutes INTEGER DEFAULT 60,
    color VARCHAR(7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица событий
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    event_type_id INTEGER REFERENCES event_types(id) ON DELETE SET NULL,
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

-- Индексы для оптимизации запросов
CREATE INDEX idx_clients_category ON clients(category_id);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_events_client ON events(client_id);
CREATE INDEX idx_events_start_time ON events(start_time);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_type ON events(event_type_id);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_categories_updated_at
    BEFORE UPDATE ON client_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Таблица платежей
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
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
CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title VARCHAR(255),
    content TEXT NOT NULL,
    is_important BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для платежей
CREATE INDEX idx_payments_client ON payments(client_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_paid_at ON payments(paid_at);

-- Индексы для заметок
CREATE INDEX idx_notes_client ON notes(client_id);
CREATE INDEX idx_notes_important ON notes(is_important);
CREATE INDEX idx_notes_created_at ON notes(created_at);

-- Полнотекстовый поиск для заметок
CREATE INDEX idx_notes_content_fts ON notes USING gin(to_tsvector('russian', content));
CREATE INDEX idx_notes_title_fts ON notes USING gin(to_tsvector('russian', coalesce(title, '')));

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Примеры начальных данных
INSERT INTO client_categories (name, description, color) VALUES
    ('VIP', 'Премиум клиенты с индивидуальным подходом', '#FFD700'),
    ('Стандарт', 'Регулярные клиенты', '#4A90E2'),
    ('Новички', 'Клиенты на пробном периоде', '#50C878'),
    ('Потенциальные', 'Лиды в воронке продаж', '#FFA500');

INSERT INTO event_types (name, description, duration_minutes, color) VALUES
    ('Индивидуальная сессия', 'Персональная коуч-сессия', 60, '#4A90E2'),
    ('Групповая сессия', 'Групповой коучинг', 90, '#9B59B6'),
    ('Первая консультация', 'Вводная встреча с новым клиентом', 45, '#50C878'),
    ('Звонок-напоминание', 'Короткий звонок для поддержки', 15, '#F39C12');

-- Пример иерархии клиентов: компания и ее сотрудники
-- Родительский клиент (например, компания)
INSERT INTO clients (first_name, last_name, email, phone, category_id, status, notes) VALUES
    ('ООО', 'Крупный Клиент', 'contact@bigcompany.ru', '+74951234500', 1, 'active', 'Основной корпоративный клиент');

-- Дочерние клиенты (например, сотрудники компании)
INSERT INTO clients (first_name, last_name, email, phone, category_id, status, parent_id, notes) VALUES
    ('Иван', 'Петров', 'ivan.petrov@bigcompany.ru', '+74951234501', 1, 'active', 1, 'Главный специалист'),
    ('Мария', 'Сидорова', 'maria.sidorova@bigcompany.ru', '+74951234502', 1, 'active', 1, 'Менеджер проекта'),
    ('Алексей', 'Козлов', 'alexey.kozlov@bigcompany.ru', '+74951234503', 2, 'active', 1, 'Технический специалист');