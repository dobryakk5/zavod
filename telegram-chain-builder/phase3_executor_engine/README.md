# Phase 3: Executor Engine

Движок выполнения цепочек — state machine, условия, задержки, интеграция с ботом.

## Файлы

- `002_create_chain_sessions.py` — Alembic миграция (sessions)
- `session_models.py` — Pydantic модели для сессий
- `conditions.py` — Логика оценки условий
- `executor.py` — ChainExecutor класс (ядро движка)
- `tasks.py` — Celery задачи (для Celery + Redis)
- `bot_integration.py` — Пример интеграции с python-telegram-bot

## Установка

### 1. Миграция

```bash
# В файле 002_create_chain_sessions.py замените:
# down_revision = "001_chains"
# на ваш текущий head

alembic upgrade head
```

### 2. Зависимости

```bash
pip install celery redis python-telegram-bot asyncpg
```

### 3. Настройка Celery

#### Опция A: Использовать готовый tasks.py

Отредактируйте `tasks.py`:

```python
# Замените импорты на ваши:
from executor import ChainExecutor
from your_db import get_db  # async DB connection
from your_bot import send_telegram_message  # бот send функция
```

#### Опция B: Создать свой celery_config.py

```python
# celery_config.py
from celery import Celery

app = Celery(
    'telegram_chains',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
)

app.conf.update(
    task_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
```

### 4. Запуск Celery worker

```bash
# В директории с tasks.py:
celery -A tasks worker --loglevel=info --concurrency=4

# Для production с systemd:
sudo systemctl start celery-chains
```

### 5. Интеграция с ботом

См. `bot_integration.py` для полного примера. Основное:

```python
from executor import ChainExecutor
from conditions import telegram_message_to_dict
from tasks import schedule_delayed_message, schedule_timeout_check

# При /start:
async with get_db() as db:
    executor = ChainExecutor(db)
    result = await executor.start_chain(user_id, chain_id, tenant_id)
    await execute_actions(result['actions'])

# При сообщении:
user_message = telegram_message_to_dict(update.to_dict())
result = await executor.process_user_message(user_id, tenant_id, user_message)
await execute_actions(result['actions'])
```

## Архитектура

### ChainExecutor

Главный класс движка:

```python
executor = ChainExecutor(db)

# Запустить цепочку
result = await executor.start_chain(
    user_id=12345,
    chain_id=1,
    tenant_id=1
)
# → { "session_id": 100, "actions": [...] }

# Обработать сообщение
result = await executor.process_user_message(
    user_id=12345,
    tenant_id=1,
    user_message={"text": "да"}
)
# → { "session_id": 100, "actions": [...], "session_status": "active" }

# Обработать таймаут
result = await executor.process_timeout(session_id=100, edge_id=10)
# → { "actions": [...] }
```

### Actions

Executor возвращает список действий для бота:

```python
[
  {
    "action_type": "send_text",
    "payload": {"text": "Привет!"},
    "delay_seconds": 0
  },
  {
    "action_type": "send_photo",
    "payload": {"photo_url": "...", "caption": "..."},
    "delay_seconds": 3
  },
  {
    "action_type": "send_buttons",
    "payload": {"text": "Выберите:", "buttons": ["A", "B"]},
    "delay_seconds": 0
  },
  {
    "action_type": "schedule_timeout",
    "payload": {
      "session_id": 100,
      "edge_id": 10,
      "timeout_seconds": 300
    },
    "delay_seconds": 0
  }
]
```

### Condition Evaluation

```python
from conditions import evaluate_conditions

edge_conditions = [
  {
    "condition_type": "button_press",
    "params": {"button_label": "Да"}
  }
]

user_message = {"button": "Да"}
session_context = {"answers": {...}}

if evaluate_conditions(edge_conditions, user_message, session_context):
    # Условие выполнено → переход по ребру
    pass
```

## Типы условий

### button_press

```python
{
  "condition_type": "button_press",
  "params": {"button_label": "Продукт"}
}

# Срабатывает на:
{"button": "Продукт"}
```

### text_contains

```python
{
  "condition_type": "text_contains",
  "params": {
    "substring": "да",
    "case_sensitive": False
  }
}

# Срабатывает на:
{"text": "Да, конечно"}
{"text": "ДА"}
```

### text_regex

```python
{
  "condition_type": "text_regex",
  "params": {
    "pattern": "^да$",
    "flags": "i"  # i = ignorecase, m = multiline, s = dotall
  }
}

# Срабатывает на:
{"text": "да"}
{"text": "Да"}
```

### timeout

```python
{
  "condition_type": "timeout",
  "params": {"timeout_seconds": 300}
}

# Срабатывает автоматически через 300 секунд если юзер не ответил
```

### any_reply

```python
{
  "condition_type": "any_reply",
  "params": {}
}

# Срабатывает на любое сообщение (catch-all)
```

## Session Context

Каждая сессия хранит JSONB контекст:

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
  "custom": {
    "utm_source": "facebook",
    "user_segment": "vip"
  }
}
```

Можно использовать в будущем для:
- Аналитики (где юзеры застревают)
- Персонализации (вставлять имя в текст)
- A/B тестов (разные варианты цепочек)

## Celery Tasks

### send_delayed_message

Отправляет сообщение с задержкой:

```python
from tasks import schedule_delayed_message

schedule_delayed_message(
    session_id=100,
    node_id=5,
    delay_seconds=10
)
```

Celery автоматически:
1. Ждёт 10 секунд
2. Проверяет что сессия всё ещё на узле 5
3. Отправляет сообщение через бота

### check_timeout

Проверяет таймаут:

```python
from tasks import schedule_timeout_check

