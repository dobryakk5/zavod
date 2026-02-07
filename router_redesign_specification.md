# Router Node UI Redesign — Specification

## Концепция

Вместо обычных рёбер с условиями в виде бейджей, Router будет показывать условия как **отдельные прямоугольники (порты)** на самом узле. Из каждого прямоугольника можно провести своё ребро к целевому узлу.

---

## Визуальная схема

### До (текущая реализация):

```
┌─────────────┐
│  🔀 РОУТЕР  │
│  "Проверка" │
└──────┬──────┘
       ├─ [Тип=text] ──→ Узел A
       ├─ [Тип=photo] ─→ Узел B
       └─ [fallback] ──→ Узел C
```

### После (новая реализация):

```
          ┌───────────────────────────┐
          │      🔀 РОУТЕР            │
          │      "Проверка типа"      │
┌─────────┤                           ├─────────┐
│ вход    │  ┌─────────────────────┐ │  выход  │
│         │  │ Тип = text          │─┼─────────┼──→ Узел A
│         │  └─────────────────────┘ │         │
│         │                           │         │
│         │  ┌─────────────────────┐ │         │
│         │  │ Тип = photo         │─┼─────────┼──→ Узел B
│         │  └─────────────────────┘ │         │
│         │                           │         │
│         │  ┌─────────────────────┐ │         │
│         │  │ fallback (любой)    │─┼─────────┼──→ Узел C
│         │  └─────────────────────┘ │         │
└─────────┴───────────────────────────┴─────────┘
```

---

## Изменения в Data Model

### 1. Структура Router Node

**До:**
```javascript
{
  id: 2,
  node_type: "router",
  payload: {
    label: "Проверка типа"
  },
  pos_x: 100,
  pos_y: 200
}
```

**После (добавляем список условий в payload):**
```javascript
{
  id: 2,
  node_type: "router",
  payload: {
    label: "Проверка типа",
    // NEW: Условия хранятся В узле, не на рёбрах
    conditions: [
      {
        id: "cond_1",
        condition_type: "content_type",
        params: { message_type: "text" },
        label: "Тип = text",        // Текст для отображения
        port_index: 0                // Порядок отображения
      },
      {
        id: "cond_2",
        condition_type: "content_type",
        params: { message_type: "photo" },
        label: "Тип = photo",
        port_index: 1
      },
      {
        id: "cond_fallback",
        condition_type: "fallback",
        params: {},
        label: "Любой",
        port_index: 2
      }
    ]
  },
  pos_x: 100,
  pos_y: 200
}
```

### 2. Структура Edge (ребро)

**До:**
```javascript
{
  id: 11,
  source_node_id: 2,      // Router
  target_node_id: 3,      // Целевой узел
  conditions: [           // Условия на ребре
    { condition_type: "content_type", params: { message_type: "text" } }
  ]
}
```

**После:**
```javascript
{
  id: 11,
  source_node_id: 2,           // Router
  source_port_id: "cond_1",    // NEW: ID условия (порта) в router
  target_node_id: 3,           // Целевой узел
  // Условий на ребре больше нет — они в router.payload.conditions
}
```

---

## Изменения в Constants

```javascript
// Увеличиваем высоту router для отображения условий
const NODE_DIMENSIONS = {
  text: { w: 220, h: 120 },
  photo: { w: 220, h: 120 },
  buttons: { w: 220, h: 120 },
  timer: { w: 220, h: 120 },
  router: { w: 280, h: "auto" }, // NEW: Ширина больше, высота динамическая
};

// Размеры порта условия
const CONDITION_PORT = {
  width: 200,      // Ширина прямоугольника условия
  height: 32,      // Высота
  spacing: 8,      // Отступ между условиями
  portRadius: 6,   // Радиус кружка порта справа
};
```

---

## Изменения в NodeCard Component

### Текущий код:
```javascript
function NodeCard({ node, isStart, isHovered, ... }) {
  const c = NODE_COLORS[node.node_type];
  
  return (
    <div style={{ width: NODE_W, height: NODE_H, ... }}>
      {/* Header, Content, Footer */}
      {/* Connection ports (top/bottom) */}
    </div>
  );
}
```

