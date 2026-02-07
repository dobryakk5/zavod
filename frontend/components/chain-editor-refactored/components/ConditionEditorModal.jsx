import { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { CONDITION_LABELS } from '../constants';
import { nextTempId, nodeLabel } from '../utils';
import { Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Label, Select } from './ui';

export function ConditionEditorModal({ edge, srcNode, tgtNode, onSave, onClose, onDelete }) {
  const isFromRouter = srcNode?.node_type === 'router';
  const isFromTimer = srcNode?.node_type === 'timer' || (srcNode?.node_type === 'text' && srcNode?.payload?.kind === 'timer');
  const [conditions, setConditions] = useState(edge.conditions ? [...edge.conditions] : []);
  const [adding, setAdding] = useState(false);
  const [newCond, setNewCond] = useState(() => ({
    condition_type: isFromRouter ? 'content_type' : 'button_press',
    params: {},
  }));

  useEffect(() => {
    setNewCond({ condition_type: isFromRouter ? 'content_type' : 'button_press', params: {} });
  }, [isFromRouter]);

  const removeCondition = (i) => setConditions(c => c.filter((_, x) => x !== i));

  const commitNew = () => {
    setConditions(c => [...c, { id: nextTempId(), edge_id: edge.id, ...newCond }]);
    setAdding(false);
    setNewCond({ condition_type: isFromRouter ? 'content_type' : 'button_press', params: {} });
  };

  const ParamInputs = () => {
    switch (newCond.condition_type) {
      case 'button_press':
        if ((srcNode?.node_type === 'buttons' || srcNode?.node_type === 'start') && srcNode.payload?.buttons) {
          const used = conditions.filter(c => c.condition_type === 'button_press').map(c => c.params.button_label);
          const rawButtons = srcNode.payload.buttons || [];
          const labels = rawButtons
            .map((b) => (typeof b === 'string' ? b : b?.text))
            .filter(Boolean);
          const available = labels.filter(b => !used.includes(b));
          return (
            <>
              <Label>Кнопка</Label>
              <Select
                value={newCond.params.button_label || ''}
                onChange={e => setNewCond(c => ({ ...c, params: { button_label: e.target.value } }))}
                options={[{ value: '', label: '— выберите —' }, ...available.map(b => ({ value: b, label: b }))]}
              />
            </>
          );
        }
        return (
          <>
            <Label>Название кнопки</Label>
            <Input
              value={newCond.params.button_label || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { button_label: e.target.value } }))}
              placeholder="Да"
            />
          </>
        );
      case 'text_contains':
        return (
          <>
            <Label>Подстрока</Label>
            <Input
              value={newCond.params.substring || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { ...c.params, substring: e.target.value } }))}
              placeholder="да"
            />
          </>
        );
      case 'text_regex':
        return (
          <>
            <Label>Regex паттерн</Label>
            <Input
              value={newCond.params.pattern || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { ...c.params, pattern: e.target.value } }))}
              placeholder="^да$"
              className="font-mono"
            />
          </>
        );
      case 'content_type':
        return (
          <>
            <Label>Тип сообщения</Label>
            <Select
              value={newCond.params.message_type || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { message_type: e.target.value } }))}
              options={[
                { value: '', label: '— выберите —' },
                { value: 'text', label: 'Текст' },
                { value: 'photo', label: 'Фото' },
                { value: 'video', label: 'Видео' },
                { value: 'audio', label: 'Аудио' },
                { value: 'voice', label: 'Голосовое' },
                { value: 'document', label: 'Документ' },
                { value: 'sticker', label: 'Стикер' },
                { value: 'location', label: 'Геолокация' },
                { value: 'contact', label: 'Контакт' },
              ]}
            />
          </>
        );
      case 'has_entities':
        return (
          <>
            <Label>Тип сущности</Label>
            <Select
              value={newCond.params.entity_type || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { entity_type: e.target.value } }))}
              options={[
                { value: '', label: '— выберите —' },
                { value: 'email', label: 'Email' },
                { value: 'phone', label: 'Телефон' },
                { value: 'url', label: 'URL / ссылка' },
                { value: 'hashtag', label: 'Хэштег' },
                { value: 'mention', label: 'Упоминание (@)' },
                { value: 'cashtag', label: 'Cashtag ($AAPL)' },
                { value: 'bot_command', label: 'Команда (/start)' },
              ]}
            />
          </>
        );
      case 'text_equals':
        return (
          <>
            <Label>Точный текст</Label>
            <Input
              value={newCond.params.exact_text || ''}
              onChange={e => setNewCond(c => ({ ...c, params: { exact_text: e.target.value } }))}
              placeholder="да"
            />
          </>
        );
      case 'has_media':
        return <p className="text-sm text-slate-600">Проверяет наличие любого медиа-вложения.</p>;
      case 'timeout':
        return (
          <>
            <Label>Таймаут (секунды)</Label>
            <Input
              type="number"
              value={String(newCond.params.timeout_seconds || 300)}
              onChange={e => setNewCond(c => ({ ...c, params: { timeout_seconds: parseInt(e.target.value) || 300 } }))}
              className="w-32"
            />
          </>
        );
      case 'any_reply':
        return <p className="text-sm text-slate-600">Любое сообщение от пользователя.</p>;
      default:
        return null;
    }
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>Условия: «{nodeLabel(srcNode)}» → «{nodeLabel(tgtNode)}»</DialogTitle>
      </DialogHeader>
      <DialogContent>
        {conditions.length > 0 && (
          <div className="space-y-2 mb-4">
            {conditions.map((c, i) => (
              <div key={c.id} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
                <span className="text-sm font-medium text-slate-700">
                  {CONDITION_LABELS[c.condition_type]}
                  {c.params.button_label ? ` → "${c.params.button_label}"` : ''}
                  {c.params.substring ? ` → "${c.params.substring}"` : ''}
                  {c.params.pattern ? ` → /${c.params.pattern}/` : ''}
                  {c.params.timeout_seconds ? ` → ${c.params.timeout_seconds}с` : ''}
                  {c.params.message_type ? ` = ${c.params.message_type}` : ''}
                  {c.params.entity_type ? ` [${c.params.entity_type}]` : ''}
                  {c.params.exact_text ? ` = "${c.params.exact_text}"` : ''}
                </span>
                <button onClick={() => removeCondition(i)} className="text-red-600 hover:text-red-700">×</button>
              </div>
            ))}
          </div>
        )}

        {isFromTimer ? (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-900">
            ⏱️ У таймера условия не используются. Переход всегда по первому ребру.
          </div>
        ) : adding ? (
          <div className="bg-slate-50 rounded-lg p-4 space-y-3">
            <div>
              <Label>Тип условия</Label>
              <Select
                value={newCond.condition_type}
                onChange={e => setNewCond({ condition_type: e.target.value, params: {} })}
                options={
                  isFromRouter
                    ? [
                        { value: 'content_type', label: CONDITION_LABELS.content_type },
                        { value: 'text_contains', label: CONDITION_LABELS.text_contains },
                        { value: 'text_equals', label: CONDITION_LABELS.text_equals },
                        { value: 'text_regex', label: CONDITION_LABELS.text_regex },
                        { value: 'has_media', label: CONDITION_LABELS.has_media },
                        { value: 'has_entities', label: CONDITION_LABELS.has_entities },
                      ]
                    : [
                        { value: 'button_press', label: CONDITION_LABELS.button_press },
                        { value: 'text_contains', label: CONDITION_LABELS.text_contains },
                        { value: 'text_regex', label: CONDITION_LABELS.text_regex },
                        { value: 'timeout', label: CONDITION_LABELS.timeout },
                        { value: 'any_reply', label: CONDITION_LABELS.any_reply },
                      ]
                }
              />
            </div>
            <ParamInputs />
            <div className="flex gap-2 pt-2">
              <Button variant="primary" onClick={commitNew}>+ Добавить</Button>
              <Button variant="ghost" onClick={() => setAdding(false)}>Отмена</Button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="w-full border border-dashed border-slate-300 rounded-lg py-3 text-sm text-slate-600 hover:bg-slate-50"
          >
            + Добавить условие
          </button>
        )}

        {conditions.length === 0 && !adding && !isFromTimer && (
          <p className="text-sm text-slate-500 text-center py-4">
            Без условий → безусловный переход (fallback)
          </p>
        )}
      </DialogContent>
      <DialogFooter>
        {onDelete && (
          <Button
            variant="ghost"
            size="sm"
            className="h-12 w-12 p-0 text-red-600 hover:bg-red-50 hover:text-red-700"
            onClick={() => { onDelete(); onClose(); }}
            aria-label="Удалить ребро"
            title="Удалить ребро"
          >
            <Trash2 className="h-12 w-12" />
          </Button>
        )}
        <Button variant="ghost" onClick={onClose}>Отмена</Button>
        <Button variant="primary" onClick={() => { onSave(conditions); onClose(); }}>
          Сохранить условия
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
