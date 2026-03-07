'use client';

import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { operatorTasksApi } from '@/lib/api/operatorTasks';
import type { OperatorTask, OperatorTaskStatus } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const STATUS_LABELS: Record<OperatorTaskStatus, string> = {
  open: 'Открыта',
  in_progress: 'В работе',
  done: 'Выполнена',
  checked: 'Проверена',
};

const STATUS_COLORS: Record<OperatorTaskStatus, string> = {
  open: 'bg-red-100 text-red-700',
  in_progress: 'bg-yellow-100 text-yellow-700',
  done: 'bg-green-100 text-green-700',
  checked: 'bg-blue-100 text-blue-700',
};

const PRIORITY_COLORS: Record<1 | 2 | 3, string> = {
  1: 'bg-red-100 text-red-700',
  2: 'bg-amber-100 text-amber-700',
  3: 'bg-slate-100 text-slate-700',
};

const PRIORITY_LABELS: Record<1 | 2 | 3, string> = {
  1: 'Приоритет 1',
  2: 'Приоритет 2',
  3: 'Приоритет 3',
};

type FilterStatus = 'all' | OperatorTaskStatus;
type FilterCreator = 'all' | 'system' | 'operator';

function formatTaskAuthor(createdBy: number, username?: string | null): string {
  if (createdBy === 0) return 'Система';
  if (username) return username;
  return `Оператор #${createdBy}`;
}

function normalizePriority(value: unknown): 1 | 2 | 3 {
  if (value === 1 || value === 2 || value === 3) return value;
  return 2;
}