### Новый код:
```javascript
function RouterNodeCard({ node, isStart, isHovered, isSelected, onPortMouseDown, ... }) {
  const c = NODE_COLORS.router;
  const conditions = node.payload.conditions || [];
  
  // Динамическая высота в зависимости от количества условий
  const headerHeight = 48;
  const conditionsHeight = conditions.length * (CONDITION_PORT.height + CONDITION_PORT.spacing) + 16;
  const totalHeight = headerHeight + conditionsHeight;
  
  return (
    <div
      style={{
        position: "absolute",
        left: node.pos_x,
        top: node.pos_y,
        width: NODE_DIMENSIONS.router.w,
        height: totalHeight,
        backgroundColor: c.bg,
        borderColor: isSelected ? c.accent : c.border,
        boxShadow: isHovered || isSelected ? c.shadow : '0 2px 8px rgba(0,0,0,0.1)',
      }}
      className="rounded-xl border-2 cursor-move select-none transition-all"
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between border-b" style={{ borderColor: c.border + '40' }}>
        <div className="flex items-center gap-2">
          <span className="text-lg">{c.icon}</span>
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>
            РОУТЕР
          </span>
        </div>
        {isStart && <span className="px-2 py-0.5 rounded-full bg-emerald-600 text-white text-xs font-bold">START</span>}
      </div>
      
      {/* Title */}
      <div className="px-4 py-2">
        <p className="text-sm font-semibold text-slate-700 text-center">
          {node.payload.label || "Router"}
        </p>
      </div>
      
      {/* Condition Ports */}
      <div className="px-4 pb-4 space-y-2">
        {conditions.map((cond, index) => (
          <ConditionPort
            key={cond.id}
            condition={cond}
            index={index}
            nodeId={node.id}
            isHovered={isHovered}
            onPortMouseDown={onPortMouseDown}
          />
        ))}
        
        {/* Add condition button (если hover) */}
        {isHovered && (
          <button
            onClick={() => openAddConditionModal(node.id)}
            className="w-full border border-dashed border-purple-300 rounded-lg py-2 text-xs text-purple-600 hover:bg-purple-50"
          >
            + Добавить условие
          </button>
        )}
      </div>
      
      {/* Input port (top center) */}
      {(isHovered || isSelected) && (
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2"
          style={{ backgroundColor: c.bg, borderColor: c.border }}
        />
      )}
    </div>
  );
}

// Новый компонент: Condition Port (прямоугольник условия с портом)
function ConditionPort({ condition, index, nodeId, isHovered, onPortMouseDown }) {
  const [localHover, setLocalHover] = useState(false);
  
  return (
    <div
      onMouseEnter={() => setLocalHover(true)}
      onMouseLeave={() => setLocalHover(false)}
      className="relative"
    >
      {/* Прямоугольник условия */}
      <div
        className="bg-purple-50 border border-purple-300 rounded-lg px-3 py-2 flex items-center justify-between transition-all"
        style={{
          height: CONDITION_PORT.height,
          boxShadow: localHover ? '0 2px 8px rgba(168,85,247,0.2)' : 'none',
        }}
      >
        <div className="flex items-center gap-2 flex-1">
          <span className="text-xs font-medium text-purple-900">
            {condition.label || formatConditionLabel(condition)}
          </span>
        </div>
        
        {/* Delete button (на hover) */}
        {localHover && (
          <button
            onClick={() => deleteCondition(nodeId, condition.id)}
            className="text-red-600 hover:text-red-700 text-xs ml-2"
          >
            ×
          </button>
        )}
      </div>
      
      {/* Output port (кружок справа от прямоугольника) */}
      {(isHovered || localHover) && (
        <div
          onMouseDown={(e) => {
            e.stopPropagation();
            onPortMouseDown(nodeId, condition.id, 'condition_output');
          }}
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 cursor-crosshair hover:scale-125 transition-transform z-10"
          style={{
            right: -8,
            borderColor: "#9333ea",
          }}
        />
      )}
    </div>
  );
}

// Helper: Форматирование label условия
function formatConditionLabel(condition) {
  const { condition_type, params } = condition;
  
  if (condition_type === "content_type") {
    return `Тип = ${params.message_type}`;
  }
  if (condition_type === "text_contains") {
    return `Текст ⊃ "${params.substring}"`;
  }
  if (condition_type === "has_entities") {
    return `Содержит [${params.entity_type}]`;
  }
  if (condition_type === "fallback") {
    return "Любой (fallback)";
  }
  return CONDITION_LABELS[condition_type] || condition_type;
}
```

---

## Изменения в Geometry Functions

