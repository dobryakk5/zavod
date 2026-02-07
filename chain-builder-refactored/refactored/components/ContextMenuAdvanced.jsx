import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

export type ContextMenuAction = 'edit' | 'copy' | 'duplicate' | 'color' | 'delete' | 'setStart';

export type ContextMenuItem = {
  action: ContextMenuAction;
  label: string;
  destructive?: boolean;
  onSelect: () => void;
  onSelectColor?: (color: string) => void;
  currentColor?: string | null;
};

export type ContextMenuAnchor = { x: number; y: number } | null;

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const MENU_WIDTH = 180;
const MENU_HEIGHT = 160;
const MENU_PADDING = 8;
const COLOR_PICKER_HEIGHT = 70;

const NODE_COLORS = [
  { label: 'Зелёный', value: '#14b8a6' },
  { label: 'Оранжевый', value: '#f59e0b' },
  { label: 'Синий', value: '#3b82f6' },
  { label: 'Красный', value: '#ef4444' },
  { label: 'Фиолетовый', value: '#a855f7' },
  { label: 'Розовый', value: '#ec4899' },
  { label: 'Жёлтый', value: '#eab308' },
] as const;

// ═══════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export function ContextMenuAdvanced({ 
  anchor, 
  containerRef, 
  items, 
  onClose 
}) {
  const menuRef = useRef(null);
  const isOpen = !!anchor;
  const [isColorPickerOpen, setIsColorPickerOpen] = useState(false);

  // Закрыть color picker при закрытии меню
  useEffect(() => {
    if (!isOpen) setIsColorPickerOpen(false);
  }, [isOpen]);

  // Закрытие меню при клике вне его или Escape
  useEffect(() => {
    if (!isOpen) return;

    const onPointerDown = (e) => {
      const target = e.target;
      if (!target) return;
      if (menuRef.current && menuRef.current.contains(target)) return;
      onClose();
    };

    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, onClose]);

  // Вычисление позиции меню с учётом границ экрана
  const style = useMemo(() => {
    if (!anchor) return null;
    
    const rect = containerRef.current?.getBoundingClientRect();
    const baseLeft = (rect?.left ?? 0) + anchor.x;
    const baseTop = (rect?.top ?? 0) + anchor.y;
    const maxLeft = (rect?.right ?? baseLeft) - MENU_WIDTH - MENU_PADDING;
    const menuHeight = MENU_HEIGHT + (isColorPickerOpen ? COLOR_PICKER_HEIGHT : 0);
    const maxTop = (rect?.bottom ?? baseTop) - menuHeight - MENU_PADDING;

    return {
      left: Math.max((rect?.left ?? 0) + MENU_PADDING, Math.min(baseLeft + MENU_PADDING, maxLeft)),
      top: Math.max((rect?.top ?? 0) + MENU_PADDING, Math.min(baseTop + MENU_PADDING, maxTop))
    };
  }, [anchor, containerRef, isColorPickerOpen]);

  if (!anchor || !style || typeof document === 'undefined') return null;

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 w-[180px] rounded-lg border bg-white p-1 text-sm shadow-md"
      style={style}
      onPointerDown={(e) => e.stopPropagation()}
    >
      {items.map((item) => {
        // Кнопка с выбором цвета
        if (item.action === 'color' && item.onSelectColor) {
          return (
            <div key={item.action}>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-slate-900 hover:bg-slate-100"
                onClick={() => setIsColorPickerOpen((prev) => !prev)}
              >
                <span>{item.label}</span>
                <span className="flex items-center gap-2">
                  {item.currentColor && (
                    <span
                      className="h-3 w-3 rounded-sm border border-slate-300"
                      style={{ backgroundColor: item.currentColor }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="text-slate-400">{isColorPickerOpen ? '▴' : '▾'}</span>
                </span>
              </button>

              {/* Color picker */}
              {isColorPickerOpen && (
                <div className="px-2 pb-2">
                  <div className="grid grid-cols-7 gap-1">
                    {NODE_COLORS.map((c) => (
                      <button
                        key={c.label}
                        type="button"
                        className={`h-6 w-6 rounded-md border border-slate-300 ${
                          item.currentColor === c.value 
                            ? 'ring-2 ring-slate-900' 
                            : 'hover:ring-2 hover:ring-slate-400'
                        }`}
                        style={{ backgroundColor: c.value }}
                        aria-label={c.label}
                        title={c.label}
                        onClick={() => {
                          item.onSelectColor?.(c.value);
                          setIsColorPickerOpen(false);
                          onClose();
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        }

        // Обычная кнопка
        return (
          <button
            key={item.action}
            type="button"
            className={`w-full rounded-md px-3 py-2 text-left hover:bg-slate-100 ${
              item.destructive 
                ? 'text-red-600 hover:bg-red-50' 
                : 'text-slate-900'
            }`}
            onClick={() => {
              item.onSelect();
              onClose();
            }}
          >
            {item.label}
          </button>
        );
      })}
    </div>,
    document.body
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Форматирование данных узла для копирования в буфер обмена
 */
export function formatNodeClipboardText(node) {
  const lines = [];
  
  lines.push(`Название: ${node.title || '—'}`);
  
  if (node.typeLabel) {
    lines.push(`Тип: ${node.typeLabel}`);
  }
  
  if (node.delay_seconds > 0) {
    lines.push(`Задержка: ${node.delay_seconds}с`);
  }

  // Для router - добавить условия
  if (node.node_type === 'router' && node.payload?.routes) {
    lines.push('Условия:');
    node.payload.routes.forEach((route, idx) => {
      lines.push(`  ${idx + 1}. ${route.condition_type}`);
    });
  }

  // Для message - добавить контент
  if (node.node_type === 'message') {
    const contentType = node.payload?.content_type || 'text';
    lines.push(`Контент: ${contentType}`);
    
    if (contentType === 'text' && node.payload?.text) {
      lines.push(`Текст: ${node.payload.text}`);
    } else if (contentType === 'buttons' && node.payload?.buttons) {
      lines.push('Кнопки:');
      node.payload.buttons.forEach((btn, idx) => {
        lines.push(`  ${idx + 1}. ${btn}`);
      });
    }
  }

  return lines.join('\n');
}
