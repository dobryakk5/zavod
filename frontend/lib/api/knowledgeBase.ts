import { apiFetch } from '../api';
import type {
  KbFolder,
  KbDocumentList,
  KbDocumentDetail,
  KbDocumentVersion,
  KbComment,
  KbDocumentShare,
  KbLinkPreview,
  KbTag,
} from '../types';

const buildQuery = (params: Record<string, string | number | boolean | undefined | null>) => {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `?${query}` : '';
};

export const kbFoldersApi = {
  list: async (): Promise<KbFolder[]> => apiFetch<KbFolder[]>('/kb/folders/'),
  tree: async (id: number): Promise<KbFolder> => apiFetch<KbFolder>(`/kb/folders/${id}/tree/`),
  create: async (payload: Partial<KbFolder>): Promise<KbFolder> =>
    apiFetch<KbFolder>('/kb/folders/', { method: 'POST', body: payload }),
  update: async (id: number, payload: Partial<KbFolder>): Promise<KbFolder> =>
    apiFetch<KbFolder>(`/kb/folders/${id}/`, { method: 'PATCH', body: payload }),
  delete: async (id: number): Promise<void> => apiFetch<void>(`/kb/folders/${id}/`, { method: 'DELETE' }),
};

export const kbDocumentsApi = {
  list: async (params?: { folder?: number | null; parent?: number | null; archived?: boolean; template?: boolean; search?: string; ordering?: string }) => {
    const query = buildQuery({
      folder: params?.folder ?? undefined,
      parent: params?.parent ?? undefined,
      archived: params?.archived ?? undefined,
      template: params?.template ?? undefined,
      search: params?.search ?? undefined,
      ordering: params?.ordering ?? undefined,
    });
    return apiFetch<KbDocumentList[]>(`/kb/documents/${query}`);
  },
  get: async (id: number): Promise<KbDocumentDetail> => apiFetch<KbDocumentDetail>(`/kb/documents/${id}/`),
  create: async (payload: Partial<KbDocumentDetail>): Promise<KbDocumentDetail> =>
    apiFetch<KbDocumentDetail>('/kb/documents/', { method: 'POST', body: payload }),
  update: async (id: number, payload: Partial<KbDocumentDetail>): Promise<KbDocumentDetail> =>
    apiFetch<KbDocumentDetail>(`/kb/documents/${id}/`, { method: 'PATCH', body: payload }),
  delete: async (id: number): Promise<void> => apiFetch<void>(`/kb/documents/${id}/`, { method: 'DELETE' }),
  move: async (id: number, payload: { folder_id?: number | null; parent_document_id?: number | null; position?: number }) =>
    apiFetch<KbDocumentDetail>(`/kb/documents/${id}/move/`, { method: 'POST', body: payload }),
  duplicate: async (id: number, payload: { title?: string; include_children?: boolean }) =>
    apiFetch<KbDocumentDetail>(`/kb/documents/${id}/duplicate/`, { method: 'POST', body: payload }),
  archive: async (id: number) => apiFetch<{ success: boolean }>(`/kb/documents/${id}/archive/`, { method: 'POST' }),
  restore: async (id: number) => apiFetch<{ success: boolean }>(`/kb/documents/${id}/restore/`, { method: 'POST' }),
  bulkArchive: async (document_ids: number[], archive = true) =>
    apiFetch<{ success: boolean; updated: number }>('/kb/documents/bulk_archive/', {
      method: 'POST',
      body: { document_ids, archive },
    }),
  versions: async (id: number): Promise<KbDocumentVersion[]> => apiFetch<KbDocumentVersion[]>(`/kb/documents/${id}/versions/`),
  createVersion: async (id: number): Promise<KbDocumentVersion> =>
    apiFetch<KbDocumentVersion>(`/kb/documents/${id}/versions/`, { method: 'POST' }),
  restoreVersion: async (id: number, versionId: number): Promise<KbDocumentDetail> =>
    apiFetch<KbDocumentDetail>(`/kb/documents/${id}/restore_version/${versionId}/`, { method: 'POST' }),
  export: async (id: number): Promise<KbDocumentDetail> => apiFetch<KbDocumentDetail>(`/kb/documents/${id}/export/`),
};

export const kbCommentsApi = {
  list: async (documentId: number): Promise<KbComment[]> =>
    apiFetch<KbComment[]>(`/kb/comments/?document=${documentId}`),
  create: async (payload: { document: number; content: string; parent_comment?: number | null; block_id?: string | null }): Promise<KbComment> =>
    apiFetch<KbComment>('/kb/comments/', { method: 'POST', body: payload }),
  update: async (id: number, payload: Partial<KbComment>): Promise<KbComment> =>
    apiFetch<KbComment>(`/kb/comments/${id}/`, { method: 'PATCH', body: payload }),
  delete: async (id: number): Promise<void> => apiFetch<void>(`/kb/comments/${id}/`, { method: 'DELETE' }),
  resolve: async (id: number): Promise<{ success: boolean }> => apiFetch(`/kb/comments/${id}/resolve/`, { method: 'POST' }),
  unresolve: async (id: number): Promise<{ success: boolean }> => apiFetch(`/kb/comments/${id}/unresolve/`, { method: 'POST' }),
};

export const kbSharesApi = {
  list: async (): Promise<KbDocumentShare[]> => apiFetch<KbDocumentShare[]>('/kb/shares/'),
  create: async (payload: { document: number; permission?: 'view' | 'comment' | 'edit'; expires_at?: string | null }): Promise<KbDocumentShare> =>
    apiFetch<KbDocumentShare>('/kb/shares/', { method: 'POST', body: payload }),
  revoke: async (id: number): Promise<{ success: boolean; is_active: boolean }> =>
    apiFetch(`/kb/shares/${id}/revoke/`, { method: 'POST' }),
  byToken: async (token: string): Promise<KbDocumentShare> =>
    apiFetch<KbDocumentShare>(`/kb/shares/by_token/${encodeURIComponent(token)}/`),
  resolveDocumentByToken: async (token: string, documentId: number): Promise<KbDocumentShare> =>
    apiFetch<KbDocumentShare>(`/kb/shares/by_token/${encodeURIComponent(token)}/document/${documentId}/`),
};

export const kbTagsApi = {
  list: async (): Promise<KbTag[]> => apiFetch<KbTag[]>('/kb/tags/'),
  create: async (payload: Partial<KbTag>): Promise<KbTag> => apiFetch<KbTag>('/kb/tags/', { method: 'POST', body: payload }),
  update: async (id: number, payload: Partial<KbTag>): Promise<KbTag> =>
    apiFetch<KbTag>(`/kb/tags/${id}/`, { method: 'PATCH', body: payload }),
  delete: async (id: number): Promise<void> => apiFetch<void>(`/kb/tags/${id}/`, { method: 'DELETE' }),
  documents: async (id: number): Promise<KbDocumentList[]> => apiFetch<KbDocumentList[]>(`/kb/tags/${id}/documents/`),
};

export const kbSearchApi = {
  search: async (query: string): Promise<KbDocumentList[]> =>
    apiFetch<KbDocumentList[]>(`/kb/search/?q=${encodeURIComponent(query)}`),
};

export const kbLinkPreviewApi = {
  preview: async (url: string): Promise<KbLinkPreview> =>
    apiFetch<KbLinkPreview>('/link-preview/', { method: 'POST', body: { url } }),
};
