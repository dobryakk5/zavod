import { apiFetch } from '../api';
import type { ContentTemplate } from '../types';

export const templatesApi = {
  /**
   * List all content templates for the current client
   */
  list: async (): Promise<ContentTemplate[]> => {
    return apiFetch<ContentTemplate[]>('/templates/');
  },

  /**
   * Get detailed information about a template
   */
  get: async (id: number): Promise<ContentTemplate> => {
    return apiFetch<ContentTemplate>(`/templates/${id}/`);
  },

  /**
   * Create a new content template
   */
  create: async (data: Partial<ContentTemplate>): Promise<ContentTemplate> => {
    return apiFetch<ContentTemplate>('/templates/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing template
   * Note: Basic fields (type, tone, length, language) are read-only
   */
  update: async (id: number, data: Partial<ContentTemplate>): Promise<ContentTemplate> => {
    return apiFetch<ContentTemplate>(`/templates/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a template
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/templates/${id}/`, {
      method: 'DELETE',
    });
  },
};
