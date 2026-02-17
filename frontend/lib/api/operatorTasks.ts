import { apiFetch } from '../api';
import type { OperatorTask, OperatorTaskHistory, OperatorTaskStatus } from '../types';

function buildQuery(params?: { level_id?: number; manual?: boolean }): string {
  if (!params) return '';
  const search = new URLSearchParams();
  if (params.level_id != null) search.set('level_id', String(params.level_id));
  if (params.manual != null) search.set('manual', params.manual ? '1' : '0');
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const operatorTasksApi = {
  list(params?: { level_id?: number; manual?: boolean }) {
    return apiFetch<OperatorTask[]>(`/telegram-tasks/crm-tasks/${buildQuery(params)}`);
  },

  get(id: number) {
    return apiFetch<OperatorTask>(`/telegram-tasks/crm-tasks/${id}/`);
  },

  create(data: {
    level_id?: number | null;
    title: string;
    description?: string | null;
    priority?: 1 | 2 | 3;
  }) {
    return apiFetch<OperatorTask>('/telegram-tasks/crm-tasks/', {
      method: 'POST',
      body: {
        level_id: data.level_id ?? null,
        title: data.title,
        description: data.description ?? null,
        priority: data.priority ?? 2,
      },
    });
  },

  addHistory(
    taskId: number,
    data: {
      note: string;
      status?: OperatorTaskStatus | null;
      priority?: 1 | 2 | 3;
    },
  ) {
    return apiFetch<OperatorTaskHistory>(`/telegram-tasks/crm-tasks/${taskId}/history/`, {
      method: 'POST',
      body: {
        note: data.note,
        status: data.status ?? null,
        priority: data.priority,
      },
    });
  },
};
