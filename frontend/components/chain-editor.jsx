'use client';

import { useState, useReducer, useRef, useCallback, useEffect } from 'react';
import { chainsApi } from '@/lib/api/chains';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS & THEME
// ═══════════════════════════════════════════════════════════════════════════
const NODE_W = 200;
const NODE_H = 100;

const NODE_COLORS = {
  text:    { bg: "#f0fdfa", border: "#14b8a6", accent: "#0d9488", label: "Текст" },
  photo:   { bg: "#fffbeb", border: "#f59e0b", accent: "#d97706", label: "Фото" },
  buttons: { bg: "#eff6ff", border: "#3b82f6", accent: "#2563eb", label: "Кнопки" },
};

const CONDITION_LABELS = {
  button_press:  "Нажата кнопка",
  text_contains: "Содержит текст",
  text_regex:    "Regex",
  timeout:       "Таймаут",
  any_reply:     "Любой ответ",
};

let tempId = -1;
const nextTempId = () => tempId--;


// ═══════════════════════════════════════════════════════════════════════════
// HOOKS
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// REDUCER
// ═══════════════════════════════════════════════════════════════════════════
function graphReducer(state, action) {
  switch (action.type) {
    case "LOAD":
      return { ...action.payload, dirty: false };

    case "MOVE_NODE": {
      const nodes = state.nodes.map(n =>
        n.id === action.id ? { ...n, pos_x: action.x, pos_y: action.y } : n
      );
      return { ...state, nodes, dirty: true };
    }

    case "ADD_NODE": {
      return { ...state, nodes: [...state.nodes, action.node], dirty: true };
    }

    case "UPDATE_NODE": {
      const nodes = state.nodes.map(n => n.id === action.id ? { ...n, ...action.data } : n);
      return { ...state, nodes, dirty: true };
    }

    case "DELETE_NODE": {
      const nodes  = state.nodes.filter(n => n.id !== action.id);
      const edges  = state.edges.filter(e => e.source_node_id !== action.id && e.target_node_id !== action.id);
      if (!state.chain) return { ...state, nodes, edges, dirty: true };
      const startNode = state.chain.start_node_id === action.id ? null : state.chain.start_node_id;
      return { ...state, nodes, edges, chain: { ...state.chain, start_node_id: startNode }, dirty: true };
    }

    case "ADD_EDGE": {
      return { ...state, edges: [...state.edges, action.edge], dirty: true };
    }

    case "DELETE_EDGE": {
      return { ...state, edges: state.edges.filter(e => e.id !== action.id), dirty: true };
    }

    case "UPDATE_EDGE_CONDITIONS": {
      const edges = state.edges.map(e => e.id === action.edgeId ? { ...e, conditions: action.conditions } : e);
      return { ...state, edges, dirty: true };
    }

    case "SET_START_NODE":
      if (!state.chain) return state;
      return { ...state, chain: { ...state.chain, start_node_id: action.id }, dirty: true };

    case "SET_STATUS":
      if (!state.chain) return state;
      return { ...state, chain: { ...state.chain, status: action.status }, dirty: true };

    case "SAVED":
      return { ...state, dirty: false };

    default:
      return state;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATION
// ═══════════════════════════════════════════════════════════════════════════
function validateGraph(state) {
  const errors = [];
  const { chain, nodes, edges } = state;

  if (!chain) {
    return errors;
  }

  if (nodes.length === 0) {
    errors.push({ type: "empty", msg: "Цепочка пустая — добавьте хотя бы один узел." });
    return errors;
  }

  if (!chain.start_node_id) {
    errors.push({ type: "no_start", msg: "Не выбран стартовый узел. Правый клик → «Сделать стартом»." });
  }

  const hasOutgoing = new Set(edges.map(e => e.source_node_id));
  const hasIncoming = new Set(edges.map(e => e.target_node_id));

  nodes.forEach(n => {
    if (n.id !== chain.start_node_id && !hasIncoming.has(n.id)) {
      errors.push({ type: "orphan", msg: `Узел «${nodeLabel(n)}» недоступен — нет входящих рёбер.`, nodeId: n.id });
    }
  });

  nodes.filter(n => n.node_type === "buttons").forEach(n => {
    const btns = n.payload.buttons || [];
    const outEdges = edges.filter(e => e.source_node_id === n.id);
    const coveredBtns = outEdges.flatMap(e =>
      (e.conditions || [])
        .filter(c => c.condition_type === "button_press")
        .map(c => c.params.button_label)
    );
    const hasDefault = outEdges.some(e => (e.conditions || []).length === 0);
    btns.forEach(b => {
      if (!coveredBtns.includes(b) && !hasDefault) {
        errors.push({ type: "uncovered_btn", msg: `Кнопка «${b}» в узле не обработана.`, nodeId: n.id });
      }
    });
  });

  return errors;
}

function nodeLabel(n) {
  if (!n) return "?";
  if (n.payload.text)  return n.payload.text.slice(0, 28);
  if (n.payload.caption) return n.payload.caption.slice(0, 28);
  return NODE_COLORS[n.node_type]?.label || n.node_type;
}

// ═══════════════════════════════════════════════════════════════════════════
// EDGE PATH GEOMETRY
// ═══════════════════════════════════════════════════════════════════════════
function getNodeCenter(n) {
  return { x: n.pos_x + NODE_W / 2, y: n.pos_y + NODE_H / 2 };
}
function getEdgePath(srcNode, tgtNode) {
  const s = getNodeCenter(srcNode);
  const t = getNodeCenter(tgtNode);
  const sx = s.x, sy = s.y + NODE_H / 2;
  const tx = t.x, ty = t.y - NODE_H / 2;
  const cpx = (sx + tx) / 2;
  return `M ${sx} ${sy} C ${cpx} ${sy + 40}, ${cpx} ${ty - 40}, ${tx} ${ty}`;
}
function getEdgeMid(srcNode, tgtNode) {
  const s = { x: srcNode.pos_x + NODE_W / 2, y: srcNode.pos_y + NODE_H };
  const t = { x: tgtNode.pos_x + NODE_W / 2, y: tgtNode.pos_y };
  return { x: (s.x + t.x) / 2, y: (s.y + t.y) / 2 };
}

// ═══════════════════════════════════════════════════════════════════════════
// UI COMPONENTS (shadcn/ui inspired)
// ═══════════════════════════════════════════════════════════════════════════

function Card({ children, className = "" }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      {children}
    </div>
  );
}

function CardHeader({ children }) {
  return <div className="px-6 py-4 border-b border-slate-100">{children}</div>;
}

function CardTitle({ children }) {
  return <h3 className="text-lg font-semibold text-slate-900">{children}</h3>;
}

function CardContent({ children }) {
  return <div className="p-6">{children}</div>;
}

function CardFooter({ children, className = "" }) {
  return <div className={`px-6 py-4 border-t border-slate-100 flex items-center justify-between ${className}`}>{children}</div>;
}

function Button({ children, onClick, disabled, variant = "primary", size = "md", className = "" }) {
  const baseClass = "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";
  const variantClass = {
    primary: "bg-slate-900 text-white hover:bg-slate-800 focus:ring-slate-900",
    outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-500",
    ghost:   "text-slate-700 hover:bg-slate-100 focus:ring-slate-500",
    danger:  "bg-red-600 text-white hover:bg-red-700 focus:ring-red-600",
  }[variant];
  const sizeClass = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  }[size];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${variantClass} ${sizeClass} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </button>
  );
}

