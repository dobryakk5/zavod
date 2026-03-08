import { apiFetch } from '../api';
import type {
  ClientProduct,
  ProductCourse,
  ProductCourseLesson,
  ProductCourseModule,
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

  getCourse: async (id: string | number): Promise<{ course: ProductCourse | null }> => {
    return apiFetch<{ course: ProductCourse | null }>(`/products/list/${id}/course/`);
  },

  upsertCourse: async (
    id: string | number,
    payload: Partial<{
      title: string;
      description: string;
      cover_url: string | null;
      is_published: boolean;
    }>
  ): Promise<{ course: ProductCourse | null }> => {
    return apiFetch<{ course: ProductCourse | null }>(`/products/list/${id}/course/`, {
      method: 'PUT',
      body: payload,
    });
  },

  createCourseModule: async (
    productId: string | number,
    payload: Partial<{
      title: string;
      cover_url: string | null;
      position: number;
      unlock_at: string | null;
      open_lessons_immediately: boolean;
      lesson_unlock_condition: 'after_student_complete' | 'after_curator_complete' | 'after_timer';
      unlock_delay_days: number;
      unlock_delay_hours: number;
      unlock_delay_minutes: number;
    }>
  ): Promise<ProductCourseModule> => {
    return apiFetch<ProductCourseModule>(`/products/list/${productId}/course/modules/`, {
      method: 'POST',
      body: payload,
    });
  },

  updateCourseModule: async (
    productId: string | number,
    moduleId: number,
    payload: Partial<{
      title: string;
      cover_url: string | null;
      position: number;
      unlock_at: string | null;
      open_lessons_immediately: boolean;
      lesson_unlock_condition: 'after_student_complete' | 'after_curator_complete' | 'after_timer';
      unlock_delay_days: number;
      unlock_delay_hours: number;
      unlock_delay_minutes: number;
    }>
  ): Promise<ProductCourseModule> => {
    return apiFetch<ProductCourseModule>(`/products/list/${productId}/course/modules/${moduleId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  deleteCourseModule: async (productId: string | number, moduleId: number): Promise<void> => {
    return apiFetch<void>(`/products/list/${productId}/course/modules/${moduleId}/`, {
      method: 'DELETE',
    });
  },

  reorderCourseModules: async (productId: string | number, orderedIds: number[]): Promise<void> => {
    return apiFetch<void>(`/products/list/${productId}/course/modules/reorder/`, {
      method: 'PATCH',
      body: { ordered_ids: orderedIds },
    });
  },

  createCourseLesson: async (
    productId: string | number,
    moduleId: number,
    payload: Partial<{
      title: string;
      content: Record<string, unknown>;
      position: number;
      is_preview: boolean;
      unlock_at: string | null;
      youtube_video_id: string | null;
      rutube_video_id: string | null;
      vk_owner_id: string | null;
      vk_video_id: string | null;
      vk_hash: string | null;
    }>
  ): Promise<ProductCourseLesson> => {
    return apiFetch<ProductCourseLesson>(`/products/list/${productId}/course/modules/${moduleId}/lessons/`, {
      method: 'POST',
      body: payload,
    });
  },

  updateCourseLesson: async (
    productId: string | number,
    lessonId: number,
    payload: Partial<{
      title: string;
      content: Record<string, unknown>;
      position: number;
      is_preview: boolean;
      unlock_at: string | null;
      youtube_video_id: string | null;
      rutube_video_id: string | null;
      vk_owner_id: string | null;
      vk_video_id: string | null;
      vk_hash: string | null;
    }>
  ): Promise<ProductCourseLesson> => {
    return apiFetch<ProductCourseLesson>(`/products/list/${productId}/course/lessons/${lessonId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  curatorCompleteCourseLesson: async (
    productId: string | number,
    lessonId: number,
    payload: { contact_id: number }
  ): Promise<{ ok: boolean; created: boolean; lesson_id: number; contact_id: number; curator_completed_at: string }> => {
    return apiFetch<{ ok: boolean; created: boolean; lesson_id: number; contact_id: number; curator_completed_at: string }>(
      `/products/list/${productId}/course/lessons/${lessonId}/curator-complete/`,
      {
        method: 'POST',
        body: payload,
      }
    );
  },

  deleteCourseLesson: async (productId: string | number, lessonId: number): Promise<void> => {
    return apiFetch<void>(`/products/list/${productId}/course/lessons/${lessonId}/`, {
      method: 'DELETE',
    });
  },

  reorderCourseLessons: async (productId: string | number, moduleId: number, orderedIds: number[]): Promise<void> => {
    return apiFetch<void>(`/products/list/${productId}/course/modules/${moduleId}/lessons/reorder/`, {
      method: 'PATCH',
      body: { ordered_ids: orderedIds },
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
