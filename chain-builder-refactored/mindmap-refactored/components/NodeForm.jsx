import { Label } from '@/shared/components';

/**
 * NodeForm - форма редактирования узла (название и тип)
 * Используется в MindMap
 */
export function NodeForm({ 
  form, 
  onChange, 
  isWebsiteNode = false 
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Title field */}
      <div className="space-y-2">
        <Label>Название</Label>
        <input
          value={form.title}
          onChange={(e) => onChange({ ...form, title: e.target.value })}
          className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-black placeholder:text-slate-400"
          placeholder="Введите название..."
        />
      </div>

      {/* Type/URL field */}
      <div className="space-y-2">
        <Label>
          Тип {isWebsiteNode && <span className="text-xs text-slate-500">(URL для website)</span>}
        </Label>
        <input
          value={form.typeLabel}
          onChange={(e) => !isWebsiteNode && onChange({ ...form, typeLabel: e.target.value })}
          readOnly={isWebsiteNode}
          className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-black placeholder:text-slate-400"
          placeholder={isWebsiteNode ? "URL (только для чтения)" : "Тип метрики..."}
        />
      </div>
    </div>
  );
}
