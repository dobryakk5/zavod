import { apiFetch } from '../api';
import type { ClientProduct, ProductType } from '../types';

export const productTypesApi = {
  list: async (): Promise<ProductType[]> => {
    return apiFetch<ProductType[]>('/products/types/');
  },

  detail: async (id: string | number): Promise<ProductType> => {
    return apiFetch<ProductType>(`/products/types/${id}/`);
  },

  create: async (payload: { name: string; value?: string | null; goal?: string | null }) => {
    return apiFetch<ProductType>('/products/types/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: string | number, payload: Partial<{ name: string; value?: string | null; goal?: string | null }>) => {
    return apiFetch<ProductType>(`/products/types/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: string | number) => {
    return apiFetch<void>(`/products/types/${id}/`, {
      method: 'DELETE'
    });
  },

  generateProduct: async (id: string | number, payload?: { language?: 'ru' | 'en' }) => {
    return apiFetch<ClientProduct>(`/products/types/${id}/generate-product/`, {
      method: 'POST',
      body: payload ?? {}
    });
  }
};
