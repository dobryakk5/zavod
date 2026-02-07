# Timer Node — Standalone Implementation

Этот файл содержит только код для узла-таймера (задержки), который можно интегрировать в существующий chain builder.

---

## 1. Константы и типы

```javascript
// Добавить к NODE_COLORS
const NODE_COLORS = {
  // ... existing types
  timer: { 
    bg: "#fef3c7",        // Янтарно-жёлтый фон
    border: "#f59e0b",    // Оранжевая рамка
    accent: "#d97706",    // Тёмно-оранжевый акцент
    shadow: "0 4px 12px rgba(245,158,11,0.15)", 
    icon: "⏱️",
    label: "ЗАДЕРЖКА"
  },
};

// Добавить к CONDITION_LABELS (если нужно)
const CONDITION_LABELS = {
  // ... existing conditions
  // Timer не использует условия на рёбрах — он всегда переходит к следующему узлу после истечения времени
};
```

---

## 2. Reducer: Создание timer узла

```javascript
// В graphReducer, в case "ADD_NODE":
case "ADD_NODE": {
  const node = { 
    id: uid(), 
    chain_id: state.chain.id, 
    node_type: action.nodeType || "text",
    
    // Для timer узла — специальный payload
    payload: (() => {
      if (action.nodeType === "router") {
        return { label: "Новый роутер", description: "" };
      } else if (action.nodeType === "timer") {
        return { 
          duration_seconds: 60,           // Длительность ожидания
          label: "Ожидание 1 мин",        // Название таймера
          show_countdown: false,          // Показывать ли обратный отсчёт пользователю
          countdown_message: null         // Сообщение с обратным отсчётом (опционально)
        };
      } else {
        return { text: "Новое сообщение" };
      }
    })(),
    
    delay_seconds: 0,  // Timer не использует delay_seconds — у него своя логика
    pos_x: action.x, 
    pos_y: action.y 
  };
  return { ...state, nodes: [...state.nodes, node], dirty: true };
}
```

---

## 3. Toolbar: Кнопка добавления таймера

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
            <div className="absolute top-full right-0 mt-1 bg-white border rounded-lg shadow-lg z-20 min-w-[200px]">
              
              {/* Existing node types */}
              <button onClick={() => { onAddNode("text"); setAddMenuOpen(false); }} className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b">
                <span className="text-lg">💬</span>
                <span>Текст</span>
              </button>
              
              <button onClick={() => { onAddNode("photo"); setAddMenuOpen(false); }} className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b">
                <span className="text-lg">📷</span>
                <span>Фото</span>
              </button>
              
              <button onClick={() => { onAddNode("buttons"); setAddMenuOpen(false); }} className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b">
                <span className="text-lg">🔘</span>
                <span>Кнопки</span>
              </button>
              
              {/* Router */}
              <button onClick={() => { onAddNode("router"); setAddMenuOpen(false); }} className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b">
                <span className="text-lg">🔀</span>
                <div>
                  <div className="font-semibold">Роутер</div>
                  <div className="text-xs text-slate-500">Условие/ветвление</div>
                </div>
              </button>
              
              {/* NEW: Timer */}
              <button onClick={() => { onAddNode("timer"); setAddMenuOpen(false); }} className="flex items-center gap-2 w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50">
                <span className="text-lg">⏱️</span>
                <div>
                  <div className="font-semibold">Задержка</div>
                  <div className="text-xs text-slate-500">Ожидание/таймер</div>
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

## 4. NodeCard: Отображение timer узла

