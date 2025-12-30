'use client';

import { MoreVertical } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import type { MindNodeProperty } from '@/lib/types';

export type MindNodeData = {
  title: string;
  typeLabel?: string;
  properties?: MindNodeProperty[];
  color?: string | null;
  meta?: Record<string, unknown>;
  onEdit?: (nodeId: string) => void;
  onChange?: (nodeId: string, patch: { title?: string }) => void;
  onOpenMenu?: (nodeId: string, clientX: number, clientY: number) => void;
};

type MindMapNodeProps = {
  id: string;
  data: MindNodeData;
  onEdit?: (nodeId: string) => void;
  onOpenMenu?: (nodeId: string, clientX: number, clientY: number) => void;
  onSelect?: (nodeId: string) => void;
};

export function MindMapNode({ id, data, onOpenMenu, onSelect }: MindMapNodeProps) {
  const properties = (data.properties ?? [])
    .slice()
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .filter((p) => (p.title ?? '').trim() || (p.value ?? '').trim() || (p.delta ?? '').trim());
  const openMenuHandler = onOpenMenu ?? data.onOpenMenu;
  const hasType = !!data.typeLabel?.trim();
  const title = data.title ?? '';

  return (
    <div
      className="relative h-full w-full min-w-[260px] max-w-[360px] rounded-xl border border-black bg-white shadow-sm"
      style={data.color ? { borderColor: data.color } : undefined}
      onPointerDown={() => onSelect?.(id)}
    >
      <div className="flex items-start justify-between gap-2 border-b px-4 py-3">
        <div className="min-w-0 flex-1 space-y-2">
          <Input
            value={title}
            placeholder="Название"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => data.onChange?.(id, { title: e.target.value })}
            className="h-8 min-w-0 border-slate-300 bg-white px-2 text-sm font-semibold text-black placeholder:text-slate-400"
          />
          {hasType && <div className="text-xs text-muted-foreground">{data.typeLabel}</div>}
        </div>
        <button
          type="button"
          className={cn(
            'rounded-md p-1 text-muted-foreground transition hover:bg-muted hover:text-foreground',
            data.color ? 'border border-transparent' : ''
          )}
          onPointerDown={(e) => {
            e.stopPropagation();
            e.preventDefault();
            openMenuHandler?.(id, e.clientX, e.clientY);
          }}
          aria-label="Меню узла"
        >
          <MoreVertical className="h-4 w-4" />
        </button>
      </div>

      {properties.length > 0 && (
        <div className="grid grid-cols-3 gap-3 px-4 py-3 text-xs">
          {properties.map((prop) => (
            <div key={prop.id ?? `${prop.title}-${prop.value}`} className="space-y-1">
              {!!prop.title?.trim() && <div className="text-[11px] font-medium text-muted-foreground">{prop.title}</div>}
              {!!prop.value?.trim() && <div className="text-sm font-semibold text-foreground">{prop.value}</div>}
              {!!prop.delta?.trim() && (
                <div className={cn('font-semibold', prop.delta.includes('-') ? 'text-red-500' : 'text-emerald-500')}>
                  {prop.delta}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
