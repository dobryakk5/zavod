# 🔄 Shared Code Map — Общий код между проектами

## 📦 Архитектура переиспользования

```
project-root/
│
├── shared/                    # Общая библиотека
│   ├── hooks/
│   │   ├── useAutoSave.ts    ✅ MindMap + ChainBuilder
│   │   ├── useIsMobile.ts    ✅ MindMap + ChainBuilder
│   │   ├── useDragAndDrop.ts ✅ MindMap + ChainBuilder
│   │   └── useTemporaryMessage.ts ✅ MindMap + ChainBuilder
│   │
│   ├── components/
│   │   ├── Alert.tsx         ✅ MindMap + ChainBuilder
│   │   └── Label.tsx         ✅ MindMap + ChainBuilder
│   │
│   └── utils/
│       ├── formatting.ts     ✅ MindMap + ChainBuilder
│       └── validation.ts     ✅ MindMap + ChainBuilder
│
├── mindmap-refactored/        # MindMap специфичный код
│   ├── components/
│   │   ├── PropertyRow.tsx
│   │   ├── NodeHeader.tsx
│   │   ├── NodeFormFields.tsx
│   │   ├── PropertiesSection.tsx
│   │   └── NodeFooter.tsx
│   │
│   ├── utils/
│   │   └── mindmap-specific.ts
│   │
│   └── EditNodePage.tsx
│
└── chain-builder-refactored/  # ChainBuilder специфичный код
    ├── components/
    │   ├── NodeCard.tsx
    │   ├── EdgeLine.tsx
    │   ├── Toolbar.tsx
    │   ├── NodeEditorModal.tsx
    │   └── ContextMenu.tsx
    │
    ├── utils/
    │   └── chainbuilder-specific.ts
    │
    └── ChainBuilder.tsx
```

---

## ✅ Общие модули (100% переиспользование)

### 1. useAutoSave

**Где используется:**
- ✅ MindMap — автосохранение узла
- ✅ ChainBuilder — автосохранение графа

**Код:**
```tsx
// shared/hooks/useAutoSave.ts
export function useAutoSave<T>(
  value: T,
  onSave: (value: T) => Promise<void>,
  delay = 500
) {
  // ... реализация
}

// В MindMap
useAutoSave({ title, typeLabel }, saveNodeNow, 500);

// В ChainBuilder
useAutoSave(state, saveGraph, 500);
```

---

### 2. useIsMobile

**Где используется:**
- ✅ MindMap — mobile vs desktop рендеринг
- ✅ ChainBuilder — адаптивный UI

**Код:**
```tsx
// shared/hooks/useIsMobile.ts
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  // ... реализация
  return isMobile;
}

// Использование одинаковое
const isMobile = useIsMobile();
return isMobile ? <MobileView /> : <DesktopView />;
```

---

### 3. useDragAndDrop

**Где используется:**
- ✅ MindMap — переупорядочивание свойств
- ✅ ChainBuilder — переупорядочивание условий router

**Код:**
```tsx
// shared/hooks/useDragAndDrop.ts
export function useDragAndDrop<T extends { key: string }>() {
  // ... реализация
  return { draggedKey, handleDragStart, handleDragEnd, handleDrop };
}

// В MindMap - свойства узла
const { draggedKey, handleDragStart, handleDrop } = useDragAndDrop<PropertyDraft>();

// В ChainBuilder - условия router
const { draggedKey, handleDragStart, handleDrop } = useDragAndDrop<Route>();
```

---

### 4. useTemporaryMessage

**Где используется:**
- ✅ MindMap — успешное сохранение
- ✅ ChainBuilder — создание/удаление узлов

**Код:**
```tsx
// shared/hooks/useTemporaryMessage.ts
export function useTemporaryMessage(duration = 3000) {
  // ... реализация
  return [message, showMessage] as const;
}

// В MindMap
const [success, showSuccess] = useTemporaryMessage(3000);
showSuccess('✓ Изменения сохранены');

// В ChainBuilder
const [success, showSuccess] = useTemporaryMessage(3000);
showSuccess('✓ Узел создан');
```

---

### 5. Alert Component

**Где используется:**
- ✅ MindMap — ошибки, успех, загрузка
- ✅ ChainBuilder — те же варианты

**Код:**
```tsx
// shared/components/Alert.tsx
export function Alert({ children, variant }: AlertProps) {
  // ... реализация
}

// Использование идентично
<Alert variant="error">{error}</Alert>
<Alert variant="success">{success}</Alert>
<Alert variant="info">Загрузка...</Alert>
```

---

### 6. Label Component

**Где используется:**
- ✅ MindMap — labels форм
- ✅ ChainBuilder — labels форм

**Код:**
```tsx
// shared/components/Label.tsx
export function Label({ children, className, htmlFor }: LabelProps) {
  // ... реализация
}

// Использование одинаковое
<Label htmlFor="title">Название</Label>
<Input id="title" />
```

---

