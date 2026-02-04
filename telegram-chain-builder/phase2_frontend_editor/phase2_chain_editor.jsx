import { useState, useReducer, useRef, useCallback, useEffect } from "react";

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS & THEME
// ═══════════════════════════════════════════════════════════════════════════
const NODE_W = 180;
const NODE_H = 90;

const NODE_COLORS = {
  text:    { bg: "#134e4a", border: "#2dd4bf", accent: "#2dd4bf", label: "Текст" },
  photo:   { bg: "#4a3a14", border: "#fbbf24", accent: "#fbbf24", label: "Фото" },
  buttons: { bg: "#1e1b4b", border: "#818cf8", accent: "#818cf8", label: "Кнопки" },
};

const CONDITION_LABELS = {
  button_press:  "Нажата кнопка",
  text_contains: "Содержит текст",
  text_regex:    "Regex",
  timeout:       "Таймаут",
  any_reply:     "Любой ответ",
};

// ═══════════════════════════════════════════════════════════════════════════
// MOCK API  (swap bodies for real fetch to your Phase 1 router)
// ═══════════════════════════════════════════════════════════════════════════
let _idSeq = 100;
const uid = () => ++_idSeq;

const MOCK_INITIAL_GRAPH = {
  chain: { id: 1, tenant_id: 1, name: "Onboarding", description: "Приветственная цепочка", status: "draft", start_node_id: null },
  nodes: [
    { id: 1, chain_id: 1, node_type: "text",    payload: { text: "Привет! Добро пожаловать 👋" },                         delay_seconds: 0,  pos_x: 80,  pos_y: 40  },
    { id: 2, chain_id: 1, node_type: "buttons", payload: { text: "Что вас интересует?",         buttons: ["Продукт","Услуги","Просто посмотреть"] }, delay_seconds: 2,  pos_x: 80,  pos_y: 200 },
    { id: 3, chain_id: 1, node_type: "text",    payload: { text: "Отлично! Расскажем про продукт..." },                  delay_seconds: 1,  pos_x: -160, pos_y: 380 },
    { id: 4, chain_id: 1, node_type: "photo",   payload: { photo_url: "https://picsum.photos/400/300", caption: "Наш каталог" }, delay_seconds: 3,  pos_x: 80,  pos_y: 380 },
    { id: 5, chain_id: 1, node_type: "text",    payload: { text: "Просто поболтаем тогда 😄" },                          delay_seconds: 1,  pos_x: 320, pos_y: 380 },
  ],
  edges: [
    { id: 10, chain_id: 1, source_node_id: 1, target_node_id: 2, priority: 0, conditions: [] },
    { id: 11, chain_id: 1, source_node_id: 2, target_node_id: 3, priority: 0, conditions: [{ id: 30, edge_id: 11, condition_type: "button_press", params: { button_label: "Продукт" } }] },
    { id: 12, chain_id: 1, source_node_id: 2, target_node_id: 4, priority: 1, conditions: [{ id: 31, edge_id: 12, condition_type: "button_press", params: { button_label: "Услуги" } }] },
    { id: 13, chain_id: 1, source_node_id: 2, target_node_id: 5, priority: 2, conditions: [{ id: 32, edge_id: 13, condition_type: "button_press", params: { button_label: "Просто посмотреть" } }] },
  ],
};

