'use client';

import { useEffect, useState } from 'react';
import { operatorTasksApi } from '@/lib/api/operatorTasks';
import type { OperatorTask, OperatorTaskStatus } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const STATUS_LABELS: Record<OperatorTaskStatus, string> = {
  open: 'Открыта',
  in_progress: 'В работе',
  done: 'Выполнена',
};

const STATUS_COLORS: Record<OperatorTaskStatus, string> = {
  open: 'bg-red-100 text-red-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  done: 'bg-green-100 text-green-700',
};

type FilterStatus = 'all' | OperatorTaskStatus;
type FilterCreator = 'all' | 'system' | 'operator';

export function OperatorTasksTab() {
  const [tasks, setTasks] = useState<OperatorTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [filterCreator, setFilterCreator] = useState<FilterCreator>('all');

  // new task form
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);

  // history step form per task
  const [noteInputs, setNoteInputs] = useState<Record<number, string>>({});
  const [statusInputs, setStatusInputs] = useState<Record<number, OperatorTaskStatus | ''>>({});
  const [submitting, setSubmitting] = useState<Record<number, boolean>>({});

  // expanded tasks
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await operatorTasksApi.list();
        setTasks(data);
      } catch {
        setError('Не удалось загрузить задачи.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const handleCreate = async () => {
    const title = newTitle.trim();
    if (!title || creating) return;
    setCreating(true);
    try {
      const created = await operatorTasksApi.create({
        title,
        description: newDescription.trim() || null,
        created_by: 1,
      });
      setTasks((prev) => [created, ...prev]);
      setNewTitle('');
      setNewDescription('');
    } catch {
      setError('Не удалось создать задачу.');
    } finally {
      setCreating(false);
    }
  };

  const handleAddHistory = async (task: OperatorTask) => {
    const note = (noteInputs[task.id] ?? '').trim();
    if (!note || submitting[task.id]) return;
    const status = (statusInputs[task.id] || null) as OperatorTaskStatus | null;
    setSubmitting((prev) => ({ ...prev, [task.id]: true }));
    try {
      const entry = await operatorTasksApi.addHistory(task.id, { note, status, created_by: 1 });
      setTasks((prev) =>
        prev.map((t) => {
          if (t.id !== task.id) return t;
          return {
            ...t,
            status: entry.status ?? t.status,
            updated_at: entry.created_at,
            history: [...(t.history ?? []), entry],
          };
        }),
      );
      setNoteInputs((prev) => ({ ...prev, [task.id]: '' }));
      setStatusInputs((prev) => ({ ...prev, [task.id]: '' }));
    } catch {
      setError('Не удалось сохранить шаг.');
    } finally {
      setSubmitting((prev) => ({ ...prev, [task.id]: false }));
    }
  };

  const filtered = tasks.filter((t) => {
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    if (filterCreator === 'system' && t.created_by !== 0) return false;
    if (filterCreator === 'operator' && t.created_by === 0) return false;
    return true;
  });

  const openCount = tasks.filter((t) => t.status === 'open').length;
  const inProgressCount = tasks.filter((t) => t.status === 'in_progress').length;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">
          Открытых: <span className={openCount > 0 ? 'font-semibold text-red-500' : 'font-semibold'}>{openCount}</span>
        </span>
        <span className="text-sm text-muted-foreground">
          В работе: <span className={inProgressCount > 0 ? 'font-semibold text-yellow-600' : 'font-semibold'}>{inProgressCount}</span>
        </span>
        <span className="text-sm text-muted-foreground">Всего: {tasks.length}</span>
      </div>

      {/* New task form */}
      <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-3">
        <div className="text-sm font-semibold">Новая задача</div>
        <div className="flex gap-2 flex-wrap">
          <Input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate(); }}
            placeholder="Название задачи"
            className="h-8 max-w-sm text-sm"
          />
          <Input
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="Описание (необязательно)"
            className="h-8 max-w-sm text-sm"
          />
          <Button size="sm" className="h-8" disabled={creating || !newTitle.trim()} onClick={() => void handleCreate()}>
            {creating ? 'Создание…' : 'Добавить'}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-muted-foreground">Статус:</span>
        {(['all', 'open', 'in_progress', 'done'] as FilterStatus[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilterStatus(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterStatus === s ? 'bg-primary text-primary-foreground shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {s === 'all' ? 'Все' : STATUS_LABELS[s]}
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-2">Источник:</span>
        {([['all', 'Все'], ['system', 'Система'], ['operator', 'Оператор']] as [FilterCreator, string][]).map(([val, label]) => (
          <button
            key={val}
            type="button"
            onClick={() => setFilterCreator(val)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterCreator === val ? 'bg-primary text-primary-foreground shadow-sm' : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {loading && <p className="text-sm text-muted-foreground">Загрузка...</p>}
      {!loading && filtered.length === 0 && <p className="text-sm text-muted-foreground">Задач не найдено.</p>}

      {!loading && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((task) => {
            const isDone = task.status === 'done';
            const isExpanded = expanded[task.id] ?? false;
            const historyCount = task.history?.length ?? 0;

            return (
              <div
                key={task.id}
                className={`rounded-xl border p-4 space-y-3 ${isDone ? 'opacity-60' : 'shadow-sm'}`}
              >
                {/* Task header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{task.title}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[task.status]}`}>
                        {STATUS_LABELS[task.status]}
                      </span>
                      <span className="rounded-full px-2 py-0.5 text-xs bg-muted text-muted-foreground">
                        {task.created_by === 0 ? 'Система' : `Оператор #${task.created_by}`}
                      </span>
                      {task.level_id != null && (
                        <span className="rounded-full px-2 py-0.5 text-xs bg-orange-100 text-orange-700">
                          Уровень сервиса
                        </span>
                      )}
                    </div>
                    {task.description && (
                      <p className="text-xs text-muted-foreground">{task.description}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {new Date(task.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric', month: 'long', year: 'numeric',
                      })}
                    </p>
                  </div>

                  {historyCount > 0 && (
                    <button
                      type="button"
                      onClick={() => setExpanded((prev) => ({ ...prev, [task.id]: !isExpanded }))}
                      className="text-xs text-muted-foreground hover:text-foreground transition shrink-0"
                    >
                      {isExpanded ? 'Скрыть' : `История (${historyCount})`}
                    </button>
                  )}
                </div>

                {/* History */}
                {isExpanded && historyCount > 0 && (
                  <div className="space-y-2 border-l-2 border-muted pl-3">
                    {(task.history ?? []).map((entry) => (
                      <div key={entry.id} className="space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs text-muted-foreground">
                            {new Date(entry.created_at).toLocaleString('ru-RU', {
                              day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
                            })}
                          </span>
                          {entry.status && (
                            <span className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${STATUS_COLORS[entry.status]}`}>
                              {STATUS_LABELS[entry.status]}
                            </span>
                          )}
                          <span className="text-xs text-muted-foreground">
                            {entry.created_by === 0 ? 'Система' : `Оператор #${entry.created_by}`}
                          </span>
                        </div>
                        <p className="text-sm">{entry.note}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add step */}
                <div className="space-y-2">
                  <textarea
                    value={noteInputs[task.id] ?? ''}
                    onChange={(e) => setNoteInputs((prev) => ({ ...prev, [task.id]: e.target.value }))}
                    placeholder={isDone ? 'Причина переоткрытия…' : 'Добавить шаг решения…'}
                    rows={2}
                    className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  <div className="flex gap-2 flex-wrap">
                    {!isDone && (
                      <select
                        value={statusInputs[task.id] ?? ''}
                        onChange={(e) =>
                          setStatusInputs((prev) => ({ ...prev, [task.id]: e.target.value as OperatorTaskStatus | '' }))
                        }
                        className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        <option value="">Статус без изменений</option>
                        <option value="in_progress">В работе</option>
                        <option value="done">Выполнена</option>
                      </select>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant={isDone ? 'outline' : 'default'}
                      className="h-8"
                      disabled={!noteInputs[task.id]?.trim() || submitting[task.id]}
                      onClick={() => void handleAddHistory(task)}
                    >
                      {submitting[task.id] ? 'Сохранение…' : isDone ? 'Переоткрыть' : 'Добавить шаг'}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
