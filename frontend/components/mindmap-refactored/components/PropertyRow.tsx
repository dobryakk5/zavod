import { GripVertical, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { PropertyDraft } from '../types';

// ═══════════════════════════════════════════════════════════════════════════
// PropertyRow Component - Draggable property editor
// ═══════════════════════════════════════════════════════════════════════════

type PropertyRowProps = {
  prop: PropertyDraft;
  onUpdate: (key: string, patch: Partial<PropertyDraft>) => void;
  onDelete: (key: string) => void;
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
};

export function PropertyRow({
  prop,
  onUpdate,
  onDelete,
  isDragging,
  onDragStart,
  onDragEnd,
}: PropertyRowProps) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`group rounded-lg border bg-white p-3 transition-all ${
        isDragging 
          ? 'opacity-50 border-slate-400' 
          : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'
      }`}
    >
      <div className="grid gap-2 sm:grid-cols-12 sm:items-center">
        {/* Drag handle */}
        <div className="hidden sm:flex sm:col-span-1 items-center justify-center cursor-move">
          <GripVertical className="h-4 w-4 text-slate-400 group-hover:text-slate-600" />
        </div>

        {/* Title */}
        <Input
          value={prop.title}
          onChange={(e) => onUpdate(prop.key, { title: e.target.value })}
          placeholder="Название"
          className="sm:col-span-3 border-slate-300 bg-white text-black placeholder:text-slate-400"
        />

        {/* Value */}
        <Input
          value={prop.value}
          onChange={(e) => onUpdate(prop.key, { value: e.target.value })}
          placeholder="Значение"
          className="sm:col-span-4 border-slate-300 bg-white text-black placeholder:text-slate-400"
        />

        {/* Delta */}
        <Input
          value={prop.delta}
          onChange={(e) => onUpdate(prop.key, { delta: e.target.value })}
          placeholder="Δ"
          className="sm:col-span-2 border-slate-300 bg-white text-black placeholder:text-slate-400"
        />

        {/* Order & Delete */}
        <div className="flex items-center gap-2 sm:col-span-2 sm:justify-end">
          <Input
            value={prop.order_index}
            type="number"
            onChange={(e) => onUpdate(prop.key, { order_index: Number(e.target.value) || 0 })}
            className="w-20 border-slate-300 bg-white text-black"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => onDelete(prop.key)}
            className="text-slate-500 hover:text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
