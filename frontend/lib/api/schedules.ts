import { apiFetch } from '../api';
import type { Schedule, TaskResponse } from '../types';

export const schedulesApi = {
  /**
   * List all schedules for the current client
   */
  list: async (): Promise<Schedule[]> => {
    return apiFetch<Schedule[]>('/schedules/');
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
  create: async (data: Partial<Schedule>): Promise<Schedule> => {
    return apiFetch<Schedule>('/schedules-manage/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing schedule
   */
  update: async (id: number, data: Partial<Schedule>): Promise<Schedule> => {
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
