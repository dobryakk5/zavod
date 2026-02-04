# Telegram Chain Builder

Полная система для создания и выполнения цепочек сообщений в Telegram с ветвлениями и условиями.

## 🎯 Что это

Конструктор позволяет вашим tenants создавать визуальные цепочки сообщений с:
- **Ветвлениями** — разные пути в зависимости от ответа пользователя
- **Условиями** — нажатие кнопки, содержание текста, regex, таймаут
- **Задержками** — отправка сообщений через N секунд
- **Типами сообщений** — текст, фото, кнопки

## 📁 Структура проекта

```
telegram-chain-builder/
├── README.md                           # Этот файл
│
├── phase1_db_and_api/                  # Фаза 1: База данных и API
│   ├── 001_create_chains_schema.py    # Alembic миграция (chains, nodes, edges, conditions)
│   ├── models.py                       # Pydantic модели
│   └── router.py                       # FastAPI роутер (CRUD + /graph эндпоинт)
│
├── phase2_frontend_editor/             # Фаза 2: Визуальный редактор
│   └── phase2_chain_editor.jsx        # React компонент (готовый артефакт)
│
└── phase3_executor_engine/             # Фаза 3: Движок выполнения
    ├── 002_create_chain_sessions.py   # Alembic миграция (sessions)
    ├── session_models.py               # Pydantic модели для сессий
    ├── conditions.py                   # Логика оценки условий
    ├── executor.py                     # ChainExecutor — ядро движка
    ├── tasks.py                        # Celery задачи (для Redis)
    └── bot_integration.py              # Пример интеграции с ботом

chain_builder_v2.jsx - UI для frontend
```

## 🚀 Быстрый старт

### 1. Фаза 1: База данных и API

#### Запуск миграций

```bash
# Подключите миграцию к вашему Alembic
# В файле 001_create_chains_schema.py замените:
# down_revision = None  →  down_revision = "<your_current_head>"

alembic revision --rev-id 001_chains
# Скопируйте содержимое 001_create_chains_schema.py в созданный файл
alembic upgrade head
```

#### Подключение API роутера

```python
# В вашем main FastAPI приложении:
from phase1_db_and_api.router import router as chains_router

app.include_router(chains_router)
```

**Важно:** В `router.py` обновите импорты:
- `from ..auth.dependencies import get_tenant_id`  →  ваша функция аутентификации
- `from ..db.dependencies import get_db`  →  ваша функция подключения к БД

#### API эндпоинты

После запуска доступны:

```
GET    /api/chains/                     # Список цепочек
POST   /api/chains/                     # Создать цепочку
GET    /api/chains/{id}                 # Детали цепочки
PATCH  /api/chains/{id}                 # Обновить цепочку
DELETE /api/chains/{id}                 # Удалить цепочку

GET    /api/chains/{id}/graph           # Полный граф (для редактора) ⭐
POST   /api/chains/{id}/nodes           # Создать узел
PATCH  /api/chains/{id}/nodes/{node_id} # Обновить узел
DELETE /api/chains/{id}/nodes/{node_id} # Удалить узел

POST   /api/chains/{id}/edges           # Создать ребро
DELETE /api/chains/{id}/edges/{edge_id} # Удалить ребро

POST   /api/chains/{id}/edges/{edge_id}/conditions     # Добавить условие
DELETE /api/chains/{id}/edges/{edge_id}/conditions/{c_id} # Удалить условие
```

### 2. Фаза 2: Frontend редактор

#### Интеграция в Next.js

```bash
# Скопируйте компонент в ваш проект
cp phase2_frontend_editor/phase2_chain_editor.jsx \
   your-nextjs-app/components/ChainEditor.jsx
```

#### Замена mock API на реальный

В `ChainEditor.jsx` найдите `mockApi` и замените на:

```javascript
const api = {
  loadGraph: (chainId) => 
    fetch(`/api/chains/${chainId}/graph`).then(r => r.json()),
  
  saveGraph: (chainId, graph) =>
    fetch(`/api/chains/${chainId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(graph)
    }).then(r => r.json()),
};
```

#### Использование компонента

```jsx
import ChainEditor from '@/components/ChainEditor';

