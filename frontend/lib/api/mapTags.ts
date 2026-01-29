import { apiFetch } from '../api';

export type TagType = 'goal' | 'pain' | 'experience';

export type MapTag = {
  id: number;
  type: TagType;
  value: string;
};

export const mapTagsApi = {
  list: async (): Promise<MapTag[]> => {
    return apiFetch<MapTag[]>('/crm/tags/');
  },

  create: async (payload: { type: TagType; value: string }) => {
    return apiFetch<MapTag>('/crm/tags/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: number | string, payload: Partial<{ type: TagType; value: string }>) => {
    return apiFetch<MapTag>(`/crm/tags/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: number | string) => {
    return apiFetch<void>(`/crm/tags/${id}/`, {
      method: 'DELETE'
    });
  }
};