const mockApi = {
  loadGraph: () => Promise.resolve(JSON.parse(JSON.stringify(MOCK_INITIAL_GRAPH))),
  saveGraph: (graph) => { console.log("[SAVE]", graph); return Promise.resolve({ success: true }); },
};

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
      const node = {
        id: uid(), chain_id: state.chain.id, node_type: "text",
        payload: { text: "Новое сообщение" }, delay_seconds: 0,
        pos_x: action.x, pos_y: action.y,
      };
      return { ...state, nodes: [...state.nodes, node], dirty: true };
    }

    case "UPDATE_NODE": {
      const nodes = state.nodes.map(n => n.id === action.id ? { ...n, ...action.data } : n);
      return { ...state, nodes, dirty: true };
    }

    case "DELETE_NODE": {
      const nodes  = state.nodes.filter(n => n.id !== action.id);
      const edges  = state.edges.filter(e => e.source_node_id !== action.id && e.target_node_id !== action.id);
      const startNode = state.chain.start_node_id === action.id ? null : state.chain.start_node_id;
      return { ...state, nodes, edges, chain: { ...state.chain, start_node_id: startNode }, dirty: true };
    }

    case "ADD_EDGE": {
      const edge = {
        id: uid(), chain_id: state.chain.id,
        source_node_id: action.source, target_node_id: action.target,
        priority: 0, conditions: [],
      };
      return { ...state, edges: [...state.edges, edge], dirty: true };
    }

    case "DELETE_EDGE": {
      return { ...state, edges: state.edges.filter(e => e.id !== action.id), dirty: true };
    }

    case "UPDATE_EDGE_CONDITIONS": {
      const edges = state.edges.map(e => e.id === action.edgeId ? { ...e, conditions: action.conditions } : e);
      return { ...state, edges, dirty: true };
    }

    case "SET_START_NODE":
      return { ...state, chain: { ...state.chain, start_node_id: action.id }, dirty: true };

    case "SET_STATUS":
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

  if (nodes.length === 0) {
    errors.push({ type: "empty", msg: "Цепочка пустая — добавьте хотя бы один узел." });
    return errors;
  }

  if (!chain.start_node_id) {
    errors.push({ type: "no_start", msg: "Не выбран стартовый узел. Правый клик → «Сделать стартом»." });
  }

  // nodes with no outgoing edges (leaf) — ok, but warn if it's not the only node
  const hasOutgoing = new Set(edges.map(e => e.source_node_id));
  const hasIncoming = new Set(edges.map(e => e.target_node_id));

  nodes.forEach(n => {
    // non-start node with no incoming edges
    if (n.id !== chain.start_node_id && !hasIncoming.has(n.id)) {
      errors.push({ type: "orphan", msg: `Узел «${nodeLabel(n)}» недоступен — нет входящих рёбер.`, nodeId: n.id });
    }
  });

  // edges from a "buttons" node: all button labels must be covered
  nodes.filter(n => n.node_type === "buttons").forEach(n => {
    const btns = n.payload.buttons || [];
    const outEdges = edges.filter(e => e.source_node_id === n.id);
    const coveredBtns = outEdges.flatMap(e =>
      e.conditions
        .filter(c => c.condition_type === "button_press")
        .map(c => c.params.button_label)
    );
    const hasDefault = outEdges.some(e => e.conditions.length === 0);
    btns.forEach(b => {
      if (!coveredBtns.includes(b) && !hasDefault) {
        errors.push({ type: "uncovered_btn", msg: `Кнопка «${b}» в узле не обработана.`, nodeId: n.id });
      }
    });
  });

  // edges with empty conditions (besides intentional "default" fallback) — warn
  edges.forEach(e => {
    const siblingCount = edges.filter(x => x.source_node_id === e.source_node_id).length;
    if (e.conditions.length === 0 && siblingCount > 1) {
      errors.push({ type: "default_edge", msg: `Ребро из «${nodeLabel(nodes.find(n=>n.id===e.source_node_id))}» без условия — будет fallback.`, edgeId: e.id });
    }
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
  const dx = t.x - s.x, dy = t.y - s.y;
  // exit from bottom of source, enter top of target (most common vertical flow)
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
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════

// ─── Toolbar ──────────────────────────────────────────────────────────────
function Toolbar({ chain, dirty, onSave, onValidate, onAddNode, validationErrors }) {
  const [statusOpen, setStatusOpen] = useState(false);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, padding: "10px 18px",
      background: "#12131a", borderBottom: "1px solid #2a2d3a",
      flexShrink: 0, flexWrap: "wrap",
    }}>
      {/* chain name */}
      <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 15, marginRight: 8 }}>{chain.name}</span>

      {/* status badge + dropdown */}
      <div style={{ position: "relative" }}>
        <button onClick={() => setStatusOpen(!statusOpen)} style={{
          background: chain.status === "active" ? "#166534" : chain.status === "paused" ? "#78350f" : "#1e293b",
          color: chain.status === "active" ? "#86efac" : chain.status === "paused" ? "#fcd34d" : "#94a3b8",
          border: "none", borderRadius: 6, padding: "3px 10px", fontSize: 12, fontWeight: 600, cursor: "pointer",
        }}>
          {chain.status} ▾
        </button>
        {statusOpen && (
          <div style={{
            position: "absolute", top: "100%", left: 0, zIndex: 50,
            background: "#1e2030", border: "1px solid #2a2d3a", borderRadius: 8,
            minWidth: 110, marginTop: 4, overflow: "hidden",
          }}>
            {["draft","active","paused","archived"].map(s => (
              <button key={s} onClick={() => { setStatusOpen(false); onValidate(s); }}
                style={{ display: "block", width: "100%", textAlign: "left", background: "none", border: "none", color: "#cbd5e1", padding: "7px 12px", fontSize: 13, cursor: "pointer" }}
                onMouseEnter={e => e.target.style.background = "#2a2d3a"}
                onMouseLeave={e => e.target.style.background = "none"}
              >{s}</button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1 }} />

      {/* error count */}
      {validationErrors.length > 0 && (
        <span style={{ fontSize: 12, color: "#f87171", fontWeight: 600, background: "#3b1111", borderRadius: 6, padding: "2px 8px" }}>
          ⚠ {validationErrors.length} ошибк{validationErrors.length === 1 ? "а" : "и"}
        </span>
      )}

      {/* buttons */}
      <button onClick={onAddNode} style={btnStyle("#6366f1")}>+ Узел</button>
      <button onClick={onValidate} style={btnStyle("#475569")}>Валидация</button>
      <button onClick={onSave} disabled={!dirty} style={{ ...btnStyle(dirty ? "#0d9488" : "#374151"), opacity: dirty ? 1 : 0.5 }}>
        {dirty ? "💾 Сохранить" : "Сохранено"}
      </button>
    </div>
  );
}
function btnStyle(bg) {
  return { background: bg, color: "#fff", border: "none", borderRadius: 6, padding: "6px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" };
}

// ─── Node Card ────────────────────────────────────────────────────────────
function NodeCard({ node, isStart, isSelected, onMouseDown, onClick, onContextMenu }) {
  const c = NODE_COLORS[node.node_type];
  return (
    <div
      onMouseDown={onMouseDown}
      onClick={onClick}
      onContextMenu={onContextMenu}
      style={{
        position: "absolute", left: node.pos_x, top: node.pos_y,
        width: NODE_W, height: NODE_H,
        background: c.bg + "cc",
        border: `2px solid ${isSelected ? "#fff" : c.border}`,
        borderRadius: 10,
        cursor: "grab",
        userSelect: "none",
        boxShadow: isSelected ? `0 0 0 2px ${c.accent}` : "0 4px 14px rgba(0,0,0,.35)",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        padding: "8px 10px",
        backdropFilter: "blur(4px)",
        transition: "box-shadow .15s",
      }}
    >
      {/* top row: type badge + start marker */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: c.accent, textTransform: "uppercase", letterSpacing: 1 }}>
          {c.label}
        </span>
        {isStart && <span style={{ fontSize: 10, background: "#16a34a", color: "#fff", borderRadius: 4, padding: "1px 6px", fontWeight: 700 }}>START</span>}
      </div>
      {/* preview text */}
      <span style={{ fontSize: 13, color: "#e2e8f0", lineHeight: 1.35, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {node.payload.text || node.payload.caption || "📷 фото"}
      </span>
      {/* delay badge */}
      {node.delay_seconds > 0 && (
        <span style={{ fontSize: 10, color: "#94a3b8" }}>⏱ {node.delay_seconds}с задержка</span>
      )}
    </div>
  );
}

// ─── Edge Line (SVG) ──────────────────────────────────────────────────────
function EdgeLine({ edge, srcNode, tgtNode, isSelected, onClick, conditions }) {
  const path = getEdgePath(srcNode, tgtNode);
  const mid  = getEdgeMid(srcNode, tgtNode);
  return (
    <g onClick={onClick} style={{ cursor: "pointer" }}>
      <path d={path} fill="none" stroke="transparent" strokeWidth={16} />  {/* fat invisible hit area */}
      <path d={path} fill="none" stroke={isSelected ? "#fff" : "#64748b"} strokeWidth={isSelected ? 2.5 : 2} strokeDasharray={conditions.length === 0 ? "6 4" : "none"} />
      {/* arrowhead */}
      <circle cx={tgtNode.pos_x + NODE_W / 2} cy={tgtNode.pos_y} r={4} fill={isSelected ? "#fff" : "#64748b"} />
      {/* condition badges */}
      {conditions.slice(0, 2).map((cond, i) => (
        <foreignObject key={cond.id} x={mid.x - 52 + i * 2} y={mid.y - 12 - i * 18} width={108} height={20}>
          <div style={{
            background: "#1e2030ee", border: "1px solid #3a3f55", borderRadius: 10,
            padding: "1px 7px", fontSize: 10, color: "#a5b4fc", whiteSpace: "nowrap", fontWeight: 600,
          }}>
            {CONDITION_LABELS[cond.condition_type]}
            {cond.params.button_label ? `: ${cond.params.button_label}` : ""}
            {cond.params.substring    ? `: "${cond.params.substring}"`  : ""}
          </div>
        </foreignObject>
      ))}
    </g>
  );
}

// ─── Context Menu ─────────────────────────────────────────────────────────
function ContextMenu({ pos, items, onClose }) {
  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 40 }} />
      <div style={{
        position: "absolute", left: pos.x, top: pos.y, zIndex: 50,
        background: "#1e2030", border: "1px solid #2a2d3a", borderRadius: 8,
        minWidth: 160, overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,.4)",
      }}>
        {items.map((it, i) => (
          <button key={i} onClick={() => { it.action(); onClose(); }}
            style={{ display: "block", width: "100%", textAlign: "left", background: "none", border: "none", color: "#cbd5e1", padding: "8px 14px", fontSize: 13, cursor: "pointer", borderBottom: i < items.length -1 ? "1px solid #2a2d3a" : "none" }}
            onMouseEnter={e => e.target.style.background = "#2a2d3a"}
            onMouseLeave={e => e.target.style.background = "none"}
          >{it.label}</button>
        ))}
      </div>
    </>
  );
}

