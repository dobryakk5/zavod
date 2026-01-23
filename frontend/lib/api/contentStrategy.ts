import { apiFetch } from '../api';

export interface WeeklyContentStrategy {
  id: number;
  week_start: string;
  comment: string;
  wordstat_cluster_ids: number[];
  created_at: string;
  updated_at: string;
}

export type WeeklyContentStrategyPayload = {
  week_start: string;
  comment?: string;
  wordstat_cluster_ids?: number[];
};

export const contentStrategyApi = {
  list: async (): Promise<WeeklyContentStrategy[]> => {
    return apiFetch<WeeklyContentStrategy[]>('/content-strategy/');
  },
  create: async (payload: WeeklyContentStrategyPayload): Promise<WeeklyContentStrategy> => {
    return apiFetch<WeeklyContentStrategy>('/content-strategy/', {
      method: 'POST',
      body: payload,
    });
  },
  update: async (id: number, payload: WeeklyContentStrategyPayload): Promise<WeeklyContentStrategy> => {
    return apiFetch<WeeklyContentStrategy>(`/content-strategy/${id}/`, {
      method: 'PUT',
      body: payload,
    });
  },
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/content-strategy/${id}/`, {
      method: 'DELETE',
    });
  },
};
