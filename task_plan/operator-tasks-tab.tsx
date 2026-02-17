'use client';

import { useEffect, useRef, useState } from 'react';
import { operatorTasksApi } from '@/lib/api/operatorTasks';
import type { OperatorTask, OperatorTaskStatus, TaskType } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const TYPE_LABELS: Record<TaskType, string> = {
  1: 'Своя',
  2: 'Уровень сервиса',
};

const STATUS_LABELS: Record<OperatorTaskStatus, string> = {
  open: 'Открыта',
  done: 'Выполнена',
};

type FilterStatus = 'all' | OperatorTaskStatus;
type FilterType = 'all' | TaskType;

export function OperatorTasksTab() {
  const [tasks, setTasks] = useState<OperatorTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [filterType, setFilterType] = useState<FilterType>('all');

  const [resolutionDrafts, setResolutionDrafts] = useState<Record<number, string>>({});
  const savingRef = useRef<Record<number, boolean>>({});

  // new task form
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await operatorTasksApi.list();
        setTasks(data);
        const drafts: Record<number, string> = {};
        for (const t of data) {
          drafts[t.id] = t.resolution_text ?? '';
        }
        setResolutionDrafts(drafts);
      } catch {
        setError('Не удалось загрузить задачи.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const saveResolution = async (task: OperatorTask, text: string, status?: OperatorTaskStatus) => {
    if (savingRef.current[task.id]) return;
    savingRef.current[task.id] = true;
    try {
      const updated = await operatorTasksApi.update(task.id, {
        resolution_text: text || null,
        status: status ?? task.status,
      });
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setResolutionDrafts((prev) => ({ ...prev, [updated.id]: updated.resolution_text ?? '' }));
    } catch {
      // silent
    } finally {
      savingRef.current[task.id] = false;
    }
  };

  const handleCreate = async () => {
    const title = newTitle.trim();
    if (!title || creating) return;
    setCreating(true);
    try {
      const created = await operatorTasksApi.create({
        type: 1,
        title,
        description: newDescription.trim() || null,
      });
      setTasks((prev) => [created, ...prev]);
      setResolutionDrafts((prev) => ({ ...prev, [created.id]: '' }));
      setNewTitle('');
      setNewDescription('');
    } catch {
      setError('Не удалось создать задачу.');
    } finally {
      setCreating(false);
    }
  };

  const filtered = tasks.filter((t) => {
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    if (filterType !== 'all' && t.type !== filterType) return false;
    return true;
  });

  const openCount = tasks.filter((t) => t.status === 'open').length;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">
          Открытых задач:{' '}
          <span className={openCount > 0 ? 'font-semibold text-red-500' : 'font-semibold'}>{openCount}</span>
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
          <Button
            size="sm"
            className="h-8"
            disabled={creating || !newTitle.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? 'Создание…' : 'Добавить'}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-muted-foreground">Статус:</span>
        {(['all', 'open', 'done'] as FilterStatus[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setFilterStatus(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterStatus === s
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {s === 'all' ? 'Все' : STATUS_LABELS[s]}
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-2">Тип:</span>
        {(['all', 1, 2] as FilterType[]).map((tp) => (
          <button
            key={String(tp)}
            type="button"
            onClick={() => setFilterType(tp)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filterType === tp
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {tp === 'all' ? 'Все' : TYPE_LABELS[tp]}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
      {loading && <p className="text-sm text-muted-foreground">Загрузка...</p>}

      {!loading && filtered.length === 0 && (
        <p className="text-sm text-muted-foreground">Задач не найдено.</p>
      )}

      {!loading && filtered.length > 0 && (
        <div className="space-y-3">
          {filtered.map((task) => {
            const isDone = task.status === 'done';
            const draft = resolutionDrafts[task.id] ?? '';
            return (
              <div
                key={task.id}
                className={`rounded-xl border p-4 space-y-3 transition ${
                  isDone ? 'bg-muted/40 opacity-70' : 'bg-card shadow-sm'
                }`}
              >
                {/* Header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{task.title}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          task.type === 2
                            ? 'bg-orange-100 text-orange-700'
                            : 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {TYPE_LABELS[task.type]}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          isDone
                            ? 'bg-green-100 text-green-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {STATUS_LABELS[task.status]}
                      </span>
                    </div>
                    {task.description && (
                      <p className="text-xs text-muted-foreground">{task.description}</p>
                    )}
                    {task.contact_name && (
                      <p className="text-xs text-muted-foreground">
                        Клиент: {task.contact_name}
                        {task.rating != null && ` · Оценка: ${task.rating}/10`}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {new Date(task.created_at).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                      })}
                    </p>
                  </div>
                </div>

                {/* Resolution */}
                <div className="space-y-2">
                  <textarea
                    value={draft}
                    onChange={(e) =>
                      setResolutionDrafts((prev) => ({ ...prev, [task.id]: e.target.value }))
                    }
                    onBlur={() => void saveResolution(task, draft)}
                    placeholder="Опишите решение…"
                    rows={2}
                    disabled={isDone}
                    className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant={isDone ? 'outline' : 'default'}
                    className="h-7 text-xs"
                    onClick={() => void saveResolution(task, draft, isDone ? 'open' : 'done')}
                  >
                    {isDone ? 'Переоткрыть' : 'Отметить выполненным'}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
