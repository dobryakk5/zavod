import { Input } from '@/components/ui/input';
import { Label } from './Label';
import type { NodeFormState } from '../types';

// ═══════════════════════════════════════════════════════════════════════════
// NodeFormFields Component - Title and Type inputs
// ═══════════════════════════════════════════════════════════════════════════

type NodeFormFieldsProps = {
  form: NodeFormState;
  isWebsiteNode: boolean;
  onChange: (patch: Partial<NodeFormState>) => void;
};

export function NodeFormFields({ 
  form, 
  isWebsiteNode, 
  onChange 
}: NodeFormFieldsProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Title */}
      <div className="space-y-2">
        <Label>Название</Label>
        <Input
          value={form.title}
          onChange={(e) => onChange({ title: e.target.value })}
          className="border-slate-300 bg-white text-black placeholder:text-slate-400"
          placeholder="Введите название..."
        />
      </div>

      {/* Type / URL */}
      <div className="space-y-2">
        <Label>
          Тип {isWebsiteNode && (
            <span className="text-xs text-slate-500">(URL для website)</span>
          )}
        </Label>
        <Input
          value={form.typeLabel}
          onChange={(e) => !isWebsiteNode && onChange({ typeLabel: e.target.value })}
          readOnly={isWebsiteNode}
          className="border-slate-300 bg-white text-black placeholder:text-slate-400"
          placeholder={isWebsiteNode ? "URL (только для чтения)" : "Тип метрики..."}
        />
      </div>
    </div>
  );
}
