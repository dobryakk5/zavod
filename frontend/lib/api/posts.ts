import { apiFetch } from '../api';
import type { Post, PostDetail, TaskResponse, GenerateImageRequest, GenerateVideoRequest, QuickPublishRequest } from '../types';

export const postsApi = {
  /**
   * List all posts for the current client
   */
  list: async (filters?: { status?: string; platform?: string }): Promise<Post[]> => {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.platform) params.set('platform', filters.platform);
    const query = params.toString();
    return apiFetch<Post[]>(`/posts/${query ? `?${query}` : ''}`);
  },

  /**
   * Get detailed information about a post
   */
  get: async (id: number): Promise<PostDetail> => {
    return apiFetch<PostDetail>(`/posts/${id}/`);
  },

  /**
   * Create a new post
   */
  create: async (data: Partial<PostDetail>): Promise<PostDetail> => {
    return apiFetch<PostDetail>('/posts/', {
      method: 'POST',
      body: data,
    });
  },

  /**
   * Update an existing post
   */
  update: async (id: number, data: Partial<PostDetail>): Promise<PostDetail> => {
    return apiFetch<PostDetail>(`/posts/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  /**
   * Delete a post
   */
  delete: async (id: number): Promise<void> => {
    return apiFetch<void>(`/posts/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Generate image for post using AI
   * @param model - One of: pollinations, nanobanana, huggingface, flux2, sora_images
   */
  generateImage: async (id: number, model: GenerateImageRequest['model']): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/posts/${id}/generate_image/`, {
      method: 'POST',
      body: { model },
    });
  },

  /**
   * Generate video from post image (requires dev mode or zavod client)
   */
  generateVideo: async (id: number, options?: GenerateVideoRequest): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/posts/${id}/generate_video/`, {
      method: 'POST',
      body: options,
    });
  },

  /**
   * Regenerate post text using AI
   */
  regenerateText: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/posts/${id}/regenerate_text/`, {
      method: 'POST',
    });
  },

  /**
   * Quick publish post to a social account
   */
  quickPublish: async (id: number, data: QuickPublishRequest): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/posts/${id}/quick_publish/`, {
      method: 'POST',
      body: data,
    });
  },
};
