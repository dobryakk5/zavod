import { apiFetch } from '../api';
import type { Story, StoryDetail, TaskResponse } from '../types';

export const storiesApi = {
  /**
   * List all stories for the current client
   */
  list: async (): Promise<Story[]> => {
    return apiFetch<Story[]>('/stories/');
  },

  /**
   * Get detailed information about a story (with episodes)
   */
  get: async (id: number): Promise<StoryDetail> => {
    return apiFetch<StoryDetail>(`/stories/${id}/`);
  },

  /**
   * Create a new story
   */
  create: async (data: Partial<StoryDetail>): Promise<StoryDetail> => {
    return apiFetch<StoryDetail>('/stories/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing story
   */
  update: async (id: number, data: Partial<StoryDetail>): Promise<StoryDetail> => {
    return apiFetch<StoryDetail>(`/stories/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a story
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/stories/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Generate posts from story episodes
   */
  generatePosts: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/stories/${id}/generate_posts/`, {
      method: 'POST',
    });
  },
};
