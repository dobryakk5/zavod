import { apiFetch } from '../api';
import type { TagType } from './mapTags';

export type MapClient = {
  id: number;
  name: string;
  tags?: Partial<Record<TagType, number[]>>;
};

export const mapClientsApi = {
  list: async (): Promise<MapClient[]> => {
    return apiFetch<MapClient[]>('/clients/');
  },

  create: async (payload: { name: string }) => {
    return apiFetch<MapClient>('/clients/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: number | string, payload: { name: string }) => {
    return apiFetch<MapClient>(`/clients/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: number | string) => {
    return apiFetch<void>(`/clients/${id}/`, {
      method: 'DELETE'
    });
  }
};
