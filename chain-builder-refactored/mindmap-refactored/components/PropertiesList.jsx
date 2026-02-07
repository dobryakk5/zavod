import { Plus } from 'lucide-react';
import { Label, EmptyState } from '@/shared/components';
import { PropertyRow } from './PropertyRow';

/**
 * PropertiesList - список свойств узла
 * Используется в MindMap
 */
export function PropertiesList({
  properties,
  onUpdate,
  onDelete,
  onAdd,
  draggedProp,
  onDragStart,
  onDragEnd,
  onDrop,
}) {
  const visibleProps = properties.filter((p) => !p.deleted);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Label className="mb-0">Свойства</Label>
        <button
          type="button"
          onClick={onAdd}
          className="px-3 py-1.5 border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg text-sm font-medium inline-flex items-center gap-1"
        >
          <Plus className="h-4 w-4" />
          Добавить свойство
        </button>
      </div>

      {/* List */}
      {visibleProps.length === 0 ? (
        <EmptyState
          icon="📝"
          title="Нет свойств"
          description="Нажмите «Добавить свойство» чтобы создать первое"
        />
      ) : (
        <div className="space-y-2">
          {visibleProps.map((prop) => (
            <div
              key={prop.key}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(prop.key)}
            >
              <PropertyRow
                prop={prop}
                onUpdate={onUpdate}
                onDelete={onDelete}
                isDragging={draggedProp === prop.key}
                onDragStart={() => onDragStart(prop.key)}
                onDragEnd={onDragEnd}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
