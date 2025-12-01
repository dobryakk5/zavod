import { apiFetch } from '../api';
import type { TrendItem, TrendItemDetail, TaskResponse, GenerateStoryRequest } from '../types';

export const trendsApi = {
  /**
   * List all trends for the current client
   * @param filters - Optional filters: topic (number), unused (boolean)
   */
  list: async (filters?: { topic?: number; unused?: boolean }): Promise<TrendItem[]> => {
    const params = new URLSearchParams();
    if (filters?.topic) params.set('topic', filters.topic.toString());
    if (filters?.unused) params.set('unused', 'true');
    const query = params.toString();
    return apiFetch<TrendItem[]>(`/trends/${query ? `?${query}` : ''}`);
  },

  /**
   * Get detailed information about a trend
   */
  get: async (id: number): Promise<TrendItemDetail> => {
    return apiFetch<TrendItemDetail>(`/trends/${id}/`);
  },

  /**
   * Delete a trend
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/trends/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Generate a single post from this trend
   */
  generatePost: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/trends/${id}/generate_post/`, {
      method: 'POST',
    });
  },

  /**
   * Generate a story (mini-series) from this trend
   * @param episodeCount - Number of episodes (default: 3)
   */
  generateStory: async (
    id: number,
    data: GenerateStoryRequest = {}
  ): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/trends/${id}/generate_story/`, {
      method: 'POST',
      body: data,
    });
  },
};