```javascript
// Старая функция - из центра низа узла
function getConnectionPoints(srcNode, tgtNode) {
  const sx = srcNode.pos_x + NODE_W / 2;
  const sy = srcNode.pos_y + NODE_H;
  const tx = tgtNode.pos_x + NODE_W / 2;
  const ty = tgtNode.pos_y;
  return { sx, sy, tx, ty };
}

// НОВАЯ функция - учитывает порты условий
function getConnectionPoints(srcNode, tgtNode, edge) {
  let sx, sy, tx, ty;
  
  // Source: если router с портом условия
  if (srcNode.node_type === "router" && edge.source_port_id) {
    const conditions = srcNode.payload.conditions || [];
    const condIndex = conditions.findIndex(c => c.id === edge.source_port_id);
    
    if (condIndex >= 0) {
      // Позиция порта условия
      const headerHeight = 48;
      const titleHeight = 32;
      const portY = headerHeight + titleHeight + 
                    condIndex * (CONDITION_PORT.height + CONDITION_PORT.spacing) + 
                    CONDITION_PORT.height / 2;
      
      sx = srcNode.pos_x + NODE_DIMENSIONS.router.w; // Справа от router
      sy = srcNode.pos_y + portY;
    } else {
      // Fallback: из центра низа
      sx = srcNode.pos_x + NODE_DIMENSIONS.router.w / 2;
      sy = srcNode.pos_y + 200; // Примерная высота
    }
  } else {
    // Обычные узлы: из центра низа
    sx = srcNode.pos_x + (NODE_DIMENSIONS[srcNode.node_type]?.w || 220) / 2;
    sy = srcNode.pos_y + (NODE_DIMENSIONS[srcNode.node_type]?.h || 120);
  }
  
  // Target: всегда в центр верха
  tx = tgtNode.pos_x + (NODE_DIMENSIONS[tgtNode.node_type]?.w || 220) / 2;
  ty = tgtNode.pos_y;
  
  return { sx, sy, tx, ty };
}
```

---

## Изменения в EdgeLine Component

```javascript
// Минимальные изменения - просто передаём edge в getConnectionPoints
function EdgeLine({ edge, srcNode, tgtNode, isHovered, onClick, onDelete }) {
  // NEW: Передаём edge для определения source_port_id
  const { sx, sy, tx, ty } = getConnectionPoints(srcNode, tgtNode, edge);
  
  const path = getCurvedPath(sx, sy, tx, ty);
  const mid = getEdgeMid(sx, sy, tx, ty);
  
  const isFromRouter = srcNode.node_type === "router";

  return (
    <g>
      <path d={path} fill="none" stroke="transparent" strokeWidth={20} onClick={onClick} className="cursor-pointer" />
      <path
        d={path}
        fill="none"
        stroke={isHovered ? "#0f172a" : isFromRouter ? "#9333ea" : "#64748b"}
        strokeWidth={isHovered ? 3 : 2}
        className="transition-all pointer-events-none"
      />
      <circle cx={tx} cy={ty} r={isHovered ? 6 : 5} fill={isHovered ? "#0f172a" : isFromRouter ? "#9333ea" : "#64748b"} className="transition-all pointer-events-none" />

      {/* Удаляем бейджи условий - они теперь на самом router */}
      
      {isHovered && (
        <foreignObject x={mid.x - 12} y={mid.y + 10} width={24} height={24}>
          <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="w-full h-full rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 shadow-lg text-xs font-bold">×</button>
        </foreignObject>
      )}
    </g>
  );
}
```

---

## Изменения в Drawing Connection Logic

```javascript
// Состояние для рисования
const [drawingFrom, setDrawingFrom] = useState(null);
// NEW структура:
// {
//   nodeId: number,
//   portId: string,           // NEW: ID порта (для router - ID условия)
//   portType: string,         // "bottom" | "condition_output"
//   x: number,
//   y: number
// }

// Обработчик начала рисования
const onPortMouseDown = (nodeId, portId, portType) => {
  const node = state.nodes.find(n => n.id === nodeId);
  if (!node) return;
  
  let sx, sy;
  
  if (portType === "condition_output") {
    // Из порта условия router
    const conditions = node.payload.conditions || [];
    const condIndex = conditions.findIndex(c => c.id === portId);
    
    const headerHeight = 48;
    const titleHeight = 32;
    const portY = headerHeight + titleHeight + 
                  condIndex * (CONDITION_PORT.height + CONDITION_PORT.spacing) + 
                  CONDITION_PORT.height / 2;
    
    sx = node.pos_x + NODE_DIMENSIONS.router.w;
    sy = node.pos_y + portY;
  } else {
    // Из обычного порта (низ узла)
    sx = node.pos_x + (NODE_DIMENSIONS[node.node_type]?.w || 220) / 2;
    sy = node.pos_y + (NODE_DIMENSIONS[node.node_type]?.h || 120);
  }
  
  setDrawingFrom({ nodeId, portId, portType, x: sx, y: sy });
  setDrawingTo({ x: sx, y: sy });
};

// Завершение рисования
const onNodeClick = (e, targetNode) => {
  e.stopPropagation();
  
  if (drawingFrom && drawingFrom.nodeId !== targetNode.id) {
    // Создаём edge с source_port_id
    dispatch({ 
      type: "ADD_EDGE", 
      source: drawingFrom.nodeId, 
      sourcePortId: drawingFrom.portId,      // NEW
      target: targetNode.id 
    });
    
    setDrawingFrom(null);
    setDrawingTo(null);
  }
};
```

