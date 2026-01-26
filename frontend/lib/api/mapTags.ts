import { apiFetch } from '../api';

export type TagType = 'goal' | 'pain' | 'experience';

export type MapTag = {
  id: number;
  type: TagType;
  value: string;
};

export const mapTagsApi = {
  list: async (): Promise<MapTag[]> => {
    return apiFetch<MapTag[]>('/tags/');
  },

  create: async (payload: { type: TagType; value: string }) => {
    return apiFetch<MapTag>('/tags/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: number | string, payload: Partial<{ type: TagType; value: string }>) => {
    return apiFetch<MapTag>(`/tags/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: number | string) => {
    return apiFetch<void>(`/tags/${id}/`, {
      method: 'DELETE'
    });
  }
};
