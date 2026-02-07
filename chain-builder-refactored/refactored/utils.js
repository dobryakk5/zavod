import { NODE_W, NODE_H, ROUTER_H, CONDITION_LABELS } from './constants';

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

let _idSeq = 100;
export const uid = () => ++_idSeq;

export function getNodeHeight(node) {
  return node.node_type === "router" ? ROUTER_H : NODE_H;
}

export function getConnectionPoints(srcNode, tgtNode, routeId = null) {
  let sx = srcNode.pos_x + NODE_W / 2;
  let sy = srcNode.pos_y + getNodeHeight(srcNode);
  
  if (srcNode.node_type === "router" && routeId) {
    const routes = srcNode.payload.routes || [];
    const routeIndex = routes.findIndex(r => r.id === routeId);
    if (routeIndex !== -1) {
      sy = srcNode.pos_y + 60 + routeIndex * 30;
    }
  }
  
  const tx = tgtNode.pos_x + NODE_W / 2;
  const ty = tgtNode.pos_y;
  return { sx, sy, tx, ty };
}

export function getCurvedPath(sx, sy, tx, ty) {
  const dy = ty - sy;
  const cp = Math.abs(dy) * 0.5;
  return `M ${sx} ${sy} C ${sx} ${sy + cp}, ${tx} ${ty - cp}, ${tx} ${ty}`;
}

export function getEdgeMid(sx, sy, tx, ty) {
  const t = 0.5;
  const dy = ty - sy;
  const cp = Math.abs(dy) * 0.5;
  const x = (1-t)*(1-t)*(1-t)*sx + 3*(1-t)*(1-t)*t*sx + 3*(1-t)*t*t*tx + t*t*t*tx;
  const y = (1-t)*(1-t)*(1-t)*sy + 3*(1-t)*(1-t)*t*(sy+cp) + 3*(1-t)*t*t*(ty-cp) + t*t*t*ty;
  return { x, y };
}

export function formatTime(seconds) {
  if (!seconds || seconds === 0) return "0с";
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  const parts = [];
  if (hours > 0) parts.push(`${hours}ч`);
  if (minutes > 0) parts.push(`${minutes}м`);
  if (secs > 0) parts.push(`${secs}с`);
  
  return parts.join(" ");
}

export function nodeLabel(n) {
  if (!n) return "?";
  if (n.node_type === "timer") return `⏱ ${formatTime(n.payload.delay_seconds || 0)}`;
  if (n.node_type === "router") return "🔀 Условия";
  if (n.node_type === "message") {
    const contentType = n.payload.content_type || "text";
    if (contentType === "text") return n.payload.text?.slice(0, 20) || "Текст";
    if (contentType === "photo") return `📷 ${n.payload.caption?.slice(0, 15) || "Фото"}`;
    if (contentType === "video") return `🎥 ${n.payload.caption?.slice(0, 15) || "Видео"}`;
    if (contentType === "audio") return `🎵 ${n.payload.caption?.slice(0, 15) || "Аудио"}`;
    if (contentType === "link") return `🔗 ${n.payload.text?.slice(0, 15) || "Ссылка"}`;
    if (contentType === "buttons") return `🔘 ${n.payload.text?.slice(0, 15) || "Кнопки"}`;
  }
  return "...";
}

export function getConditionLabel(route) {
  const label = CONDITION_LABELS[route.condition_type] || "?";
  if (route.condition_type === "button_press") {
    return `${label}: ${route.params.button_label || "?"}`;
  }
  if (route.condition_type === "text_contains") {
    return `${label}: "${route.params.text || "?"}"`;
  }
  if (route.condition_type === "text_regex") {
    return `${label}: ${route.params.pattern || "?"}`;
  }
  if (route.condition_type === "timeout") {
    return `${label}: ${route.params.seconds || "?"}с`;
  }
  return label;
}
