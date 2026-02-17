'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError } from '@/lib/api';
import { telegramTasksApi } from '@/lib/api/telegramTasks';
import { operatorTasksApi } from '@/lib/api/operatorTasks';
import type { OperatorTask, OperatorTaskStatus, TelegramTask } from '@/lib/types';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';

type SortKey = 'received_at' | 'rating' | 'message_text' | 'tg_name';
type SortDirection = 'asc' | 'desc';

const defaultSort: { key: SortKey; direction: SortDirection } = {
  key: 'received_at',
  direction: 'desc',
};

const defaultDirectionForKey = (key: SortKey): SortDirection =>
  key === 'received_at' || key === 'rating' ? 'desc' : 'asc';

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

// ---------------------------------------------------------------------------
// Task Modal
// ---------------------------------------------------------------------------

type TaskModalProps = {
  item: TelegramTask;
  tasks: OperatorTask[];
  creating: boolean;
  onClose: () => void;
  onCreateTask: (item: TelegramTask) => Promise<void>;
  onAddHistory: (
    taskId: number,
    note: string,
    status: OperatorTaskStatus | null,
  ) => Promise<void>;
};

function TaskModal({ item, tasks, creating, onClose, onCreateTask, onAddHistory }: TaskModalProps) {
  const [noteInputs, setNoteInputs] = useState<Record<number, string>>({});
  const [statusInputs, setStatusInputs] = useState<Record<number, OperatorTaskStatus | ''>>({});
  const [submitting, setSubmitting] = useState<Record<number, boolean>>({});

  const handleSubmit = async (task: OperatorTask) => {
    const note = (noteInputs[task.id] ?? '').trim();
    if (!note || submitting[task.id]) return;
    const status = (statusInputs[task.id] || null) as OperatorTaskStatus | null;
    setSubmitting((prev) => ({ ...prev, [task.id]: true }));
    try {
      await onAddHistory(task.id, note, status);
      setNoteInputs((prev) => ({ ...prev, [task.id]: '' }));
      setStatusInputs((prev) => ({ ...prev, [task.id]: '' }));
    } finally {
      setSubmitting((prev) => ({ ...prev, [task.id]: false }));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-semibold text-base">Задачи по обратной связи</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {item.tg_name ? `@${item.tg_name}` : '—'}
              {item.rating != null && ` · Оценка: ${item.rating}/10`}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition"
            aria-label="Закрыть"
          >
            ✕
          </button>
        </div>

        {/* Source message */}
        {item.message_text && (
          <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-muted-foreground whitespace-pre-wrap">
            {item.message_text}
          </div>
        )}

        {/* Task list */}
        {tasks.length > 0 && (
          <div className="space-y-4">
            {tasks.map((task) => (
              <div key={task.id} className="rounded-lg border p-4 space-y-3">
                {/* Task header */}
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-medium text-sm">{task.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[task.status]}`}>
                    {STATUS_LABELS[task.status]}
                  </span>
                </div>
                {task.description && (
                  <p className="text-xs text-muted-foreground">{task.description}</p>
                )}

                {/* History */}
                {(task.history ?? []).length > 0 && (
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

                {/* Add step form */}
                {task.status !== 'done' && (
                  <div className="space-y-2 pt-1">
                    <textarea
                      value={noteInputs[task.id] ?? ''}
                      onChange={(e) =>
                        setNoteInputs((prev) => ({ ...prev, [task.id]: e.target.value }))
                      }
                      placeholder="Добавить шаг решения…"
                      rows={2}
                      className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                    <div className="flex gap-2 flex-wrap">
                      <select
                        value={statusInputs[task.id] ?? ''}
                        onChange={(e) =>
                          setStatusInputs((prev) => ({
                            ...prev,
                            [task.id]: e.target.value as OperatorTaskStatus | '',
                          }))
                        }
                        className="h-8 rounded-md border border-input bg-transparent px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        <option value="">Статус без изменений</option>
                        <option value="in_progress">В работе</option>
                        <option value="done">Выполнена</option>
                      </select>
                      <Button
                        type="button"
                        size="sm"
                        className="h-8"
                        disabled={!noteInputs[task.id]?.trim() || submitting[task.id]}
                        onClick={() => void handleSubmit(task)}
                      >
                        {submitting[task.id] ? 'Сохранение…' : 'Добавить шаг'}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Reopen if done */}
                {task.status === 'done' && (
                  <div className="space-y-2 pt-1">
                    <textarea
                      value={noteInputs[task.id] ?? ''}
                      onChange={(e) =>
                        setNoteInputs((prev) => ({ ...prev, [task.id]: e.target.value }))
                      }
                      placeholder="Причина переоткрытия…"
                      rows={2}
                      className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8"
                      disabled={!noteInputs[task.id]?.trim() || submitting[task.id]}
                      onClick={() => void handleSubmit(task)}
                    >
                      Переоткрыть
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Create new task button */}
        <Button
          onClick={() => void onCreateTask(item)}
          disabled={creating}
          variant={tasks.length > 0 ? 'outline' : 'default'}
          className="w-full"
        >
          {creating ? 'Создание…' : tasks.length > 0 ? '+ Ещё одна задача' : 'Создать задачу'}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export default function ScheduleTasksView() {
  const router = useRouter();
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [items, setItems] = useState<TelegramTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState(defaultSort);

  // tasks keyed by level_id → array (one crm_level can have many tasks)
  const [tasksByLevelId, setTasksByLevelId] = useState<Record<number, OperatorTask[]>>({});

  const [modalItem, setModalItem] = useState<TelegramTask | null>(null);
  const [creatingTaskFor, setCreatingTaskFor] = useState<number | null>(null);

  useEffect(() => {
    const loadItems = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await telegramTasksApi.list();
        setItems(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить обратную связь');
        }
      } finally {
        setLoading(false);
      }
    };
    loadItems();
  }, [router]);

  useEffect(() => {
    const loadTasks = async () => {
      try {
        const tasks = await operatorTasksApi.list();
        const byLevelId: Record<number, OperatorTask[]> = {};
        for (const t of tasks) {
          if (t.level_id != null) {
            byLevelId[t.level_id] = [...(byLevelId[t.level_id] ?? []), t];
          }
        }
        setTasksByLevelId(byLevelId);
      } catch {
        // non-critical
      }
    };
    loadTasks();
  }, []);

  const sortedItems = useMemo(() => {
    const copy = [...items];
    const compareNullable = (
      a: number | string | null | undefined,
      b: number | string | null | undefined,
    ) => {
      if (a == null && b == null) return 0;
      if (a == null) return 1;
      if (b == null) return -1;
      if (a < b) return -1;
      if (a > b) return 1;
      return 0;
    };
    copy.sort((a, b) => {
      let result = 0;
      switch (sort.key) {
        case 'received_at':
          result = new Date(a.received_at).getTime() - new Date(b.received_at).getTime();
          break;
        case 'rating':
          result = compareNullable(a.rating, b.rating);
          break;
        case 'message_text':
          result = compareNullable(a.message_text?.toLowerCase(), b.message_text?.toLowerCase());
          break;
        case 'tg_name':
          result = compareNullable(a.tg_name?.toLowerCase(), b.tg_name?.toLowerCase());
          break;
      }
      return sort.direction === 'asc' ? result : -result;
    });
    return copy;
  }, [items, sort.direction, sort.key]);

  const handleSort = (key: SortKey) => {
    setSort((prev) => {
      if (prev.key === key) return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      return { key, direction: defaultDirectionForKey(key) };
    });
  };

  const sortIndicator = (key: SortKey) => {
    if (sort.key !== key) return null;
    return sort.direction === 'asc' ? ' ▲' : ' ▼';
  };

  const handleAddHistory = async (
    taskId: number,
    note: string,
    status: OperatorTaskStatus | null,
  ) => {
    const entry = await operatorTasksApi.addHistory(taskId, { note, status, created_by: 1 });
    setTasksByLevelId((prev) => {
      const next = { ...prev };
      for (const levelId of Object.keys(next)) {
        const idx = next[Number(levelId)].findIndex((t) => t.id === taskId);
        if (idx !== -1) {
          const updatedTask = {
            ...next[Number(levelId)][idx],
            status: entry.status ?? next[Number(levelId)][idx].status,
            updated_at: entry.created_at,
            history: [...(next[Number(levelId)][idx].history ?? []), entry],
          };
          next[Number(levelId)] = [
            ...next[Number(levelId)].slice(0, idx),
            updatedTask,
            ...next[Number(levelId)].slice(idx + 1),
          ];
          break;
        }
      }
      return next;
    });
  };

  const handleCreateTask = async (item: TelegramTask) => {
    setCreatingTaskFor(item.id);
    try {
      const created = await operatorTasksApi.create({
        level_id: item.id,
        title: `Обратная связь от ${item.tg_name ? `@${item.tg_name}` : 'клиента'}`,
        description: item.message_text || null,
        created_by: 1,
      });
      setTasksByLevelId((prev) => ({
        ...prev,
        [item.id]: [...(prev[item.id] ?? []), created],
      }));
    } catch {
      // silent
    } finally {
      setCreatingTaskFor(null);
    }
  };

  const modalTasks = modalItem ? (tasksByLevelId[modalItem.id] ?? []) : [];

  // Summary badge for a crm_level row
  const getTaskBadge = (levelId: number) => {
    const tasks = tasksByLevelId[levelId] ?? [];
    if (tasks.length === 0) return null;
    const hasOpen = tasks.some((t) => t.status !== 'done');
    const allDone = tasks.every((t) => t.status === 'done');
    if (allDone) return { label: `✓ ${tasks.length}`, color: 'bg-green-100 text-green-700' };
    if (hasOpen) return { label: `● ${tasks.length}`, color: 'bg-red-100 text-red-700' };
    return null;
  };

  return (
    <div className="space-y-4">
      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div className="text-center py-8 text-slate-500">Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          Обратной связи пока нет.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-48">
                  <button type="button" className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left" onClick={() => handleSort('received_at')}>
                    Дата{sortIndicator('received_at')}
                  </button>
                </TableHead>
                <TableHead className="w-28">
                  <button type="button" className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left" onClick={() => handleSort('rating')}>
                    Оценка{sortIndicator('rating')}
                  </button>
                </TableHead>
                <TableHead>
                  <button type="button" className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left" onClick={() => handleSort('message_text')}>
                    Комментарий{sortIndicator('message_text')}
                  </button>
                </TableHead>
                <TableHead className="w-44">
                  <button type="button" className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left" onClick={() => handleSort('tg_name')}>
                    Клиент{sortIndicator('tg_name')}
                  </button>
                </TableHead>
                <TableHead className="w-28">Задачи</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedItems.map((item) => {
                const badge = getTaskBadge(item.id);
                return (
                  <TableRow key={item.id}>
                    <TableCell className="text-sm text-muted-foreground align-top">
                      {formatInTenantTimezone(item.received_at, tenantTimezone, {
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </TableCell>
                    <TableCell className="font-medium align-top">
                      {item.rating != null ? (
                        <span className={item.rating < 8 ? 'text-red-600 font-semibold' : ''}>
                          {item.rating}/10
                        </span>
                      ) : '—'}
                    </TableCell>
                    <TableCell className="align-top">
                      {item.message_text ? (
                        <span className="whitespace-pre-wrap">{item.message_text}</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">Пожеланий нет.</span>
                      )}
                    </TableCell>
                    <TableCell className="align-top">
                      {item.tg_name ? `@${item.tg_name}` : '—'}
                    </TableCell>
                    <TableCell className="align-top">
                      <Button
                        type="button"
                        size="sm"
                        variant={badge ? (badge.color.includes('green') ? 'outline' : 'secondary') : 'ghost'}
                        className="h-7 text-xs px-2 w-full"
                        onClick={() => setModalItem(item)}
                      >
                        {badge ? (
                          <span className={`rounded-full px-1.5 text-xs font-medium ${badge.color}`}>
                            {badge.label}
                          </span>
                        ) : '+ Задача'}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {modalItem && (
        <TaskModal
          item={modalItem}
          tasks={modalTasks}
          creating={creatingTaskFor === modalItem.id}
          onClose={() => setModalItem(null)}
          onCreateTask={handleCreateTask}
          onAddHistory={handleAddHistory}
        />
      )}
    </div>
  );
}