function ChainEditorPage({ chainId }) {
  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <ChainEditor chainId={chainId} />
    </div>
  );
}
```

### 3. Фаза 3: Движок выполнения

#### Миграция сессий

```bash
alembic revision --rev-id 002_chain_sessions
# Скопируйте содержимое 002_create_chain_sessions.py
alembic upgrade head
```

#### Установка зависимостей

```bash
pip install celery redis python-telegram-bot asyncpg
```

#### Настройка Celery

Обновите `phase3_executor_engine/tasks.py`:

```python
# Замените эти импорты на ваши реальные:
from executor import ChainExecutor
from your_db import get_db
from your_bot import send_telegram_message
```

#### Запуск Celery worker

```bash
# В директории с tasks.py:
celery -A tasks worker --loglevel=info --concurrency=4
```

#### Интеграция с ботом

Пример интеграции в `bot_integration.py`. Основные точки подключения:

```python
from executor import ChainExecutor
from conditions import telegram_message_to_dict
from tasks import schedule_delayed_message, schedule_timeout_check

# При получении сообщения:
async def message_handler(update: Update, context):
    user_id = update.effective_user.id
    tenant_id = await get_user_tenant(user_id)
    
    user_message = telegram_message_to_dict(update.to_dict())
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        result = await executor.process_user_message(
            user_id=user_id,
            tenant_id=tenant_id,
            user_message=user_message
        )
        
        # Отправить сообщения
        for action in result['actions']:
            if action['delay_seconds'] > 0:
                schedule_delayed_message(...)
            else:
                await send_immediately(action)
```

## 📊 Архитектура

### База данных (schema: `chains`)

```
chains
  ├── chains              # Основная таблица цепочек
  ├── chain_nodes         # Узлы (сообщения)
  ├── chain_edges         # Рёбра (переходы)
  ├── chain_conditions    # Условия на рёбрах
  └── chain_sessions      # Сессии выполнения (где юзер сейчас)
```

### Изоляция по tenant

Все таблицы связаны с `public.core_client(id)` через `tenant_id`. Каждый запрос автоматически фильтруется по текущему tenant через `get_tenant_id()` dependency.

### Типы узлов

- **text** — текстовое сообщение
  ```json
  { "text": "Привет!" }
  ```

- **photo** — фото с подписью
  ```json
  { "photo_url": "https://...", "caption": "Описание" }
  ```

- **buttons** — текст + inline кнопки
  ```json
  { "text": "Выберите:", "buttons": ["Да", "Нет"] }
  ```

### Типы условий

- **button_press** — юзер нажал кнопку
  ```json
  { "button_label": "Да" }
  ```

- **text_contains** — текст содержит подстроку
  ```json
  { "substring": "да", "case_sensitive": false }
  ```

- **text_regex** — текст соответствует regex
  ```json
  { "pattern": "^да$", "flags": "i" }
  ```

- **timeout** — юзер не ответил за N секунд
  ```json
  { "timeout_seconds": 300 }
  ```

- **any_reply** — любой ответ юзера (catch-all)
  ```json
  {}
  ```

### Поток выполнения

1. **Tenant создаёт цепочку** в редакторе (фаза 2)
2. **Бот запускает цепочку** для юзера → `executor.start_chain()`
3. **Executor создаёт session** и отправляет первое сообщение
4. **Юзер отвечает** → `executor.process_user_message()`
5. **Executor оценивает условия** на рёбрах → находит подходящее
6. **Переход на следующий узел** → отправка сообщения (с задержкой или сразу)
7. Повторяется до завершения цепочки

## 🔧 Конфигурация

### Celery + Redis

В `tasks.py` настройки по умолчанию:

```python
app = Celery(
    'telegram_chains',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
)
```

Для production измените на ваш Redis:

```python
broker='redis://your-redis-host:6379/0'
```

### Database

Подключите ваш async PostgreSQL connection pool в `get_db()`:

```python
# Пример с asyncpg:
import asyncpg

async def get_db():
    conn = await asyncpg.connect(
        host='localhost',
        database='your_db',
        user='user',
        password='password'
    )
    try:
        yield conn
    finally:
        await conn.close()
```

### Telegram Bot

В `bot_integration.py` замените placeholder на ваш бот:

```python
from your_bot import bot

async def send_telegram_message(user_id: int, **kwargs):
    if 'text' in kwargs:
        await bot.send_message(user_id, text=kwargs['text'])
    elif 'photo' in kwargs:
        await bot.send_photo(user_id, photo=kwargs['photo'], ...)
```

## 🧪 Тестирование

### 1. Проверка API

```bash
# Создать цепочку
curl -X POST http://localhost:8000/api/chains/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name":"Test Chain","description":"Testing"}'

# Получить граф
curl http://localhost:8000/api/chains/1/graph \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Тест редактора