---

## Изменения в Reducer

```javascript
case "ADD_EDGE": {
  const exists = state.edges.some(e => 
    e.source_node_id === action.source && 
    e.target_node_id === action.target &&
    e.source_port_id === action.sourcePortId  // NEW: Проверяем и порт
  );
  
  if (exists) return state;
  
  const edge = { 
    id: uid(), 
    chain_id: state.chain.id, 
    source_node_id: action.source, 
    source_port_id: action.sourcePortId || null,  // NEW
    target_node_id: action.target, 
    priority: 0 
  };
  
  return { ...state, edges: [...state.edges, edge], dirty: true };
}

// NEW: Добавление условия в router
case "ADD_ROUTER_CONDITION": {
  const nodes = state.nodes.map(n => {
    if (n.id === action.nodeId) {
      const conditions = [...(n.payload.conditions || [])];
      conditions.push({
        id: uid(),
        condition_type: action.conditionType,
        params: action.params,
        label: action.label,
        port_index: conditions.length
      });
      return { ...n, payload: { ...n.payload, conditions } };
    }
    return n;
  });
  return { ...state, nodes, dirty: true };
}

// NEW: Удаление условия из router
case "DELETE_ROUTER_CONDITION": {
  const nodes = state.nodes.map(n => {
    if (n.id === action.nodeId) {
      const conditions = (n.payload.conditions || []).filter(c => c.id !== action.conditionId);
      // Обновляем port_index
      conditions.forEach((c, i) => c.port_index = i);
      return { ...n, payload: { ...n.payload, conditions } };
    }
    return n;
  });
  
  // Удаляем все рёбра от этого порта
  const edges = state.edges.filter(e => 
    !(e.source_node_id === action.nodeId && e.source_port_id === action.conditionId)
  );
  
  return { ...state, nodes, edges, dirty: true };
}
```

---

## Изменения в Modals

### NodeEditorModal - теперь НЕ редактируются условия

```javascript
function NodeEditorModal({ node, onSave, onClose }) {
  // ...
  
  if (isRouter) {
    return (
      <Dialog>
        <div className="space-y-4">
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <p className="text-sm text-purple-900">
              🔀 <strong>Роутер</strong> — условия редактируются прямо на узле
            </p>
          </div>
          
          <div>
            <label>Название роутера</label>
            <input value={form.payload.label} onChange={e => setP("label", e.target.value)} />
          </div>
          
          <div>
            <label>Описание (опционально)</label>
            <textarea value={form.payload.description} onChange={e => setP("description", e.target.value)} />
          </div>
          
          {/* Условия НЕ редактируются здесь */}
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-600">
              💡 Чтобы добавить условие, наведите на узел роутера и нажмите "+ Добавить условие"
            </p>
          </div>
        </div>
      </Dialog>
    );
  }
  
  // ...
}
```

### NEW: AddConditionModal

