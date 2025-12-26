'use client';

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { ApiError, apiFetch } from '@/lib/api';
import { ContentTemplate } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatTemplateDisplayName } from '@/lib/utils';
import { emitPostGenerationStart } from '@/lib/post-generation-events';

interface PlanWeeklyResponse {
  success: boolean;
  message?: string;
  task_id?: string;
}

interface GenerationStatusResponse {
  success?: boolean;
  status?: string;
  task_id: string;
  result?: {
    created_posts?: number[] | number;
    requested?: number;
    [key: string]: unknown;
  };
  error?: string;
}

type GenerationStatusValue = 'pending' | 'started' | 'retry' | 'success' | 'failure' | 'revoked' | 'unknown';

interface GenerationStatus {
  taskId: string;
  status: GenerationStatusValue;
  expectedCount?: number;
  createdCount?: number;
  error?: string;
}

const normalizeStatus = (status?: string | null): GenerationStatusValue => {
  const value = (status || '').toLowerCase();
  if (value === 'pending' || value === 'started' || value === 'retry' || value === 'success' || value === 'failure' || value === 'revoked') {
    return value;
  }
  return 'unknown';
};

const isTerminalStatus = (status: GenerationStatusValue) => status === 'success' || status === 'failure' || status === 'revoked';

export function WeeklyPlanTable() {
  const [templates, setTemplates] = useState<ContentTemplate[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<number, string>>({});
  const [pending, setPending] = useState<Record<number, boolean>>({});
  const [generationStatuses, setGenerationStatuses] = useState<Record<number, GenerationStatus>>({});
  const generationStatusesRef = useRef<Record<number, GenerationStatus>>({});

  useEffect(() => {
    const loadTemplates = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<ContentTemplate[]>('/templates/');
        setTemplates(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          return;
        }
        setError('Не удалось загрузить шаблоны');
      } finally {
        setLoading(false);
      }
    };

    loadTemplates();
  }, []);

  useEffect(() => {
    generationStatusesRef.current = generationStatuses;
  }, [generationStatuses]);

  const activeTaskKey = Object.values(generationStatuses)
    .filter((status) => status && !isTerminalStatus(status.status))
    .map((status) => status.taskId)
    .join('|');

  useEffect(() => {
    if (!activeTaskKey) {
      return;
    }

    const pollStatuses = async () => {
      const currentStatuses = generationStatusesRef.current;
      const activeEntries = Object.entries(currentStatuses).filter(
        ([, status]) => status && !isTerminalStatus(status.status)
      );

      for (const [templateId, status] of activeEntries) {
        const previousStatus = status.status;
        try {
          const response = await apiFetch<GenerationStatusResponse>(`/posts/generation-status/?task_id=${encodeURIComponent(status.taskId)}`);
          const normalized = normalizeStatus(response.status);
          const createdCount = Array.isArray(response.result?.created_posts)
            ? response.result.created_posts.length
            : typeof response.result?.created_posts === 'number'
              ? response.result.created_posts
              : undefined;

          setGenerationStatuses((prev) => ({
            ...prev,
            [Number(templateId)]: {
              ...prev[Number(templateId)],
              taskId: status.taskId,
              status: normalized,
              createdCount: createdCount ?? prev[Number(templateId)]?.createdCount,
              error: response.error,
            },
          }));

          if (previousStatus !== normalized) {
            if (normalized === 'success') {
              toast.success('Генерация постов завершена');
            } else if (normalized === 'failure' || normalized === 'revoked') {
              toast.error(response.error || 'Генерация постов завершилась с ошибкой');
            }
          }
        } catch (pollError) {
          console.warn('Не удалось обновить статус генерации постов', pollError);
        }
      }
    };

    pollStatuses();
    const intervalId = setInterval(pollStatuses, 5000);

    return () => {
      clearInterval(intervalId);
    };
  }, [activeTaskKey]);

  const handleCountChange = (templateId: number, value: string) => {
    setCounts((prev) => ({ ...prev, [templateId]: value }));
  };

  const getStatusText = (status?: GenerationStatus) => {
    if (!status) {
      return null;
    }
    if (!isTerminalStatus(status.status)) {
      const countLabel = status.expectedCount ? `${status.expectedCount} постов` : 'постов';
      return `Генерация ${countLabel}...`;
    }
    if (status.status === 'success') {
      if (status.createdCount) {
        return `Готово: создано ${status.createdCount}`;
      }
      return 'Генерация завершена';
    }
    if (status.status === 'failure' || status.status === 'revoked') {
      return status.error || 'Генерация завершилась с ошибкой';
    }
    return null;
  };

  const handlePlan = async (template: ContentTemplate) => {
    const rawValue = counts[template.id];
    const parsed = Number(rawValue);

    if (!rawValue || Number.isNaN(parsed) || parsed <= 0) {
      toast.error('Укажите количество постов от 1 до 21');
      return;
    }

    setPending((prev) => ({ ...prev, [template.id]: true }));

    try {
      const response = await apiFetch<PlanWeeklyResponse>('/posts/plan-weekly/', {
        method: 'POST',
        body: {
          template_id: template.id,
          posts_per_week: parsed
        }
      });

      toast.success(response.message || 'Генерация запущена');
      const templateLabel = formatTemplateDisplayName(template.name) || template.name;
      emitPostGenerationStart({
        count: parsed,
        templateName: templateLabel
      });

      if (response.task_id) {
        setGenerationStatuses((prev) => ({
          ...prev,
          [template.id]: {
            taskId: response.task_id as string,
            status: 'pending',
            expectedCount: parsed,
            createdCount: prev[template.id]?.createdCount,
          },
        }));
      }
    } catch (err) {
      if (err instanceof ApiError) {
        let message = 'Не удалось запустить генерацию';
        if (err.body) {
          try {
            const payload = JSON.parse(err.body);
            if (payload?.error) {
              message = payload.error;
            }
          } catch {}
        }
        toast.error(message);
      } else {
        toast.error('Неизвестная ошибка при запуске генерации');
      }
    } finally {
      setPending((prev) => ({ ...prev, [template.id]: false }));
    }
  };

  return (
    <div className="space-y-3 rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <p className="font-medium">Планирование недели</p>
        <p className="text-sm text-muted-foreground">Выберите шаблон, укажите количество постов и запустите автогенерацию на следующую неделю.</p>
      </div>

      {error && <div className="px-4 text-sm text-destructive">{error}</div>}

      {loading ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">Загрузка шаблонов...</div>
      ) : templates.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground">Сначала создайте хотя бы один шаблон.</div>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Шаблон</TableHead>
                <TableHead className="w-48">Постов в неделю</TableHead>
                <TableHead className="w-40 text-right">Запуск</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {templates.map((template) => {
                const value = counts[template.id] ?? '';
                const isPending = pending[template.id] ?? false;
                const generationStatus = generationStatuses[template.id];
                const isRunningGeneration = generationStatus ? !isTerminalStatus(generationStatus.status) : false;
                const disabled = isPending || !value || isRunningGeneration;
                const statusText = getStatusText(generationStatus);
                const buttonLabel = isPending ? 'Создание...' : isRunningGeneration ? 'Генерация...' : 'Создать';

                return (
                  <TableRow key={template.id}>
                    <TableCell>
                      <span className="font-medium">{formatTemplateDisplayName(template.name)}</span>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={1}
                        max={21}
                        value={value}
                        onChange={(event) => handleCountChange(template.id, event.target.value)}
                        placeholder="Например, 5"
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-col items-end gap-2">
                        <Button size="sm" disabled={disabled} onClick={() => handlePlan(template)}>
                          {buttonLabel}
                        </Button>
                        {statusText && (
                          <div className="flex items-center gap-2 text-sm">
                            {isRunningGeneration ? (
                              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            ) : generationStatus?.status === 'success' ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                            ) : (
                              <AlertCircle className="h-4 w-4 text-destructive" />
                            )}
                            <span
                              className={
                                generationStatus?.status === 'success'
                                  ? 'text-emerald-700'
                                  : generationStatus?.status === 'failure' || generationStatus?.status === 'revoked'
                                    ? 'text-destructive'
                                    : 'text-muted-foreground'
                              }
                            >
                              {statusText}
                            </span>
                          </div>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
