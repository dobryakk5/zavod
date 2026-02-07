# 🏗️ Общая архитектура: ChainBuilder + MindMap

## 📦 Структура проекта

```
project/
├── shared/                      # Общие компоненты для обоих проектов
│   ├── components.js           # Alert, Card, Label, LoadingSpinner, etc.
│   └── hooks.js                # useAutoSave, useIsMobile, useDragAndDrop
│
├── chain-builder/              # ChainBuilder (чат-боты)
│   ├── ChainBuilder.jsx        # Главный компонент
│   ├── constants.js            # NODE_COLORS, CONDITION_LABELS
│   ├── utils.js                # formatTime, getNodeHeight
│   ├── reducer.js              # graphReducer
│   ├── mockApi.js              # API layer
│   └── components/
│       ├── Toolbar.jsx
│       ├── NodeCard.jsx
│       ├── EdgeLine.jsx
│       ├── NodeEditorModal.jsx
│       └── ContextMenuAdvanced.jsx
│
└── mindmap/                    # MindMap (карты знаний)
    ├── EditNodePage.jsx        # Главный компонент
    ├── utils.js                # toDrafts, extractProductId
    └── components/
        ├── NodeForm.jsx
        ├── PropertyRow.jsx
        └── PropertiesList.jsx
```

---

## 🔄 Shared Components

### Компоненты используемые в обоих проектах:

| Компонент | ChainBuilder | MindMap | Назначение |
|-----------|--------------|---------|------------|
| `Alert` | ✅ | ✅ | Уведомления (error/success/info) |
| `LoadingSpinner` | ✅ | ✅ | Индикатор загрузки |
| `Card` | ✅ | ✅ | Карточки контента |
| `Label` | ✅ | ✅ | Подписи к полям |
| `EmptyState` | ✅ | ✅ | Пустые состояния |
| `DraggableItem` | ✅ | ✅ | Wrapper для D&D |
| `SaveButton` | ✅ | ✅ | Кнопка сохранения |

### Хуки используемые в обоих проектах:

| Хук | ChainBuilder | MindMap | Назначение |
|-----|--------------|---------|------------|
| `useAutoSave` | ✅ | ✅ | Автосохранение с debounce |
| `useIsMobile` | ✅ | ✅ | Адаптивность |
| `useTemporaryMessage` | ✅ | ✅ | Временные уведомления |
| `useAsyncStatus` | ✅ | ✅ | Управление состояниями |
| `useDragAndDrop` | ✅ | ✅ | Переупорядочивание |

---

## 📊 Сравнение архитектур

### ChainBuilder (Граф чат-бота)

**Особенности:**
- Canvas с drag & drop узлов
- Визуальные связи между узлами
- 3 типа узлов: message, router, timer
- Условия маршрутизации
- Контекстное меню с выбором цвета

**Структура данных:**
```javascript
{
  chain: { id, name, status, start_node_id },
  nodes: [
    { 
      id, 
      node_type: 'message',
      payload: { content_type, text },
      pos_x, 
      pos_y 
    }
  ],
  edges: [
    { 
      id, 
      source_node_id, 
      target_node_id, 
      route_id 
    }
  ]
}
```

### MindMap (Карта знаний)

**Особенности:**
- Редактор одного узла
- Свойства с drag & drop
- Автосохранение полей
- Валидация данных
- Интеграция с product

**Структура данных:**
```javascript
{
  map: { id, name },
  nodes: [
    {
      id,
      text,
      meta: { entity, metric_type },
      properties: [
        { id, title, value, delta, order_index }
      ]
    }
  ]
}
```

---

## 🎯 Что общего

### 1. Автосохранение
Оба проекта используют `useAutoSave` с 500ms debounce:

```javascript
// ChainBuilder
useAutoSave(state, async (data) => {
  await mockApi.saveGraph(data);
}, 500);

// MindMap
useAutoSave({ title, typeLabel }, async (data) => {
  await mindMapsApi.updateNode(nodeId, data);
}, 500);
```

### 2. Drag & Drop
Оба проекта используют `useDragAndDrop`:

```javascript
// ChainBuilder - переупорядочивание условий router
const { draggedItem, handleDragStart, handleDrop } = useDragAndDrop(
  routes, 
  setRoutes
);

// MindMap - переупорядочивание свойств
const { draggedItem, handleDragStart, handleDrop } = useDragAndDrop(
  properties, 
  setProperties
);
```

### 3. Адаптивность
Оба используют `useIsMobile` для mobile/desktop:

```javascript
const isMobile = useIsMobile();

return isMobile ? (
  <FullscreenView>{content}</FullscreenView>
) : (
  <ModalView>{content}</ModalView>
);
```

