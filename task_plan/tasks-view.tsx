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

// ---------------------------------------------------------------------------
// Task Modal
// ---------------------------------------------------------------------------

type TaskModalProps = {
  item: TelegramTask;
  task: OperatorTask | null;
  creating: boolean;
  onClose: () => void;
  onCreateTask: (item: TelegramTask) => Promise<void>;
  onSaveResolution: (task: OperatorTask, text: string, status?: OperatorTaskStatus) => Promise<void>;
  resolutionDraft: string;
  onDraftChange: (text: string) => void;
};

function TaskModal({
  item,
  task,
  creating,
  onClose,
  onCreateTask,
  onSaveResolution,
  resolutionDraft,
  onDraftChange,
}: TaskModalProps) {
  const isDone = task?.status === 'done';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl p-6 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-semibold text-base">Задача по обратной связи</div>
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

        {item.message_text && (
          <div className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-muted-foreground whitespace-pre-wrap">
            {item.message_text}
          </div>
        )}

        {!task && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Задача ещё не создана.</p>
            <Button
              onClick={() => void onCreateTask(item)}
              disabled={creating}
              className="w-full"
            >
              {creating ? 'Создание…' : 'Создать задачу'}
            </Button>
          </div>
        )}

        {task && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  isDone ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}
              >
                {isDone ? 'Выполнена' : 'Открыта'}
              </span>
              <span className="text-xs text-muted-foreground">
                Создана {new Date(task.created_at).toLocaleDateString('ru-RU', {
                  day: 'numeric', month: 'long', year: 'numeric',
                })}
              </span>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Решение</label>
              <textarea
                value={resolutionDraft}
                onChange={(e) => onDraftChange(e.target.value)}
                onBlur={() => void onSaveResolution(task, resolutionDraft)}
                placeholder="Опишите что сделано…"
                rows={3}
                disabled={isDone}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
              />
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                variant={isDone ? 'outline' : 'default'}
                className="flex-1"
                onClick={() => void onSaveResolution(task, resolutionDraft, isDone ? 'open' : 'done')}
              >
                {isDone ? 'Переоткрыть' : 'Отметить выполненным'}
              </Button>
              <Button type="button" variant="outline" onClick={onClose}>
                Закрыть
              </Button>
            </div>
          </div>
        )}
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

  const [tasksByTgId, setTasksByTgId] = useState<Record<number, OperatorTask>>({});
  const [resolutionDrafts, setResolutionDrafts] = useState<Record<number, string>>({});
  const savingRef = useRef<Record<number, boolean>>({});

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
          setError('Не удалось загрузить задачи');
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
        const byTgId: Record<number, OperatorTask> = {};
        const drafts: Record<number, string> = {};
        for (const t of tasks) {
          if (t.telegram_task_id != null) {
            byTgId[t.telegram_task_id] = t;
            drafts[t.id] = t.resolution_text ?? '';
          }
        }
        setTasksByTgId(byTgId);
        setResolutionDrafts(drafts);
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

  const saveResolution = async (
    task: OperatorTask,
    text: string,
    status?: OperatorTaskStatus,
  ) => {
    if (savingRef.current[task.id]) return;
    savingRef.current[task.id] = true;
    try {
      const updated = await operatorTasksApi.update(task.id, {
        resolution_text: text || null,
        status: status ?? task.status,
      });
      setTasksByTgId((prev) => {
        if (updated.telegram_task_id == null) return prev;
        return { ...prev, [updated.telegram_task_id]: updated };
      });
      setResolutionDrafts((prev) => ({ ...prev, [updated.id]: updated.resolution_text ?? '' }));
    } catch {
      // silent
    } finally {
      savingRef.current[task.id] = false;
    }
  };

  const handleCreateTask = async (item: TelegramTask) => {
    setCreatingTaskFor(item.id);
    try {
      const created = await operatorTasksApi.create({
        type: item.rating != null && item.rating < 8 ? 2 : 1,
        title: `Обратная связь от ${item.tg_name ? `@${item.tg_name}` : 'клиента'}`,
        description: item.message_text || null,
        telegram_task_id: item.id,
        contact_name: item.tg_name ? `@${item.tg_name}` : null,
        rating: item.rating,
      });
      setTasksByTgId((prev) => ({ ...prev, [item.id]: created }));
      setResolutionDrafts((prev) => ({ ...prev, [created.id]: '' }));
    } catch {
      // silent
    } finally {
      setCreatingTaskFor(null);
    }
  };

  const modalTask = modalItem ? (tasksByTgId[modalItem.id] ?? null) : null;
  const modalDraftTaskId = modalTask?.id;
  const modalDraft = modalDraftTaskId != null ? (resolutionDrafts[modalDraftTaskId] ?? '') : '';

  return (
    <div className="space-y-4">
      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div className="text-center py-8 text-slate-500">Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          Сообщений из Telegram пока нет.
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
                <TableHead className="w-64">Решение</TableHead>
                <TableHead className="w-28">Задача</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedItems.map((item) => {
                const task = tasksByTgId[item.id] ?? null;
                const taskId = task?.id;
                const draft = taskId != null ? (resolutionDrafts[taskId] ?? '') : '';
                const isDone = task?.status === 'done';

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

                    {/* Resolution — all rows */}
                    <TableCell className="align-top">
                      {task ? (
                        <div className="space-y-1.5">
                          <textarea
                            value={draft}
                            onChange={(e) => {
                              if (taskId == null) return;
                              setResolutionDrafts((prev) => ({ ...prev, [taskId]: e.target.value }));
                            }}
                            onBlur={() => { if (task) void saveResolution(task, draft); }}
                            placeholder="Опишите что сделано…"
                            rows={2}
                            disabled={isDone}
                            className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs shadow-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
                          />
                          <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${isDone ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {isDone ? 'Выполнена' : 'Открыта'}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>

                    {/* Task button — all rows */}
                    <TableCell className="align-top">
                      <Button
                        type="button"
                        size="sm"
                        variant={task ? (isDone ? 'outline' : 'secondary') : 'ghost'}
                        className="h-7 text-xs px-2 w-full"
                        onClick={() => setModalItem(item)}
                      >
                        {task ? (isDone ? '✓ Задача' : '● Задача') : '+ Задача'}
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
          task={modalTask}
          creating={creatingTaskFor === modalItem.id}
          onClose={() => setModalItem(null)}
          onCreateTask={handleCreateTask}
          onSaveResolution={saveResolution}
          resolutionDraft={modalDraft}
          onDraftChange={(text) => {
            if (modalDraftTaskId == null) return;
            setResolutionDrafts((prev) => ({ ...prev, [modalDraftTaskId]: text }));
          }}
        />
      )}
    </div>
  );
}
