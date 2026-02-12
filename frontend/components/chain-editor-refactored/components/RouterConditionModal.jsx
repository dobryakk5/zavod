import { useEffect, useState } from 'react';
import { CONDITION_LABELS } from '../constants';
import { formatRouterConditionLabel } from '../utils';
import { Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Label, Select } from './ui';

const ROUTER_CONDITION_OPTIONS = [
  { value: 'button_press', label: CONDITION_LABELS.button_press },
  { value: 'content_type', label: CONDITION_LABELS.content_type },
  { value: 'text_contains', label: CONDITION_LABELS.text_contains },
  { value: 'client_tag_contains', label: CONDITION_LABELS.client_tag_contains },
  { value: 'text_equals', label: CONDITION_LABELS.text_equals },
  { value: 'text_regex', label: CONDITION_LABELS.text_regex },
  { value: 'has_media', label: CONDITION_LABELS.has_media },
  { value: 'has_entities', label: CONDITION_LABELS.has_entities },
  { value: 'fallback', label: 'Fallback (любой)' },
];

function defaultParams(type) {
  switch (type) {
    case 'button_press':
      return { button_label: '' };
    case 'content_type':
      return { message_type: '' };
    case 'text_contains':
      return { substring: '' };
    case 'client_tag_contains':
      return { substring: '' };
    case 'text_equals':
      return { exact_text: '' };
    case 'text_regex':
      return { pattern: '' };
    case 'has_entities':
      return { entity_type: '' };
    default:
      return {};
  }
}

export function RouterConditionModal({ condition, onSave, onClose }) {
  const [type, setType] = useState(condition?.condition_type || 'content_type');
  const [params, setParams] = useState(condition?.params || defaultParams(condition?.condition_type || 'content_type'));
  const [label, setLabel] = useState(condition?.label || '');

  useEffect(() => {
    if (condition) {
      setType(condition.condition_type || 'content_type');
      setParams(condition.params || defaultParams(condition.condition_type || 'content_type'));
      setLabel(condition.label || '');
    }
  }, [condition]);

  const handleSave = () => {
    const trimmed = label.trim();
    const payload = {
      ...(condition?.id ? { id: condition.id } : {}),
      condition_type: type,
      params,
    };
    if (trimmed) {
      payload.label = trimmed;
    }
    onSave(payload);
  };

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>{condition ? 'Редактировать условие' : 'Добавить условие'}</DialogTitle>
      </DialogHeader>
      <DialogContent>
        <div className="space-y-4">
          <div>
            <Label>Тип условия</Label>
            <Select
              value={type}
              onChange={(e) => {
                const nextType = e.target.value;
                setType(nextType);
                setParams(defaultParams(nextType));
              }}
              options={ROUTER_CONDITION_OPTIONS}
            />
          </div>

          {type === 'button_press' && (
            <div>
              <Label>Текст кнопки</Label>
              <Input
                value={params.button_label || ''}
                onChange={(e) => setParams({ button_label: e.target.value })}
                placeholder="Да"
              />
            </div>
          )}

          {type === 'content_type' && (
            <div>
              <Label>Тип сообщения</Label>
              <Select
                value={params.message_type || ''}
                onChange={(e) => setParams({ message_type: e.target.value })}
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
            </div>
          )}

          {type === 'text_contains' && (
            <div>
              <Label>Подстрока</Label>
              <Input
                value={params.substring || ''}
                onChange={(e) => setParams({ substring: e.target.value })}
                placeholder="да"
              />
            </div>
          )}

          {type === 'client_tag_contains' && (
            <div>
              <Label>Текст в теге клиента</Label>
              <Input
                value={params.substring || ''}
                onChange={(e) => setParams({ substring: e.target.value })}
                placeholder="vip"
              />
            </div>
          )}

          {type === 'text_equals' && (
            <div>
              <Label>Точный текст</Label>
              <Input
                value={params.exact_text || ''}
                onChange={(e) => setParams({ exact_text: e.target.value })}
                placeholder="да"
              />
            </div>
          )}

          {type === 'text_regex' && (
            <div>
              <Label>Regex паттерн</Label>
              <Input
                value={params.pattern || ''}
                onChange={(e) => setParams({ pattern: e.target.value })}
                placeholder="^да$"
                className="font-mono"
              />
            </div>
          )}

          {type === 'has_entities' && (
            <div>
              <Label>Тип сущности</Label>
              <Select
                value={params.entity_type || ''}
                onChange={(e) => setParams({ entity_type: e.target.value })}
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
            </div>
          )}

          {type === 'has_media' && (
            <p className="text-sm text-slate-600">Проверяет наличие любого медиа-вложения.</p>
          )}

          {type === 'fallback' && (
            <p className="text-sm text-slate-600">Fallback срабатывает, если другие условия не подошли.</p>
          )}

          <div>
            <Label>Название условия (опционально)</Label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={formatRouterConditionLabel({ condition_type: type, params })}
            />
          </div>
        </div>
      </DialogContent>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Отмена</Button>
        <Button variant="primary" onClick={handleSave}>
          {condition ? 'Сохранить' : 'Добавить'}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
