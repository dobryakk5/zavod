'use client';

import type { RefObject } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

export type NodeMenuAction = 'edit' | 'copy' | 'duplicate' | 'color' | 'delete';

export type NodeMenuItem = {
  action: NodeMenuAction;
  label: string;
  destructive?: boolean;
  onSelect: () => void;
  onSelectColor?: (color: string) => void;
  currentColor?: string | null;
};

export type NodeContextMenuAnchor = { x: number; y: number } | null;

export type NodeContextMenuProps = {
  anchor: NodeContextMenuAnchor;
  containerRef: RefObject<HTMLElement | null>;
  items: NodeMenuItem[];
  onClose: () => void;
};

const MENU_WIDTH = 180;
const MENU_HEIGHT = 160;
const MENU_PADDING = 8;
const COLOR_PICKER_HEIGHT = 70;

const RAINBOW_COLORS = [
  { label: 'red', value: '#ef4444' },
  { label: 'orange', value: '#f97316' },
  { label: 'yellow', value: '#eab308' },
  { label: 'green', value: '#22c55e' },
  { label: 'blue', value: '#3b82f6' },
  { label: 'indigo', value: '#6366f1' },
  { label: 'violet', value: '#a855f7' }
] as const;

export function NodeContextMenu({ anchor, containerRef, items, onClose }: NodeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isOpen = !!anchor;
  const [isColorPickerOpen, setIsColorPickerOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) setIsColorPickerOpen(false);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (menuRef.current && menuRef.current.contains(target)) return;
      onClose();
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [isOpen, onClose]);

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
    } as const;
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

              {isColorPickerOpen && (
                <div className="px-2 pb-2">
                  <div className="grid grid-cols-7 gap-1">
                    {RAINBOW_COLORS.map((c) => (
                      <button
                        key={c.label}
                        type="button"
                        className={cn(
                          'h-6 w-6 rounded-md border border-slate-300',
                          item.currentColor === c.value ? 'ring-2 ring-slate-900' : 'hover:ring-2 hover:ring-slate-400'
                        )}
                        style={{ backgroundColor: c.value }}
                        aria-label={c.label}
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

        return (
          <button
            key={item.action}
            type="button"
            className={cn(
              'w-full rounded-md px-3 py-2 text-left hover:bg-slate-100',
              item.destructive ? 'text-red-600 hover:bg-red-50' : 'text-slate-900'
            )}
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

export type NodeClipboardData = {
  title: string;
  typeLabel?: string;
  color?: string | null;
  properties?: Array<{
    title?: string | null;
    value?: string | null;
    delta?: string | null;
    order_index?: number | null;
    meta?: Record<string, unknown> | null;
  }>;
};

export function formatNodeClipboardText(node: NodeClipboardData) {
  const lines: string[] = [];
  lines.push(`Название: ${node.title || '—'}`);
  lines.push(`Тип: ${node.typeLabel || '—'}`);
  const props = (node.properties ?? [])
    .slice()
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .filter((p) => (p.title ?? '').trim() || (p.value ?? '').trim());

  if (props.length) {
    lines.push('Свойства:');
    for (const p of props) {
      const title = (p.title ?? '').trim() || '—';
      const value = (p.value ?? '').trim() || '—';
      const delta = (p.delta ?? '').trim();
      lines.push(`- ${title}: ${value}${delta ? ` (${delta})` : ''}`);
    }
  } else {
    lines.push('Свойства: —');
  }

  return lines.join('\n');
}
