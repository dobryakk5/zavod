# Router Node — Standalone Implementation

Этот файл содержит только код для узла-роутера, который можно интегрировать в существующий chain builder.

---

## 1. Константы и типы

```javascript
// Добавить к NODE_COLORS
const NODE_COLORS = {
  // ... existing types
  router: { 
    bg: "#faf5ff",        // Фиолетовый фон
    border: "#a855f7",    // Фиолетовая рамка
    accent: "#9333ea",    // Тёмно-фиолетовый акцент
    shadow: "0 4px 12px rgba(168,85,247,0.15)", 
    icon: "🔀",
    label: "РОУТЕР"
  },
};

// Добавить к CONDITION_LABELS
const CONDITION_LABELS = {
  // ... existing conditions
  content_type:   "Тип контента",    // NEW: Check message type
  has_media:      "Есть медиа?",     // NEW: Has any media attachment
  text_equals:    "Текст =",         // NEW: Exact match
  has_entities:   "Содержит",        // NEW: email/phone/url/hashtag
};
```

---

## 2. Reducer: Создание router узла

```javascript
// В graphReducer, в case "ADD_NODE":
case "ADD_NODE": {
  const node = { 
    id: uid(), 
    chain_id: state.chain.id, 
    node_type: action.nodeType || "text",
    
    // Для router узла — специальный payload
    payload: action.nodeType === "router" 
      ? { label: "Новый роутер", description: "" }  // Router payload
      : { text: "Новое сообщение" },                 // Default payload
    
    delay_seconds: 0, 
    pos_x: action.x, 
    pos_y: action.y 
  };
  return { ...state, nodes: [...state.nodes, node], dirty: true };
}
```

---

## 3. Toolbar: Кнопка добавления роутера

```javascript
function Toolbar({ chain, dirty, onSave, onAddNode, saving }) {
  const [addMenuOpen, setAddMenuOpen] = useState(false);

  return (
    <div className="flex items-center gap-4 px-6 py-4 bg-white border-b">
      {/* ... existing toolbar content */}
      
      {/* Dropdown для выбора типа узла */}
      <div className="relative">
        <button 
          onClick={() => setAddMenuOpen(!addMenuOpen)} 
          className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-sm font-medium"
        >
          + Узел ▾
        </button>
        
        {addMenuOpen && (
          <>
            <div onClick={() => setAddMenuOpen(false)} className="fixed inset-0 z-10" />
            <div className="absolute top-full right-0 mt-1 bg-white border rounded-lg shadow-lg z-20 min-w-[180px]">
              
              <button 
                onClick={() => { onAddNode("text"); setAddMenuOpen(false); }} 
                className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b"
              >
                <span className="text-lg">💬</span>
                <span>Текст</span>
              </button>
              
              <button 
                onClick={() => { onAddNode("photo"); setAddMenuOpen(false); }} 
                className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b"
              >
                <span className="text-lg">📷</span>
                <span>Фото</span>
              </button>
              
              <button 
                onClick={() => { onAddNode("buttons"); setAddMenuOpen(false); }} 
                className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b"
              >
                <span className="text-lg">🔘</span>
                <span>Кнопки</span>
              </button>
              
              {/* NEW: Router option */}
              <button 
                onClick={() => { onAddNode("router"); setAddMenuOpen(false); }} 
                className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50"
              >
                <span className="text-lg">🔀</span>
                <div>
                  <div className="font-semibold">Роутер</div>
                  <div className="text-xs text-slate-500">Условие/ветвление</div>
                </div>
              </button>
              
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Обработчик в Main App:
const handleAddNode = (nodeType = "text") => {
  const cx = (canvasRef.current?.clientWidth || 600) / 2 - pan.x - NODE_W / 2;
  const cy = (canvasRef.current?.clientHeight || 400) / 2 - pan.y - NODE_H / 2;
  dispatch({ type: "ADD_NODE", x: cx, y: cy, nodeType });
};
```

---

## 4. NodeCard: Отображение router узла

