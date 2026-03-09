'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { ApiError, apiFetch } from '@/lib/api';
import type { OperatorTaskStatus } from '@/lib/types';

type PublicContactTask = {
  id: number;
  contact_id: number | null;
  title: string;
  description: string | null;
  status: OperatorTaskStatus;
  priority: 1 | 2 | 3;
  due_at: string | null;
  created_at: string;
  updated_at: string;
};

type PublicClientTasksResponse = {
  contact_id?: number;
  items?: PublicContactTask[];
};

const TASK_STAGE_ORDER: OperatorTaskStatus[] = ['open', 'in_progress', 'done', 'checked'];

const TASK_STAGE_LABELS: Record<OperatorTaskStatus, string> = {
  open: 'Создано',
  in_progress: 'Выполняется',
  done: 'Выполнено',
  checked: 'Проверено',
};

function normalizeTaskStatus(raw: unknown): OperatorTaskStatus {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'open' || value === 'in_progress' || value === 'done' || value === 'checked') {
    return value;
  }
  return 'open';
}

function normalizeTask(task: PublicContactTask): PublicContactTask {
  return {
    ...task,
    status: normalizeTaskStatus(task.status),
  };
}

type PublicTasksPageClientProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function PublicTasksPage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicTasksPageClientProps = {}) {
  const { client_id: rawClientId } = useParams<{ client_id?: string }>();
  const pageClientId = resolvedClientId ?? Number(rawClientId);
  const publicRootPath = useCustomDomainPaths ? '/' : `/c/${pageClientId}`;

  const [tasks, setTasks] = useState<PublicContactTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadTasks = async () => {
      if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
        setError('Некорректный идентификатор клиента.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<PublicClientTasksResponse>(`/public/client-page/${pageClientId}/tasks/`);
        const items = Array.isArray(data?.items) ? data.items.map(normalizeTask) : [];
        setTasks(items);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setError('Войдите как контакт через Telegram или VK, чтобы увидеть свои задания.');
        } else if (err instanceof ApiError && err.status === 404) {
          setError('Страница заданий не найдена.');
        } else {
          setError('Не удалось загрузить задания.');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadTasks();
  }, [pageClientId]);

  const columns = useMemo(() => {
    const grouped = TASK_STAGE_ORDER.reduce<Record<OperatorTaskStatus, PublicContactTask[]>>((acc, stage) => {
      acc[stage] = [];
      return acc;
    }, {} as Record<OperatorTaskStatus, PublicContactTask[]>);

    tasks.forEach((task) => {
      grouped[task.status].push(task);
    });

    return grouped;
  }, [tasks]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">Загрузка заданий...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>
        <Link href={publicRootPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          На страницу клиента
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Задания</h1>
        <p className="text-sm text-muted-foreground">Ваши текущие задания по стадиям.</p>
      </div>

      {tasks.length === 0 ? (
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">У вас пока нет заданий.</div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-4">
          {TASK_STAGE_ORDER.map((stage) => (
            <div key={stage} className="rounded-xl border bg-card/70 p-3 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold">{TASK_STAGE_LABELS[stage]}</div>
                <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
                  {columns[stage].length}
                </span>
              </div>
              <div className="min-h-[120px] space-y-2">
                {columns[stage].length === 0 ? (
                  <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">Пусто</div>
                ) : (
                  columns[stage].map((task) => (
                    <div key={task.id} className="rounded-lg border bg-background p-3">
                      <div className="text-sm font-medium">{task.title}</div>
                      {task.description ? (
                        <p className="mt-1 text-xs text-muted-foreground">{task.description}</p>
                      ) : null}
                      {task.due_at ? (
                        <p
                          className={`mt-2 text-xs ${
                            (task.status === 'done' || task.status === 'checked')
                              ? 'text-muted-foreground'
                              : new Date(task.due_at).getTime() < Date.now()
                                ? 'text-red-500'
                                : 'text-muted-foreground'
                          }`}
                        >
                          Дедлайн: {new Date(task.due_at).toLocaleString('ru-RU', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </p>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
