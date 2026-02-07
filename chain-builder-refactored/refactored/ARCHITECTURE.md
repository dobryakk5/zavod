# Карта зависимостей проекта

```
ChainBuilder.jsx (главный компонент)
├── constants.js
├── utils.js
├── reducer.js
├── mockApi.js
└── components/
    ├── Toolbar.jsx
    │   └── constants.js (NODE_TYPES)
    │
    ├── NodeCard.jsx
    │   ├── constants.js (NODE_COLORS, NODE_W)
    │   └── utils.js (getNodeHeight, getConditionLabel, formatTime)
    │
    ├── EdgeLine.jsx
    │   └── utils.js (getConnectionPoints, getCurvedPath, getEdgeMid)
    │
    ├── NodeEditorModal.jsx
    │   ├── constants.js (CONDITION_LABELS, CONTENT_TYPES)
    │   └── utils.js (formatTime, uid)
    │
    └── ContextMenu.jsx
        (без зависимостей)
```

## Граф зависимостей

```
                    ┌─────────────────┐
                    │  ChainBuilder   │
                    │   (главный)     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐          ┌────▼────┐         ┌────▼────┐
   │constants│          │  utils  │         │ reducer │
   └─────────┘          └─────────┘         └─────────┘
        │                    │                    
        │                    │                    
   ┌────┴────────────────────┴─────┐
   │                                │
┌──▼──────────┐            ┌───────▼──────┐
│  Toolbar    │            │  NodeCard    │
└─────────────┘            └──────────────┘
                                   
┌──────────────┐           ┌──────────────┐
│  EdgeLine    │           │ ContextMenu  │
└──────────────┘           └──────────────┘
                                   
         ┌────────────────────┐
         │ NodeEditorModal    │
         └────────────────────┘
```

## Принципы организации

1. **constants.js** - единый источник правды для констант
2. **utils.js** - переиспользуемые функции без состояния
3. **reducer.js** - вся логика изменения состояния в одном месте
4. **components/** - UI компоненты, каждый делает одну вещь
5. **ChainBuilder.jsx** - оркестрирует всё вместе

## Отсутствие циклических зависимостей ✅

Все зависимости идут в одном направлении:
- Компоненты зависят от utils/constants
- utils/constants не зависят от компонентов
- ChainBuilder объединяет всё

Это делает код:
- Легко тестируемым
- Легко понимаемым
- Безопасным для рефакторинга