```javascript
function NodeCard({ node, isStart, isHovered, isSelected, ... }) {
  const c = NODE_COLORS[node.node_type];
  const isRouter = node.node_type === "router";
  const isTimer = node.node_type === "timer";

  // Форматирование длительности
  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds}с`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}м`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}ч`;
    return `${Math.floor(seconds / 86400)}д`;
  };

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
          {isTimer ? (
            <span className="text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>
              ЗАДЕРЖКА
            </span>
          ) : isRouter ? (
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
        {isTimer ? (
          <div className="text-center">
            <div className="text-3xl font-bold mb-1" style={{ color: c.accent }}>
              {formatDuration(node.payload.duration_seconds || 60)}
            </div>
            <p className="text-xs text-slate-600">
              {node.payload.label || "Ожидание"}
            </p>
            {node.payload.show_countdown && (
              <div className="mt-1 text-xs text-slate-500">
                ⏳ с обратным отсчётом
              </div>
            )}
          </div>
        ) : isRouter ? (
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
      
      {/* Footer - не показываем для router и timer */}
      {!isRouter && !isTimer && node.delay_seconds > 0 && (
        <div className="px-4 py-1 text-xs text-slate-500 border-t" style={{ borderColor: c.border + '40' }}>
          ⏱ {node.delay_seconds}с
        </div>
      )}

      {/* Connection ports */}
      {(isHovered || isSelected) && (
        <>
          <div
            onMouseDown={(e) => { e.stopPropagation(); onPortMouseDown(node.id, 'bottom'); }}
            className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 cursor-crosshair hover:scale-125 transition-transform z-10"
            style={{ borderColor: c.accent }}
          />
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2"
            style={{ backgroundColor: c.bg, borderColor: c.border }}
          />
        </>
      )}
    </div>
  );
}
```

---

## 5. EdgeLine: Линии от timer (обычные, без особенностей)

```javascript
// Timer не требует специальной визуализации линий
// Линии от timer выглядят как обычные (без условий - dashed)
// Код не меняется
```

---

## 6. NodeEditorModal: Редактирование timer

```javascript
function NodeEditorModal({ node, onSave, onClose }) {
  const [form, setForm] = useState({ 
    ...node, 
    payload: { ...node.payload }, 
    buttons: node.payload.buttons ? [...node.payload.buttons] : [] 
  });
  
  const setP = (k, v) => setForm(f => ({ ...f, payload: { ...f.payload, [k]: v } }));
  const isRouter = node.node_type === "router";
  const isTimer = node.node_type === "timer";

  const handleSave = () => {
    if (isRouter) {
      onSave({ payload: { label: form.payload.label, description: form.payload.description } });
      return;
    }
    
    if (isTimer) {
      onSave({ 
        payload: { 
          duration_seconds: form.payload.duration_seconds,
          label: form.payload.label,
          show_countdown: form.payload.show_countdown,
          countdown_message: form.payload.countdown_message
        } 
      });
      return;
    }
    
    // Normal nodes: existing logic
    const payload = { ...form.payload };
    if (form.node_type === "buttons") payload.buttons = form.buttons.filter(Boolean);
    onSave({ node_type: form.node_type, payload, delay_seconds: form.delay_seconds });
  };

  // Duration presets
  const DURATION_PRESETS = [
    { label: "30 секунд", value: 30 },
    { label: "1 минута", value: 60 },
    { label: "5 минут", value: 300 },
    { label: "15 минут", value: 900 },
    { label: "30 минут", value: 1800 },
    { label: "1 час", value: 3600 },
    { label: "2 часа", value: 7200 },
    { label: "6 часов", value: 21600 },
    { label: "12 часов", value: 43200 },
    { label: "1 день", value: 86400 },
    { label: "2 дня", value: 172800 },
    { label: "7 дней", value: 604800 },
  ];

  return (
    <Dialog open onClose={onClose} title={
      isTimer ? "Редактирование задержки" : 
      isRouter ? "Редактирование роутера" : 
      "Редактирование узла"
    }>
      <div className="space-y-4">
        
        {isTimer ? (
          // TIMER FORM
          <>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">
              <p className="text-sm text-amber-900">
                ⏱️ <strong>Задержка</strong> — узел который ждёт указанное время перед переходом к следующему шагу.
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Название задержки
              </label>
              <input 
                value={form.payload.label || ""} 
                onChange={e => setP("label", e.target.value)} 
                className="w-full px-3 py-2 border border-slate-300 rounded-lg" 
                placeholder="Ожидание 1 минуту"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Длительность
              </label>
              
              {/* Quick presets */}
              <div className="grid grid-cols-3 gap-2 mb-3">
                {DURATION_PRESETS.slice(0, 6).map(preset => (
                  <button
                    key={preset.value}
                    onClick={() => setP("duration_seconds", preset.value)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      form.payload.duration_seconds === preset.value
                        ? 'bg-amber-100 text-amber-900 border-2 border-amber-400'
                        : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              
              {/* Custom duration */}
              <div className="flex gap-2 items-center">
                <input 
                  type="number" 
                  value={form.payload.duration_seconds || 60} 
                  onChange={e => setP("duration_seconds", Math.max(1, parseInt(e.target.value) || 60))} 
                  className="w-32 px-3 py-2 border border-slate-300 rounded-lg" 
                  min="1"
                />
                <span className="text-sm text-slate-600">секунд</span>
                
                {/* Human-readable */}
                <span className="text-sm text-slate-500 ml-auto">
                  = {(() => {
                    const s = form.payload.duration_seconds || 60;
                    if (s < 60) return `${s} сек`;
                    if (s < 3600) return `${Math.floor(s / 60)} мин`;
                    if (s < 86400) return `${Math.floor(s / 3600)} ч ${Math.floor((s % 3600) / 60)} мин`;
                    return `${Math.floor(s / 86400)} дн ${Math.floor((s % 86400) / 3600)} ч`;
                  })()}
                </span>
              </div>
              
              {/* More presets (collapsed) */}
              <details className="mt-2">
                <summary className="text-xs text-slate-600 cursor-pointer hover:text-slate-900">
                  Ещё варианты...
                </summary>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  {DURATION_PRESETS.slice(6).map(preset => (
                    <button
                      key={preset.value}
                      onClick={() => setP("duration_seconds", preset.value)}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        form.payload.duration_seconds === preset.value
                          ? 'bg-amber-100 text-amber-900 border-2 border-amber-400'
                          : 'bg-slate-50 text-slate-700 border border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </details>
            </div>
            
            {/* Countdown option */}
            <div className="border-t pt-4">
              <label className="flex items-start gap-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={form.payload.show_countdown || false}
                  onChange={e => setP("show_countdown", e.target.checked)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="text-sm font-medium text-slate-700">
                    Показывать обратный отсчёт
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Пользователь увидит таймер: "⏳ Осталось: 2:45"
                  </div>
                </div>
              </label>
              
              {form.payload.show_countdown && (
                <div className="mt-3 ml-6">
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Текст сообщения с таймером (опционально)
                  </label>
                  <input 
                    value={form.payload.countdown_message || ""} 
                    onChange={e => setP("countdown_message", e.target.value)} 
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" 
                    placeholder="Подготавливаем для вас контент..."
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Если не указано — будет просто "⏳ Осталось: X:XX"
                  </p>
                </div>
              )}
            </div>
            
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
              <p className="text-xs text-slate-600">
                💡 <strong>Как это работает:</strong> После достижения этого узла бот ждёт указанное время, затем автоматически переходит к следующему узлу.
              </p>
            </div>
          </>
        ) : isRouter ? (
          // ROUTER FORM (existing code)
          <>
            {/* ... existing router form ... */}
          </>
        ) : (
          // NORMAL NODE FORM (existing code)
          <>
            {/* ... existing normal node form ... */}
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

## 7. ConditionEditorModal: Timer не использует условия

```javascript
// Timer всегда идёт к следующему узлу после истечения времени
// Условия на рёбрах от timer не нужны
// Если от timer идёт несколько рёбер — берётся первое (priority=0)
```

---

## 8. Backend: Database Schema

```sql
-- Таблица nodes уже поддерживает timer через node_type
-- Никаких изменений не нужно!

-- Пример timer node в БД:
INSERT INTO chain_nodes (chain_id, node_type, payload, delay_seconds, pos_x, pos_y)
VALUES (
  1,
  'timer',  -- Тип узла
  '{
    "duration_seconds": 300,
    "label": "Ожидание 5 минут",
    "show_countdown": true,
    "countdown_message": "Готовим для вас контент..."
  }',
  0,  -- Timer использует payload.duration_seconds, не delay_seconds
  100,
  280
);

-- Рёбра от timer:
INSERT INTO chain_edges (chain_id, source_node_id, target_node_id, priority)
VALUES (1, 5, 6, 0);  -- Без условий — просто переход после таймера

-- Можно иметь несколько рёбер (но условия игнорируются, берётся первое по priority):
INSERT INTO chain_edges (chain_id, source_node_id, target_node_id, priority)
VALUES 
  (1, 5, 6, 0),  -- Основной переход
  (1, 5, 7, 1);  -- Альтернативный (не будет использован)
```

---

## 9. Backend: Execution Logic

```python
# tasks.py

from celery import shared_task
from datetime import datetime, timedelta
import time

@shared_task
def execute_timer_node(chain_id, node_id, user_id, telegram_chat_id):
    """
    Выполняет timer узел — ждёт указанное время, затем переходит к следующему
    
    Args:
        chain_id: ID цепочки
        node_id: ID timer узла
        user_id: ID пользователя
        telegram_chat_id: Telegram chat ID для отправки countdown
    """
    from app.models import ChainNode, ChainEdge, UserState
    from app.database import SessionLocal
    from app.telegram import send_message, edit_message
    
    db = SessionLocal()
    
    try:
        # Получаем timer узел
        node = db.query(ChainNode).filter(ChainNode.id == node_id).first()
        if not node or node.node_type != "timer":
            print(f"[ERROR] Node {node_id} is not a timer")
            return
        
        duration = node.payload.get("duration_seconds", 60)
        show_countdown = node.payload.get("show_countdown", False)
        countdown_message = node.payload.get("countdown_message")
        
        # Если нужно показывать обратный отсчёт
        countdown_msg_id = None
        if show_countdown:
            # Отправляем первое сообщение с таймером
            text = countdown_message or "⏳"
            text += f"\nОсталось: {format_time_remaining(duration)}"
            
            response = send_message(
                chat_id=telegram_chat_id,
                text=text
            )
            countdown_msg_id = response.message_id
        
        # Ждём с обновлением каждые N секунд
        start_time = time.time()
        update_interval = min(10, duration // 10)  # Обновляем каждые 10 сек или чаще
        
        while True:
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            
            if remaining <= 0:
                break
            
            # Обновляем сообщение если показываем countdown
            if show_countdown and countdown_msg_id and remaining > update_interval:
                text = countdown_message or "⏳"
                text += f"\nОсталось: {format_time_remaining(int(remaining))}"
                
                edit_message(
                    chat_id=telegram_chat_id,
                    message_id=countdown_msg_id,
                    text=text
                )
            
            # Спим до следующего обновления
            time.sleep(min(update_interval, remaining))
        
        # Удаляем countdown сообщение или обновляем на "Готово!"
        if show_countdown and countdown_msg_id:
            text = countdown_message or "✅ Готово!"
            edit_message(
                chat_id=telegram_chat_id,
                message_id=countdown_msg_id,
                text=text
            )
        
        # Находим следующий узел
        next_edge = db.query(ChainEdge).filter(
            ChainEdge.source_node_id == node_id
        ).order_by(ChainEdge.priority).first()
        
        if not next_edge:
            print(f"[WARN] Timer node {node_id} has no outgoing edges")
            return
        
        next_node_id = next_edge.target_node_id
        
        # Обновляем состояние пользователя
        user_state = db.query(UserState).filter(
            UserState.user_id == user_id,
            UserState.chain_id == chain_id
        ).first()
        
        if user_state:
            user_state.current_node_id = next_node_id
            db.commit()
        
        # Запускаем выполнение следующего узла
        from app.tasks import execute_chain_node
        execute_chain_node.delay(chain_id, next_node_id, user_id, telegram_chat_id)
        
    finally:
        db.close()


def format_time_remaining(seconds):
    """Форматирует оставшееся время в читаемый вид"""
    if seconds < 60:
        return f"{seconds}с"
    
    minutes = seconds // 60
    secs = seconds % 60
    
    if minutes < 60:
        return f"{minutes}:{secs:02d}"
    
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}:{secs:02d}"


# В основном обработчике цепочки:
def execute_chain_node(chain_id, node_id, user_id, telegram_chat_id, message=None):
    """Выполняет узел цепочки"""
    from app.models import ChainNode
    from app.database import SessionLocal
    
    db = SessionLocal()
    node = db.query(ChainNode).filter(ChainNode.id == node_id).first()
    db.close()
    
    if not node:
        return
    
    # Разные типы узлов
    if node.node_type == "text":
        execute_text_node(chain_id, node_id, user_id, telegram_chat_id)
    
    elif node.node_type == "photo":
        execute_photo_node(chain_id, node_id, user_id, telegram_chat_id)
    
    elif node.node_type == "buttons":
        execute_buttons_node(chain_id, node_id, user_id, telegram_chat_id)
    
    elif node.node_type == "router":
        # Router не выполняется сам — он только проверяет условия при получении сообщения
        # См. router_node_implementation.md
        pass
    
    elif node.node_type == "timer":
        # NEW: Timer node
        execute_timer_node.delay(chain_id, node_id, user_id, telegram_chat_id)
    
    else:
        print(f"[WARN] Unknown node type: {node.node_type}")
```

---

## 10. Альтернативная реализация: Celery ETA

```python
# Более эффективная реализация через Celery ETA (отложенное выполнение)

from celery import shared_task
from datetime import datetime, timedelta

@shared_task
def execute_timer_node_eta(chain_id, node_id, user_id, telegram_chat_id):
    """
    Выполняет timer узел через Celery ETA (более эффективно)
    """
    from app.models import ChainNode, ChainEdge
    from app.database import SessionLocal
    
    db = SessionLocal()
    
    try:
        node = db.query(ChainNode).filter(ChainNode.id == node_id).first()
        if not node or node.node_type != "timer":
            return
        
        duration = node.payload.get("duration_seconds", 60)
        show_countdown = node.payload.get("show_countdown", False)
        
        # Если показываем countdown — нужна отдельная задача для обновлений
        if show_countdown:
            # Запускаем задачу обновления countdown
            countdown_task.delay(
                telegram_chat_id=telegram_chat_id,
                duration_seconds=duration,
                message_text=node.payload.get("countdown_message")
            )
        
        # Находим следующий узел
        next_edge = db.query(ChainEdge).filter(
            ChainEdge.source_node_id == node_id
        ).order_by(ChainEdge.priority).first()
        
        if not next_edge:
            return
        
        next_node_id = next_edge.target_node_id
        
        # Запускаем следующий узел с задержкой через ETA
        from app.tasks import execute_chain_node
        execute_chain_node.apply_async(
            args=[chain_id, next_node_id, user_id, telegram_chat_id],
            eta=datetime.utcnow() + timedelta(seconds=duration)
        )
        
    finally:
        db.close()


@shared_task
def countdown_task(telegram_chat_id, duration_seconds, message_text=None):
    """Отдельная задача для обновления countdown"""
    from app.telegram import send_message, edit_message
    import time
    
    # Отправляем первое сообщение
    text = message_text or "⏳"
    text += f"\nОсталось: {format_time_remaining(duration_seconds)}"
    
    response = send_message(chat_id=telegram_chat_id, text=text)
    msg_id = response.message_id
    
    # Обновляем каждые 10 секунд
    start_time = time.time()
    update_interval = min(10, duration_seconds // 10)
    
    while True:
        elapsed = time.time() - start_time
        remaining = duration_seconds - elapsed
        
        if remaining <= 0:
            break
        
        if remaining > update_interval:
            text = message_text or "⏳"
            text += f"\nОсталось: {format_time_remaining(int(remaining))}"
            edit_message(chat_id=telegram_chat_id, message_id=msg_id, text=text)
        
        time.sleep(min(update_interval, remaining))
    
    # Финальное обновление
    text = message_text or "✅ Готово!"
    edit_message(chat_id=telegram_chat_id, message_id=msg_id, text=text)
```

---

## 11. Примеры использования

### Пример 1: Простая задержка перед отправкой

```
Узел 1 (text): "Спасибо за заказ!"
    ↓
Узел 2 (timer): "Ожидание 5 минут" [duration=300, show_countdown=false]
    ↓
Узел 3 (text): "Ваш заказ готов к отправке 📦"
```

**Как это работает:**
1. Пользователь видит "Спасибо за заказ!"
2. Бот ждёт 5 минут (в фоне, без сообщений)
3. Через 5 минут отправляется "Ваш заказ готов к отправке"

---

### Пример 2: С обратным отсчётом

```
Узел 1 (text): "Готовим для вас персональное предложение..."
    ↓
Узел 2 (timer): 
  - duration_seconds: 60
  - show_countdown: true
  - countdown_message: "🎁 Анализируем ваши предпочтения..."
    ↓
Узел 3 (text): "Вот что мы для вас подобрали! 🎉"
```

**Что видит пользователь:**
```
> Готовим для вас персональное предложение...
> 🎁 Анализируем ваши предпочтения...
  Осталось: 1:00
  
[Сообщение обновляется каждые 10 секунд]
  
> 🎁 Анализируем ваши предпочтения...
  Осталось: 0:50
  
...

> ✅ Готово!
> Вот что мы для вас подобрали! 🎉
```

---

### Пример 3: Многоуровневые напоминания

```
Узел 1 (text): "Подписка оформлена! Первый урок через 24 часа"
    ↓
Узел 2 (timer): "24 часа" [duration=86400]
    ↓
Узел 3 (text): "📚 Урок 1: Введение"
    ↓
Узел 4 (timer): "3 дня" [duration=259200]
    ↓
Узел 5 (text): "📚 Урок 2: Основы"
```

**Use case:** Образовательные курсы с расписанием

---

### Пример 4: Напоминания с выбором времени

```
Узел 1 (buttons): "Когда напомнить?" [15 мин] [1 час] [Завтра]
    ↙         ↓         ↘
[button]  [button]  [button]
  ↓          ↓          ↓
Timer     Timer     Timer
15 мин    1 час     24 часа
  ↓          ↓          ↓
  └──────────┴──────────┘
            ↓
Узел 2 (text): "⏰ Напоминание!"
```

---

### Пример 5: Комбинация с Router

```
Узел 1 (text): "Отправьте документ"
    ↓
Узел 2 (router): "Проверка типа"
    ├─→ [content_type=document] → Узел 3: "Обрабатываем..."
    └─→ [timeout=60]            → Узел 4: "Время вышло"
                                      ↓
                                  Узел 5 (timer): 5 минут
                                      ↓
                                  Узел 6: "Попробуйте ещё раз?"
```

---

## 12. Дополнительные фичи (опционально)

### 12.1 Cancellable Timer

```javascript
// Payload для timer с возможностью отмены
{
  "duration_seconds": 300,
  "label": "Ожидание 5 минут",
  "show_countdown": true,
  "cancellable": true,           // NEW: Можно отменить
  "cancel_button_text": "Отмена" // Текст кнопки отмены
}
```

```python
# Backend
if node.payload.get("cancellable"):
    # Отправляем кнопку отмены
    send_message(
        chat_id=telegram_chat_id,
        text="⏳ Ожидание...",
        reply_markup={
            "inline_keyboard": [[
                {"text": node.payload.get("cancel_button_text", "Отмена"), 
                 "callback_data": f"cancel_timer:{node.id}"}
            ]]
        }
    )
```

---

### 12.2 Dynamic Timer (переменная длительность)

```javascript
// Payload с переменной длительностью
{
  "duration_type": "dynamic",      // NEW: Длительность зависит от переменной
  "duration_variable": "wait_time", // Имя переменной в user_state
  "default_duration": 60,          // Дефолт если переменная не найдена
  "label": "Персональное ожидание"
}
```

```python
# Backend
if node.payload.get("duration_type") == "dynamic":
    var_name = node.payload.get("duration_variable")
    user_state = db.query(UserState).filter(...).first()
    duration = user_state.variables.get(var_name, node.payload.get("default_duration", 60))
```

---

## Интеграция

Чтобы добавить timer в существующий chain builder:

1. Скопируй константы из раздела 1
2. Добавь код из разделов 2-6 в соответствующие компоненты
3. Обнови Backend согласно разделам 8-9 (или 10 для ETA)
4. Протестируй примеры из раздела 11

Готово! ⏱️
