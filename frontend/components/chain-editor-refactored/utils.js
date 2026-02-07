import {
  CONDITION_LABELS,
  CONDITION_PORT,
  NODE_COLORS,
  NODE_H,
  NODE_W,
  ROUTER_ADD_H,
  ROUTER_HEADER_H,
  ROUTER_PADDING,
  ROUTER_TITLE_H,
  ROUTER_W,
} from './constants';

let tempId = -1;
export const nextTempId = () => tempId--;

export function nodeLabel(n) {
  if (!n) return '?';
  if (n.node_type === 'router' && n.payload?.label) return n.payload.label.slice(0, 28);
  if (n.node_type === 'timer' && n.payload?.label) return n.payload.label.slice(0, 28);
  if (n.payload?.text) return n.payload.text.slice(0, 28);
  if (n.payload?.caption) return n.payload.caption.slice(0, 28);
  return NODE_COLORS[n.node_type]?.label || n.node_type;
}

export function getNodeDimensions(n) {
  if (n?.node_type === 'timer') {
    return { w: Math.max(90, Math.round(NODE_W / 2)), h: Math.max(60, Math.round(NODE_H / 2)) };
  }
  if (n?.node_type === 'router') {
    const conditions = Array.isArray(n.payload?.conditions) ? n.payload.conditions : [];
    const conditionsHeight = conditions.length * CONDITION_PORT.height
      + Math.max(0, conditions.length - 1) * CONDITION_PORT.spacing;
    const total =
      ROUTER_HEADER_H +
      ROUTER_TITLE_H +
      ROUTER_PADDING +
      conditionsHeight +
      ROUTER_ADD_H +
      ROUTER_PADDING;
    return { w: ROUTER_W, h: Math.max(NODE_H, total) };
  }
  return { w: NODE_W, h: NODE_H };
}

export function getNodeCenter(n) {
  const { w, h } = getNodeDimensions(n);
  return { x: n.pos_x + w / 2, y: n.pos_y + h / 2 };
}

const SIDE_DIR = {
  top: { x: 0, y: -1 },
  right: { x: 1, y: 0 },
  bottom: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
};

export function getPortPosition(node, side) {
  const { w, h } = getNodeDimensions(node);
  switch (side) {
    case 'top':
      return { x: node.pos_x + w / 2, y: node.pos_y };
    case 'right':
      return { x: node.pos_x + w, y: node.pos_y + h / 2 };
    case 'bottom':
      return { x: node.pos_x + w / 2, y: node.pos_y + h };
    case 'left':
      return { x: node.pos_x, y: node.pos_y + h / 2 };
    default:
      return { x: node.pos_x + w / 2, y: node.pos_y + h / 2 };
  }
}

export function inferSideBetweenPoints(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? 'right' : 'left';
  return dy >= 0 ? 'bottom' : 'top';
}

export function getCurvedPath(a, aSide, b, bSide) {
  const MAX_OFFSET = 80;
  const distance = Math.hypot(b.x - a.x, b.y - a.y);
  const offset = Math.min(MAX_OFFSET, distance * 0.5);
  const da = SIDE_DIR[aSide] ?? { x: 0, y: 0 };
  const db = SIDE_DIR[bSide] ?? { x: 0, y: 0 };
  const c1 = { x: a.x + da.x * offset, y: a.y + da.y * offset };
  const c2 = { x: b.x + db.x * offset, y: b.y + db.y * offset };
  return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
}