// ─── Modal Shell ──────────────────────────────────────────────────────────
function Modal({ title, onClose, children, width = 440 }) {
  return (
    <>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", zIndex: 100 }} />
      <div style={{
        position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
        width, background: "#1a1c2a", border: "1px solid #2a2d3a", borderRadius: 14,
        zIndex: 101, boxShadow: "0 16px 48px rgba(0,0,0,.5)", overflow: "hidden",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 20px", borderBottom: "1px solid #2a2d3a" }}>
          <span style={{ color: "#e2e8f0", fontWeight: 700, fontSize: 15 }}>{title}</span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", fontSize: 20, cursor: "pointer", lineHeight: 1 }}>×</button>
        </div>
        <div style={{ padding: "20px" }}>{children}</div>
      </div>
    </>
  );
}

function Label({ children }) {
  return <div style={{ color: "#94a3b8", fontSize: 12, fontWeight: 600, marginBottom: 5, letterSpacing: .5 }}>{children}</div>;
}
function Input({ value, onChange, placeholder, style: s }) {
  return (
    <input value={value} onChange={onChange} placeholder={placeholder} style={{
      width: "100%", background: "#12131a", border: "1px solid #2a2d3a", borderRadius: 7,
      color: "#e2e8f0", padding: "8px 10px", fontSize: 13, outline: "none", boxSizing: "border-box", ...s
    }} />
  );
}
function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange} style={{
      width: "100%", background: "#12131a", border: "1px solid #2a2d3a", borderRadius: 7,
      color: "#e2e8f0", padding: "8px 10px", fontSize: 13, outline: "none",
    }}>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}
