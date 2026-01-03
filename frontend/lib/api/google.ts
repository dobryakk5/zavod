import { apiFetch } from '../api';
import type {
  GoogleCompetitorSiteListResponse,
  GoogleCompetitorsResolveResponse,
  GoogleCompetitorsAnalyzeResponse,
  GoogleCompetitorsStoreResponse,
  GoogleCseSearchResponse
} from '../types';

export const googleApi = {
  cseSearch: async (query: string, num: number = 10): Promise<GoogleCseSearchResponse> => {
    const params = new URLSearchParams();
    params.set('q', query);
    params.set('num', String(num));
    return apiFetch<GoogleCseSearchResponse>(`/google/cse-search/?${params.toString()}`);
  },

  competitorsAnalyze: async (urls: string[], max_sites: number = 5): Promise<GoogleCompetitorsAnalyzeResponse> => {
    return apiFetch<GoogleCompetitorsAnalyzeResponse>('/google/competitors/analyze/', {
      method: 'POST',
      body: {
        urls,
        max_sites
      }
    });
  },
  competitorsStore: async (payload: {
    query: string;
    results: Array<{ url: string; domain?: string }>;
  }): Promise<GoogleCompetitorsStoreResponse> => {
    return apiFetch<GoogleCompetitorsStoreResponse>('/google/competitors/store/', {
      method: 'POST',
      body: payload
    });
  },

  competitorsSites: async (): Promise<GoogleCompetitorSiteListResponse> => {
    return apiFetch<GoogleCompetitorSiteListResponse>('/google/competitors/sites/');
  },

  competitorsResolve: async (payload: {
    query: string;
    results: Array<{ position?: number; title?: string; url: string; domain?: string }>;
    max_results?: number;
  }): Promise<GoogleCompetitorsResolveResponse> => {
    return apiFetch<GoogleCompetitorsResolveResponse>('/google/competitors/resolve/', {
      method: 'POST',
      body: payload
    });
  },

  competitorsMark: async (domain: string, is_competitor: boolean | null): Promise<{ success: boolean; domain: string; manual_is_competitor: boolean | null }> => {
    return apiFetch<{ success: boolean; domain: string; manual_is_competitor: boolean | null }>('/google/competitors/mark/', {
      method: 'POST',
      body: {
        domain,
        is_competitor
      }
    });
  },

  competitorsCached: async (query: string): Promise<GoogleCompetitorsResolveResponse> => {
    const params = new URLSearchParams();
    params.set('q', query);
    return apiFetch<GoogleCompetitorsResolveResponse>(`/google/competitors/cached/?${params.toString()}`);
  }
};
