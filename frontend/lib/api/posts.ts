import { apiFetch } from '../api';
import type {
  PaginatedResponse,
  Post,
  PostDetail,
  TaskResponse,
  GenerateVideoRequest,
  QuickPublishRequest,
} from '../types';

export const postsApi = {
  /**
   * List posts for the current client (paginated)
   */
  list: async (filters?: { status?: string; platform?: string; page?: number; pageSize?: number }): Promise<PaginatedResponse<Post>> => {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.platform) params.set('platform', filters.platform);
    if (filters?.page) params.set('page', filters.page.toString());
    if (filters?.pageSize) params.set('page_size', filters.pageSize.toString());
    const query = params.toString();
    return apiFetch<PaginatedResponse<Post>>(`/posts/${query ? `?${query}` : ''}`);
  },

  /**
   * List posts without pagination (legacy endpoint)
   */
  listAll: async (filters?: { status?: string; platform?: string }): Promise<Post[]> => {
    const params = new URLSearchParams();
    if (filters?.status) params.set('status', filters.status);
    if (filters?.platform) params.set('platform', filters.platform);
    const query = params.toString();
    return apiFetch<Post[]>(`/posts-list/${query ? `?${query}` : ''}`);
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
   * Generate image for post using AI (method selected in system settings)
   */
  generateImage: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/posts/${id}/generate_image/`, {
      method: 'POST',
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

  /**
   * Delete a specific image from a post
   */
  deleteImage: async (postId: number, imageId: number): Promise<{ success: boolean; message: string }> => {
    return apiFetch<{ success: boolean; message: string }>(`/posts/${postId}/delete_image/?image_id=${imageId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Delete a specific video from a post
   */
  deleteVideo: async (postId: number, videoId: number): Promise<{ success: boolean; message: string }> => {
    return apiFetch<{ success: boolean; message: string }>(`/posts/${postId}/delete_video/?video_id=${videoId}`, {
      method: 'DELETE',
    });
  },
};