```javascript
function AddConditionModal({ nodeId, onSave, onClose }) {
  const [conditionType, setConditionType] = useState("content_type");
  const [params, setParams] = useState({});
  const [label, setLabel] = useState("");
  
  const handleSave = () => {
    dispatch({
      type: "ADD_ROUTER_CONDITION",
      nodeId,
      conditionType,
      params,
      label: label || formatConditionLabel({ condition_type: conditionType, params })
    });
    onClose();
  };
  
  return (
    <Dialog open onClose={onClose} title="Добавить условие">
      <div className="space-y-4">
        {/* Тип условия */}
        <div>
          <label>Тип условия</label>
          <select value={conditionType} onChange={e => setConditionType(e.target.value)}>
            <option value="content_type">Тип контента</option>
            <option value="text_contains">Содержит текст</option>
            <option value="has_entities">Содержит (email/phone/url)</option>
            <option value="text_equals">Точное совпадение</option>
            <option value="fallback">Fallback (любой)</option>
          </select>
        </div>
        
        {/* Параметры в зависимости от типа */}
        {conditionType === "content_type" && (
          <div>
            <label>Тип сообщения</label>
            <select value={params.message_type || ""} onChange={e => setParams({ message_type: e.target.value })}>
              <option value="">— выберите —</option>
              <option value="text">Текст</option>
              <option value="photo">Фото</option>
              <option value="video">Видео</option>
              <option value="audio">Аудио</option>
              <option value="document">Документ</option>
            </select>
          </div>
        )}
        
        {/* ... другие типы условий ... */}
        
        {/* Кастомный label (опционально) */}
        <div>
          <label>Название условия (опционально)</label>
          <input 
            value={label} 
            onChange={e => setLabel(e.target.value)} 
            placeholder={formatConditionLabel({ condition_type: conditionType, params })}
          />
        </div>
        
        <div className="flex justify-end gap-3">
          <button onClick={onClose}>Отмена</button>
          <button onClick={handleSave} className="bg-purple-600 text-white">Добавить</button>
        </div>
      </div>
    </Dialog>
  );
}
```

---

## Database Schema Changes

```sql
-- chain_nodes: payload теперь содержит условия
CREATE TABLE chain_nodes (
  id SERIAL PRIMARY KEY,
  chain_id INTEGER REFERENCES chains(id),
  node_type VARCHAR(50),  -- 'text' | 'photo' | 'buttons' | 'router' | 'timer'
  payload JSONB,          -- Для router: { label, description, conditions: [...] }
  delay_seconds INTEGER,
  pos_x REAL,
  pos_y REAL
);

-- chain_edges: теперь хранит source_port_id
CREATE TABLE chain_edges (
  id SERIAL PRIMARY KEY,
  chain_id INTEGER REFERENCES chains(id),
  source_node_id INTEGER REFERENCES chain_nodes(id),
  source_port_id VARCHAR(50),   -- NEW: ID условия (порта) для router
  target_node_id INTEGER REFERENCES chain_nodes(id),
  priority INTEGER DEFAULT 0
);

-- edge_conditions: больше НЕ нужна (условия в node.payload)
-- DROP TABLE edge_conditions;

-- Пример router node:
INSERT INTO chain_nodes (chain_id, node_type, payload, pos_x, pos_y)
VALUES (
  1,
  'router',
  '{
    "label": "Проверка типа контента",
    "description": "Анализирует входящее сообщение",
    "conditions": [
      {
        "id": "cond_abc123",
        "condition_type": "content_type",
        "params": {"message_type": "text"},
        "label": "Текстовое сообщение",
        "port_index": 0
      },
      {
        "id": "cond_def456",
        "condition_type": "content_type",
        "params": {"message_type": "photo"},
        "label": "Фотография",
        "port_index": 1
      },
      {
        "id": "cond_fallback",
        "condition_type": "fallback",
        "params": {},
        "label": "Любой другой тип",
        "port_index": 2
      }
    ]
  }',
  100,
  200
);

-- Пример ребра от router:
INSERT INTO chain_edges (chain_id, source_node_id, source_port_id, target_node_id, priority)
VALUES 
  (1, 2, 'cond_abc123', 3, 0),  -- Текст → Узел 3
  (1, 2, 'cond_def456', 4, 0),  -- Фото → Узел 4
  (1, 2, 'cond_fallback', 5, 0); -- Fallback → Узел 5
```

---

## Backend Execution Changes

```python
# tasks.py

def find_next_node_from_router(router_node_id, telegram_message, db):
    """
    Находит следующий узел после router на основе условий В узле
    """
    # Получаем router узел
    router = db.query(ChainNode).filter(ChainNode.id == router_node_id).first()
    if not router or router.node_type != "router":
        return None
    
    # Условия теперь в payload.conditions
    conditions = router.payload.get("conditions", [])
    
    # Проверяем каждое условие по порядку port_index
    sorted_conditions = sorted(conditions, key=lambda c: c.get("port_index", 0))
    
    for condition in sorted_conditions:
        # Проверяем условие
        if evaluate_router_condition(condition, telegram_message):
            # Находим ребро для этого condition.id
            edge = db.query(ChainEdge).filter(
                ChainEdge.source_node_id == router_node_id,
                ChainEdge.source_port_id == condition["id"]
            ).first()
            
            if edge:
                return edge.target_node_id
    
    # Ничего не подошло
    return None


def evaluate_router_condition(condition, telegram_message):
    """Проверяет условие (без изменений)"""
    condition_type = condition["condition_type"]
    params = condition.get("params", {})
    
    if condition_type == "fallback":
        return True  # Fallback всегда проходит
    
    if condition_type == "content_type":
        message_type = params.get("message_type")
        if message_type == "text":
            return bool(telegram_message.text)
        elif message_type == "photo":
            return bool(telegram_message.photo)
        # ...
    
    # ... остальные типы условий
```

