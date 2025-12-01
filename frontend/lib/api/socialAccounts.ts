import { apiFetch } from '../api';
import type { SocialAccount } from '../types';

export const socialAccountsApi = {
  /**
   * List all social accounts for the current client
   */
  list: async (): Promise<SocialAccount[]> => {
    return apiFetch<SocialAccount[]>('/social-accounts/');
  },

  /**
   * Get detailed information about a social account
   */
  get: async (id: number): Promise<SocialAccount> => {
    return apiFetch<SocialAccount>(`/social-accounts/${id}/`);
  },

  /**
   * Add a new social account
   */
  create: async (data: Partial<SocialAccount> & {
    access_token?: string;
    refresh_token?: string;
  }): Promise<SocialAccount> => {
    return apiFetch<SocialAccount>('/social-accounts/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing social account
   */
  update: async (id: number, data: Partial<SocialAccount> & {
    access_token?: string;
    refresh_token?: string;
  }): Promise<SocialAccount> => {
    return apiFetch<SocialAccount>(`/social-accounts/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a social account
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/social-accounts/${id}/`, {
      method: 'DELETE',
    });
  },
};
