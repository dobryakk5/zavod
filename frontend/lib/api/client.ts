import { apiFetch } from '../api';
import type { ClientInfo, ClientSettings, ClientSummary } from '../types';

export const clientApi = {
  /**
   * Get current client info and user role
   */
  info: async (): Promise<ClientInfo> => {
    return apiFetch<ClientInfo>('/client/info/');
  },

  /**
   * Get client summary statistics
   */
  summary: async (): Promise<ClientSummary> => {
    return apiFetch<ClientSummary>('/client/summary/');
  },

  /**
   * Get current client settings (excludes id and name)
   */
  getSettings: async (): Promise<ClientSettings> => {
    return apiFetch<ClientSettings>('/client/settings/');
  },

  /**
   * Update client settings (excludes id and name)
   */
  updateSettings: async (data: Partial<ClientSettings>): Promise<ClientSettings> => {
    return apiFetch<ClientSettings>('/client/settings/', {
      method: 'PATCH',
      body: data,
    });
  },
};
