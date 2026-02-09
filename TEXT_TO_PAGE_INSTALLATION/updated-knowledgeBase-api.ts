// lib/api/knowledgeBase.ts
// Обновленный API клиент с методом дублирования

import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Interceptor для добавления токена
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Типы данных
export interface KbDocument {
  id: number;
  title: string;
  icon: string | null;
  cover_image: string | null;
  content: any;
  parent_document: number | null;
  created_by?: {
    id: number;
    username: string;
    email: string;
  };
  last_edited_by?: {
    id: number;
    username: string;
  };
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  child_documents?: KbDocument[];
}

export interface KbDocumentList {
  id: number;
  title: string;
  icon: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

// API методы для документов
export const kbDocumentsApi = {
  // Получить список документов
  list: async (params?: {
    archived?: boolean;
    search?: string;
  }): Promise<KbDocumentList[]> => {
    const response = await apiClient.get('/documents/', { params });
    return response.data.results || response.data;
  },

  // Получить документ по ID
  get: async (id: number): Promise<KbDocument> => {
    const response = await apiClient.get(`/documents/${id}/`);
    return response.data;
  },

  // Создать документ
  create: async (data: {
    title: string;
    content: any;
    icon?: string;
    cover_image?: string;
    parent_document?: number;
  }): Promise<KbDocument> => {
    const response = await apiClient.post('/documents/', data);
    return response.data;
  },

  // Обновить документ
  update: async (id: number, data: Partial<KbDocument>): Promise<KbDocument> => {
    const response = await apiClient.patch(`/documents/${id}/`, data);
    return response.data;
  },

  // Удалить документ
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/documents/${id}/`);
  },

  // Архивировать документ
  archive: async (id: number): Promise<void> => {
    await apiClient.post(`/documents/${id}/archive/`);
  },

  // Восстановить документ из архива
  restore: async (id: number): Promise<void> => {
    await apiClient.post(`/documents/${id}/restore/`);
  },

  // Дублировать документ
  duplicate: async (
    id: number,
    data: {
      title?: string;
      include_children?: boolean;
    }
  ): Promise<KbDocument> => {
    const response = await apiClient.post(`/documents/${id}/duplicate/`, data);
    return response.data;
  },

  // Переместить документ
  move: async (
    id: number,
    data: {
      parent_document_id?: number | null;
      position?: number;
    }
  ): Promise<KbDocument> => {
    const response = await apiClient.post(`/documents/${id}/move/`, data);
    return response.data;
  },

  // Получить версии документа
  versions: async (id: number): Promise<any[]> => {
    const response = await apiClient.get(`/documents/${id}/versions/`);
    return response.data;
  },

  // Восстановить версию
  restoreVersion: async (id: number, versionId: number): Promise<KbDocument> => {
    const response = await apiClient.post(
      `/documents/${id}/restore_version/${versionId}/`
    );
    return response.data;
  },

  // Экспорт документа
  export: async (id: number): Promise<any> => {
    const response = await apiClient.get(`/documents/${id}/export/`);
    return response.data;
  },
};

export default apiClient;