export function getEdgeMidFromPoints(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

export function getRouterConditionPortPosition(node, conditionId) {
  if (node?.node_type !== 'router') return null;
  const conditions = Array.isArray(node.payload?.conditions) ? node.payload.conditions : [];
  const ordered = conditions
    .map((c, i) => ({ cond: c, order: c.port_index ?? i }))
    .sort((a, b) => a.order - b.order)
    .map((item) => item.cond);
  const idx = ordered.findIndex((c) => c.id === conditionId);
  if (idx < 0) return null;
  const y =
    node.pos_y +
    ROUTER_HEADER_H +
    ROUTER_TITLE_H +
    ROUTER_PADDING +
    idx * (CONDITION_PORT.height + CONDITION_PORT.spacing) +
    CONDITION_PORT.height / 2;
  return { x: node.pos_x + ROUTER_W, y };
}

export function getEdgePath(srcNode, tgtNode, edge = null) {
  const sCenter = getNodeCenter(srcNode);
  const tCenter = getNodeCenter(tgtNode);
  let sSide = inferSideBetweenPoints(sCenter, tCenter);
  const tSide = inferSideBetweenPoints(tCenter, sCenter);
  let s = getPortPosition(srcNode, sSide);
  if (srcNode?.node_type === 'router' && edge?.source_port_id) {
    const routerPort = getRouterConditionPortPosition(srcNode, edge.source_port_id);
    if (routerPort) {
      s = routerPort;
      sSide = 'right';
    }
  }
  const t = getPortPosition(tgtNode, tSide);
  return getCurvedPath(s, sSide, t, tSide);
}

export function getEdgeMid(srcNode, tgtNode, edge = null) {
  const sCenter = getNodeCenter(srcNode);
  const tCenter = getNodeCenter(tgtNode);
  let sSide = inferSideBetweenPoints(sCenter, tCenter);
  const tSide = inferSideBetweenPoints(tCenter, sCenter);
  let s = getPortPosition(srcNode, sSide);
  if (srcNode?.node_type === 'router' && edge?.source_port_id) {
    const routerPort = getRouterConditionPortPosition(srcNode, edge.source_port_id);
    if (routerPort) {
      s = routerPort;
      sSide = 'right';
    }
  }
  const t = getPortPosition(tgtNode, tSide);
  return getEdgeMidFromPoints(s, t);
}

export function formatRouterConditionLabel(condition) {
  if (!condition) return '';
  const { condition_type: type, params = {} } = condition;
  if (type === 'fallback') return 'Любой (fallback)';
  if (type === 'content_type') {
    return `Тип = ${params.message_type || '—'}`;
  }
  if (type === 'text_contains') {
    return `Текст содержит "${params.substring || ''}"`.trim();
  }
  if (type === 'text_regex') {
    return `Regex: /${params.pattern || ''}/`.trim();
  }
  if (type === 'text_equals') {
    return `Текст = "${params.exact_text || ''}"`.trim();
  }
  if (type === 'has_entities') {
    return `Содержит [${params.entity_type || ''}]`.trim();
  }
  if (type === 'has_media') {
    return 'Есть медиа';
  }
  return CONDITION_LABELS[type] || type;
}

export function validateGraph(state) {
  const errors = [];
  const { chain, nodes, edges } = state;

  if (!chain) {
    return errors;
  }

  if (nodes.length === 0) {
    errors.push({ type: 'empty', msg: 'Цепочка пустая — добавьте хотя бы один узел.' });
    return errors;
  }

  if (!chain.start_node_id) {
    errors.push({ type: 'no_start', msg: 'Не выбран стартовый узел. Правый клик → «Сделать стартом».' });
  }

  const hasOutgoing = new Set(edges.map(e => e.source_node_id));
  const hasIncoming = new Set(edges.map(e => e.target_node_id));

  nodes.forEach(n => {
    if (n.id !== chain.start_node_id && !hasIncoming.has(n.id)) {
      errors.push({ type: 'orphan', msg: `Узел «${nodeLabel(n)}» недоступен — нет входящих рёбер.`, nodeId: n.id });
    }
  });

  nodes.filter(n => n.node_type === 'buttons' || n.node_type === 'start').forEach(n => {
    const rawButtons = n.payload?.buttons || [];
    const btns = rawButtons.map(b => (typeof b === 'string' ? b : b?.text)).filter(Boolean);
    const outEdges = edges.filter(e => e.source_node_id === n.id);
    const coveredBtns = outEdges.flatMap(e =>
      (e.conditions || [])
        .filter(c => c.condition_type === 'button_press')
        .map(c => c.params.button_label)
    );
    const hasDefault = outEdges.some(e => (e.conditions || []).length === 0);
    btns.forEach(b => {
      if (!coveredBtns.includes(b) && !hasDefault) {
        errors.push({ type: 'uncovered_btn', msg: `Кнопка «${b}» в узле не обработана.`, nodeId: n.id });
      }
    });
  });

  return errors;
}
