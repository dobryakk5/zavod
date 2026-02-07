# MindMap Refactored

## 📊 Статистика рефакторинга

### До
```
mindmap_improved.tsx - 569 строк ❌
```

### После
```
mindmap-refactored/
├── types/
│   └── index.ts              (24 строки)
├── hooks/
│   └── index.ts              (102 строки)
├── utils/
│   └── index.ts              (84 строки)
├── components/
│   ├── Alert.tsx             (22 строки)
│   ├── Label.tsx             (19 строк)
│   ├── PropertyRow.tsx       (83 строки)
│   ├── NodeHeader.tsx        (33 строки)
│   ├── NodeFormFields.tsx    (52 строки)
│   ├── PropertiesSection.tsx (86 строк)
│   └── NodeFooter.tsx        (50 строк)
└── EditNodePage.tsx          (234 строки)
──────────────────────────────────────
ИТОГО: 789 строк в 11 файлах ✅
```

**Результат:**
- 📦 11 модулей вместо 1
- 📏 Максимум 234 строки в файле (было 569)
- ♻️ Переиспользуемый код
- 🧪 Легко тестировать

---

## 🔄 Переиспользование с ChainBuilder

### Общие компоненты

✅ **Alert** — используется в обоих проектах
```tsx
// В MindMap
<Alert variant="error">{error}</Alert>

// В ChainBuilder
<Alert variant="success">Узел создан</Alert>
```

✅ **Hooks** — используются в обоих проектах
```tsx
// useAutoSave
useAutoSave(state, saveFunction, 500);

// useIsMobile
const isMobile = useIsMobile();

// useTemporaryMessage
const [message, showMessage] = useTemporaryMessage(3000);

// useDragAndDrop
const { draggedKey, handleDragStart, handleDrop } = useDragAndDrop();
```

---

## 📦 Структура модулей

### types/index.ts
Общие TypeScript типы для всего приложения.

```tsx
import type { NodeFormState, PropertyDraft } from './types';
```

### hooks/index.ts
Переиспользуемые React хуки:
- `useIsMobile()` — определение мобильного устройства
- `useAutoSave()` — автосохранение с debounce
- `useDragAndDrop()` — управление drag & drop
- `useTemporaryMessage()` — временные уведомления

### utils/index.ts
Утилиты для работы с данными:
- `toDrafts()` — конвертация свойств
- `extractProductId()` — извлечение ID продукта
- `isWebsiteNode()` — проверка типа узла
- `validateProperties()` — валидация данных
- `filterDeleted()` — фильтрация удалённых

### components/
UI компоненты:
- **Alert** — уведомления с вариантами
- **Label** — label для форм
- **PropertyRow** — редактор свойства с drag & drop
- **NodeHeader** — навигация и статус
- **NodeFormFields** — поля формы узла
- **PropertiesSection** — секция со свойствами
- **NodeFooter** — футер с кнопками

### EditNodePage.tsx
Главный компонент — теперь всего 234 строки!

---

## 🎯 Преимущества рефакторинга

### 1. Читаемость
**Было:**
```tsx
// 569 строк в одном файле
// Сложно найти нужный код
```

**Стало:**
```tsx
// Логическое разделение
components/NodeHeader.tsx    // Навигация
components/NodeFormFields.tsx // Форма
components/PropertiesSection.tsx // Свойства
```

### 2. Переиспользование
```tsx
// Хуки можно использовать везде
import { useAutoSave } from './hooks';

// В любом компоненте
useAutoSave(data, saveFunction, 500);
```

### 3. Тестируемость
```tsx
// Легко писать unit-тесты
import { validateProperties } from './utils';

test('validates empty title', () => {
  const error = validateProperties([
    { key: '1', title: '', value: 'test' }
  ]);
  expect(error).toBe('У новых свойств нужно заполнить название');
});
```

