import { apiFetch, BACKEND_BASE_URL } from '../api';
import type { VkIntegration } from '../types';

export type VkPublishPayload = {
  integration_id: number;
  message: string;
  images?: File[];
};

export const vkApi = {
  listIntegrations: async (): Promise<VkIntegration[]> => {
    return apiFetch<VkIntegration[]>('/vk/integrations/');
  },

  deleteIntegration: async (id: number): Promise<void> => {
    return apiFetch<void>(`/vk/integrations/${id}/`, {
      method: 'DELETE',
    });
  },

  publishPost: async (payload: VkPublishPayload): Promise<Record<string, unknown>> => {
    const formData = new FormData();
    formData.append('integration_id', payload.integration_id.toString());
    formData.append('message', payload.message);

    payload.images?.forEach((file) => {
      formData.append('images', file);
    });

    return apiFetch<Record<string, unknown>>('/vk/post_with_photos/', {
      method: 'POST',
      body: formData,
    });
  },
};

export function getVkConnectUrl(query?: { groupId?: number | string; state?: string }): string {
  const base = BACKEND_BASE_URL.replace(/\/$/, '');
  const url = new URL(`${base}/vk/connect/`);

  if (query?.groupId) {
    url.searchParams.set('group_id', String(query.groupId));
  }
  if (query?.state) {
    url.searchParams.set('state', query.state);
  }

  return url.toString();
}