function ActionBtn({ onClick, children, danger }) {
  return (
    <button onClick={onClick} style={{
      background: danger ? "#7f1d1d" : "#6366f1", color: "#fff", border: "none", borderRadius: 7,
      padding: "8px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer",
    }}>{children}</button>
  );
}

// ─── Node Editor Modal ────────────────────────────────────────────────────
function NodeEditorModal({ node, onSave, onClose }) {
  const [form, setForm] = useState({ ...node, payload: { ...node.payload }, buttons: node.payload.buttons ? [...node.payload.buttons] : [] });

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const setP = (k, v) => setForm(f => ({ ...f, payload: { ...f.payload, [k]: v } }));

  const addBtn = () => setForm(f => ({ ...f, buttons: [...f.buttons, ""] }));
  const setBtn = (i, v) => setForm(f => { const b = [...f.buttons]; b[i] = v; return { ...f, buttons: b }; });
  const rmBtn  = (i)    => setForm(f => ({ ...f, buttons: f.buttons.filter((_, x) => x !== i) }));

  const handleSave = () => {
    const payload = { ...form.payload };
    if (form.node_type === "buttons") payload.buttons = form.buttons.filter(Boolean);
    onSave({ node_type: form.node_type, payload, delay_seconds: form.delay_seconds });
  };

  return (
    <Modal title="Редактор узла" onClose={onClose}>
      <Label>Тип сообщения</Label>
      <Select value={form.node_type} onChange={e => set("node_type", e.target.value)}
        options={[{ value: "text", label: "Текст" }, { value: "photo", label: "Фото" }, { value: "buttons", label: "Кнопки" }]}
      />
      <div style={{ height: 14 }} />

      {(form.node_type === "text" || form.node_type === "buttons") && (
        <>
          <Label>Текст сообщения</Label>
          <Input value={form.payload.text || ""} onChange={e => setP("text", e.target.value)} placeholder="Введите текст..." />
          <div style={{ height: 14 }} />
        </>
      )}

      {form.node_type === "photo" && (
        <>
          <Label>URL фото</Label>
          <Input value={form.payload.photo_url || ""} onChange={e => setP("photo_url", e.target.value)} placeholder="https://..." />
          <div style={{ height: 10 }} />
          <Label>Подпись (caption)</Label>
          <Input value={form.payload.caption || ""} onChange={e => setP("caption", e.target.value)} placeholder="Необязательно" />
          <div style={{ height: 14 }} />
        </>
      )}

      {form.node_type === "buttons" && (
        <>
          <Label>Кнопки</Label>
          {form.buttons.map((b, i) => (
            <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6 }}>
              <Input value={b} onChange={e => setBtn(i, e.target.value)} placeholder={`Кнопка ${i + 1}`} />
              <button onClick={() => rmBtn(i)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 16 }}>×</button>
            </div>
          ))}
          <button onClick={addBtn} style={{ background: "none", border: "1px dashed #475569", borderRadius: 6, color: "#94a3b8", padding: "5px 10px", fontSize: 12, cursor: "pointer", width: "100%" }}>+ Кнопка</button>
          <div style={{ height: 14 }} />
        </>
      )}

      <Label>Задержка перед отправкой (секунды)</Label>
      <Input value={String(form.delay_seconds)} onChange={e => set("delay_seconds", Math.max(0, parseInt(e.target.value) || 0))} style={{ width: 100 }} />

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
        <button onClick={onClose} style={{ background: "#2a2d3a", border: "none", borderRadius: 7, color: "#cbd5e1", padding: "8px 16px", fontSize: 13, cursor: "pointer" }}>Отмена</button>
        <ActionBtn onClick={handleSave}>Сохранить узел</ActionBtn>
      </div>
    </Modal>
  );
}

