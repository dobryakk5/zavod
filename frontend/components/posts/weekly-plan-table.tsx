'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { ApiError, apiFetch } from '@/lib/api';
import { ContentTemplate } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatTemplateDisplayName } from '@/lib/utils';

interface PlanWeeklyResponse {
  success: boolean;
  message?: string;
  task_id?: string;
}

export function WeeklyPlanTable() {
  const [templates, setTemplates] = useState<ContentTemplate[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<number, string>>({});
  const [pending, setPending] = useState<Record<number, boolean>>({});

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

  const handleCountChange = (templateId: number, value: string) => {
    setCounts((prev) => ({ ...prev, [templateId]: value }));
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
                const disabled = isPending || !value;

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
                      <Button size="sm" disabled={disabled} onClick={() => handlePlan(template)}>
                        {isPending ? 'Создание...' : 'Создать'}
                      </Button>
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
