# Phase 2: Frontend Editor

Визуальный редактор цепочек с drag & drop узлами и рёбрами.

## Файлы

- `phase2_chain_editor.jsx` — React компонент редактора

## Возможности

- 🎨 **Визуальное редактирование** — drag & drop узлы, рисование рёбер
- 🔗 **Соединения** — правый клик → "Провести ребро" или режим соединения
- ⚙️ **Модальные окна** — редактирование узлов и условий
- ✅ **Валидация** — проверка графа перед сохранением
- 💾 **Автосохранение** — отслеживание изменений (dirty state)
- 🎯 **Типы узлов** — текст, фото, кнопки
- 🔀 **Условия** — button_press, text_contains, regex, timeout, any_reply

## Установка в Next.js

### 1. Скопировать файл

```bash
cp phase2_chain_editor.jsx your-nextjs-app/components/ChainEditor.jsx
```

### 2. Создать страницу

```jsx
// app/chains/[id]/edit/page.tsx
'use client';

import ChainEditor from '@/components/ChainEditor';

export default function ChainEditorPage({ params }) {
  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <ChainEditor chainId={params.id} />
    </div>
  );
}
```

### 3. Подключить API

В `ChainEditor.jsx` найдите `mockApi` (строка ~40) и замените на:

```javascript
const api = {
  loadGraph: async (chainId) => {
    const res = await fetch(`/api/chains/${chainId}/graph`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.json();
  },
  
  saveGraph: async (chainId, graph) => {
    // Сохранение происходит через отдельные CRUD операции:
    // 1. UPDATE nodes (изменённые позиции, payload)
    // 2. CREATE/DELETE edges
    // 3. UPDATE edge conditions
    
    // Для простоты можно делать batch update (если добавить такой эндпоинт в API):
    const res = await fetch(`/api/chains/${chainId}/batch-update`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(graph)
    });
    return res.json();
  }
};
```

## Использование

### Основные действия

| Действие | Как |
|----------|-----|
| Добавить узел | Двойной клик на канвас ИЛИ кнопка "+ Узел" |
| Переместить узел | Тянуть мышкой |
| Редактировать узел | Правый клик → "Редактировать" |
| Провести ребро | Правый клик на узле → "Провести ребро" → кликнуть целевой узел |
| Условия на ребре | Кликнуть на ребро |
| Удалить узел | Правый клик → "Удалить" |
| Сделать стартовым | Правый клик → "Сделать стартом" |
| Валидация | Кнопка "Валидация" в тулбаре |
| Сохранить | Кнопка "Сохранить" (активна при изменениях) |

### Навигация

- **Пэн** — тянуть за пустое место канваса
- **Зум** — пока не реализован (можно добавить через wheel event)

## Компоненты

### Главный компонент

```jsx
<ChainBuilder chainId={1} />
```

### Структура состояния

```javascript
const state = {
  chain: {
    id: 1,
    name: "Onboarding",
    status: "draft",
    start_node_id: 1
  },
  nodes: [
    {
      id: 1,
      node_type: "text",
      payload: { text: "Привет!" },
      delay_seconds: 0,
      pos_x: 100,
      pos_y: 100
    }
  ],
  edges: [
    {
      id: 10,
      source_node_id: 1,
      target_node_id: 2,
      priority: 0,
      conditions: [
        {
          id: 30,
          condition_type: "button_press",
          params: { button_label: "Да" }
        }
      ]
    }
  ],
  dirty: false  // true если есть несохранённые изменения
};
```

### Reducer actions

```javascript
// Узлы
dispatch({ type: "ADD_NODE", x: 100, y: 100 })
dispatch({ type: "MOVE_NODE", id: 1, x: 150, y: 150 })
dispatch({ type: "UPDATE_NODE", id: 1, data: { payload: {...} } })
dispatch({ type: "DELETE_NODE", id: 1 })

// Рёбра
dispatch({ type: "ADD_EDGE", source: 1, target: 2 })
dispatch({ type: "DELETE_EDGE", id: 10 })
dispatch({ type: "UPDATE_EDGE_CONDITIONS", edgeId: 10, conditions: [...] })

// Цепочка
dispatch({ type: "SET_START_NODE", id: 1 })
dispatch({ type: "SET_STATUS", status: "active" })

// Сохранение
dispatch({ type: "SAVED" })
```

## Кастомизация

### Цвета узлов

В файле `NODE_COLORS`:

```javascript
const NODE_COLORS = {
  text:    { bg: "#134e4a", border: "#2dd4bf", accent: "#2dd4bf" },
  photo:   { bg: "#4a3a14", border: "#fbbf24", accent: "#fbbf24" },
  buttons: { bg: "#1e1b4b", border: "#818cf8", accent: "#818cf8" },
};
```

### Размер узлов

```javascript
const NODE_W = 180;
const NODE_H = 90;
```

### Тема

Сейчас тёмная тема. Для светлой замените:

```javascript
background: "#0f1117"  →  "#ffffff"
color: "#e2e8f0"       →  "#1a1a1a"
// и т.д.
```

## Валидация

Редактор проверяет:

- ✅ **Стартовый узел** — должен быть выбран
- ✅ **Сиротские узлы** — узлы без входящих рёбер (кроме стартового)
- ✅ **Необработанные кнопки** — если узел типа "buttons", все кнопки должны быть обработаны условиями
- ✅ **Fallback рёбра** — рёбра без условий помечаются как default

Ошибки показываются в панели валидации (кнопка "Валидация").

## Горячие клавиши

Можно добавить:

```javascript
useEffect(() => {
  const handleKeyPress = (e) => {
    if (e.key === 's' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === 'Delete' && selectedNode) {
      dispatch({ type: "DELETE_NODE", id: selectedNode.id });
    }
  };
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

## Экспорт/Импорт

Добавьте кнопки в тулбар:

```javascript
const exportChain = () => {
  const json = JSON.stringify(state, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chain-${state.chain.id}.json`;
  a.click();
};

const importChain = (file) => {
  const reader = new FileReader();
  reader.onload = (e) => {
    const data = JSON.parse(e.target.result);
    dispatch({ type: "LOAD", payload: data });
  };
  reader.readAsText(file);
};
```

## Troubleshooting

### Канвас не рендерится

Проверьте что родительский элемент имеет фиксированную высоту:

```jsx
<div style={{ height: '100vh' }}>
  <ChainEditor />
</div>
```

### Сохранение не работает

1. Проверьте что API эндпоинт `/api/chains/{id}/graph` доступен
2. Проверьте CORS если фронт на другом домене
3. Откройте DevTools → Network и посмотрите ответ сервера

### Рёбра рисуются криво

SVG пути вычисляются в `getEdgePath()`. Если у вас другая раскладка узлов, измените формулу:

```javascript
function getEdgePath(srcNode, tgtNode) {
  // Текущая: выход снизу источника, вход сверху цели
  // Можно изменить на боковые выходы и т.д.
}
```
