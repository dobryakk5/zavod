import { apiFetch } from '../api';
import type { Topic, TopicDetail, TaskResponse } from '../types';

export const topicsApi = {
  /**
   * List all topics for the current client
   */
  list: async (): Promise<Topic[]> => {
    return apiFetch<Topic[]>('/topics/');
  },

  /**
   * Get detailed information about a topic
   */
  get: async (id: number): Promise<TopicDetail> => {
    return apiFetch<TopicDetail>(`/topics/${id}/`);
  },

  /**
   * Create a new topic
   */
  create: async (data: Partial<Topic>): Promise<Topic> => {
    return apiFetch<Topic>('/topics/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing topic
   */
  update: async (id: number, data: Partial<Topic>): Promise<Topic> => {
    return apiFetch<Topic>(`/topics/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a topic
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/topics/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Discover new content (trends) for this topic from enabled sources
   */
  discoverContent: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/topics/${id}/discover_content/`, {
      method: 'POST',
    });
  },

  /**
   * Generate posts from all unused trends for this topic
   */
  generatePosts: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/topics/${id}/generate_posts/`, {
      method: 'POST',
    });
  },

  /**
   * Generate SEO keywords for this topic
   */
  generateSEO: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/topics/${id}/generate_seo/`, {
      method: 'POST',
    });
  },
};
