import { apiFetch } from '../api';
import type { SemanticGroup } from '../types';

export const semanticGroupsApi = {
  /**
   * List semantic groups for the active client
   */
  list: async (): Promise<SemanticGroup[]> => {
    return apiFetch<SemanticGroup[]>('/semantic-groups/');
  },

  /**
   * Retrieve a semantic group
   */
  get: async (id: number): Promise<SemanticGroup> => {
    return apiFetch<SemanticGroup>(`/semantic-groups/${id}/`);
  },

  /**
   * Create a semantic group
   */
  create: async (payload: Partial<SemanticGroup>): Promise<SemanticGroup> => {
    return apiFetch<SemanticGroup>('/semantic-groups/', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Update a semantic group
   */
  update: async (id: number, payload: Partial<SemanticGroup>): Promise<SemanticGroup> => {
    return apiFetch<SemanticGroup>(`/semantic-groups/${id}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  /**
   * Delete a semantic group
   */
  remove: async (id: number): Promise<void> => {
    return apiFetch<void>(`/semantic-groups/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Generate SEO clusters for a semantic group
   */
  generateClusters: async (id: number): Promise<{ success: boolean; message?: string; clusters_count?: number }> => {
    return apiFetch<{ success: boolean; message?: string; clusters_count?: number }>(
      `/semantic-groups/${id}/generate-clusters/`,
      {
        method: 'POST',
      }
    );
  },
};
