import { apiFetch } from '../api';

export interface WeeklySalesPlan {
  id: number;
  week_start: string;
  cold_leads_plan: number | null;
  cold_leads_fact: number | null;
  hot_leads_plan: number | null;
  hot_leads_fact: number | null;
  sales_plan: number | null;
  sales_fact: number | null;
  created_at: string;
  updated_at: string;
}

export type WeeklySalesPlanPayload = {
  week_start: string;
  cold_leads_plan?: number | null;
  cold_leads_fact?: number | null;
  hot_leads_plan?: number | null;
  hot_leads_fact?: number | null;
  sales_plan?: number | null;
  sales_fact?: number | null;
};

export const weeklySalesApi = {
  list: async (): Promise<WeeklySalesPlan[]> => {
    return apiFetch<WeeklySalesPlan[]>('/weekly-sales/');
  },
  create: async (payload: WeeklySalesPlanPayload): Promise<WeeklySalesPlan> => {
    return apiFetch<WeeklySalesPlan>('/weekly-sales/', {
      method: 'POST',
      body: payload
    });
  },
  update: async (id: number, payload: WeeklySalesPlanPayload): Promise<WeeklySalesPlan> => {
    return apiFetch<WeeklySalesPlan>(`/weekly-sales/${id}/`, {
      method: 'PUT',
      body: payload
    });
  },
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/weekly-sales/${id}/`, {
      method: 'DELETE'
    });
  }
};
