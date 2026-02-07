// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS & THEME
// ═══════════════════════════════════════════════════════════════════════════

export const NODE_W = 200;
export const NODE_H = 100;
export const ROUTER_W = 280;
export const ROUTER_HEADER_H = 0;
export const ROUTER_TITLE_H = 0;
export const ROUTER_PADDING = 12;
export const ROUTER_ADD_H = 32;

export const CONDITION_PORT = {
  width: 200,
  height: 32,
  spacing: 8,
  portRadius: 6,
};

export const NODE_COLORS = {
  start:   { bg: '#ecfdf3', border: '#22c55e', accent: '#16a34a', label: 'Старт', icon: '⭐' },
  text:    { bg: '#f0fdfa', border: '#14b8a6', accent: '#0d9488', label: 'Сообщение', icon: '💬' },
  photo:   { bg: '#fffbeb', border: '#f59e0b', accent: '#d97706', label: 'Фото', icon: '📷' },
  buttons: { bg: '#eff6ff', border: '#3b82f6', accent: '#2563eb', label: 'Кнопки', icon: '🔘' },
  router:  { bg: '#faf5ff', border: '#a855f7', accent: '#9333ea', label: 'Условие', icon: '🔀' },
  timer:   { bg: '#fef3c7', border: '#f59e0b', accent: '#d97706', label: 'Задержка', icon: '⏱️' },
};

export const CONDITION_LABELS = {
  button_press:  'Нажата кнопка',
  text_contains: 'Содержит текст',
  text_regex:    'Regex',
  timeout:       'Таймаут',
  any_reply:     'Любой ответ',
  content_type:  'Тип контента',
  has_media:     'Есть медиа?',
  text_equals:   'Текст =',
  has_entities:  'Содержит',
};
