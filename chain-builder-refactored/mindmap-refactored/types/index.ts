// ═══════════════════════════════════════════════════════════════════════════
// TYPES - Shared types for MindMap
// ═══════════════════════════════════════════════════════════════════════════

export type NodeFormState = {
  title: string;
  typeLabel: string;
  meta: Record<string, unknown>;
};

export type PropertyDraft = {
  key: string;
  id?: number;
  title: string;
  value: string;
  delta: string;
  order_index: number;
  deleted?: boolean;
};

export type AlertVariant = 'info' | 'error' | 'warning' | 'success';

export type DragState = {
  draggedKey: string | null;
  isDragging: boolean;
};
