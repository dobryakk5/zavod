import { useEffect, useState } from 'react';
import { CONDITION_LABELS } from '../constants';
import { formatRouterConditionLabel } from '../utils';
import { Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Label, Select } from './ui';

const CONDITION_GROUPS = {
  content: [
    { value: 'button_press', label: CONDITION_LABELS.button_press },
    { value: 'has_media', label: CONDITION_LABELS.has_media },
    { value: 'content_type', label: CONDITION_LABELS.content_type },
  ],
  text: [
    { value: 'text_regex', label: CONDITION_LABELS.text_regex },
    { value: 'has_entities', label: CONDITION_LABELS.has_entities },
    { value: 'text_contains', label: CONDITION_LABELS.text_contains },
    { value: 'text_equals', label: CONDITION_LABELS.text_equals },
  ],
  client: [
    { value: 'client_tag_contains', label: CONDITION_LABELS.client_tag_contains },
    { value: 'client_has_meeting', label: CONDITION_LABELS.client_has_meeting },
    { value: 'client_has_payment', label: CONDITION_LABELS.client_has_payment },
  ],
  fallback: [
    { value: 'fallback', label: 'Fallback (любой)' },
  ],
};

const CONDITION_GROUP_OPTIONS = [
  { value: 'content', label: 'Контент' },
  { value: 'text', label: 'Текст' },
  { value: 'client', label: 'Клиент' },
  { value: 'fallback', label: 'Fallback (иное)' },
];

const NEAREST_RELATION_OPTIONS = [
  { value: '', label: 'Без проверки времени' },
  { value: 'before', label: 'До ближайшей даты' },
  { value: 'after', label: 'После ближайшей даты' },
];

function inferGroupByType(type) {
  const entries = Object.entries(CONDITION_GROUPS);
  for (const [group, options] of entries) {
    if (options.some((item) => item.value === type)) return group;
  }
  return 'content';
}

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
    case 'client_has_meeting':
      return { status: '', nearest_relation: '' };
    case 'client_has_payment':
      return { status: '', nearest_relation: '' };
    default:
      return {};
  }
}

export function RouterConditionModal({ condition, onSave, onClose }) {
  const initialType = condition?.condition_type || 'content_type';
  const [group, setGroup] = useState(inferGroupByType(initialType));
  const [type, setType] = useState(initialType);
  const [params, setParams] = useState(condition?.params || defaultParams(initialType));
  const [label, setLabel] = useState(condition?.label || '');

  useEffect(() => {
    if (condition) {
      const nextType = condition.condition_type || 'content_type';
      setType(nextType);
      setGroup(inferGroupByType(nextType));
      setParams(condition.params || defaultParams(nextType));
      setLabel(condition.label || '');
      return;
    }
    setGroup('content');
    setType('content_type');
    setParams(defaultParams('content_type'));
    setLabel('');
  }, [condition]);

  const conditionTypeOptions = CONDITION_GROUPS[group] || [];

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
            <Label>Группа</Label>
            <Select
              value={group}
              onChange={(e) => {
                const nextGroup = e.target.value;
                const firstOption = (CONDITION_GROUPS[nextGroup] || [])[0];
                if (!firstOption) return;
                setGroup(nextGroup);
                setType(firstOption.value);
                setParams(defaultParams(firstOption.value));
              }}
              options={CONDITION_GROUP_OPTIONS}
            />
          </div>

          <div>
            <Label>Тип условия</Label>
            <Select
              value={type}
              onChange={(e) => {
                const nextType = e.target.value;
                setType(nextType);
                setGroup(inferGroupByType(nextType));
                setParams(defaultParams(nextType));
              }}
              options={conditionTypeOptions}
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

          {type === 'client_has_meeting' && (
            <div className="space-y-3">
              <div>
                <Label>Статус встречи (опционально)</Label>
                <Select
                  value={params.status || ''}
                  onChange={(e) => setParams({ ...params, status: e.target.value })}
                  options={[
                    { value: '', label: 'Любая встреча' },
                    { value: 'scheduled', label: 'Запланирована' },
                    { value: 'completed', label: 'Завершена' },
                    { value: 'cancelled', label: 'Отменена' },
                    { value: 'no_show', label: 'Не явился' },
                  ]}
                />
              </div>
              <div>
                <Label>Относительно ближайшей встречи</Label>
                <Select
                  value={params.nearest_relation || ''}
                  onChange={(e) => setParams({ ...params, nearest_relation: e.target.value })}
                  options={NEAREST_RELATION_OPTIONS}
                />
              </div>
            </div>
          )}

          {type === 'client_has_payment' && (
            <div className="space-y-3">
              <div>
                <Label>Статус оплаты (опционально)</Label>
                <Select
                  value={params.status || ''}
                  onChange={(e) => setParams({ ...params, status: e.target.value })}
                  options={[
                    { value: '', label: 'Любая оплата' },
                    { value: 'pending', label: 'В ожидании' },
                    { value: 'paid', label: 'Оплачено' },
                    { value: 'failed', label: 'Ошибка' },
                    { value: 'refunded', label: 'Возврат' },
                  ]}
                />
              </div>
              <div>
                <Label>Относительно ближайшей оплаты</Label>
                <Select
                  value={params.nearest_relation || ''}
                  onChange={(e) => setParams({ ...params, nearest_relation: e.target.value })}
                  options={NEAREST_RELATION_OPTIONS}
                />
              </div>
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