function Input({ value, onChange, onBlur, placeholder, className = "", type = "text", ...props }) {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      onBlur={onBlur}
      placeholder={placeholder}
      className={`w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent ${className}`}
      {...props}
    />
  );
}

function Label({ children, className = "" }) {
  return <label className={`block text-sm font-medium text-slate-700 mb-1.5 ${className}`}>{children}</label>;
}

function Select({ value, onChange, options, className = "" }) {
  return (
    <select
      value={value}
      onChange={onChange}
      className={`w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 bg-white ${className}`}
    >
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function Dialog({ open, onClose, children }) {
  if (!open) return null;
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/50 z-40" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}

function DialogHeader({ children }) {
  return <div className="px-6 py-4 border-b border-slate-100">{children}</div>;
}

function DialogTitle({ children }) {
  return <h2 className="text-xl font-semibold text-slate-900">{children}</h2>;
}

function DialogContent({ children }) {
  return <div className="px-6 py-4">{children}</div>;
}

function DialogFooter({ children }) {
  return <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-end gap-3">{children}</div>;
}

function Alert({ children, variant = "info" }) {
  const variantClass = {
    info: "bg-blue-50 text-blue-900 border-blue-200",
    error: "bg-red-50 text-red-900 border-red-200",
    warning: "bg-amber-50 text-amber-900 border-amber-200",
    success: "bg-emerald-50 text-emerald-900 border-emerald-200",
  }[variant];

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${variantClass}`}>
      {children}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════

function Toolbar({ chain, dirty, onSave, onValidate, onAddNode, validationErrors, saving }) {
  const [statusOpen, setStatusOpen] = useState(false);
  
  return (
    <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-slate-200 flex-wrap">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-slate-900">{chain.name}</h1>
        
        <div className="relative">
          <button
            onClick={() => setStatusOpen(!statusOpen)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              chain.status === "active" ? "bg-emerald-100 text-emerald-700" :
              chain.status === "paused" ? "bg-amber-100 text-amber-700" :
              "bg-slate-100 text-slate-700"
            }`}
          >
            {chain.status} ▾
          </button>
          {statusOpen && (
            <>
              <div onClick={() => setStatusOpen(false)} className="fixed inset-0 z-10" />
              <div className="absolute top-full left-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 min-w-[120px]">
                {["draft","active","paused","archived"].map(s => (
                  <button
                    key={s}
                    onClick={() => { onValidate(s); setStatusOpen(false); }}
                    className="block w-full text-left px-4 py-2 text-sm hover:bg-slate-50 first:rounded-t-lg last:rounded-b-lg"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="flex-1" />

      {validationErrors.length > 0 && (
        <span className="px-3 py-1 rounded-full bg-red-100 text-red-700 text-xs font-medium">
          ⚠ {validationErrors.length} ошибк{validationErrors.length === 1 ? "а" : "и"}
        </span>
      )}

      <Button variant="outline" onClick={onAddNode}>+ Узел</Button>
      <Button variant="outline" onClick={onValidate}>Валидация</Button>
      <Button variant="primary" onClick={onSave} disabled={!dirty || saving}>
        {saving ? "Сохранение..." : dirty ? "💾 Сохранить" : "Сохранено"}
      </Button>
    </div>
  );
}

function NodeCard({ node, isStart, isSelected, onMouseDown, onClick, onContextMenu }) {
  const c = NODE_COLORS[node.node_type];
  return (
    <div
      onMouseDown={onMouseDown}
      onClick={onClick}
      onContextMenu={onContextMenu}
      className={`rounded-xl border-2 cursor-grab select-none shadow-lg transition-all ${
        isSelected ? 'ring-2 ring-offset-2' : ''
      }`}
      style={{
        position: "absolute",
        left: node.pos_x,
        top: node.pos_y,
        width: NODE_W,
        height: NODE_H,
        backgroundColor: c.bg,
        borderColor: isSelected ? c.accent : c.border,
        ringColor: c.accent,
      }}
    >
      <div className="p-3 h-full flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>
            {c.label}
          </span>
          {isStart && (
            <span className="px-2 py-0.5 rounded bg-emerald-600 text-white text-xs font-bold">
              START
            </span>
          )}
        </div>
        <p className="text-sm text-slate-700 line-clamp-2 leading-snug">
          {node.payload.text || node.payload.caption || "📷 фото"}
        </p>
        {node.delay_seconds > 0 && (
          <span className="text-xs text-slate-500">⏱ {node.delay_seconds}с задержка</span>
        )}
      </div>
    </div>
  );
}

function EdgeLine({ edge, srcNode, tgtNode, isSelected, onClick, conditions }) {
  const path = getEdgePath(srcNode, tgtNode);
  const mid  = getEdgeMid(srcNode, tgtNode);
  return (
    <g onClick={onClick} className="cursor-pointer">
      <path d={path} fill="none" stroke="transparent" strokeWidth={16} />
      <path
        d={path}
        fill="none"
        stroke={isSelected ? "#0f172a" : "#64748b"}
        strokeWidth={isSelected ? 3 : 2}
        strokeDasharray={conditions.length === 0 ? "6 4" : "none"}
      />
      <circle cx={tgtNode.pos_x + NODE_W / 2} cy={tgtNode.pos_y} r={5} fill={isSelected ? "#0f172a" : "#64748b"} />
      {conditions.slice(0, 2).map((cond, i) => (
        <foreignObject key={cond.id} x={mid.x - 60 + i * 2} y={mid.y - 14 - i * 20} width={120} height={24}>
          <div className="bg-white/95 backdrop-blur border border-slate-200 rounded-lg px-2 py-1 text-xs font-medium text-slate-700 shadow-sm whitespace-nowrap">
            {CONDITION_LABELS[cond.condition_type]}
            {cond.params.button_label ? `: ${cond.params.button_label}` : ""}
            {cond.params.substring    ? `: "${cond.params.substring}"`  : ""}
          </div>
        </foreignObject>
      ))}
    </g>
  );
}

function ContextMenu({ pos, items, onClose }) {
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 z-30" />
      <div
        className="fixed z-40 bg-white border border-slate-200 rounded-lg shadow-xl min-w-[180px] overflow-hidden"
        style={{ left: pos.x, top: pos.y }}
      >
        {items.map((it, i) => (
          <button
            key={i}
            onClick={() => { it.action(); onClose(); }}
            className="block w-full text-left px-4 py-2.5 text-sm hover:bg-slate-50 border-b border-slate-100 last:border-0"
          >
            {it.label}
          </button>
        ))}
      </div>
    </>
  );
}

function NodeEditorModal({ node, onSave, onClose }) {
  const [form, setForm] = useState({ ...node, payload: { ...node.payload }, buttons: node.payload.buttons ? [...node.payload.buttons] : [] });
  const [error, setError] = useState(null);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const setP = (k, v) => setForm(f => ({ ...f, payload: { ...f.payload, [k]: v } }));

  const addBtn = () => setForm(f => ({ ...f, buttons: [...f.buttons, ""] }));
  const setBtn = (i, v) => setForm(f => { const b = [...f.buttons]; b[i] = v; return { ...f, buttons: b }; });
  const rmBtn  = (i)    => setForm(f => ({ ...f, buttons: f.buttons.filter((_, x) => x !== i) }));

  const handleSave = () => {
    if (form.node_type === "text" && !form.payload.text?.trim()) {
      setError("Введите текст сообщения");
      return;
    }
    if (form.node_type === "buttons" && form.buttons.filter(Boolean).length === 0) {
      setError("Добавьте хотя бы одну кнопку");
      return;
    }

    const payload = { ...form.payload };
    if (form.node_type === "buttons") payload.buttons = form.buttons.filter(Boolean);
    onSave({ node_type: form.node_type, payload, delay_seconds: form.delay_seconds });
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>Редактирование узла</DialogTitle>
      </DialogHeader>
      <DialogContent>
        {error && <Alert variant="error">{error}</Alert>}
        
        <div className="space-y-4 mt-4">
          <div>
            <Label>Тип сообщения</Label>
            <Select
              value={form.node_type}
              onChange={e => set("node_type", e.target.value)}
              options={[
                { value: "text", label: "Текст" },
                { value: "photo", label: "Фото" },
                { value: "buttons", label: "Кнопки" }
              ]}
            />
          </div>

          {(form.node_type === "text" || form.node_type === "buttons") && (
            <div>
              <Label>Текст сообщения</Label>
              <textarea
                value={form.payload.text || ""}
                onChange={e => setP("text", e.target.value)}
                placeholder="Введите текст..."
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 resize-none"
                rows={3}
              />
            </div>
          )}

          {form.node_type === "photo" && (
            <>
              <div>
                <Label>URL фото</Label>
                <Input value={form.payload.photo_url || ""} onChange={e => setP("photo_url", e.target.value)} placeholder="https://..." />
              </div>
              <div>
                <Label>Подпись (caption)</Label>
                <Input value={form.payload.caption || ""} onChange={e => setP("caption", e.target.value)} placeholder="Необязательно" />
              </div>
            </>
          )}

          {form.node_type === "buttons" && (
            <div>
              <Label>Кнопки</Label>
              <div className="space-y-2">
                {form.buttons.map((b, i) => (
                  <div key={i} className="flex gap-2">
                    <Input value={b} onChange={e => setBtn(i, e.target.value)} placeholder={`Кнопка ${i + 1}`} />
                    <button onClick={() => rmBtn(i)} className="text-red-600 hover:text-red-700 px-2">×</button>
                  </div>
                ))}
                <button onClick={addBtn} className="w-full border border-dashed border-slate-300 rounded-lg py-2 text-sm text-slate-600 hover:bg-slate-50">
                  + Добавить кнопку
                </button>
              </div>
            </div>
          )}

          <div>
            <Label>Задержка перед отправкой (секунды)</Label>
            <Input type="number" value={String(form.delay_seconds)} onChange={e => set("delay_seconds", Math.max(0, parseInt(e.target.value) || 0))} className="w-32" />
          </div>
        </div>
      </DialogContent>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Отмена</Button>
        <Button variant="primary" onClick={handleSave}>Сохранить узел</Button>
      </DialogFooter>
    </Dialog>
  );
}

function ConditionEditorModal({ edge, srcNode, tgtNode, onSave, onClose }) {
  const [conditions, setConditions] = useState(edge.conditions ? [...edge.conditions] : []);
  const [adding, setAdding] = useState(false);
  const [newCond, setNewCond] = useState({ condition_type: "button_press", params: {} });

  const removeCondition = (i) => setConditions(c => c.filter((_, x) => x !== i));

  const commitNew = () => {
    setConditions(c => [...c, { id: nextTempId(), edge_id: edge.id, ...newCond }]);
    setAdding(false);
    setNewCond({ condition_type: "button_press", params: {} });
  };

  const ParamInputs = () => {
    switch (newCond.condition_type) {
      case "button_press":
        if (srcNode?.node_type === "buttons" && srcNode.payload.buttons) {
          const used = conditions.filter(c => c.condition_type === "button_press").map(c => c.params.button_label);
          const available = srcNode.payload.buttons.filter(b => !used.includes(b));
          return (
            <>
              <Label>Кнопка</Label>
              <Select
                value={newCond.params.button_label || ""}
                onChange={e => setNewCond(c => ({ ...c, params: { button_label: e.target.value } }))}
                options={[{ value: "", label: "— выберите —" }, ...available.map(b => ({ value: b, label: b }))]}
              />
            </>
          );
        }
        return (
          <>
            <Label>Название кнопки</Label>
            <Input value={newCond.params.button_label || ""} onChange={e => setNewCond(c => ({ ...c, params: { button_label: e.target.value } }))} placeholder="Да" />
          </>
        );
      case "text_contains":
        return (
          <>
            <Label>Подстрока</Label>
            <Input value={newCond.params.substring || ""} onChange={e => setNewCond(c => ({ ...c, params: { ...c.params, substring: e.target.value } }))} placeholder="да" />
          </>
        );
      case "text_regex":
        return (
          <>
            <Label>Regex паттерн</Label>
            <Input value={newCond.params.pattern || ""} onChange={e => setNewCond(c => ({ ...c, params: { ...c.params, pattern: e.target.value } }))} placeholder="^да$" className="font-mono" />
          </>
        );
      case "timeout":
        return (
          <>
            <Label>Таймаут (секунды)</Label>
            <Input type="number" value={String(newCond.params.timeout_seconds || 300)} onChange={e => setNewCond(c => ({ ...c, params: { timeout_seconds: parseInt(e.target.value) || 300 } }))} className="w-32" />
          </>
        );
      case "any_reply":
        return <p className="text-sm text-slate-600">Любое сообщение от пользователя.</p>;
      default:
        return null;
    }
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>Условия: «{nodeLabel(srcNode)}» → «{nodeLabel(tgtNode)}»</DialogTitle>
      </DialogHeader>
      <DialogContent>
        {conditions.length > 0 && (
          <div className="space-y-2 mb-4">
            {conditions.map((c, i) => (
              <div key={c.id} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
                <span className="text-sm font-medium text-slate-700">
                  {CONDITION_LABELS[c.condition_type]}
                  {c.params.button_label ? ` → "${c.params.button_label}"` : ""}
                  {c.params.substring    ? ` → "${c.params.substring}"`    : ""}
                  {c.params.pattern      ? ` → /${c.params.pattern}/`      : ""}
                  {c.params.timeout_seconds ? ` → ${c.params.timeout_seconds}с` : ""}
                </span>
                <button onClick={() => removeCondition(i)} className="text-red-600 hover:text-red-700">×</button>
              </div>
            ))}
          </div>
        )}

        {adding ? (
          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <div>
              <Label>Тип условия</Label>
              <Select
                value={newCond.condition_type}
                onChange={e => setNewCond({ condition_type: e.target.value, params: {} })}
                options={Object.entries(CONDITION_LABELS).map(([v, l]) => ({ value: v, label: l }))}
              />
            </div>
            <ParamInputs />
            <div className="flex gap-2 pt-2">
              <Button variant="primary" onClick={commitNew}>+ Добавить</Button>
              <Button variant="ghost" onClick={() => setAdding(false)}>Отмена</Button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="w-full border border-dashed border-slate-300 rounded-lg py-3 text-sm text-slate-600 hover:bg-slate-50"
          >
            + Добавить условие
          </button>
        )}

        {conditions.length === 0 && !adding && (
          <p className="text-sm text-slate-500 text-center py-4">
            Без условий → безусловный переход (fallback)
          </p>
        )}
      </DialogContent>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Отмена</Button>
        <Button variant="primary" onClick={() => { onSave(conditions); onClose(); }}>Сохранить условия</Button>
      </DialogFooter>
    </Dialog>
  );
}

function ValidationPanel({ errors, onClose }) {
  return (
    <Card className="fixed top-20 right-6 w-80 z-30 shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Валидация</CardTitle>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      </CardHeader>
      <CardContent>
        {errors.length === 0 ? (
          <Alert variant="success">✓ Всё в порядке!</Alert>
        ) : (
          <div className="space-y-2">
            {errors.map((e, i) => (
              <Alert key={i} variant="error">
                <div className="flex gap-2">
                  <span>⚠</span>
                  <span>{e.msg}</span>
                </div>
              </Alert>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════
export default function ChainEditor({ className = "" } = {}) {
  const [state, dispatch] = useReducer(graphReducer, { chain: null, nodes: [], edges: [], dirty: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const [editingNode, setEditingNode] = useState(null);
  const [editingEdge, setEditingEdge] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [showValidation, setShowValidation] = useState(false);
  const [connectingFrom, setConnectingFrom] = useState(null);

  const [pan, setPan] = useState({ x: 0, y: 0 });
  const panRef = useRef({ startMouse: null, startPan: null });
  const dragging = useRef(null);
  const canvasRef = useRef(null);
  const positionQueueRef = useRef(new Map());
  const flushTimerRef = useRef(null);

  useEffect(() => {
    let isActive = true;
    chainsApi.getGraph()
      .then((graph) => {
        if (!isActive) return;
        dispatch({ type: "LOAD", payload: graph });
        setLoading(false);
      })
      .catch(() => {
        if (!isActive) return;
        setError("Не удалось загрузить цепочку");
        setLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, []);

  const flushPositions = useCallback(async () => {
    if (positionQueueRef.current.size === 0) return;
    const updates = Array.from(positionQueueRef.current.entries());
    positionQueueRef.current.clear();
    setSaving(true);
    setError(null);
    try {
      await Promise.all(
        updates.map(([nodeId, pos]) => chainsApi.updateNode(nodeId, pos))
      );
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось сохранить позиции узлов");
    } finally {
      setSaving(false);
    }
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
    }
    flushTimerRef.current = setTimeout(() => {
      flushPositions();
    }, 600);
  }, [flushPositions]);

  const queuePositionUpdate = useCallback((nodeId, x, y) => {
    positionQueueRef.current.set(nodeId, { pos_x: x, pos_y: y });
    scheduleFlush();
  }, [scheduleFlush]);

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
      }
    };
  }, []);

  const createNodeAt = useCallback(async (x, y) => {
    setSaving(true);
    setError(null);
    try {
      const created = await chainsApi.createNode({
        node_type: "text",
        payload: { text: "Новое сообщение" },
        delay_seconds: 0,
        pos_x: x,
        pos_y: y,
      });
      dispatch({ type: "ADD_NODE", node: created });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось создать узел");
    } finally {
      setSaving(false);
    }
  }, []);

  const updateNode = useCallback(async (nodeId, data) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await chainsApi.updateNode(nodeId, data);
      dispatch({ type: "UPDATE_NODE", id: nodeId, data: updated });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось обновить узел");
    } finally {
      setSaving(false);
    }
  }, []);

  const deleteNode = useCallback(async (nodeId) => {
    setSaving(true);
    setError(null);
    try {
      await chainsApi.deleteNode(nodeId);
      dispatch({ type: "DELETE_NODE", id: nodeId });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось удалить узел");
    } finally {
      setSaving(false);
    }
  }, []);

  const setStartNode = useCallback(async (nodeId) => {
    if (!state.chain) return;
    setSaving(true);
    setError(null);
    try {
      await chainsApi.updateChain({ start_node_id: nodeId });
      dispatch({ type: "SET_START_NODE", id: nodeId });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось обновить стартовый узел");
    } finally {
      setSaving(false);
    }
  }, [state.chain]);

  const createEdge = useCallback(async (sourceId, targetId) => {
    if (state.edges.some((edge) => edge.source_node_id === sourceId && edge.target_node_id === targetId)) {
      return;
    }
    const priorities = state.edges
      .filter((edge) => edge.source_node_id === sourceId)
      .map((edge) => edge.priority || 0);
    const nextPriority = priorities.length ? Math.max(...priorities) + 1 : 0;

    setSaving(true);
    setError(null);
    try {
      const created = await chainsApi.createEdge({
        source_node_id: sourceId,
        target_node_id: targetId,
        priority: nextPriority,
      });
      dispatch({ type: "ADD_EDGE", edge: { ...created, conditions: [] } });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось создать ребро");
    } finally {
      setSaving(false);
    }
  }, [state.edges]);

  const deleteEdge = useCallback(async (edgeId) => {
    setSaving(true);
    setError(null);
    try {
      await chainsApi.deleteEdge(edgeId);
      dispatch({ type: "DELETE_EDGE", id: edgeId });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось удалить ребро");
    } finally {
      setSaving(false);
    }
  }, []);

  const saveEdgeConditions = useCallback(async (edgeId, nextConditions) => {
    setSaving(true);
    setError(null);
    try {
      const edge = state.edges.find((item) => item.id === edgeId);
      const existing = edge?.conditions || [];
      const existingIds = existing
        .map((cond) => cond.id)
        .filter((id) => typeof id === "number" && id > 0);

      await Promise.all(existingIds.map((id) => chainsApi.deleteCondition(edgeId, id)));

      const created = [];
      for (const condition of nextConditions) {
        const payload = {
          condition_type: condition.condition_type,
          params: condition.params || {},
        };
        const saved = await chainsApi.createCondition(edgeId, payload);
        created.push(saved);
      }

      dispatch({ type: "UPDATE_EDGE_CONDITIONS", edgeId, conditions: created });
      dispatch({ type: "SAVED" });
    } catch (err) {
      setError("Не удалось сохранить условия");
    } finally {
      setSaving(false);
    }
  }, [state.edges]);

  const validationErrors = !loading ? validateGraph(state) : [];

  const onCanvasMouseDown = useCallback((e) => {
    if (e.target !== canvasRef.current && e.target.tagName !== "svg") return;
    panRef.current = { startMouse: { x: e.clientX, y: e.clientY }, startPan: { ...pan } };
    e.preventDefault();
  }, [pan]);

  const onMouseMove = useCallback((e) => {
    if (dragging.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - pan.x - dragging.current.offsetX;
      const y = e.clientY - rect.top  - pan.y - dragging.current.offsetY;
      dispatch({ type: "MOVE_NODE", id: dragging.current.id, x, y });
      queuePositionUpdate(dragging.current.id, x, y);
      return;
    }
    if (panRef.current?.startMouse) {
      const dx = e.clientX - panRef.current.startMouse.x;
      const dy = e.clientY - panRef.current.startMouse.y;
      setPan({ x: panRef.current.startPan.x + dx, y: panRef.current.startPan.y + dy });
    }
  }, [pan]);

  const onMouseUp = useCallback(() => {
    dragging.current = null;
    panRef.current = null;
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => { window.removeEventListener("mousemove", onMouseMove); window.removeEventListener("mouseup", onMouseUp); };
  }, [onMouseMove, onMouseUp]);

  const onNodeMouseDown = (e, node) => {
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    dragging.current = {
      id: node.id,
      offsetX: e.clientX - rect.left - pan.x - node.pos_x,
      offsetY: e.clientY - rect.top  - pan.y - node.pos_y,
    };
  };

  const onNodeClick = (e, node) => {
    e.stopPropagation();
    if (connectingFrom !== null) {
      if (connectingFrom !== node.id) {
        createEdge(connectingFrom, node.id);
      }
      setConnectingFrom(null);
      return;
    }
  };

  const onNodeCtx = (e, node) => {
    e.preventDefault(); e.stopPropagation();
    setContextMenu({
      x: e.clientX, y: e.clientY,
      items: [
        { label: "✏️  Редактировать", action: () => setEditingNode(node) },
        { label: "🔗  Провести ребро", action: () => setConnectingFrom(node.id) },
        {
          label: node.id === state.chain?.start_node_id ? "⭐ Стартовый узел" : "⭐ Сделать стартом",
          action: () => setStartNode(node.id),
        },
        { label: "🗑️  Удалить", action: () => deleteNode(node.id) },
      ],
    });
  };

  const onEdgeClick = (e, edge) => {
    e.stopPropagation();
    setEditingEdge(edge);
  };

  const onCanvasDblClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    createNodeAt(
      e.clientX - rect.left - pan.x - NODE_W / 2,
      e.clientY - rect.top - pan.y - NODE_H / 2
    );
  };

  const handleAddNode = () => {
    const cx = (canvasRef.current?.clientWidth || 600) / 2 - pan.x - NODE_W / 2;
    const cy = (canvasRef.current?.clientHeight || 400) / 2 - pan.y - NODE_H / 2;
    createNodeAt(cx, cy);
  };

  const handleValidate = async (newStatus) => {
    if (newStatus) {
      setSaving(true);
      setError(null);
      try {
        await chainsApi.updateChain({ status: newStatus });
        dispatch({ type: "SET_STATUS", status: newStatus });
        dispatch({ type: "SAVED" });
      } catch (err) {
        setError("Не удалось обновить статус цепочки");
      } finally {
        setSaving(false);
      }
    }
    setShowValidation(true);
  };

  const handleSave = async () => {
    await flushPositions();
  };

  if (loading) return <div className="min-h-[400px] flex items-center justify-center text-slate-600">Загрузка...</div>;
  if (!state.chain) return <div className="min-h-[400px] flex items-center justify-center text-slate-600">Цепочка недоступна</div>;

  const nodeMap = Object.fromEntries(state.nodes.map(n => [n.id, n]));

  return (
    <div className={`flex flex-col h-full min-h-[600px] bg-slate-50 ${className}`}>
      <Toolbar
        chain={state.chain}
        dirty={state.dirty}
        saving={saving}
        onSave={handleSave}
        onValidate={handleValidate}
        onAddNode={handleAddNode}
        validationErrors={validationErrors}
      />

      {error && (
        <div className="px-6 py-3 bg-red-50 border-b border-red-200">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {connectingFrom && (
        <div className="px-6 py-3 bg-blue-50 border-b border-blue-200 flex items-center justify-center gap-4">
          <span className="text-sm text-blue-900">🔗 Кликните на целевой узел для соединения</span>
          <button onClick={() => setConnectingFrom(null)} className="text-sm text-blue-700 underline">отменить</button>
        </div>
      )}

      <div className="flex-1 relative overflow-hidden">
        {showValidation && <ValidationPanel errors={validationErrors} onClose={() => setShowValidation(false)} />}

        <div
          ref={canvasRef}
          onMouseDown={onCanvasMouseDown}
          onDoubleClick={onCanvasDblClick}
          onContextMenu={e => e.preventDefault()}
          className="w-full h-full relative cursor-grab"
        >
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <defs>
              <pattern id="grid" width={32} height={32} patternUnits="userSpaceOnUse" patternTransform={`translate(${pan.x % 32}, ${pan.y % 32})`}>
                <circle cx={16} cy={16} r={1} fill="#cbd5e1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          <div style={{ position: "absolute", left: pan.x, top: pan.y, width: 0, height: 0 }}>
            <svg style={{ position: "absolute", overflow: "visible", left: 0, top: 0, width: 0, height: 0, pointerEvents: "none" }}>
              <g style={{ pointerEvents: "auto" }}>
                {state.edges.map(edge => {
                  const src = nodeMap[edge.source_node_id];
                  const tgt = nodeMap[edge.target_node_id];
                  if (!src || !tgt) return null;
                  return (
                    <EdgeLine
                      key={edge.id}
                      edge={edge}
                      srcNode={src}
                      tgtNode={tgt}
                      isSelected={false}
                      conditions={edge.conditions || []}
                      onClick={(e) => onEdgeClick(e, edge)}
                    />
                  );
                })}
              </g>
            </svg>

            {state.nodes.map(node => (
              <NodeCard
                key={node.id}
                node={node}
                isStart={state.chain.start_node_id === node.id}
                isSelected={connectingFrom === node.id}
                onMouseDown={e => onNodeMouseDown(e, node)}
                onClick={e => onNodeClick(e, node)}
                onContextMenu={e => onNodeCtx(e, node)}
              />
            ))}
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 bg-white/90 backdrop-blur border-t border-slate-200 px-6 py-2 flex gap-6 text-xs text-slate-500">
          <span>Двойной клик — добавить узел</span>
          <span>Правый клик — контекст</span>
          <span>Клик на ребро — условия</span>
          <span>{state.dirty && !saving && "● Несохранённые изменения"}</span>
          {saving && <span>💾 Сохранение...</span>}
        </div>
      </div>

      {editingNode && (
        <NodeEditorModal
          node={editingNode}
          onSave={async data => {
            await updateNode(editingNode.id, data);
            setEditingNode(null);
          }}
          onClose={() => setEditingNode(null)}
        />
      )}
      {editingEdge && (
        <ConditionEditorModal
          edge={editingEdge}
          srcNode={nodeMap[editingEdge.source_node_id]}
          tgtNode={nodeMap[editingEdge.target_node_id]}
          onSave={async conditions => {
            await saveEdgeConditions(editingEdge.id, conditions);
          }}
          onClose={() => setEditingEdge(null)}
        />
      )}
      {contextMenu && <ContextMenu pos={contextMenu} items={contextMenu.items} onClose={() => setContextMenu(null)} />}
    </div>
  );
}
