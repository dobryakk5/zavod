import { apiFetch } from '../api';
import type { ProjectSemanticSet } from '../types';

export const semanticsApi = {
  /**
   * List project semantic sets for the active client
   */
  list: async (params?: { source?: string; status?: string }): Promise<ProjectSemanticSet[]> => {
    const search = new URLSearchParams();
    if (params?.source) search.set('source', params.source);
    if (params?.status) search.set('status', params.status);
    const suffix = search.toString();
    return apiFetch<ProjectSemanticSet[]>(`/project-semantics/${suffix ? `?${suffix}` : ''}`);
  },
};
