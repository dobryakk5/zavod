import { apiFetch } from '../api';
import type { WordstatQuery, WordstatResultType } from '../types';

type WordstatRequestPayload = {
  phrase: string;
  include_parent?: boolean;
  regions?: number[];
  devices?: string[];
};

export const wordstatApi = {
  list: async (): Promise<WordstatQuery[]> => {
    return apiFetch<WordstatQuery[]>('/wordstat/');
  },

  get: async (id: number | string): Promise<WordstatQuery> => {
    return apiFetch<WordstatQuery>(`/wordstat/${id}/`);
  },

  fetch: async (payload: WordstatRequestPayload): Promise<WordstatQuery> => {
    return apiFetch<WordstatQuery>('/wordstat/', {
      method: 'POST',
      body: payload,
    });
  },

  updateResultType: async (resultId: number, result_type: WordstatResultType): Promise<void> => {
    await apiFetch<void>(`/wordstat-results/${resultId}/`, {
      method: 'PATCH',
      body: { result_type },
    });
  },
};
