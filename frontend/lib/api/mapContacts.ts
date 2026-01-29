import { apiFetch } from '../api';
import type { MapClient } from './mapClients';
import type { MapTag } from './mapTags';

export type { MapClient } from './mapClients';

export const mapContactsApi = {
  list: async (): Promise<MapClient[]> => {
    return apiFetch<MapClient[]>('/crm/contacts/');
  },

  detail: async (id: number | string): Promise<MapClient> => {
    return apiFetch<MapClient>(`/crm/contacts/${id}/`);
  },

  create: async (payload: { name: string }) => {
    return apiFetch<MapClient>('/crm/contacts/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: number | string, payload: { name: string }) => {
    return apiFetch<MapClient>(`/crm/contacts/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: number | string) => {
    return apiFetch<void>(`/crm/contacts/${id}/`, {
      method: 'DELETE'
    });
  }
};

export const contactTagsApi = {
  assign: async (contactId: number | string, tagId: number | string) => {
    return apiFetch<{ success: boolean }>('/crm/contact-tags/', {
      method: 'POST',
      body: { contactId, tagId }
    });
  },

  remove: async (contactId: number | string, tagId: number | string) => {
    return apiFetch<void>('/crm/contact-tags/', {
      method: 'DELETE',
      body: { contactId, tagId }
    });
  }
};
