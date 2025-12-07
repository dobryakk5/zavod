import { apiFetch } from '../api';

export interface PostType {
  id: number;
  value: string;
  label: string;
  is_default: boolean;
  created_at: string;
}

export interface PostTone {
  id: number;
  value: string;
  label: string;
  is_default: boolean;
  created_at: string;
}

export const postTypesApi = {
  list: async (): Promise<PostType[]> => {
    return apiFetch<PostType[]>('/post-types/');
  },

  create: async (data: { value: string; label: string }): Promise<PostType> => {
    return apiFetch<PostType>('/post-types/', {
      method: 'POST',
      body: data,
    });
  },
};

export const postTonesApi = {
  list: async (): Promise<PostTone[]> => {
    return apiFetch<PostTone[]>('/post-tones/');
  },

  create: async (data: { value: string; label: string }): Promise<PostTone> => {
    return apiFetch<PostTone>('/post-tones/', {
      method: 'POST',
      body: data,
    });
  },
};
