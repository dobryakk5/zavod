import { useState } from 'react';
import { Alert } from './Alert';
import { Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, Input, Label, Select } from './ui';

export function NodeEditorModal({ node, onSave, onClose }) {
  const isStartNode = node.node_type === 'start';
  const initialButtons = isStartNode
    ? (node.payload?.buttons || []).map((b) =>
      typeof b === 'string'
        ? { text: b, color: 'green' }
        : { text: b?.text || '', color: b?.color || 'green' }
    )
    : (node.payload?.buttons || []).map((b) => (typeof b === 'string' ? b : b?.text || ''));
  const [form, setForm] = useState({
    ...node,
    payload: { ...node.payload },
    buttons: initialButtons,
  });
  const [error, setError] = useState(null);
  const isTimer = form.node_type === 'timer' || form.payload?.kind === 'timer';
  const isRouter = form.node_type === 'router';
  const isStart = form.node_type === 'start';

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const setP = (k, v) => setForm(f => ({ ...f, payload: { ...f.payload, [k]: v } }));

  const addBtn = () => setForm(f => ({ ...f, buttons: [...f.buttons, ''] }));
  const setBtn = (i, v) => setForm(f => {
    const b = [...f.buttons];
    b[i] = v;
    return { ...f, buttons: b };
  });
  const rmBtn = (i) => setForm(f => ({ ...f, buttons: f.buttons.filter((_, x) => x !== i) }));

  const addStartBtn = () => setForm(f => ({ ...f, buttons: [...f.buttons, { text: '', color: 'green' }] }));
  const setStartBtn = (i, key, value) => setForm(f => {
    const b = [...f.buttons];
    b[i] = { ...(b[i] || {}), [key]: value };
    return { ...f, buttons: b };
  });
  const rmStartBtn = (i) => setForm(f => ({ ...f, buttons: f.buttons.filter((_, x) => x !== i) }));

  const handleSave = () => {
    if (!isTimer && (form.node_type === 'text' || isStart) && !form.payload.text?.trim()) {
      setError('Введите текст сообщения');
      return;
    }
    if (form.node_type === 'buttons' && form.buttons.filter(Boolean).length === 0) {
      setError('Добавьте хотя бы одну кнопку');
      return;
    }

    let payload = { ...form.payload };
    let nodeType = form.node_type;

    if (form.node_type === 'buttons') payload.buttons = form.buttons.filter(Boolean);

    if (form.node_type === 'text') {
      const cleanedButtons = form.buttons
        .map((b) => (b || '').trim())
        .filter(Boolean);
      if (cleanedButtons.length) {
        payload.buttons = cleanedButtons;
      } else {
        delete payload.buttons;
      }
    }

    if (isStart) {
      nodeType = 'start';
      payload = {
        text: (payload.text || '').trim(),
        buttons: form.buttons
          .map((b) => ({
            text: (b?.text || '').trim(),
            color: b?.color || 'green',
          }))
          .filter((b) => b.text),
      };
    }

    if (isRouter) {
      payload.label = (payload.label || '').trim();
      payload.description = (payload.description || '').trim();
    }

    if (isTimer) {
      nodeType = 'timer';
      const raw = Number(payload.duration_seconds);
      const duration = Number.isFinite(raw) ? Math.max(1, Math.floor(raw)) : 60;
      const label = (payload.label || '').trim();
      payload = {
        duration_seconds: duration,
        show_countdown: Boolean(payload.show_countdown),
        countdown_message: payload.countdown_message || null,
      };
      if (label) payload.label = label;
    }

    onSave({
      node_type: nodeType,
      payload,
      delay_seconds: isRouter || isTimer ? 0 : form.delay_seconds,
    });
  };

  const DURATION_PRESETS = [
    { label: '30 сек', value: 30 },
    { label: '1 мин', value: 60 },
    { label: '5 мин', value: 300 },
    { label: '15 мин', value: 900 },
    { label: '30 мин', value: 1800 },
    { label: '1 час', value: 3600 },
    { label: '2 часа', value: 7200 },
    { label: '6 часов', value: 21600 },
    { label: '12 часов', value: 43200 },
    { label: '1 день', value: 86400 },
    { label: '2 дня', value: 172800 },
    { label: '7 дней', value: 604800 },
  ];

  return (
    <Dialog open onClose={onClose}>
      <DialogHeader>
        <DialogTitle>
          {isTimer ? 'Редактирование задержки' : isRouter ? 'Редактирование роутера' : 'Редактирование узла'}
        </DialogTitle>
      </DialogHeader>
      <DialogContent>
        {error && <Alert variant="error">{error}</Alert>}

        <div className="space-y-4 mt-4">
          {!isStart && (
            <div>
              <Label>Тип сообщения</Label>
              <Select
                value={form.node_type}
                onChange={e => set('node_type', e.target.value)}
                options={[
                  { value: 'text', label: 'Сообщение' },
                  { value: 'photo', label: 'Фото' },
                  { value: 'buttons', label: 'Кнопки' },
                  { value: 'router', label: 'Условие' },
                  { value: 'timer', label: 'Задержка' }
                ]}
              />
            </div>
          )}

          {isTimer && (
            <div className="space-y-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
                ⏱️ <strong>Задержка</strong> — ждёт указанное время и переходит дальше.
              </div>

              <div>
                <Label>Название задержки</Label>
                <Input
                  value={form.payload.label || ''}
                  onChange={e => setP('label', e.target.value)}
                  placeholder="Ожидание 1 минуту"
                />
              </div>

              <div className="space-y-2">
                <Label>Длительность</Label>
                <div className="flex flex-wrap gap-2">
                  {DURATION_PRESETS.slice(0, 6).map((preset) => (
                    <button
                      key={preset.value}
                      onClick={() => setP('duration_seconds', preset.value)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
                        Number(form.payload.duration_seconds || 60) === preset.value
                          ? 'bg-amber-100 text-amber-900 border-amber-400'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={String(form.payload.duration_seconds || 60)}
                    onChange={e => setP('duration_seconds', Math.max(1, parseInt(e.target.value) || 60))}
                    className="w-32"
                  />
                  <span className="text-sm text-slate-600">секунд</span>
                </div>

                <details className="text-xs text-slate-600">
                  <summary className="cursor-pointer">Ещё варианты…</summary>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {DURATION_PRESETS.slice(6).map((preset) => (
                      <button
                        key={preset.value}
                        onClick={() => setP('duration_seconds', preset.value)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
                          Number(form.payload.duration_seconds || 60) === preset.value
                            ? 'bg-amber-100 text-amber-900 border-amber-400'
                            : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </details>
              </div>

              <div className="space-y-2 border-t border-slate-200 pt-3">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={Boolean(form.payload.show_countdown)}
                    onChange={e => setP('show_countdown', e.target.checked)}
                    className="mt-1"
                  />
                  <div className="text-sm text-slate-700">
                    Показывать обратный отсчёт
                    <div className="text-xs text-slate-500 mt-0.5">
                      Пользователь увидит сообщение с таймером.
                    </div>
                  </div>
                </label>
                {form.payload.show_countdown && (
                  <div className="ml-6">
                    <Label>Текст сообщения с таймером</Label>
                    <Input
                      value={form.payload.countdown_message || ''}
                      onChange={e => setP('countdown_message', e.target.value)}
                      placeholder="Готовим для вас контент…"
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {form.node_type === 'router' && (
            <div className="space-y-3">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm text-purple-900">
                🔀 <strong>Условие</strong> — анализирует входящее сообщение и направляет по веткам.
              </div>
              <div>
                <Label>Название условия</Label>
                <Input
                  value={form.payload.label || ''}
                  onChange={e => setP('label', e.target.value)}
                  placeholder="Проверка типа сообщения"
                />
              </div>
              <div>
                <Label>Описание (опционально)</Label>
                <textarea
                  value={form.payload.description || ''}
                  onChange={e => setP('description', e.target.value)}
                  placeholder="Дополнительная информация"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 resize-none"
                  rows={2}
                />
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs text-slate-600">
                💡 Условия настраиваются прямо на узле.
              </div>
            </div>
          )}

          {isStart && (
            <div className="space-y-3">
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-900">
                ⭐ <strong>START</strong> — стартовый узел цепочки.
              </div>
              <div>
                <Label>Текст сообщения</Label>
                <textarea
                  value={form.payload.text || ''}
                  onChange={e => setP('text', e.target.value)}
                  placeholder="Введите текст..."
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 resize-none"
                  rows={3}
                />
              </div>
              <div>
                <Label>Кнопки</Label>
                <div className="space-y-2">
                  {form.buttons.map((b, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <Input
                        value={b?.text || ''}
                        onChange={e => setStartBtn(i, 'text', e.target.value)}
                        placeholder={`Кнопка ${i + 1}`}
                      />
                      <button onClick={() => rmStartBtn(i)} className="text-red-600 hover:text-red-700 px-2">×</button>
                    </div>
                  ))}
                  <button onClick={addStartBtn} className="w-full border border-dashed border-slate-300 rounded-lg py-2 text-sm text-slate-600 hover:bg-slate-50">
                    + Добавить кнопку
                  </button>
                </div>
              </div>
            </div>
          )}

          {!isStart && !isTimer && (form.node_type === 'text' || form.node_type === 'buttons') && (
            <div>
              <Label>Текст сообщения</Label>
              <textarea
                value={form.payload.text || ''}
                onChange={e => setP('text', e.target.value)}
                placeholder="Введите текст..."
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 resize-none"
                rows={3}
              />
            </div>
          )}

          {form.node_type === 'photo' && (
            <>
              <div>
                <Label>URL фото</Label>
                <Input value={form.payload.photo_url || ''} onChange={e => setP('photo_url', e.target.value)} placeholder="https://..." />
              </div>
              <div>
                <Label>Подпись (caption)</Label>
                <Input value={form.payload.caption || ''} onChange={e => setP('caption', e.target.value)} placeholder="Необязательно" />
              </div>
            </>
          )}

          {(form.node_type === 'buttons' || form.node_type === 'text') && (
            <div>
              <Label>Кнопки</Label>
              <div className="space-y-2">
                {form.buttons.map((b, i) => (
                  <div key={i} className="flex gap-2">
                    <Input value={b} onChange={e => setBtn(i, e.target.value)} placeholder={`Кнопка ${i + 1}`} />
                    <button onClick={() => rmBtn(i)} className="text-red-600 hover:text-red-700 px-2">×</button>
                  </div>
                ))}
                <button onClick={addBtn} className="w-full border border-dashed border-slate-300 rounded-lg py-2 text-sm text-slate-600 hover:bg-slate-50">
                  + Добавить кнопку
                </button>
              </div>
            </div>
          )}

          {!isRouter && !isTimer && !isStart && (
            <div>
              <Label>Задержка перед отправкой (секунды)</Label>
              <Input
                type="number"
                value={String(form.delay_seconds)}
                onChange={e => set('delay_seconds', Math.max(0, parseInt(e.target.value) || 0))}
                className="w-32"
              />
            </div>
          )}
        </div>
      </DialogContent>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>Отмена</Button>
        <Button variant="primary" onClick={handleSave}>Сохранить узел</Button>
      </DialogFooter>
    </Dialog>
  );
}