## 📊 Статистика переиспользования

| Модуль | MindMap | ChainBuilder | Размер | Экономия |
|--------|---------|--------------|--------|----------|
| useAutoSave | ✅ | ✅ | 35 строк | 35 строк |
| useIsMobile | ✅ | ✅ | 15 строк | 15 строк |
| useDragAndDrop | ✅ | ✅ | 40 строк | 40 строк |
| useTemporaryMessage | ✅ | ✅ | 25 строк | 25 строк |
| Alert | ✅ | ✅ | 22 строки | 22 строки |
| Label | ✅ | ✅ | 19 строк | 19 строк |
| **ИТОГО** | | | **156 строк** | **156 строк** |

**Экономия:** 156 строк кода не дублируются! 🎉

---

## 🎯 План миграции на shared библиотеку

### Шаг 1: Создать shared директорию
```bash
mkdir -p shared/{hooks,components,utils}
```

### Шаг 2: Переместить общий код
```bash
# Hooks
mv mindmap-refactored/hooks/useAutoSave.ts shared/hooks/
mv mindmap-refactored/hooks/useIsMobile.ts shared/hooks/
mv mindmap-refactored/hooks/useDragAndDrop.ts shared/hooks/
mv mindmap-refactored/hooks/useTemporaryMessage.ts shared/hooks/

# Components
mv mindmap-refactored/components/Alert.tsx shared/components/
mv mindmap-refactored/components/Label.tsx shared/components/
```

### Шаг 3: Обновить импорты

**В MindMap:**
```tsx
// Было
import { useAutoSave } from './hooks';
import { Alert } from './components/Alert';

// Стало
import { useAutoSave } from '@/shared/hooks';
import { Alert } from '@/shared/components';
```

**В ChainBuilder:**
```tsx
// Было
import { useAutoSave } from './hooks';
import { Alert } from './components/Alert';

// Стало
import { useAutoSave } from '@/shared/hooks';
import { Alert } from '@/shared/components';
```

### Шаг 4: Обновить package.json (если separate packages)
```json
{
  "name": "@mycompany/shared",
  "version": "1.0.0",
  "exports": {
    "./hooks": "./hooks/index.ts",
    "./components": "./components/index.ts",
    "./utils": "./utils/index.ts"
  }
}
```

---

## 💡 Лучшие практики

### 1. Проверяй совместимость
```tsx
// ✅ Хорошо - generic, работает везде
export function useDragAndDrop<T extends { key: string }>() {
  // ...
}

// ❌ Плохо - завязан на конкретный тип
export function useDragAndDrop<PropertyDraft>() {
  // ...
}
```

### 2. Избегай специфичных зависимостей
```tsx
// ✅ Хорошо - общий код
import { useState } from 'react';

// ❌ Плохо - зависимость от MindMap
import { mindMapsApi } from '@/lib/api/mindmaps';
```

### 3. Документируй использование
```tsx
/**
 * Автосохранение с debounce
 * 
 * @example
 * // В MindMap
 * useAutoSave({ title, typeLabel }, saveNode, 500);
 * 
 * @example
 * // В ChainBuilder
 * useAutoSave(state, saveGraph, 500);
 */
export function useAutoSave<T>(...) {
  // ...
}
```

---

## 🚀 Преимущества shared подхода

### 1. DRY (Don't Repeat Yourself)
```tsx
// ❌ Было - код дублировался
// mindmap/useAutoSave.ts (35 строк)
// chainbuilder/useAutoSave.ts (35 строк)

// ✅ Стало - один источник правды
// shared/hooks/useAutoSave.ts (35 строк)
```

### 2. Единый источник обновлений
```tsx
// Исправил баг в useAutoSave?
// → Автоматически работает в MindMap И ChainBuilder
```

### 3. Консистентность
```tsx
// Alert выглядит одинаково везде
// UX одинаковый в обоих проектах
```

### 4. Тестируемость
```tsx
// Тесты один раз
// shared/hooks/__tests__/useAutoSave.test.ts

// Работает для обоих проектов
```

---

## 📈 Roadmap

### Фаза 1: Извлечение (текущая)
- [x] Выделить общие хуки
- [x] Выделить общие компоненты
- [x] Создать документацию

### Фаза 2: Consolidation
- [ ] Создать shared директорию
- [ ] Переместить код
- [ ] Обновить импорты

### Фаза 3: Оптимизация
- [ ] Добавить unit-тесты
- [ ] Создать Storybook
- [ ] Опубликовать как npm пакет

### Фаза 4: Расширение
- [ ] Добавить больше shared компонентов
- [ ] Shared theme/styles
- [ ] Shared API client

---

## 🎉 Итог

**Было:** Два независимых проекта с дублированием кода  
**Стало:** Два проекта, использующие общую библиотеку

**Результат:**
- 📉 Меньше кода
- 🐛 Меньше багов
- ⚡ Быстрее разработка
- 🎨 Консистентный UX
