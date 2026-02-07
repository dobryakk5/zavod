// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

export const NODE_W = 220;
export const NODE_H = 120;
export const ROUTER_H = 180;

export const NODE_COLORS = {
  message: { bg: "#f0fdfa", border: "#14b8a6", accent: "#0d9488", shadow: "0 4px 12px rgba(20,184,166,0.15)" },
  router:  { bg: "#faf5ff", border: "#a855f7", accent: "#9333ea", shadow: "0 4px 12px rgba(168,85,247,0.15)" },
  timer:   { bg: "#fef2f2", border: "#ef4444", accent: "#dc2626", shadow: "0 4px 12px rgba(239,68,68,0.15)" },
};

// Палитра цветов для кастомизации узлов
export const CUSTOM_COLORS = [
  { label: 'Зелёный', value: '#14b8a6', bg: '#f0fdfa', border: '#14b8a6', accent: '#0d9488' },
  { label: 'Оранжевый', value: '#f59e0b', bg: '#fffbeb', border: '#f59e0b', accent: '#d97706' },
  { label: 'Синий', value: '#3b82f6', bg: '#eff6ff', border: '#3b82f6', accent: '#2563eb' },
  { label: 'Красный', value: '#ef4444', bg: '#fef2f2', border: '#ef4444', accent: '#dc2626' },
  { label: 'Фиолетовый', value: '#a855f7', bg: '#faf5ff', border: '#a855f7', accent: '#9333ea' },
  { label: 'Розовый', value: '#ec4899', bg: '#fdf2f8', border: '#ec4899', accent: '#db2777' },
  { label: 'Жёлтый', value: '#eab308', bg: '#fefce8', border: '#eab308', accent: '#ca8a04' },
];

export const CONDITION_LABELS = {
  button_press:  "Кнопка",
  text_contains: "Текст ⊃",
  text_regex:    "Regex",
  timeout:       "⏱",
  any_reply:     "Любой",
};

export const CONTENT_TYPES = [
  { type: "text", icon: "📝", label: "Текст" },
  { type: "photo", icon: "📷", label: "Фото" },
  { type: "video", icon: "🎥", label: "Видео" },
  { type: "audio", icon: "🎵", label: "Аудио" },
  { type: "link", icon: "🔗", label: "Ссылка" },
  { type: "buttons", icon: "🔘", label: "Кнопки" }
];

export const NODE_TYPES = [
  { type: "message", icon: "💬", label: "Сообщение" },
  { type: "router", icon: "🔀", label: "Условие" },
  { type: "timer", icon: "⏱", label: "Таймер" },
];