schedule_timeout_check(
    session_id=100,
    edge_id=10,
    timeout_seconds=300
)
```

Celery автоматически:
1. Ждёт 300 секунд
2. Проверяет что юзер не ответил
3. Вызывает `executor.process_timeout()`
4. Отправляет сообщения из следующего узла

## Мониторинг

### Celery Flower

```bash
pip install flower
celery -A tasks flower --port=5555

# Открыть http://localhost:5555
```

### Активные сессии

```sql
SELECT 
    s.id,
    s.user_id,
    c.name as chain_name,
    n.payload->>'text' as current_message,
    s.last_activity_at
FROM chains.chain_sessions s
JOIN chains.chains c ON c.id = s.chain_id
LEFT JOIN chains.chain_nodes n ON n.id = s.current_node_id
WHERE s.status = 'active'
ORDER BY s.last_activity_at DESC;
```

### Застрявшие сессии

```sql
SELECT * FROM chains.chain_sessions
WHERE status = 'active'
  AND last_activity_at < now() - interval '1 hour';

-- Можно сбросить:
UPDATE chains.chain_sessions
SET status = 'paused'
WHERE id IN (...);
```

## Интеграция с существующим ботом

### python-telegram-bot

См. `bot_integration.py` — полный рабочий пример.

### aiogram

```python
from aiogram import Bot, Dispatcher, types
from executor import ChainExecutor

@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    tenant_id = await get_user_tenant(user_id)
    
    user_message = {"text": message.text}
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        result = await executor.process_user_message(
            user_id, tenant_id, user_message
        )
        
        for action in result['actions']:
            if action['delay_seconds'] > 0:
                schedule_delayed_message(...)
            else:
                await execute_action(action, message.chat.id)
```

### telebot

```python
from telebot.async_api import AsyncTeleBot
from executor import ChainExecutor

@bot.message_handler(func=lambda m: True)
async def handle_message(message):
    user_id = message.from_user.id
    tenant_id = await get_user_tenant(user_id)
    
    user_message = {"text": message.text}
    
    async with get_db() as db:
        executor = ChainExecutor(db)
        result = await executor.process_user_message(
            user_id, tenant_id, user_message
        )
        
        for action in result['actions']:
            # ... handle actions
```

## Тестирование

### Тест executor

```python
import pytest
from executor import ChainExecutor

@pytest.mark.asyncio
async def test_start_chain(db):
    executor = ChainExecutor(db)
    
    result = await executor.start_chain(
        user_id=12345,
        chain_id=1,
        tenant_id=1
    )
    
    assert result['session_id'] > 0
    assert len(result['actions']) > 0
    assert result['actions'][0]['action_type'] == 'send_text'

@pytest.mark.asyncio
async def test_process_message(db):
    # Создать тестовую сессию
    # ...
    
    executor = ChainExecutor(db)
    result = await executor.process_user_message(
        user_id=12345,
        tenant_id=1,
        user_message={"button": "Продукт"}
    )
    
    assert result['session_status'] == 'active'
    assert len(result['actions']) > 0
```

### Тест условий

```python
from conditions import evaluate_conditions

def test_button_press():
    conditions = [
        {
            "condition_type": "button_press",
            "params": {"button_label": "Да"}
        }
    ]
    
    assert evaluate_conditions(conditions, {"button": "Да"}, {})
    assert not evaluate_conditions(conditions, {"button": "Нет"}, {})

def test_text_contains():
    conditions = [
        {
            "condition_type": "text_contains",
            "params": {"substring": "да", "case_sensitive": False}
        }
    ]
    
    assert evaluate_conditions(conditions, {"text": "Да, конечно"}, {})
    assert evaluate_conditions(conditions, {"text": "ДА"}, {})
    assert not evaluate_conditions(conditions, {"text": "Нет"}, {})
```

## Troubleshooting

### Сообщения не отправляются

1. Проверьте Celery worker запущен
2. Проверьте Redis доступен: `redis-cli ping`
3. Посмотрите логи Celery
4. Проверьте `schedule_delayed_message()` вызывается

### Условия не срабатывают

1. Проверьте формат `user_message` в логах
2. Добавьте логирование в `conditions.py`:
   ```python
   logger.debug(f"Evaluating {cond_type}: {params} against {user_message}")
   ```
3. Проверьте что условие правильно сохранено в БД

### Таймауты не срабатывают

1. Проверьте что `schedule_timeout_check()` вызывается
2. Проверьте Celery worker обрабатывает задачи
3. Проверьте в Flower что задачи в очереди

### Session не создаётся

Проверьте:
1. `chain.start_node_id` установлен (не NULL)
2. tenant_id корректный
3. В логах нет ошибок БД

## Production Deployment

### Systemd service для Celery

```ini
# /etc/systemd/system/celery-chains.service
[Unit]
Description=Celery Worker for Telegram Chains
After=network.target

[Service]
Type=forking
User=your_user
Group=your_group
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A tasks worker \
    --loglevel=info \
    --concurrency=4 \
    --pidfile=/var/run/celery/chains.pid \
    --logfile=/var/log/celery/chains.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable celery-chains
sudo systemctl start celery-chains
sudo systemctl status celery-chains
```

### Мониторинг

```bash
# Логи
tail -f /var/log/celery/chains.log

# Статус очереди
celery -A tasks inspect active

# Число рабочих
celery -A tasks inspect stats
```

### Масштабирование

Для высоких нагрузок:

```bash
# Запустить несколько workers
celery -A tasks worker --concurrency=8 -n worker1@%h
celery -A tasks worker --concurrency=8 -n worker2@%h

# Или использовать autoscale
celery -A tasks worker --autoscale=10,3
```
