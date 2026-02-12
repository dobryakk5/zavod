-- Таблица для хранения публичных share-ссылок на документы
CREATE TABLE kb_document_share (
  id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES kb_document(id) ON DELETE CASCADE,
  share_token VARCHAR(255) NOT NULL UNIQUE,
  is_active BOOLEAN NOT NULL DEFAULT true,
  view_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_viewed_at TIMESTAMP,
  expires_at TIMESTAMP, -- опционально: время истечения ссылки
  created_by INTEGER REFERENCES users(id), -- опционально: кто создал share
  
  CONSTRAINT kb_document_share_token_unique UNIQUE (share_token)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_kb_document_share_token ON kb_document_share(share_token) WHERE is_active = true;
CREATE INDEX idx_kb_document_share_document ON kb_document_share(document_id) WHERE is_active = true;

-- Комментарии
COMMENT ON TABLE kb_document_share IS 'Публичные share-ссылки на документы базы знаний';
COMMENT ON COLUMN kb_document_share.share_token IS 'Уникальный токен для публичной ссылки (32 hex символа)';
COMMENT ON COLUMN kb_document_share.is_active IS 'Активна ли ссылка (можно деактивировать для отзыва доступа)';
COMMENT ON COLUMN kb_document_share.view_count IS 'Количество просмотров по этой ссылке';
COMMENT ON COLUMN kb_document_share.expires_at IS 'Дата истечения ссылки (NULL = бессрочная)';