export function OperatorTasksTab() {
  const [tasks, setTasks] = useState<OperatorTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [filterCreator, setFilterCreator] = useState<FilterCreator>('all');

  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newPriority, setNewPriority] = useState<1 | 2 | 3>(2);
  const [newDueAt, setNewDueAt] = useState('');
  const [creating, setCreating] = useState(false);

  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const [actionTask, setActionTask] = useState<OperatorTask | null>(null);
  const [actionNote, setActionNote] = useState('');
  const [actionStatus, setActionStatus] = useState<OperatorTaskStatus | ''>('');
  const [actionPriority, setActionPriority] = useState<1 | 2 | 3>(2);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await operatorTasksApi.list();
        setTasks(data.map((task) => ({ ...task, priority: normalizePriority(task.priority) })));
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
    const dueAtDate = newDueAt ? new Date(newDueAt) : null;
    if (dueAtDate && Number.isNaN(dueAtDate.getTime())) {
      setError('Некорректный дедлайн.');
      return;
    }
    const dueAtIso = dueAtDate ? dueAtDate.toISOString() : null;
    setCreating(true);
    try {
      const created = await operatorTasksApi.create({
        title,
        description: newDescription.trim() || null,
        priority: newPriority,
        due_at: dueAtIso,
      });
      setTasks((prev) => [{ ...created, priority: normalizePriority(created.priority) }, ...prev]);
      setNewTitle('');
      setNewDescription('');
      setNewPriority(2);
      setNewDueAt('');
    } catch {
      setError('Не удалось создать задачу.');
    } finally {
      setCreating(false);
    }
  };

  const openActionModal = (task: OperatorTask) => {
    setActionTask(task);
    setActionNote('');
    setActionStatus(task.status === 'done' || task.status === 'checked' ? 'open' : '');
    setActionPriority(normalizePriority(task.priority));
  };

  const closeActionModal = () => {
    if (actionSubmitting) return;
    setActionTask(null);
    setActionNote('');
    setActionStatus('');
    setActionPriority(2);
  };

  const submitAction = async () => {
    if (!actionTask) return;
    const note = actionNote.trim();
    if (!note || actionSubmitting) return;

    setActionSubmitting(true);
    try {
      const statusToSend = actionStatus || null;
      const entry = await operatorTasksApi.addHistory(actionTask.id, {
        note,
        status: statusToSend,
        priority: actionPriority,
      });

      setTasks((prev) =>
        prev.map((task) => {
          if (task.id !== actionTask.id) return task;
          return {
            ...task,
            status: entry.status ?? statusToSend ?? task.status,
            priority: actionPriority,
            updated_at: entry.created_at,
            history: [...(task.history ?? []), entry],
          };
        }),
      );

      closeActionModal();
    } catch {
      setError('Не удалось сохранить шаг.');
    } finally {
      setActionSubmitting(false);
    }
  };

  const filtered = [...tasks]
    .filter((task) => {
      if (filterStatus !== 'all' && task.status !== filterStatus) return false;
      if (filterCreator === 'system' && task.created_by !== 0) return false;
      if (filterCreator === 'operator' && task.created_by === 0) return false;
      return true;
    })
    .sort((a, b) => {
      const aPriority = normalizePriority(a.priority);
      const bPriority = normalizePriority(b.priority);
      if (aPriority !== bPriority) return aPriority - bPriority;
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });

  const openCount = tasks.filter((task) => task.status === 'open').length;
  const inProgressCount = tasks.filter((task) => task.status === 'in_progress').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">
          Открытых: <span className={openCount > 0 ? 'font-semibold text-red-500' : 'font-semibold'}>{openCount}</span>
        </span>
        <span className="text-sm text-muted-foreground">
          В работе: <span className={inProgressCount > 0 ? 'font-semibold text-yellow-600' : 'font-semibold'}>{inProgressCount}</span>
        </span>
        <span className="text-sm text-muted-foreground">Всего: {tasks.length}</span>
      </div>

      <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-3">
        <div className="text-sm font-semibold">Новая задача</div>
        <div className="flex gap-2 flex-wrap items-center">
          <Input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleCreate();
            }}
            placeholder="Название задачи"
            className="h-8 max-w-sm text-sm"
          />
          <Input
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="Описание (необязательно)"
            className="h-8 max-w-sm text-sm"
          />
          <select
            value={newPriority}
            onChange={(e) => setNewPriority(Number(e.target.value) as 1 | 2 | 3)}
            className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value={1}>Приоритет 1</option>
            <option value={2}>Приоритет 2</option>
            <option value={3}>Приоритет 3</option>
          </select>
          <Input
            type="datetime-local"
            value={newDueAt}
            onChange={(e) => setNewDueAt(e.target.value)}
            className="h-8 max-w-[220px] text-sm"
          />
          <Button size="sm" className="h-8" disabled={creating || !newTitle.trim()} onClick={() => void handleCreate()}>
            {creating ? 'Создание…' : 'Добавить'}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-muted-foreground">Статус:</span>
        {(['all', 'open', 'in_progress', 'done', 'checked'] as FilterStatus[]).map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setFilterStatus(status)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterStatus === status
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {status === 'all' ? 'Все' : STATUS_LABELS[status]}
          </button>
        ))}

        <span className="text-xs text-muted-foreground ml-2">Источник:</span>
        {([['all', 'Все'], ['system', 'Система'], ['operator', 'Оператор']] as [FilterCreator, string][]).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilterCreator(value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterCreator === value
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
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
            const isDone = task.status === 'done' || task.status === 'checked';
            const isExpanded = expanded[task.id] ?? false;
            const historyCount = task.history?.length ?? 0;
            const priority = normalizePriority(task.priority);

            return (
              <div
                key={task.id}
                className={`rounded-xl border p-4 space-y-3 ${isDone ? 'opacity-60' : 'shadow-sm'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{task.title}</span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[task.status]}`}>
                        {STATUS_LABELS[task.status]}
                      </span>
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_COLORS[priority]}`}>
                        {PRIORITY_LABELS[priority]}
                      </span>
                      <span className="rounded-full px-2 py-0.5 text-xs bg-muted text-muted-foreground">
                        {formatTaskAuthor(task.created_by, task.created_by_username)}
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
                    {task.due_at && (
                      <p
                        className={`text-xs ${
                          isDone ? 'text-muted-foreground' : new Date(task.due_at).getTime() < Date.now() ? 'text-red-500' : 'text-muted-foreground'
                        }`}
                      >
                        Дедлайн:{' '}
                        {new Date(task.due_at).toLocaleString('ru-RU', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {new Date(task.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric', month: 'long', year: 'numeric',
                      })}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      type="button"
                      size="icon"
                      variant="outline"
                      className="h-7 w-7"
                      onClick={() => openActionModal(task)}
                      aria-label="Добавить шаг"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                    {historyCount > 0 && (
                      <button
                        type="button"
                        onClick={() => setExpanded((prev) => ({ ...prev, [task.id]: !isExpanded }))}
                        className="text-xs text-muted-foreground hover:text-foreground transition"
                      >
                        {isExpanded ? 'Скрыть' : `История (${historyCount})`}
                      </button>
                    )}
                  </div>
                </div>

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
                            {formatTaskAuthor(entry.created_by, entry.created_by_username)}
                          </span>
                        </div>
                        <p className="text-sm">{entry.note}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {actionTask && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeActionModal();
          }}
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl p-6 space-y-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-base">Добавить шаг</div>
                <div className="text-xs text-muted-foreground mt-0.5">{actionTask.title}</div>
              </div>
              <button
                type="button"
                onClick={closeActionModal}
                className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition"
                aria-label="Закрыть"
              >
                ✕
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Комментарий шага</label>
              <textarea
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                placeholder="Напишите, что было сделано…"
                rows={4}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Статус</label>
              <select
                value={actionStatus}
                onChange={(e) => setActionStatus(e.target.value as OperatorTaskStatus | '')}
                className="h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">Без изменений</option>
                <option value="open">Открыта</option>
                <option value="in_progress">В работе</option>
                <option value="done">Выполнена</option>
                <option value="checked">Проверена</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">Приоритет</label>
              <div className="flex gap-3">
                {[1, 2, 3].map((priority) => (
                  <label key={priority} className="inline-flex items-center gap-1.5 text-sm">
                    <input
                      type="radio"
                      name="task-priority"
                      checked={actionPriority === priority}
                      onChange={() => setActionPriority(priority as 1 | 2 | 3)}
                    />
                    {priority}
                  </label>
                ))}
              </div>
            </div>

            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" onClick={closeActionModal} disabled={actionSubmitting}>
                Отмена
              </Button>
              <Button
                type="button"
                onClick={() => void submitAction()}
                disabled={!actionNote.trim() || actionSubmitting}
              >
                {actionSubmitting ? 'Сохранение…' : 'Сохранить'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
