import { apiFetch } from '../api';

export type WebsiteScanStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export interface WebsiteScan {
  id: number;
  base_url: string;
  status: WebsiteScanStatus;
  progress: number;
  max_depth: number;
  max_pages: number;
  pages_total?: number | null;
  mind_map_id?: number | null;
  error?: string;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
  pages_count?: number | null;
}

export interface WebsiteScanDetail extends WebsiteScan {
  task_id?: string;
  robots_url?: string;
  robots_txt?: string;
  sitemap_urls?: string[];
  started_at?: string | null;
  finished_at?: string | null;
}

export interface WebsiteScanPage {
  id: number;
  url: string;
  parent_id?: number | null;
  depth: number;
  status_code?: number | null;
  content_type?: string;
  title?: string;
  meta_description?: string;
  headings?: Record<string, unknown>;
  wordstats?: Array<{ word: string; count: number }>;
  can_fetch_all?: boolean;
  can_fetch_googlebot?: boolean;
  fetched_at?: string | null;
}

export const websitesApi = {
  listScans: async (): Promise<WebsiteScan[]> => {
    return apiFetch<WebsiteScan[]>('/website-scans/');
  },

  createScan: async (payload: { base_url: string; max_depth?: number; max_pages?: number }): Promise<WebsiteScanDetail> => {
    return apiFetch<WebsiteScanDetail>('/website-scans/', {
      method: 'POST',
      body: payload
    });
  },

  getScan: async (id: string | number): Promise<WebsiteScanDetail> => {
    return apiFetch<WebsiteScanDetail>(`/website-scans/${id}/`);
  },

  deleteScan: async (id: string | number): Promise<void> => {
    return apiFetch<void>(`/website-scans/${id}/`, { method: 'DELETE' });
  },

  rerunScan: async (id: string | number): Promise<{ success: boolean; task_id?: string }> => {
    return apiFetch<{ success: boolean; scan_id?: number; task_id?: string }>(`/website-scans/${id}/rerun/`, { method: 'POST' });
  },

  listPages: async (id: string | number): Promise<WebsiteScanPage[]> => {
    return apiFetch<WebsiteScanPage[]>(`/website-scans/${id}/pages/`);
  },

  getMindMapId: async (id: string | number): Promise<{ mind_map_id: number | null }> => {
    return apiFetch<{ mind_map_id: number | null }>(`/website-scans/${id}/mind-map/`);
  }
};
