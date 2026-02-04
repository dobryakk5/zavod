# Phase 1: Database & API

База данных и REST API для управления цепочками.

## Файлы

- `001_create_chains_schema.py` — Alembic миграция (chains, nodes, edges, conditions)
- `models.py` — Pydantic модели
- `router.py` — FastAPI роутер

## Установка

### 1. Миграция базы данных

```bash
# В файле 001_create_chains_schema.py замените:
# down_revision = None
# на ваш текущий head:
# down_revision = "abc123def456"

# Запустите миграцию
alembic upgrade head
```

### 2. Подключение роутера

```python
# main.py
from phase1_db_and_api.router import router as chains_router

app = FastAPI()
app.include_router(chains_router)
```

### 3. Обновите импорты в router.py

Замените эти строки на ваши реальные функции:

```python
# Было:
from ..auth.dependencies import get_tenant_id
from ..db.dependencies import get_db

# Должно быть (пример):
from app.auth import get_current_tenant_id as get_tenant_id
from app.database import get_async_db as get_db
```

## API Endpoints

### Chains (цепочки)

```
GET    /api/chains/              # Список цепочек текущего tenant
POST   /api/chains/              # Создать цепочку
GET    /api/chains/{id}          # Детали цепочки
PATCH  /api/chains/{id}          # Обновить цепочку
DELETE /api/chains/{id}          # Удалить цепочку
GET    /api/chains/{id}/graph    # Полный граф для редактора ⭐
PATCH  /api/chains/{id}/start-node?node_id=X  # Установить стартовый узел
```

### Nodes (узлы)

```
GET    /api/chains/{id}/nodes           # Список узлов
POST   /api/chains/{id}/nodes           # Создать узел
PATCH  /api/chains/{id}/nodes/{node_id} # Обновить узел
DELETE /api/chains/{id}/nodes/{node_id} # Удалить узел
```

### Edges (рёбра)

```
GET    /api/chains/{id}/edges           # Список рёбер
POST   /api/chains/{id}/edges           # Создать ребро
PATCH  /api/chains/{id}/edges/{edge_id} # Обновить ребро
DELETE /api/chains/{id}/edges/{edge_id} # Удалить ребро
```

### Conditions (условия)

```
GET    /api/chains/{id}/edges/{edge_id}/conditions        # Список условий
POST   /api/chains/{id}/edges/{edge_id}/conditions        # Добавить условие
DELETE /api/chains/{id}/edges/{edge_id}/conditions/{c_id} # Удалить условие
```

## Примеры запросов

### Создать цепочку

```bash
curl -X POST http://localhost:8000/api/chains/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Onboarding",
    "description": "Приветственная цепочка",
    "status": "draft"
  }'
```

### Создать узел

```bash
curl -X POST http://localhost:8000/api/chains/1/nodes \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "node_type": "text",
    "payload": {"text": "Привет!"},
    "delay_seconds": 0,
    "pos_x": 100,
    "pos_y": 100
  }'
```

### Получить полный граф

```bash
curl http://localhost:8000/api/chains/1/graph \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Ответ:
```json
{
  "chain": {
    "id": 1,
    "name": "Onboarding",
    "start_node_id": 1,
    ...
  },
  "nodes": [
    {
      "id": 1,
      "node_type": "text",
      "payload": {"text": "Привет!"},
      ...
    }
  ],
  "edges": [
    {
      "id": 10,
      "source_node_id": 1,
      "target_node_id": 2,
      "conditions": [
        {
          "id": 30,
          "condition_type": "button_press",
          "params": {"button_label": "Да"}
        }
      ]
    }
  ]
}
```

## Схема БД

```sql
chains.chains
  ├── id (BIGSERIAL)
  ├── tenant_id (BIGINT) → public.core_client(id)
  ├── name (VARCHAR)
  ├── description (TEXT)
  ├── status (VARCHAR) — draft | active | paused | archived
  ├── start_node_id (BIGINT) → chain_nodes(id)
  └── timestamps

chains.chain_nodes
  ├── id (BIGSERIAL)
  ├── chain_id (BIGINT) → chains(id)
  ├── node_type (VARCHAR) — text | photo | buttons
  ├── payload (JSONB)
  ├── delay_seconds (INTEGER)
  ├── pos_x, pos_y (FLOAT) — позиция в редакторе
  └── timestamps

chains.chain_edges
  ├── id (BIGSERIAL)
  ├── chain_id (BIGINT) → chains(id)
  ├── source_node_id (BIGINT) → chain_nodes(id)
  ├── target_node_id (BIGINT) → chain_nodes(id)
  ├── priority (INTEGER) — порядок проверки условий
  └── timestamps

chains.chain_conditions
  ├── id (BIGSERIAL)
  ├── edge_id (BIGINT) → chain_edges(id)
  ├── condition_type (VARCHAR)
  ├── params (JSONB)
  └── created_at
```

## Валидация

API автоматически проверяет:
- Tenant isolation (все запросы фильтруются по tenant_id)
- Node принадлежит chain
- Edge соединяет узлы одной цепочки
- Нет дублирующих рёбер между одними и теми же узлами

## Тестирование

```python
# test_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_chain(client: AsyncClient):
    response = await client.post(
        "/api/chains/",
        json={"name": "Test", "description": "Test chain"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test"

@pytest.mark.asyncio
async def test_get_graph(client: AsyncClient):
    # Создать тестовую цепочку с узлами и рёбрами
    # ...
    
    response = await client.get("/api/chains/1/graph")
    assert response.status_code == 200
    data = response.json()
    assert "chain" in data
    assert "nodes" in data
    assert "edges" in data
```

## Troubleshooting

### 404 Not Found на всех эндпоинтах

Проверьте что роутер подключён к приложению:
```python
app.include_router(chains_router)
```

### 403 Forbidden

Проверьте что `get_tenant_id()` dependency работает корректно и возвращает tenant_id.

### 500 Internal Server Error

Проверьте логи FastAPI и убедитесь что:
- БД подключение работает
- Миграции применены
- Импорты корректны
