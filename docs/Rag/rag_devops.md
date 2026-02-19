# RAG — DevOps инструкция по установке

## 1. pgvector в Postgres

### Ubuntu / Debian

```bash
# зависимости для сборки
sudo apt install -y postgresql-server-dev-all build-essential git

# клонируем и собираем
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Проверка версии Postgres

```bash
pg_config --version
# должно быть 13+
```

### Если Postgres установлен через apt (pg 14/15/16)

```bash
sudo apt install -y postgresql-14-pgvector
# или
sudo apt install -y postgresql-15-pgvector
# или
sudo apt install -y postgresql-16-pgvector
```

### Активация расширений в БД

```sql
-- подключись к нужной БД
\c your_database

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- проверка
SELECT * FROM pg_extension WHERE extname IN ('vector', 'pg_trgm');
```

---

## 2. Python окружение

```bash
python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install \
    asyncpg \
    pgvector \
    sentence-transformers \
    openai \
    adrf \
    djangorestframework \
    torch --index-url https://download.pytorch.org/whl/cpu
```

> `torch` с CPU-индексом — если нужен GPU замени на стандартный `pip install torch`

---

## 3. Скачать и сохранить E5 модель локально

Скачиваем один раз при деплое, чтобы не тянуть с HuggingFace при каждом старте:

```python
# scripts/download_model.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-small")
model.save("./models/multilingual-e5-small")
print("Модель сохранена в ./models/multilingual-e5-small")
```

```bash
python scripts/download_model.py
```

### Обновить config.py — путь к локальной модели

```python
# rag/config.py
e5_model = "./models/multilingual-e5-small"  # вместо "intfloat/multilingual-e5-small"
```

---

## 4. Инициализация БД

```bash
# применяем SQL схему
psql -U your_user -d your_database -f rag/sql/schema.sql
```

Создай файл `rag/sql/schema.sql` — скопируй туда SQL из основной инструкции пакета.

---

## 5. Переменные окружения

```bash
# .env
RAG_PG_DSN=postgresql://user:pass@localhost:5432/your_database
RAG_DEEPSEEK_API_KEY=your_deepseek_key
RAG_DEEPSEEK_BASE_URL=https://api.deepseek.com
RAG_DEEPSEEK_MODEL=deepseek-chat
RAG_E5_MODEL=./models/multilingual-e5-small
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=64
RAG_RRF_K=60
RAG_TOP_K=10
```

Обнови `rag/config.py` для чтения из env:

```python
import os
from django.conf import settings

def _get(key, default=None):
    cfg = getattr(settings, "RAG_CONFIG", {})
    return cfg.get(key) or os.getenv(f"RAG_{key}") or default

class Config:
    pg_dsn            = _get("PG_DSN")
    deepseek_api_key  = _get("DEEPSEEK_API_KEY")
    deepseek_base_url = _get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model    = _get("DEEPSEEK_MODEL", "deepseek-chat")
    e5_model          = _get("E5_MODEL", "./models/multilingual-e5-small")
    chunk_size        = int(_get("CHUNK_SIZE", 512))
    chunk_overlap     = int(_get("CHUNK_OVERLAP", 64))
    rrf_k             = int(_get("RRF_K", 60))
    top_k             = int(_get("TOP_K", 10))

config = Config()
```

---

## 6. Docker (опционально)

Если используешь Docker — готовый `docker-compose.yml`:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: rag
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./rag/sql/schema.sql:/docker-entrypoint-initdb.d/schema.sql

  app:
    build: .
    env_file: .env
    volumes:
      - ./models:/app/models
    depends_on:
      - db

volumes:
  pgdata:
```

`pgvector/pgvector:pg16` — официальный образ с уже встроенным pgvector, расширения создавать вручную не нужно, только `CREATE EXTENSION` в схеме.

---

## 7. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# скачиваем модель при сборке образа
RUN python scripts/download_model.py

CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]
```

---

## 8. requirements.txt

```
asyncpg
pgvector
sentence-transformers
openai
adrf
djangorestframework
torch --index-url https://download.pytorch.org/whl/cpu
gunicorn
python-dotenv
```

---

## Порядок первого запуска

```
1. docker-compose up -d db        # поднять Postgres с pgvector
2. python scripts/download_model.py  # скачать e5 (если без Docker)
3. psql ... -f rag/sql/schema.sql    # применить схему (если без Docker)
4. python manage.py runserver        # запустить Django
5. POST /api/rag/migrate/            # мигрировать документы
```

---

## Фоновая индексация KB (в проекте)

Индексация запускается в фоне задачей Celery:
- задача: `core.tasks.process_pending_kb_rag_indexing`
- расписание: `RAG_INDEX_POLL_SECONDS` (по умолчанию `300`, то есть 5 минут)
- размер батча: `RAG_INDEX_BATCH_SIZE` (по умолчанию `25`)

Включение/выключение через ENV:

```bash
RAG_INDEXING_ENABLED=True   # включить
RAG_INDEXING_ENABLED=False  # выключить
```

Какой процесс этим занимается:
- `celery beat` ставит задачу по расписанию
- `celery worker` выполняет задачу и делает индексацию
