import { apiFetch } from '../api';
import type { SEOKeywordSet, TaskResponse } from '../types';

export const seoApi = {
  /**
   * List SEO keyword sets for the active client
   */
  list: async (): Promise<SEOKeywordSet[]> => {
    return apiFetch<SEOKeywordSet[]>('/seo-keywords/');
  },

  /**
   * Trigger generation of SEO keyword sets for the active client
   */
  generate: async (): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>('/seo-keywords/generate/', {
      method: 'POST',
    });
  },
};
