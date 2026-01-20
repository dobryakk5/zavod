import { apiFetch } from '../api';
import type { WordstatCluster, WordstatQuery, WordstatResultType } from '../types';

type WordstatRequestPayload = {
  phrase?: string;
  phrases?: string[];
  include_parent?: boolean;
  regions?: number[];
  devices?: string[];
  group_name?: string;
};

type WordstatSeedGroupsResponse = {
  success: boolean;
  queries: WordstatQuery[];
  seed_groups?: Record<string, string[]>;
};

export const wordstatApi = {
  list: async (): Promise<WordstatQuery[]> => {
    return apiFetch<WordstatQuery[]>('/wordstat/');
  },

  listClusters: async (): Promise<WordstatCluster[]> => {
    return apiFetch<WordstatCluster[]>('/wordstat-clusters/');
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

  generateSeedGroups: async (): Promise<WordstatSeedGroupsResponse> => {
    return apiFetch<WordstatSeedGroupsResponse>('/wordstat/seed-from-settings/', {
      method: 'POST',
    });
  },

  append: async (id: number, payload: { phrases: string[] }): Promise<WordstatQuery> => {
    return apiFetch<WordstatQuery>(`/wordstat/${id}/append/`, {
      method: 'POST',
      body: payload,
    });
  },

  updateGroupName: async (id: number, group_name: string): Promise<WordstatQuery> => {
    return apiFetch<WordstatQuery>(`/wordstat/${id}/`, {
      method: 'PATCH',
      body: { group_name },
    });
  },

  remove: async (id: number): Promise<void> => {
    await apiFetch<void>(`/wordstat/${id}/`, {
      method: 'DELETE',
    });
  },

  updateResultType: async (resultId: number, result_type: WordstatResultType): Promise<void> => {
    await apiFetch<void>(`/wordstat-results/${resultId}/`, {
      method: 'PATCH',
      body: { result_type },
    });
  },

  updateCluster: async (resultId: number, cluster: number | null): Promise<void> => {
    await apiFetch<void>(`/wordstat-results/${resultId}/`, {
      method: 'PATCH',
      body: { cluster },
    });
  },

  clusterFavorites: async (): Promise<{ success: boolean; clusters: WordstatCluster[] }> => {
    return apiFetch<{ success: boolean; clusters: WordstatCluster[] }>('/wordstat-results/cluster-favorites/', {
      method: 'POST',
    });
  },
};