// ─── Condition Editor Modal ───────────────────────────────────────────────
function ConditionEditorModal({ edge, srcNode, tgtNode, onSave, onClose }) {
  const [conditions, setConditions] = useState(edge.conditions ? [...edge.conditions] : []);
  const [adding, setAdding] = useState(false);
  const [newCond, setNewCond] = useState({ condition_type: "button_press", params: {} });

  const removeCondition = (i) => setConditions(c => c.filter((_, x) => x !== i));

  const commitNew = () => {
    setConditions(c => [...c, { id: uid(), edge_id: edge.id, ...newCond }]);
    setAdding(false);
    setNewCond({ condition_type: "button_press", params: {} });
  };

  const ParamInputs = () => {
    switch (newCond.condition_type) {
      case "button_press":
        // show buttons from source node if it's a buttons type
        if (srcNode?.node_type === "buttons" && srcNode.payload.buttons) {
          const used = conditions.filter(c => c.condition_type === "button_press").map(c => c.params.button_label);
          const available = srcNode.payload.buttons.filter(b => !used.includes(b));
          return (
            <>
              <Label>Кнопка</Label>
              <Select value={newCond.params.button_label || ""} onChange={e => setNewCond(c => ({ ...c, params: { button_label: e.target.value } }))}
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
            <Input value={newCond.params.pattern || ""} onChange={e => setNewCond(c => ({ ...c, params: { ...c.params, pattern: e.target.value } }))} placeholder="^да$" style={{ fontFamily: "monospace" }} />
          </>
        );
      case "timeout":
        return (
          <>
            <Label>Таймаут (секунды)</Label>
            <Input value={String(newCond.params.timeout_seconds || 300)} onChange={e => setNewCond(c => ({ ...c, params: { timeout_seconds: parseInt(e.target.value) || 300 } }))} style={{ width: 100 }} />
          </>
        );
      case "any_reply":
        return <div style={{ color: "#64748b", fontSize: 13, marginTop: 4 }}>Любое сообщение от пользователя.</div>;
      default:
        return null;
    }
  };

  return (
    <Modal title={`Условия: «${nodeLabel(srcNode)}» → «${nodeLabel(tgtNode)}»`} onClose={onClose} width={460}>
      {/* existing conditions */}
      {conditions.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {conditions.map((c, i) => (
            <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#12131a", borderRadius: 7, padding: "7px 10px", marginBottom: 5 }}>
              <span style={{ color: "#a5b4fc", fontSize: 13, fontWeight: 600 }}>
                {CONDITION_LABELS[c.condition_type]}
                {c.params.button_label ? ` → "${c.params.button_label}"` : ""}
                {c.params.substring    ? ` → "${c.params.substring}"`    : ""}
                {c.params.pattern      ? ` → /${c.params.pattern}/`      : ""}
                {c.params.timeout_seconds ? ` → ${c.params.timeout_seconds}с` : ""}
              </span>
              <button onClick={() => removeCondition(i)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontSize: 16 }}>×</button>
            </div>
          ))}
        </div>
      )}

      {/* add new condition form */}
      {adding ? (
        <div style={{ background: "#12131a", borderRadius: 8, padding: 14, marginBottom: 10 }}>
          <Label>Тип условия</Label>
          <Select value={newCond.condition_type} onChange={e => setNewCond({ condition_type: e.target.value, params: {} })}
            options={Object.entries(CONDITION_LABELS).map(([v, l]) => ({ value: v, label: l }))}
          />
          <div style={{ height: 12 }} />
          <ParamInputs />
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <ActionBtn onClick={commitNew}>+ Добавить</ActionBtn>
            <button onClick={() => setAdding(false)} style={{ background: "#2a2d3a", border: "none", borderRadius: 7, color: "#cbd5e1", padding: "8px 14px", fontSize: 13, cursor: "pointer" }}>Отмена</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} style={{ background: "none", border: "1px dashed #475569", borderRadius: 7, color: "#94a3b8", padding: "7px 12px", fontSize: 13, cursor: "pointer", width: "100%" }}>
          + Добавить условие
        </button>
      )}

      {conditions.length === 0 && !adding && (
        <div style={{ color: "#64748b", fontSize: 13, textAlign: "center", padding: "8px 0" }}>
          Без условий → безусловный переход (fallback)
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
        <button onClick={onClose} style={{ background: "#2a2d3a", border: "none", borderRadius: 7, color: "#cbd5e1", padding: "8px 16px", fontSize: 13, cursor: "pointer" }}>Отмена</button>
        <ActionBtn onClick={() => { onSave(conditions); onClose(); }}>Сохранить условия</ActionBtn>
      </div>
    </Modal>
  );
}

