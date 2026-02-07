# Улучшения Chain Builder на основе production MindMap

## 🎯 Что можно позаимствовать из MindMap

### 1. **Автосохранение с debounce**

**Текущая проблема:** В Chain Builder ручное сохранение через кнопку  
**Решение из MindMap:** Хук `useAutoSave` с debounce 500ms

```typescript
// utils/hooks.js
export function useAutoSave(value, onSave, delay = 500) {
  const timerRef = useRef(null);
  const lastSavedRef = useRef(value);

  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(lastSavedRef.current)) return;
    
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      onSave(value);
      lastSavedRef.current = value;
    }, delay);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, onSave, delay]);
}
```

**Применение в ChainBuilder:**
```javascript
// Автосохранение узла при изменении
useAutoSave(editingNode, async (node) => {
  await mockApi.updateNode(node);
}, 500);
```

---

### 2. **Drag & Drop для переупорядочивания**

**Из MindMap:** Свойства можно перетаскивать для изменения порядка

```javascript
// В NodeEditorModal для условий router
const [draggedRoute, setDraggedRoute] = useState(null);

const handleDragStart = (routeId) => {
  setDraggedRoute(routeId);
};

const handleDrop = (targetRouteId) => {
  if (!draggedRoute || draggedRoute === targetRouteId) return;
  
  setRoutes((prev) => {
    const draggedIdx = prev.findIndex((r) => r.id === draggedRoute);
    const targetIdx = prev.findIndex((r) => r.id === targetRouteId);
    
    const reordered = [...prev];
    const [removed] = reordered.splice(draggedIdx, 1);
    reordered.splice(targetIdx, 0, removed);
    
    return reordered.map((r, i) => ({ ...r, order_index: i }));
  });
};

// В JSX:
<div
  draggable
  onDragStart={() => handleDragStart(route.id)}
  onDragOver={(e) => e.preventDefault()}
  onDrop={() => handleDrop(route.id)}
>
  <GripVertical className="h-4 w-4" /> {/* иконка для захвата */}
  {/* route content */}
</div>
```

---

### 3. **Адаптивность: Desktop Modal vs Mobile Fullscreen**

**Из MindMap:** На мобильных - полноэкранный режим, на десктопе - модалка

```javascript
// utils/hooks.js
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handleChange = (e) => setIsMobile(e.matches);
    handleChange(mql);
    mql.addEventListener('change', handleChange);
    return () => mql.removeEventListener('change', handleChange);
  }, []);

  return isMobile;
}

// В ChainBuilder
const isMobile = useIsMobile();

return isMobile ? (
  <div className="min-h-screen bg-slate-50 p-6">
    {content}
  </div>
) : (
  <Dialog open onOpenChange={onClose}>
    <DialogContent>
      {content}
    </DialogContent>
  </Dialog>
);
```

---

### 4. **Alert компонент с вариантами**

```javascript
// components/Alert.jsx
export function Alert({ children, variant = 'info' }) {
  const variantClass = {
    info: 'bg-blue-50 text-blue-900 border-blue-200',
    error: 'bg-red-50 text-red-900 border-red-200',
    warning: 'bg-amber-50 text-amber-900 border-amber-200',
    success: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  }[variant];

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${variantClass}`}>
      {children}
    </div>
  );
}

// Использование
{error && <Alert variant="error">{error}</Alert>}
{saving && <Alert variant="info">Сохранение...</Alert>}
{successMessage && <Alert variant="success">{successMessage}</Alert>}
```

---

### 5. **Временные уведомления об успехе**

```javascript
const [successMessage, setSuccessMessage] = useState(null);

const handleSave = async () => {
  await mockApi.saveGraph(state);
  setSuccessMessage('✓ Изменения сохранены');
  setTimeout(() => setSuccessMessage(null), 3000);
};
```

---

### 6. **Валидация перед сохранением**

**Из MindMap:**
```javascript
const saveAll = async () => {
  // Проверка на пустые обязательные поля
  const hasInvalidNew = properties.some(
    (p) => !p.deleted && !p.id && !p.title.trim()
  );
  
  if (hasInvalidNew) {
    setError('У новых свойств нужно заполнить название');
    return;
  }
  
  // ... сохранение
};
```

**Применить в Chain Builder для валидации условий router:**
```javascript
const hasInvalidConditions = routes.some(r => {
  if (r.condition_type === 'button_press' && !r.params.button_label?.trim()) {
    return true;
  }
  if (r.condition_type === 'text_contains' && !r.params.text?.trim()) {
    return true;
  }
  return false;
});

if (hasInvalidConditions) {
  setError('Заполните все параметры условий');
  return;
}
```

---

### 7. **Улучшенная структура Card компонентов**

**Из MindMap:**
```jsx
<Card className="border-slate-200 bg-white shadow-sm">
  <CardHeader className="border-b border-slate-100">
    <CardTitle>Редактирование узла</CardTitle>
  </CardHeader>
  
  <CardContent className="space-y-6 pt-6">
    {/* content */}
  </CardContent>
  
  <CardFooter className="border-t border-slate-100 bg-slate-50/50">
    <Button>Сохранить</Button>
  </CardFooter>
