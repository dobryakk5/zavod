import { Trash2, GripVertical } from 'lucide-react';
import { DraggableItem } from '@/shared/components';

/**
 * PropertyRow - строка свойства узла
 * Используется в MindMap для редактирования свойств
 */
export function PropertyRow({
  prop,
  onUpdate,
  onDelete,
  isDragging,
  onDragStart,
  onDragEnd,
}) {
  return (
    <DraggableItem
      isDragging={isDragging}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className="group rounded-lg border bg-white p-3"
    >
      <div className="grid gap-2 sm:grid-cols-12 sm:items-center">
        {/* Drag handle */}
        <div className="hidden sm:flex sm:col-span-1 items-center justify-center cursor-move">
          <GripVertical className="h-4 w-4 text-slate-400 group-hover:text-slate-600" />
        </div>

        {/* Title */}
        <input
          value={prop.title}
          onChange={(e) => onUpdate(prop.key, { title: e.target.value })}
          placeholder="Название"
          className="sm:col-span-3 px-3 py-2 border border-slate-300 rounded-lg bg-white text-black placeholder:text-slate-400"
        />

        {/* Value */}
        <input
          value={prop.value}
          onChange={(e) => onUpdate(prop.key, { value: e.target.value })}
          placeholder="Значение"
          className="sm:col-span-4 px-3 py-2 border border-slate-300 rounded-lg bg-white text-black placeholder:text-slate-400"
        />

        {/* Delta */}
        <input
          value={prop.delta}
          onChange={(e) => onUpdate(prop.key, { delta: e.target.value })}
          placeholder="Δ"
          className="sm:col-span-2 px-3 py-2 border border-slate-300 rounded-lg bg-white text-black placeholder:text-slate-400"
        />

        {/* Order & Delete */}
        <div className="flex items-center gap-2 sm:col-span-2 sm:justify-end">
          <input
            value={prop.order_index}
            type="number"
            onChange={(e) => onUpdate(prop.key, { order_index: Number(e.target.value) || 0 })}
            className="w-20 px-3 py-2 border border-slate-300 rounded-lg bg-white text-black"
          />
          <button
            type="button"
            onClick={() => onDelete(prop.key)}
            className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </DraggableItem>
  );
}
