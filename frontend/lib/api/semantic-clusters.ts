import { apiFetch } from '../api';
import type { SemanticCluster, SemanticPhrase } from '../types';

export const semanticClustersApi = {
  /**
   * List semantic clusters for a semantic group
   */
  list: async (semanticGroupId: number): Promise<SemanticCluster[]> => {
    return apiFetch<SemanticCluster[]>(`/semantic-clusters/?semantic_group=${semanticGroupId}`);
  },

  /**
   * Retrieve a semantic cluster
   */
  get: async (id: number): Promise<SemanticCluster> => {
    return apiFetch<SemanticCluster>(`/semantic-clusters/${id}/`);
  },

  /**
   * Update a semantic cluster
   */
  update: async (id: number, payload: Partial<SemanticCluster>): Promise<SemanticCluster> => {
    return apiFetch<SemanticCluster>(`/semantic-clusters/${id}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  /**
   * List phrases for a semantic cluster
   */
  listPhrases: async (id: number): Promise<SemanticPhrase[]> => {
    return apiFetch<SemanticPhrase[]>(`/semantic-clusters/${id}/phrases/`);
  },

  /**
   * Delete all phrases for a semantic cluster
   */
  deletePhrases: async (
    id: number
  ): Promise<{ success: boolean; deleted?: number; message?: string }> => {
    return apiFetch<{ success: boolean; deleted?: number; message?: string }>(
      `/semantic-clusters/${id}/phrases/`,
      {
        method: 'DELETE',
      }
    );
  },

  /**
   * Add phrases to a semantic cluster
   */
  addPhrases: async (
    id: number,
    payload: { phrases: string[] }
  ): Promise<{
    success: boolean;
    added?: number;
    message?: string;
    phrases?: SemanticPhrase[];
    wordstat_error?: string;
  }> => {
    return apiFetch<{
      success: boolean;
      added?: number;
      message?: string;
      phrases?: SemanticPhrase[];
      wordstat_error?: string;
    }>(`/semantic-clusters/${id}/phrases/`, {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Remove a phrase from a semantic cluster
   */
  removePhrase: async (id: number, phraseId: number): Promise<{ success: boolean; message?: string }> => {
    return apiFetch<{ success: boolean; message?: string }>(
      `/semantic-clusters/${id}/phrases/${phraseId}/`,
      {
        method: 'DELETE',
      }
    );
  },

  /**
   * Generate phrases for a semantic cluster
   */
  generatePhrases: async (
    id: number
  ): Promise<{ success: boolean; message?: string; phrases_count?: number; phrases?: SemanticPhrase[] }> => {
    return apiFetch<{ success: boolean; message?: string; phrases_count?: number; phrases?: SemanticPhrase[] }>(
      `/semantic-clusters/${id}/generate-phrases/`,
      {
        method: 'POST',
      }
    );
  },

  /**
   * Generate LSI context phrases for a semantic cluster
   */
  generateContext: async (
    id: number
  ): Promise<{ success: boolean; message?: string; phrases_count?: number; phrases?: SemanticPhrase[] }> => {
    return apiFetch<{ success: boolean; message?: string; phrases_count?: number; phrases?: SemanticPhrase[] }>(
      `/semantic-clusters/${id}/generate-context/`,
      {
        method: 'POST',
      }
    );
  },
};
