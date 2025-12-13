import { apiFetch } from '../api';
import type { Schedule, TaskResponse } from '../types';

type ScheduleFilters = {
  post?: number;
};

type SchedulePayload = {
  post: number;
  social_account: number;
  scheduled_at: string;
};

export const schedulesApi = {
  /**
   * List schedules for the current client (optionally filtered by post)
   */
  list: async (filters?: ScheduleFilters): Promise<Schedule[]> => {
    const params = new URLSearchParams();
    if (filters?.post) {
      params.set('post', String(filters.post));
    }
    const query = params.toString();
    return apiFetch<Schedule[]>(`/schedules/${query ? `?${query}` : ''}`);
  },

  /**
   * Get detailed information about a schedule
   */
  get: async (id: number): Promise<Schedule> => {
    return apiFetch<Schedule>(`/schedules-manage/${id}/`);
  },

  /**
   * Create a new schedule
   */
  create: async (data: SchedulePayload): Promise<Schedule> => {
    return apiFetch<Schedule>('/schedules-manage/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing schedule
   */
  update: async (id: number, data: Partial<SchedulePayload>): Promise<Schedule> => {
    return apiFetch<Schedule>(`/schedules-manage/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a schedule
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/schedules-manage/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Publish this schedule immediately
   */
  publishNow: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/schedules-manage/${id}/publish_now/`, {
      method: 'POST',
    });
  },
};
