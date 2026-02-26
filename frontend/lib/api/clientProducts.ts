import { apiFetch } from '../api';
import type {
  ClientProduct,
  KbDocumentDetail,
  MindMap,
  ProductGenerationResponse,
  ProductPackageConfig,
  ProductStatus,
} from '../types';

export const clientProductsApi = {
  list: async (): Promise<ClientProduct[]> => {
    return apiFetch<ClientProduct[]>('/products/list/');
  },

  createCore: async (payload: { name: string; short_description: string }) => {
    return apiFetch<ClientProduct>('/products/list/create-core/', {
      method: 'POST',
      body: payload
    });
  },

  createCoreAi: async (payload: { name: string; short_description: string; language?: 'ru' | 'en' }) => {
    return apiFetch<ProductGenerationResponse>('/products/list/create-core-ai/', {
      method: 'POST',
      body: payload
    });
  },

  detail: async (id: string | number): Promise<ClientProduct> => {
    return apiFetch<ClientProduct>(`/products/list/${id}/`);
  },

  create: async (payload: {
    name: string;
    status?: ProductStatus;
    product_type_id?: number | null;
    short_description?: string | null;
    packages?: ProductPackageConfig[];
    structure?: Record<string, unknown>;
  }) => {
    return apiFetch<ClientProduct>('/products/list/', {
      method: 'POST',
      body: payload
    });
  },

  createRelatedAi: async (
    coreProductId: string | number,
    payload: { name: string; product_type_id: number; short_description?: string; language?: 'ru' | 'en' }
  ) => {
    return apiFetch<ProductGenerationResponse>(`/products/list/${coreProductId}/create-related-ai/`, {
      method: 'POST',
      body: payload
    });
  },

  generationStatus: async (taskId: string): Promise<ProductGenerationResponse> => {
    return apiFetch<ProductGenerationResponse>(`/products/list/generation-status/?task_id=${encodeURIComponent(taskId)}`);
  },

  createRelatedMap: async (coreProductId: string | number): Promise<MindMap> => {
    return apiFetch<MindMap>(`/products/list/${coreProductId}/create-related-map/`, {
      method: 'POST'
    });
  },

  createDigitalProductPage: async (id: string | number): Promise<{
    product: ClientProduct;
    document: KbDocumentDetail;
    kb_url: string;
    created: boolean;
  }> => {
    return apiFetch(`/products/list/${id}/create-digital-product-page/`, {
      method: 'POST',
    });
  },

  update: async (
    id: string | number,
    payload: Partial<{
      name: string;
      status: ProductStatus;
      product_type_id: number | null;
      short_description: string | null;
      packages: ProductPackageConfig[];
      structure: Record<string, unknown>;
    }>
  ) => {
    return apiFetch<ClientProduct>(`/products/list/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: string | number) => {
    return apiFetch<void>(`/products/list/${id}/`, {
      method: 'DELETE'
    });
  }
};
