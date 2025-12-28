'use client';

import type { RefObject } from 'react';
import { useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

export type NodeMenuAction = 'edit' | 'copy' | 'duplicate' | 'delete';

export type NodeMenuItem = {
  action: NodeMenuAction;
  label: string;
  destructive?: boolean;
  onSelect: () => void;
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

export function NodeContextMenu({ anchor, containerRef, items, onClose }: NodeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isOpen = !!anchor;

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
    const maxTop = (rect?.bottom ?? baseTop) - MENU_HEIGHT - MENU_PADDING;

    return {
      left: Math.max((rect?.left ?? 0) + MENU_PADDING, Math.min(baseLeft + MENU_PADDING, maxLeft)),
      top: Math.max((rect?.top ?? 0) + MENU_PADDING, Math.min(baseTop + MENU_PADDING, maxTop))
    } as const;
  }, [anchor, containerRef]);

  if (!anchor || !style || typeof document === 'undefined') return null;

  return createPortal(
    <div
      ref={menuRef}
      className="fixed z-50 w-[180px] rounded-lg border bg-white p-1 text-sm shadow-md"
      style={style}
      onPointerDown={(e) => e.stopPropagation()}
    >
      {items.map((item) => (
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
      ))}
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