1. Откройте редактор в браузере
2. Добавьте несколько узлов (двойной клик на канвас)
3. Соедините их (правый клик → "Провести ребро")
4. Добавьте условия (клик на ребро)
5. Сохраните (кнопка "Сохранить")

### 3. Тест выполнения

```python
# В Python shell:
from executor import ChainExecutor
from your_db import get_db

async def test():
    async with get_db() as db:
        executor = ChainExecutor(db)
        
        # Запустить цепочку
        result = await executor.start_chain(
            user_id=12345,
            chain_id=1,
            tenant_id=1
        )
        print(result)

import asyncio
asyncio.run(test())
```

### 4. Тест бота

1. Запустите Celery worker
2. Запустите бота
3. Отправьте `/start` боту
4. Проверьте, что пришло первое сообщение цепочки
5. Ответьте на сообщение → проверьте переход

## 📝 Валидация цепочки

Редактор автоматически проверяет:

- ✅ Есть ли стартовый узел
- ✅ Нет ли сиротских узлов (без входящих рёбер)
- ✅ Все ли кнопки обработаны условиями
- ✅ Нет ли тупиков (узлов без выходящих рёбер, кроме листьев)

Валидация запускается по кнопке "Валидация" или автоматически перед сохранением.

## 🔍 Мониторинг

### Celery Flower

```bash
pip install flower
celery -A tasks flower --port=5555

# Открыть http://localhost:5555
```

### Логи выполнения

```python
# В executor.py уже встроено логирование:
logger.info(f"Advanced session {session_id} to node {node_id}")
logger.warning(f"No matching edge from node {current_node_id}")
```

### Проверка сессий

```sql
-- Активные сессии
SELECT s.id, s.user_id, c.name as chain_name, s.current_node_id, s.last_activity_at
FROM chains.chain_sessions s
JOIN chains.chains c ON c.id = s.chain_id
WHERE s.status = 'active'
ORDER BY s.last_activity_at DESC;

-- Застрявшие сессии (не обновлялись > 1 часа)
SELECT * FROM chains.chain_sessions
WHERE status = 'active' 
  AND last_activity_at < now() - interval '1 hour';
```

## 🐛 Troubleshooting

### Сообщения не отправляются с задержкой

Проверьте:
1. Celery worker запущен
2. Redis доступен
3. В логах Celery нет ошибок
4. `schedule_delayed_message()` вызывается в executor.py

### Условия не срабатывают

Проверьте:
1. Формат user_message соответствует ожидаемому в `conditions.py`
2. Условие правильно настроено в редакторе
3. Логи executor показывают какое условие оценивается

### Юзер застрял в цепочке

```sql
-- Сбросить сессию
UPDATE chains.chain_sessions
SET status = 'paused'
WHERE user_id = 12345 AND status = 'active';
```

### Граф не загружается в редакторе

1. Проверьте `/api/chains/{id}/graph` возвращает корректный JSON
2. Убедитесь что tenant_id соответствует
3. Проверьте CORS настройки если фронт на другом домене

## 📚 Дополнительные возможности

### Аналитика

Добавьте в `chain_sessions.context`:

```json
{
  "answers": {
    "1": {"text": "да"},
    "2": {"button": "Продукт"}
  },
  "timestamps": {
    "node_1": "2025-02-03T10:00:00Z",
    "node_2": "2025-02-03T10:00:15Z"
  },
  "custom_data": {
    "utm_source": "facebook",
    "user_segment": "vip"
  }
}
```

### Шаблоны цепочек

Добавьте поле `is_template` в `chains.chains` и функцию клонирования:

```sql
INSERT INTO chains.chains (tenant_id, name, description, ...)
SELECT tenant_id, name || ' (копия)', description, ...
FROM chains.chains WHERE id = $1;
```

### API-триггеры

Добавьте эндпоинт для внешних систем:

```python
@router.post("/api/chains/trigger")
async def trigger_chain(
    user_id: int,
    chain_id: int,
    tenant_id: int = Depends(get_tenant_id)
):
    """Запуск цепочки по внешнему API вызову (из CRM, вебхука и т.д.)"""
    executor = ChainExecutor(db)
    return await executor.start_chain(user_id, chain_id, tenant_id)
```

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте логи Celery и FastAPI
2. Проверьте таблицу `chain_sessions` в БД
3. Убедитесь что все миграции применены
4. Проверьте Redis подключение

## 📄 Лицензия

MIT

---

**Создано с ❤️ для вашей multitenant маркетинговой платформы**