---

## Migration Script (если уже есть данные)

```python
# migrate_router_conditions.py

from app.database import SessionLocal
from app.models import ChainNode, ChainEdge, EdgeCondition

def migrate_router_conditions():
    db = SessionLocal()
    
    # Находим все router узлы
    routers = db.query(ChainNode).filter(ChainNode.node_type == "router").all()
    
    for router in routers:
        print(f"Migrating router {router.id}")
        
        # Получаем все рёбра от этого router
        edges = db.query(ChainEdge).filter(ChainEdge.source_node_id == router.id).all()
        
        conditions = []
        port_index = 0
        
        for edge in edges:
            # Получаем условия этого ребра
            edge_conditions = db.query(EdgeCondition).filter(EdgeCondition.edge_id == edge.id).all()
            
            if edge_conditions:
                # Есть условия — создаём condition port
                for ec in edge_conditions:
                    cond_id = f"cond_{edge.id}_{ec.id}"
                    conditions.append({
                        "id": cond_id,
                        "condition_type": ec.condition_type,
                        "params": ec.params,
                        "label": format_condition_label(ec),
                        "port_index": port_index
                    })
                    
                    # Обновляем edge
                    edge.source_port_id = cond_id
                    port_index += 1
            else:
                # Нет условий — это fallback
                cond_id = f"cond_fallback_{edge.id}"
                conditions.append({
                    "id": cond_id,
                    "condition_type": "fallback",
                    "params": {},
                    "label": "Любой (fallback)",
                    "port_index": port_index
                })
                
                edge.source_port_id = cond_id
                port_index += 1
        
        # Обновляем router payload
        router.payload["conditions"] = conditions
        
    db.commit()
    db.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_router_conditions()
```

---

## Summary: Что менять

### Frontend:

1. **Constants.js**
   - Добавить `NODE_DIMENSIONS` с динамической высотой для router
   - Добавить `CONDITION_PORT` размеры

2. **NodeCard.jsx**
   - Заменить обычный `NodeCard` на `RouterNodeCard` для router
   - Добавить компонент `ConditionPort`
   - Добавить `formatConditionLabel` helper

3. **geometry.js**
   - Обновить `getConnectionPoints` для учёта `source_port_id`

4. **EdgeLine.jsx**
   - Передавать `edge` в `getConnectionPoints`
   - Убрать отображение condition бейджей

5. **ConnectionDrawing.js**
   - Обновить `drawingFrom` state структуру
   - Обновить `onPortMouseDown` для condition ports
   - Обновить `onNodeClick` для передачи `sourcePortId`

6. **Reducer.js**
   - Добавить `source_port_id` в `ADD_EDGE`
   - Добавить `ADD_ROUTER_CONDITION` action
   - Добавить `DELETE_ROUTER_CONDITION` action

7. **Modals.jsx**
   - Упростить `NodeEditorModal` для router (убрать редактирование условий)
   - Добавить `AddConditionModal`

### Backend:

8. **models.py**
   - Добавить `source_port_id` в `ChainEdge` модель
   - Удалить `EdgeCondition` модель (опционально)

9. **tasks.py**
   - Обновить `find_next_node_from_router` для чтения условий из `node.payload.conditions`
   - Обновить для использования `edge.source_port_id`

10. **Database**
    - Добавить migration для `source_port_id` колонки
    - Запустить migration script для существующих данных

---

## Преимущества новой реализации

✅ **Визуальная ясность** — условия видны на самом узле  
✅ **Лучший UX** — не нужно кликать на рёбра чтобы увидеть условия  
✅ **Легче понять логику** — видно сколько веток из router  
✅ **Похоже на Miro/Figma** — профессиональный вид  
✅ **Drag & Drop** — можно менять порядок условий (перетаскиванием)  
✅ **Масштабируемость** — легко добавить много условий  

Готово! 🎨