// ─── Validation Panel ─────────────────────────────────────────────────────
function ValidationPanel({ errors, onClose }) {
  return (
    <div style={{
      position: "absolute", top: 50, right: 16, width: 300, zIndex: 30,
      background: "#1a1c2a", border: "1px solid #3b1111", borderRadius: 12,
      boxShadow: "0 8px 24px rgba(0,0,0,.4)", overflow: "hidden",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid #2a2d3a", background: "#12131a" }}>
        <span style={{ color: "#fca5a5", fontWeight: 700, fontSize: 14 }}>Валидация</span>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", fontSize: 18, cursor: "pointer" }}>×</button>
      </div>
      <div style={{ padding: 12 }}>
        {errors.length === 0 ? (
          <div style={{ color: "#86efac", fontSize: 14, textAlign: "center", padding: 12 }}>✓ Всё в порядке!</div>
        ) : errors.map((e, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", background: "#1f1010", borderRadius: 7, padding: "8px 10px", marginBottom: 6 }}>
            <span style={{ color: "#f87171", fontSize: 14 }}>⚠</span>
            <span style={{ color: "#fca5a5", fontSize: 13, lineHeight: 1.4 }}>{e.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════
export default function ChainBuilder() {
  const [state, dispatch] = useReducer(graphReducer, { chain: {}, nodes: [], edges: [], dirty: false });
  const [loading, setLoading] = useState(true);

  // ── modals / panels
  const [editingNode,       setEditingNode]       = useState(null);   // node object
  const [editingEdge,       setEditingEdge]       = useState(null);   // edge object
  const [contextMenu,       setContextMenu]       = useState(null);   // { x, y, items }
  const [showValidation,    setShowValidation]    = useState(false);
  const [connectingFrom,    setConnectingFrom]    = useState(null);   // node id when drawing edge

  // ── pan
  const [pan, setPan]         = useState({ x: 0, y: 0 });
  const panRef                = useRef({ startMouse: null, startPan: null });

  // ── drag node
  const dragging              = useRef(null); // { id, offsetX, offsetY }
  const canvasRef             = useRef(null);

  // ── load
  useEffect(() => {
    mockApi.loadGraph().then(g => { dispatch({ type: "LOAD", payload: g }); setLoading(false); });
  }, []);

  // ── validation errors (live)
  const validationErrors = !loading ? validateGraph(state) : [];

  // ─── MOUSE HANDLERS (canvas) ──────────────────────────────────────────
  const onCanvasMouseDown = useCallback((e) => {
    if (e.target !== canvasRef.current && e.target.tagName !== "svg") return;
    // start pan
    panRef.current = { startMouse: { x: e.clientX, y: e.clientY }, startPan: { ...pan } };
    e.preventDefault();
  }, [pan]);

  const onMouseMove = useCallback((e) => {
    if (dragging.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - pan.x - dragging.current.offsetX;
      const y = e.clientY - rect.top  - pan.y - dragging.current.offsetY;
      dispatch({ type: "MOVE_NODE", id: dragging.current.id, x, y });
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
    panRef.current   = null;
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup",   onMouseUp);
    return () => { window.removeEventListener("mousemove", onMouseMove); window.removeEventListener("mouseup", onMouseUp); };
  }, [onMouseMove, onMouseUp]);

  // ─── NODE DRAG ────────────────────────────────────────────────────────
  const onNodeMouseDown = (e, node) => {
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    dragging.current = {
      id: node.id,
      offsetX: e.clientX - rect.left - pan.x - node.pos_x,
      offsetY: e.clientY - rect.top  - pan.y - node.pos_y,
    };
  };

  // ─── NODE CLICK (single click = select / connect) ────────────────────
  const onNodeClick = (e, node) => {
    e.stopPropagation();
    if (connectingFrom !== null) {
      if (connectingFrom !== node.id) {
        // check duplicate
        const exists = state.edges.some(ed => ed.source_node_id === connectingFrom && ed.target_node_id === node.id);
        if (!exists) dispatch({ type: "ADD_EDGE", source: connectingFrom, target: node.id });
      }
      setConnectingFrom(null);
      return;
    }
  };

  // ─── NODE CONTEXT MENU ────────────────────────────────────────────────
  const onNodeCtx = (e, node) => {
    e.preventDefault(); e.stopPropagation();
    setContextMenu({
      x: e.clientX, y: e.clientY,
      items: [
        { label: "✏️  Редактировать",       action: () => setEditingNode(node) },
        { label: "🔗  Провести ребро",      action: () => setConnectingFrom(node.id) },
        { label: node.id === state.chain.start_node_id ? "⭐ Стартовый узел" : "⭐ Сделать стартом", action: () => dispatch({ type: "SET_START_NODE", id: node.id }) },
        { label: "🗑️  Удалить",            action: () => dispatch({ type: "DELETE_NODE", id: node.id }) },
      ],
    });
  };

  // ─── EDGE CLICK ───────────────────────────────────────────────────────
  const onEdgeClick = (e, edge) => {
    e.stopPropagation();
    setEditingEdge(edge);
  };

  // ─── CANVAS DOUBLE-CLICK → add node ──────────────────────────────────
  const onCanvasDblClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    dispatch({ type: "ADD_NODE", x: e.clientX - rect.left - pan.x - NODE_W / 2, y: e.clientY - rect.top - pan.y - NODE_H / 2 });
  };

  // ─── TOOLBAR ACTIONS ──────────────────────────────────────────────────
  const handleAddNode = () => {
    const cx = (canvasRef.current?.clientWidth || 600) / 2 - pan.x - NODE_W / 2;
    const cy = (canvasRef.current?.clientHeight || 400) / 2 - pan.y - NODE_H / 2;
    dispatch({ type: "ADD_NODE", x: cx, y: cy });
  };

  const handleValidate = (newStatus) => {
    if (newStatus) dispatch({ type: "SET_STATUS", status: newStatus });
    setShowValidation(true);
  };

  const handleSave = async () => {
    await mockApi.saveGraph(state);
    dispatch({ type: "SAVED" });
  };

  // ─── RENDER ───────────────────────────────────────────────────────────
  if (loading) return <div style={{ background: "#0f1117", color: "#64748b", height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>Загрузка...</div>;

  const nodeMap = Object.fromEntries(state.nodes.map(n => [n.id, n]));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0f1117", color: "#e2e8f0", fontFamily: "'Segoe UI', system-ui, sans-serif", userSelect: "none" }}>
      {/* ── toolbar ─── */}
      <Toolbar
        chain={state.chain}
        dirty={state.dirty}
        onSave={handleSave}
        onValidate={handleValidate}
        onAddNode={handleAddNode}
        validationErrors={validationErrors}
      />

      {/* ── connecting hint ─── */}
      {connectingFrom && (
        <div style={{ background: "#1e40af", color: "#bfdbfe", textAlign: "center", padding: "5px 0", fontSize: 13, fontWeight: 600 }}>
          🔗 Кликайте на целевой узел для соединения  •  <button onClick={() => setConnectingFrom(null)} style={{ background: "none", border: "none", color: "#93c5fd", cursor: "pointer", textDecoration: "underline", padding: 0 }}>отменить</button>
        </div>
      )}

      {/* ── canvas ─── */}
      <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>

        {/* validation panel */}
        {showValidation && <ValidationPanel errors={validationErrors} onClose={() => setShowValidation(false)} />}

        {/* scrollable / pannable area */}
        <div
          ref={canvasRef}
          onMouseDown={onCanvasMouseDown}
          onDoubleClick={onCanvasDblClick}
          onContextMenu={e => e.preventDefault()}
          style={{ width: "100%", height: "100%", position: "relative", cursor: "grab" }}
        >
          {/* dot-grid background */}
          <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
            <defs>
              <pattern id="grid" width={32} height={32} patternUnits="userSpaceOnUse" patternTransform={`translate(${pan.x % 32}, ${pan.y % 32})`}>
                <circle cx={16} cy={16} r={1} fill="#2a2d3a" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          {/* panned group */}
          <div style={{ position: "absolute", left: pan.x, top: pan.y, width: 0, height: 0 }}>

            {/* SVG edges layer */}
            <svg style={{ position: "absolute", overflow: "visible", left: 0, top: 0, width: 0, height: 0, pointerEvents: "none" }}>
              <defs>
                <marker id="arrowhead" markerWidth={8} markerHeight={6} refX={7} refY={3} orient="auto">
                  <polygon points="0 0, 8 3, 0 6" fill="#64748b" />
                </marker>
              </defs>
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

            {/* Node cards */}
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

        {/* hint footer */}
        <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, background: "#0f1117cc", borderTop: "1px solid #1e2030", padding: "5px 16px", display: "flex", gap: 20, fontSize: 11, color: "#475569", backdropFilter: "blur(4px)" }}>
          <span>双击 добавить узел</span>
          <span>правый клик → контекст</span>
          <span>тянуть — перемещать узел / канвас</span>
          <span>клик на ребро — условия</span>
        </div>
      </div>

      {/* ── MODALS ─── */}
      {editingNode && (
        <NodeEditorModal
          node={editingNode}
          onSave={data => { dispatch({ type: "UPDATE_NODE", id: editingNode.id, data }); setEditingNode(null); }}
          onClose={() => setEditingNode(null)}
        />
      )}
      {editingEdge && (
        <ConditionEditorModal
          edge={editingEdge}
          srcNode={nodeMap[editingEdge.source_node_id]}
          tgtNode={nodeMap[editingEdge.target_node_id]}
          onSave={conditions => dispatch({ type: "UPDATE_EDGE_CONDITIONS", edgeId: editingEdge.id, conditions })}
          onClose={() => setEditingEdge(null)}
        />
      )}
      {contextMenu && <ContextMenu pos={contextMenu} items={contextMenu.items} onClose={() => setContextMenu(null)} />}
    </div>
  );
}
