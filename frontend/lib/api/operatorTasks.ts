import { apiFetch } from '../api';
import type { OperatorTask, OperatorTaskHistory, OperatorTaskStatus } from '../types';

function buildQuery(params?: { level_id?: number; manual?: boolean; contact_id?: number }): string {
  if (!params) return '';
  const search = new URLSearchParams();
  if (params.level_id != null) search.set('level_id', String(params.level_id));
  if (params.manual != null) search.set('manual', params.manual ? '1' : '0');
  if (params.contact_id != null) search.set('contact_id', String(params.contact_id));
  const query = search.toString();
  return query ? `?${query}` : '';
}

export const operatorTasksApi = {
  list(params?: { level_id?: number; manual?: boolean; contact_id?: number }) {
    return apiFetch<OperatorTask[]>(`/telegram-tasks/crm-tasks/${buildQuery(params)}`);
  },

  get(id: number) {
    return apiFetch<OperatorTask>(`/telegram-tasks/crm-tasks/${id}/`);
  },

  create(data: {
    level_id?: number | null;
    contact_id?: number | null;
    title: string;
    description?: string | null;
    priority?: 1 | 2 | 3;
    due_at?: string | null;
  }) {
    return apiFetch<OperatorTask>('/telegram-tasks/crm-tasks/', {
      method: 'POST',
      body: {
        level_id: data.level_id ?? null,
        contact_id: data.contact_id ?? null,
        title: data.title,
        description: data.description ?? null,
        priority: data.priority ?? 2,
        due_at: data.due_at ?? null,
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