### 4. Поддержка
```tsx
// Нужно изменить логику drag & drop?
// Открой hooks/index.ts → useDragAndDrop()

// Нужно изменить валидацию?
// Открой utils/index.ts → validateProperties()
```

---

## 🚀 Как использовать

### Импорт в существующий проект

```tsx
// Импортируй нужные компоненты
import { Alert } from '@/mindmap-refactored/components/Alert';
import { useAutoSave } from '@/mindmap-refactored/hooks';

// Используй в своём компоненте
export function MyComponent() {
  useAutoSave(data, saveData, 500);
  
  return (
    <>
      {error && <Alert variant="error">{error}</Alert>}
      {/* ... */}
    </>
  );
}
```

### Интеграция с ChainBuilder

```tsx
// ChainBuilder может использовать те же хуки
import { useAutoSave, useDragAndDrop } from '@/mindmap-refactored/hooks';
import { Alert } from '@/mindmap-refactored/components/Alert';

export function ChainBuilder() {
  const { draggedKey, handleDragStart, handleDrop } = useDragAndDrop();
  
  useAutoSave(state, saveGraph, 500);
  
  return <Alert variant="success">Сохранено!</Alert>;
}
```

---

## 📈 Метрики улучшений

| Метрика | До | После | Улучшение |
|---------|-----|--------|-----------|
| **Файлов** | 1 | 11 | +1000% |
| **Макс. строк** | 569 | 234 | -59% |
| **Переиспользуемые хуки** | 2 (встроенные) | 4 (выделенные) | +100% |
| **UI компонентов** | 0 | 7 | ∞ |
| **Утилит** | 1 | 7 | +600% |

---

## 🎨 Совместимость с ChainBuilder

Все модули совместимы и могут переиспользоваться:

```
Shared between MindMap & ChainBuilder:
├── hooks/
│   ├── useAutoSave ✅
│   ├── useIsMobile ✅
│   ├── useDragAndDrop ✅
│   └── useTemporaryMessage ✅
└── components/
    ├── Alert ✅
    └── Label ✅
```

Уникальные для MindMap:
```
MindMap specific:
├── components/
│   ├── PropertyRow
│   ├── NodeHeader
│   ├── NodeFormFields
│   ├── PropertiesSection
│   └── NodeFooter
└── utils/
    └── MindMap-specific utilities
```

---

## 🔧 Следующие шаги

1. ✅ Объединить общие модули в shared библиотеку
2. ✅ Добавить unit-тесты для всех утилит
3. ✅ Создать Storybook для компонентов
4. ✅ Мигрировать на полный TypeScript
5. ✅ Добавить E2E тесты

---

## 💡 Лучшие практики

### 1. Один файл = одна ответственность
```tsx
// ❌ Плохо
EditNodePage.tsx - всё в одном файле

// ✅ Хорошо
NodeHeader.tsx - только навигация
NodeFormFields.tsx - только форма
PropertiesSection.tsx - только свойства
```

### 2. Переиспользуемые хуки
```tsx
// ✅ Хук можно использовать везде
export function useAutoSave(value, onSave, delay) {
  // ... логика
}

// В разных компонентах
useAutoSave(nodeData, saveNode, 500);
useAutoSave(mapData, saveMap, 500);
```

### 3. Типизация
```tsx
// ✅ Экспортируй типы
export type PropertyDraft = {
  key: string;
  title: string;
  // ...
};

// Используй в других файлах
import type { PropertyDraft } from './types';
```

---

## 📚 Документация

- **README.md** (этот файл) — обзор
- **ARCHITECTURE.md** — граф зависимостей
- **MIGRATION.md** — гайд по миграции

---

## 🤝 Совместное использование с ChainBuilder

См. также:
- `/refactored/` — рефакторенный ChainBuilder
- `/refactored/IMPROVEMENTS.md` — улучшения из MindMap
- `/refactored/SUMMARY.md` — итоговый обзор

Оба проекта теперь используют общие модули! 🎉
