import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from './Label';
import { PropertyRow } from './PropertyRow';
import type { PropertyDraft } from '../types';

// ═══════════════════════════════════════════════════════════════════════════
// PropertiesSection Component - Properties management
// ═══════════════════════════════════════════════════════════════════════════

type PropertiesSectionProps = {
  properties: PropertyDraft[];
  draggedKey: string | null;
  onAdd: () => void;
  onUpdate: (key: string, patch: Partial<PropertyDraft>) => void;
  onDelete: (key: string) => void;
  onDragStart: (key: string) => void;
  onDragEnd: () => void;
  onDrop: (targetKey: string) => void;
};

export function PropertiesSection({
  properties,
  draggedKey,
  onAdd,
  onUpdate,
  onDelete,
  onDragStart,
  onDragEnd,
  onDrop,
}: PropertiesSectionProps) {
  const visibleProperties = properties.filter((p) => !p.deleted);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Label className="mb-0">Свойства</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onAdd}
          className="border-slate-300 text-slate-700 hover:bg-slate-50"
        >
          <Plus className="h-4 w-4 mr-1" />
          Добавить свойство
        </Button>
      </div>

      {/* Empty state */}
      {visibleProperties.length === 0 ? (
        <div className="text-center py-8 text-sm text-slate-500 bg-slate-50 rounded-lg border border-slate-200">
          Нет свойств. Нажмите «Добавить свойство», чтобы создать первое.
        </div>
      ) : (
        /* Properties list */
        <div className="space-y-2">
          {visibleProperties.map((prop) => (
            <div
              key={prop.key}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(prop.key)}
            >
              <PropertyRow
                prop={prop}
                onUpdate={onUpdate}
                onDelete={onDelete}
                isDragging={draggedKey === prop.key}
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
