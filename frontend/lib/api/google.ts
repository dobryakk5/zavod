import { apiFetch } from '../api';
import type { GoogleCseSearchResponse } from '../types';

export const googleApi = {
  cseSearch: async (query: string, num: number = 10): Promise<GoogleCseSearchResponse> => {
    const params = new URLSearchParams();
    params.set('q', query);
    params.set('num', String(num));
    return apiFetch<GoogleCseSearchResponse>(`/google/cse-search/?${params.toString()}`);
  },
};