```javascript
function NodeCard({ node, isStart, isHovered, isSelected, ... }) {
  const c = NODE_COLORS[node.node_type];
  const isRouter = node.node_type === "router";

  return (
    <div
      /* ... existing props */
      style={{
        backgroundColor: c.bg,
        borderColor: isSelected ? c.accent : c.border,
        boxShadow: isHovered || isSelected ? c.shadow : '0 2px 8px rgba(0,0,0,0.1)',
        ringColor: c.accent,
      }}
    >
      {/* Header */}
      <div className="px-4 py-2 flex items-center justify-between border-b" style={{ borderColor: c.border + '40' }}>
        <div className="flex items-center gap-2">
          <span className="text-lg">{c.icon}</span>
          {isRouter ? (
            <span className="text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>
              РОУТЕР
            </span>
          ) : (
            <span className="text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>
              {node.node_type}
            </span>
          )}
        </div>
        {isStart && <span className="px-2 py-0.5 rounded-full bg-emerald-600 text-white text-xs font-bold">START</span>}
      </div>
      
      {/* Content */}
      <div className="px-4 py-3 flex-1 flex items-center justify-center">
        {isRouter ? (
          <div className="text-center">
            <p className="text-sm font-semibold text-slate-700">
              {node.payload.label || "Router"}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Проверяет условия
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-700 line-clamp-2 leading-snug">
            {node.payload.text || node.payload.caption || "📷"}
          </p>
        )}
      </div>
      
      {/* Footer - только для НЕ-router узлов */}
      {!isRouter && node.delay_seconds > 0 && (
        <div className="px-4 py-1 text-xs text-slate-500 border-t" style={{ borderColor: c.border + '40' }}>
          ⏱ {node.delay_seconds}с
        </div>
      )}

      {/* Connection ports */}
      {/* ... existing port code */}
    </div>
  );
}
```

---

## 5. EdgeLine: Фиолетовые линии от router