</Card>
```

---

### 8. **Оптимизация производительности через useMemo**

**Из MindMap:** Вычисляемые значения кешируются

```javascript
const nodeMap = useMemo(
  () => Object.fromEntries(state.nodes.map(n => [n.id, n])),
  [state.nodes]
);

const visibleNodes = useMemo(
  () => state.nodes.filter(n => !n.hidden),
  [state.nodes]
);
```

---

### 9. **Статусы загрузки и ошибок**

**Единая структура состояния:**
```javascript
const [status, setStatus] = useState({
  loading: false,
  saving: false,
  error: null,
  success: null
});

// Удобное использование
{status.loading && <Alert variant="info">Загрузка...</Alert>}
{status.error && <Alert variant="error">{status.error}</Alert>}
{status.success && <Alert variant="success">{status.success}</Alert>}
```

---

### 10. **Продвинутое контекстное меню с выбором цвета**

**Из MindMap:** Контекстное меню через createPortal с выбором цвета

```javascript
// components/ContextMenuAdvanced.jsx
import { createPortal } from 'react-dom';

// Меню с выбором цвета узла
const items = [
  { 
    action: 'edit', 
    label: '✏️  Редактировать', 
    onSelect: () => setEditingNode(node) 
  },
  { 
    action: 'color', 
    label: '🎨 Изменить цвет', 
    currentColor: node.color,
    onSelectColor: (color) => {
      dispatch({ 
        type: 'UPDATE_NODE', 
        id: node.id, 
        data: { color } 
      });
    }
  },
  { 
    action: 'copy', 
    label: '📋 Копировать', 
    onSelect: () => {
      const text = formatNodeClipboardText(node);
      navigator.clipboard.writeText(text);
      showSuccess('✓ Скопировано в буфер обмена');
    }
  },
  { 
    action: 'delete', 
    label: '🗑️  Удалить', 
    destructive: true,
    onSelect: () => dispatch({ type: 'DELETE_NODE', id: node.id })
  }
];

// Рендер с createPortal для правильного позиционирования
return createPortal(
  <div style={{ position: 'fixed', left: pos.x, top: pos.y }}>
    {/* menu content */}
  </div>,
  document.body
);
```

**Особенности:**
- Меню рендерится в `document.body` через `createPortal`
- Автоматическое позиционирование с учётом границ экрана
- Раскрывающийся color picker
- Визуальная индикация текущего цвета
- Закрытие по Escape или клику вне меню

---

### 11. **Копирование узла в буфер обмена**

```javascript
// Форматированный текст для копирования
function formatNodeClipboardText(node) {
  const lines = [];
  lines.push(`Название: ${node.title || '—'}`);
  lines.push(`Тип: ${node.node_type}`);
  
  if (node.node_type === 'router') {
    lines.push('Условия:');
    node.payload.routes.forEach((r, i) => {
      lines.push(`  ${i + 1}. ${r.condition_type}`);
    });
  }
  
  return lines.join('\n');
}

// Копирование
await navigator.clipboard.writeText(formatNodeClipboardText(node));
showSuccess('✓ Скопировано');
```

---

### 12. **Кастомные цвета узлов**

```javascript
// constants.js
export const CUSTOM_COLORS = [
  { label: 'Зелёный', value: '#14b8a6', bg: '#f0fdfa' },
  { label: 'Синий', value: '#3b82f6', bg: '#eff6ff' },
  // ... остальные цвета
];

// В reducer добавить поддержку color
case "UPDATE_NODE": {
  const nodes = state.nodes.map(n => 
    n.id === action.id 
      ? { ...n, ...action.data, color: action.data.color || n.color } 
      : n
  );
  return { ...state, nodes, dirty: true };
}

// В NodeCard использовать кастомный цвет
const getNodeColor = (node) => {
  if (node.color) {
    const customColor = CUSTOM_COLORS.find(c => c.value === node.color);
    if (customColor) return customColor;
  }
  return NODE_COLORS[node.node_type];
};
```

---

## 📦 Готовые компоненты для переиспользования

### 1. useAutoSave hook
### 2. useIsMobile hook  
### 3. Alert component
### 4. Drag & Drop логика
### 5. Временные уведомления
### 6. Валидация форм

---

## 🚀 План внедрения

### Фаза 1: Базовые улучшения
1. ✅ Добавить `useAutoSave` для автосохранения
2. ✅ Добавить `Alert` компонент
3. ✅ Добавить временные уведомления об успехе
4. ✅ Добавить валидацию перед сохранением

### Фаза 2: UX улучшения
1. ✅ Drag & Drop для переупорядочивания условий
2. ✅ `useIsMobile` для адаптивности
3. ✅ Улучшить структуру Card компонентов
4. ✅ Добавить иконки к кнопкам

### Фаза 3: Оптимизация
1. ✅ Использовать `useMemo` для тяжёлых вычислений
2. ✅ Единая структура состояния загрузки/ошибок
3. ✅ Оптимизировать рендеринг узлов

---

## 📝 Пример улучшенного файла

См. `ChainBuilderImproved.jsx` с интегрированными улучшениями.