### 4. Уведомления
Оба используют `Alert` и `useTemporaryMessage`:

```javascript
const [success, showSuccess] = useTemporaryMessage(3000);

showSuccess('✓ Изменения сохранены');

{success && <Alert variant="success">{success}</Alert>}
```

---

## 🚀 Преимущества общей архитектуры

### ✅ DRY (Don't Repeat Yourself)
- Hooks написаны один раз, используются везде
- Компоненты переиспользуются
- Одинаковое поведение в обоих проектах

### ✅ Консистентность
- Одинаковый UX (автосохранение, drag & drop)
- Одинаковые компоненты (Alert, Card)
- Одинаковые паттерны (mobile/desktop)

### ✅ Легкость поддержки
- Исправление бага в shared → работает везде
- Добавление фичи в shared → доступно везде
- Одна документация на общие части

### ✅ Меньше кода
**Без shared:**
- ChainBuilder: 1400 строк
- MindMap: 570 строк
- **Итого: 1970 строк**

**С shared:**
- Shared: 300 строк
- ChainBuilder: 1100 строк (−300)
- MindMap: 280 строк (−290)
- **Итого: 1680 строк (−15%)**

---

## 📝 Как использовать

### 1. Установка shared
```bash
# Скопировать shared компоненты
cp -r shared/ your-project/
```

### 2. Использование в ChainBuilder
```javascript
import { Alert, LoadingSpinner } from '@/shared/components';
import { useAutoSave, useIsMobile } from '@/shared/hooks';

function ChainBuilder() {
  const [error, setError] = useState(null);
  const isMobile = useIsMobile();
  
  useAutoSave(state, saveState, 500);
  
  return (
    <>
      {error && <Alert variant="error">{error}</Alert>}
      {/* ... */}
    </>
  );
}
```

### 3. Использование в MindMap
```javascript
import { Alert, SaveButton } from '@/shared/components';
import { useDragAndDrop } from '@/shared/hooks';

function EditNodePage() {
  const { draggedItem, handleDragStart } = useDragAndDrop(
    properties, 
    setProperties
  );
  
  return (
    <>
      {/* drag & drop items */}
      <SaveButton onClick={save} saving={saving} />
    </>
  );
}
```

---

## 🎨 Кастомизация

### Настройка shared компонентов

Если нужно изменить Alert для конкретного проекта:

```javascript
// project-specific/components/CustomAlert.jsx
import { Alert as SharedAlert } from '@/shared/components';

export function Alert({ children, variant }) {
  // Добавить проектную логику
  const icon = getProjectIcon(variant);
  
  return (
    <SharedAlert variant={variant}>
      {icon} {children}
    </SharedAlert>
  );
}
```

---

## 📚 Документация

- **shared/README.md** — документация по shared компонентам
- **chain-builder/README.md** — документация ChainBuilder
- **mindmap/README.md** — документация MindMap
- **SHARED_ARCHITECTURE.md** — этот файл

---

## 🔄 Миграция существующих проектов

### Шаг 1: Извлечь общий код
```bash
# Найти дубликаты
grep -r "useAutoSave" project1/ project2/
grep -r "Alert variant" project1/ project2/
```

### Шаг 2: Создать shared/
```bash
mkdir shared
touch shared/components.js
touch shared/hooks.js
```

### Шаг 3: Переместить код
```javascript
// Было в project1/hooks.js и project2/hooks.js
export function useAutoSave() { ... }

// Стало в shared/hooks.js
export function useAutoSave() { ... }
```

### Шаг 4: Обновить импорты
```javascript
// Было
import { useAutoSave } from './hooks';

// Стало
import { useAutoSave } from '@/shared/hooks';
```

---

## ✅ Checklist для новых фичей

Перед добавлением новой фичи:

- [ ] Нужна ли она в обоих проектах?
- [ ] Можно ли сделать её generic?
- [ ] Где лучше — в shared или project-specific?
- [ ] Документирована ли она?
- [ ] Есть ли примеры использования?

---

## 💡 Best Practices

### ✅ DO:
- Использовать shared для общего функционала
- Документировать API shared компонентов
- Делать shared компоненты generic
- Добавлять примеры использования

### ❌ DON'T:
- Добавлять project-specific логику в shared
- Делать shared компоненты слишком сложными
- Забывать обновлять документацию
- Копировать код вместо переиспользования

---

## 🎯 Roadmap

### Ближайшие планы:
- [ ] Добавить тесты для shared компонентов
- [ ] Создать Storybook для shared
- [ ] Добавить TypeScript типы
- [ ] Опубликовать shared как npm пакет

### Долгосрочные:
- [ ] Создать CLI для генерации shared компонентов
- [ ] Добавить визуальный редактор для shared
- [ ] Интеграция с design system