```javascript
function EdgeLine({ edge, srcNode, tgtNode, isHovered, onClick, onDelete, conditions }) {
  const { sx, sy, tx, ty } = getConnectionPoints(srcNode, tgtNode);
  const path = getCurvedPath(sx, sy, tx, ty);
  const mid = getEdgeMid(sx, sy, tx, ty);
  const hasConditions = conditions.length > 0;
  
  // NEW: Check if source is router
  const isFromRouter = srcNode.node_type === "router";

  return (
    <g>
      {/* Invisible hit area */}
      <path d={path} fill="none" stroke="transparent" strokeWidth={20} onClick={onClick} className="cursor-pointer" />
      
      {/* Visible line */}
      <path
        d={path}
        fill="none"
        stroke={
          isHovered ? "#0f172a" :              // Hover: black
          isFromRouter ? "#9333ea" :           // From router: purple
          hasConditions ? "#64748b" : "#cbd5e1"  // Normal
        }
        strokeWidth={isHovered ? 3 : isFromRouter ? 2.5 : 2}
        strokeDasharray={hasConditions ? "none" : "8 4"}
        className="transition-all pointer-events-none"
      />
      
      {/* Arrowhead */}
      <circle 
        cx={tx} 
        cy={ty} 
        r={isHovered ? 6 : 5} 
        fill={isHovered ? "#0f172a" : isFromRouter ? "#9333ea" : "#64748b"} 
        className="transition-all pointer-events-none" 
      />

      {/* Condition badges - фиолетовые для router */}
      {conditions.slice(0, 3).map((cond, i) => (
        <foreignObject key={cond.id} x={mid.x - 60} y={mid.y - 12 - i * 22} width={120} height={20}>
          <div className={`backdrop-blur border rounded-full px-2 py-0.5 text-xs font-medium shadow-sm text-center ${
            isFromRouter 
              ? 'bg-purple-100/95 border-purple-300 text-purple-700'  // Router style
              : 'bg-white/95 border-slate-300 text-slate-700'         // Normal style
          }`}>
            {CONDITION_LABELS[cond.condition_type]}
            {cond.params.message_type && ` = ${cond.params.message_type}`}
            {cond.params.button_label && ` "${cond.params.button_label.slice(0,8)}"`}
            {cond.params.entity_type && ` [${cond.params.entity_type}]`}
          </div>
        </foreignObject>
      ))}

      {/* Delete button */}
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

## 6. NodeEditorModal: Редактирование router

```javascript
function NodeEditorModal({ node, onSave, onClose }) {
  const [form, setForm] = useState({ 
    ...node, 
    payload: { ...node.payload }, 
    buttons: node.payload.buttons ? [...node.payload.buttons] : [] 
  });
  
  const setP = (k, v) => setForm(f => ({ ...f, payload: { ...f.payload, [k]: v } }));
  const isRouter = node.node_type === "router";

  const handleSave = () => {
    if (isRouter) {
      // Router: сохраняем только label и description
      onSave({ 
        payload: { 
          label: form.payload.label,
          description: form.payload.description 
        } 
      });
      return;
    }
    
    // Normal nodes: existing logic
    const payload = { ...form.payload };
    if (form.node_type === "buttons") payload.buttons = form.buttons.filter(Boolean);
    onSave({ node_type: form.node_type, payload, delay_seconds: form.delay_seconds });
  };

  return (
    <Dialog open onClose={onClose} title={isRouter ? "Редактирование роутера" : "Редактирование узла"}>
      <div className="space-y-4">
        
        {isRouter ? (
          // ROUTER FORM
          <>
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 mb-4">
              <p className="text-sm text-purple-900">
                🔀 <strong>Роутер</strong> — узел который анализирует входящее сообщение и направляет по веткам в зависимости от условий.
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Название роутера
              </label>
              <input 
                value={form.payload.label || ""} 
                onChange={e => setP("label", e.target.value)} 
                className="w-full px-3 py-2 border border-slate-300 rounded-lg" 
                placeholder="Проверка типа сообщения"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Описание (опционально)
              </label>
              <textarea 
                value={form.payload.description || ""} 
                onChange={e => setP("description", e.target.value)} 
                className="w-full px-3 py-2 border border-slate-300 rounded-lg resize-none" 
                rows={2}
                placeholder="Дополнительная информация о роутере"
              />
            </div>
            
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
              <p className="text-xs text-slate-600">
                💡 <strong>Условия</strong> настраиваются на рёбрах (кликните на линию от роутера)
              </p>
            </div>
          </>
        ) : (
          // NORMAL NODE FORM
          <>
            {/* Existing form fields for text/photo/buttons */}
          </>
        )}

        <div className="flex justify-end gap-3 pt-4">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">
            Отмена
          </button>
          <button onClick={handleSave} className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800">
            Сохранить
          </button>
        </div>
      </div>
    </Dialog>
  );
}
```

---

## 7. ConditionEditorModal: Router-специфичные условия

```javascript
function ConditionEditorModal({ edge, srcNode, tgtNode, onSave, onClose }) {
  const [conditions, setConditions] = useState(edge.conditions ? [...edge.conditions] : []);
  const [adding, setAdding] = useState(false);
  const [newCond, setNewCond] = useState({ condition_type: "button_press", params: {} });

  const isFromRouter = srcNode?.node_type === "router";

  // При открытии модалки для router — дефолтный тип условия "content_type"
  useEffect(() => {
    if (isFromRouter) {
      setNewCond({ condition_type: "content_type", params: {} });
    }
  }, [isFromRouter]);

  const commitNew = () => {
    setConditions(c => [...c, { id: uid(), edge_id: edge.id, ...newCond }]);
    setAdding(false);
    setNewCond({ 
      condition_type: isFromRouter ? "content_type" : "button_press", 
      params: {} 
    });
  };

  return (
    <Dialog open onClose={onClose} title={`Условия: «${nodeLabel(srcNode)}» → «${nodeLabel(tgtNode)}»`}>
      <div className="space-y-4">
        
        {/* Header для router */}
        {isFromRouter && (
          <div className="bg-purple-50 border border-purple-200 rounded-lg px-4 py-3">
            <p className="text-sm text-purple-900">
              🔀 <strong>Роутер</strong> — проверяет тип или содержимое входящего сообщения и направляет по нужной ветке.
            </p>
          </div>
        )}

        {/* Existing conditions */}
        {conditions.length > 0 && (
          <div className="space-y-2">
            {conditions.map((c, i) => (
              <div 
                key={c.id} 
                className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                  isFromRouter 
                    ? 'bg-purple-50 border border-purple-200' 
                    : 'bg-slate-50'
                }`}
              >
                <span className={`text-sm font-medium ${
                  isFromRouter ? 'text-purple-900' : 'text-slate-700'
                }`}>
                  {CONDITION_LABELS[c.condition_type]}
                  {c.params.message_type && ` = ${c.params.message_type}`}
                  {c.params.button_label && ` → "${c.params.button_label}"`}
                  {c.params.entity_type && ` [${c.params.entity_type}]`}
                  {c.params.substring && ` ⊃ "${c.params.substring}"`}
                </span>
                <button onClick={() => removeCondition(i)} className="text-red-600 hover:text-red-700">×</button>
              </div>
            ))}
          </div>
        )}

        {/* Add new condition */}
        {adding ? (
          <div className={`rounded-lg p-4 space-y-3 ${
            isFromRouter 
              ? 'bg-purple-50 border border-purple-200' 
              : 'bg-slate-50'
          }`}>
            
            {/* Condition type selector */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Тип условия</label>
              <select 
                value={newCond.condition_type} 
                onChange={e => setNewCond({ condition_type: e.target.value, params: {} })} 
                className="w-full px-3 py-2 border rounded-lg"
              >
                {isFromRouter ? (
                  // Router-specific conditions
                  <>
                    <option value="content_type">Тип контента</option>
                    <option value="text_contains">Содержит текст</option>
                    <option value="text_equals">Точное совпадение</option>
                    <option value="text_regex">Regex</option>
                    <option value="has_media">Есть медиа?</option>
                    <option value="has_entities">Содержит (email/phone/url)</option>
                  </>
                ) : (
                  // Normal conditions
                  <>
                    <option value="button_press">Нажата кнопка</option>
                    <option value="text_contains">Содержит текст</option>
                    <option value="text_regex">Regex</option>
                    <option value="timeout">Таймаут</option>
                    <option value="any_reply">Любой ответ</option>
                  </>
                )}
              </select>
            </div>

            {/* 1. CONTENT TYPE */}
            {newCond.condition_type === "content_type" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Тип сообщения</label>
                <select 
                  value={newCond.params.message_type || ""} 
                  onChange={e => setNewCond(c => ({ ...c, params: { message_type: e.target.value } }))} 
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="">— выберите —</option>
                  <option value="text">Текст</option>
                  <option value="photo">Фото</option>
                  <option value="video">Видео</option>
                  <option value="audio">Аудио</option>
                  <option value="voice">Голосовое</option>
                  <option value="document">Документ</option>
                  <option value="sticker">Стикер</option>
                  <option value="location">Геолокация</option>
                  <option value="contact">Контакт</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  Проверяет тип входящего сообщения от пользователя
                </p>
              </div>
            )}

            {/* 2. HAS ENTITIES */}
            {newCond.condition_type === "has_entities" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Тип сущности</label>
                <select 
                  value={newCond.params.entity_type || ""} 
                  onChange={e => setNewCond(c => ({ ...c, params: { entity_type: e.target.value } }))} 
                  className="w-full px-3 py-2 border rounded-lg"
                >
                  <option value="">— выберите —</option>
                  <option value="email">Email</option>
                  <option value="phone">Телефон</option>
                  <option value="url">URL / ссылка</option>
                  <option value="hashtag">Хэштег</option>
                  <option value="mention">Упоминание (@username)</option>
                  <option value="cashtag">Cashtag ($AAPL)</option>
                  <option value="bot_command">Команда бота (/start)</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  Проверяет наличие email, телефона, ссылки и т.д. в тексте сообщения
                </p>
              </div>
            )}

            {/* 3. TEXT EQUALS */}
            {newCond.condition_type === "text_equals" && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Точный текст</label>
                <input 
                  value={newCond.params.exact_text || ""} 
                  onChange={e => setNewCond(c => ({ ...c, params: { exact_text: e.target.value } }))} 
                  className="w-full px-3 py-2 border rounded-lg" 
                  placeholder="да"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Точное совпадение (с учётом регистра)
                </p>
              </div>
            )}

            {/* 4. HAS MEDIA */}
            {newCond.condition_type === "has_media" && (
              <div className="bg-white border border-slate-200 rounded p-3">
                <p className="text-sm text-slate-600">
                  ✓ Проверяет наличие <strong>любого медиа-вложения</strong> (фото, видео, документ, аудио)
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Параметры не требуются
                </p>
              </div>
            )}

            {/* Existing condition param fields */}
            {/* ... button_press, text_contains, text_regex, timeout, etc. */}

            <div className="flex gap-2 pt-2">
              <button 
                onClick={commitNew} 
                className={`px-4 py-2 text-white rounded-lg ${
                  isFromRouter 
                    ? 'bg-purple-600 hover:bg-purple-700' 
                    : 'bg-emerald-600 hover:bg-emerald-700'
                }`}
              >
                Добавить
              </button>
              <button onClick={() => setAdding(false)} className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">
                Отмена
              </button>
            </div>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} className="w-full border border-dashed border-slate-300 rounded-lg py-3 text-sm text-slate-600 hover:bg-slate-50">
            + Добавить условие
          </button>
        )}

        <div className="flex justify-end gap-3 pt-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg">
            Отмена
          </button>
          <button onClick={() => { onSave(conditions); onClose(); }} className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800">
            Сохранить условия
          </button>
        </div>
      </div>
    </Dialog>
  );
}
```

---

## 8. Backend: Database Schema

```sql
-- Таблица nodes уже поддерживает router через node_type
-- Никаких изменений не нужно!

-- Пример router node в БД:
INSERT INTO chain_nodes (chain_id, node_type, payload, delay_seconds, pos_x, pos_y)
VALUES (
  1,
  'router',  -- Тип узла
  '{"label": "Проверка контента", "description": "Анализирует тип входящего сообщения"}',
  0,  -- Router не имеет delay
  100,
  280
);

-- Пример условий на ребре от router:
INSERT INTO edge_conditions (edge_id, condition_type, params)
VALUES 
  (15, 'content_type', '{"message_type": "text"}'),
  (16, 'content_type', '{"message_type": "photo"}'),
  (17, 'has_entities', '{"entity_type": "email"}');
```

---

## 9. Backend: Evaluation Logic

```python
# tasks.py или chain_executor.py

def evaluate_router_condition(condition, telegram_message):
    """
    Проверяет условие роутера на входящем Telegram сообщении
    
    Args:
        condition: dict - условие с полями condition_type и params
        telegram_message: Telegram Message object
    
    Returns:
        bool - True если условие выполнено
    """
    condition_type = condition["condition_type"]
    params = condition.get("params", {})
    
    # 1. Проверка типа контента
    if condition_type == "content_type":
        message_type = params.get("message_type")
        
        if message_type == "text":
            return bool(telegram_message.text and not telegram_message.caption)
        elif message_type == "photo":
            return bool(telegram_message.photo)
        elif message_type == "video":
            return bool(telegram_message.video)
        elif message_type == "audio":
            return bool(telegram_message.audio)
        elif message_type == "voice":
            return bool(telegram_message.voice)
        elif message_type == "document":
            return bool(telegram_message.document)
        elif message_type == "sticker":
            return bool(telegram_message.sticker)
        elif message_type == "location":
            return bool(telegram_message.location)
        elif message_type == "contact":
            return bool(telegram_message.contact)
        return False
    
    # 2. Проверка наличия медиа
    elif condition_type == "has_media":
        return bool(
            telegram_message.photo or 
            telegram_message.video or 
            telegram_message.document or 
            telegram_message.audio or 
            telegram_message.voice
        )
    
    # 3. Проверка наличия сущностей
    elif condition_type == "has_entities":
        entity_type = params.get("entity_type")
        if not telegram_message.entities:
            return False
        
        for entity in telegram_message.entities:
            if entity_type == "email" and entity.type == "email":
                return True
            elif entity_type == "phone" and entity.type == "phone_number":
                return True
            elif entity_type == "url" and entity.type in ["url", "text_link"]:
                return True
            elif entity_type == "hashtag" and entity.type == "hashtag":
                return True
            elif entity_type == "mention" and entity.type == "mention":
                return True
            elif entity_type == "cashtag" and entity.type == "cashtag":
                return True
            elif entity_type == "bot_command" and entity.type == "bot_command":
                return True
        return False
    
    # 4. Точное совпадение текста
    elif condition_type == "text_equals":
        exact_text = params.get("exact_text", "")
        text = telegram_message.text or telegram_message.caption or ""
        return text == exact_text
    
    # 5. Содержит текст (case-insensitive)
    elif condition_type == "text_contains":
        substring = params.get("substring", "").lower()
        text = (telegram_message.text or telegram_message.caption or "").lower()
        return substring in text
    
    # 6. Regex
    elif condition_type == "text_regex":
        import re
        pattern = params.get("pattern", "")
        flags_str = params.get("flags", "")
        text = telegram_message.text or telegram_message.caption or ""
        
        flags = 0
        if "i" in flags_str:
            flags |= re.IGNORECASE
        if "m" in flags_str:
            flags |= re.MULTILINE
        
        try:
            return bool(re.search(pattern, text, flags))
        except re.error:
            return False
    
    return False


def find_next_node_from_router(router_node_id, telegram_message, db):
    """
    Находит следующий узел после router на основе условий
    
    Returns:
        int or None - ID следующего узла
    """
    # Получаем все рёбра от router, отсортированные по priority
    edges = db.query(ChainEdge).filter(
        ChainEdge.source_node_id == router_node_id
    ).order_by(ChainEdge.priority).all()
    
    for edge in edges:
        # Если нет условий — это fallback
        if not edge.conditions:
            return edge.target_node_id
        
        # Проверяем все условия на ребре (AND логика)
        all_match = True
        for condition in edge.conditions:
            if not evaluate_router_condition(condition.__dict__, telegram_message):
                all_match = False
                break
        
        if all_match:
            return edge.target_node_id
    
    # Ничего не подошло
    return None
```

---

## 10. Примеры использования

### Пример 1: Роутинг по типу контента

```
Узел 1 (text): "Отправьте мне что-нибудь"
    ↓
Узел 2 (router): "Определяем тип"
    ├─→ [content_type=text]  → Узел 3: "Получил текст"
    ├─→ [content_type=photo] → Узел 4: "Получил фото"
    └─→ [fallback]           → Узел 5: "Не знаю что это"
```

### Пример 2: Проверка email в тексте

```
Узел 1 (text): "Введите ваш email"
    ↓
Узел 2 (router): "Проверка email"
    ├─→ [has_entities=email] → Узел 3: "Email получен!"
    └─→ [fallback]           → Узел 4: "Не нашёл email"
```

### Пример 3: Сложная логика

```
Узел 1 (text): "Отправьте документ или ссылку"
    ↓
Узел 2 (router): "Анализ контента"
    ├─→ [content_type=document] → Узел 3: "Обрабатываю документ"
    ├─→ [has_entities=url]      → Узел 4: "Скачиваю по ссылке"
    └─→ [fallback]              → Узел 5: "Нужен документ или ссылка"
```

---

## Интеграция

Чтобы добавить router в существующий chain builder:

1. Скопируй константы из раздела 1
2. Добавь код из раздела 2-7 в соответствующие компоненты
3. Обнови Backend согласно разделам 8-9
4. Протестируй примеры из раздела 10

Готово! 🎉
