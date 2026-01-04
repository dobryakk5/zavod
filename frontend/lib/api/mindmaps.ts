import { apiFetch } from '../api';
import type { MindEdge, MindMap, MindMapDetail, MindNode, MindNodePosition } from '../types';

export const mindMapsApi = {
  list: async (): Promise<MindMap[]> => {
    return apiFetch<MindMap[]>('/map/mind-maps/');
  },

  createProductsMap: async (): Promise<MindMap> => {
    return apiFetch<MindMap>('/map/mind-maps/create-products-map/', {
      method: 'POST'
    });
  },

  create: async (payload: { title: string; description?: string; is_public?: boolean }) => {
    return apiFetch<MindMap>('/map/mind-maps/', {
      method: 'POST',
      body: payload
    });
  },

  update: async (id: string | number, payload: Partial<{ title: string; description: string | null; is_public: boolean }>) => {
    return apiFetch<MindMap>(`/map/mind-maps/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  delete: async (id: string | number) => {
    return apiFetch<void>(`/map/mind-maps/${id}/`, {
      method: 'DELETE'
    });
  },

  detail: async (id: string | number): Promise<MindMapDetail> => {
    return apiFetch<MindMapDetail>(`/map/mind-maps/${id}/`);
  },

  createNode: async (mapId: number, payload: Partial<MindNode>) => {
    return apiFetch<MindNode>(`/map/mind-maps/${mapId}/nodes/`, {
      method: 'POST',
      body: payload
    });
  },

  updateNode: async (mapId: number, nodeId: string, payload: Partial<MindNode>) => {
    return apiFetch<MindNode>(`/map/mind-maps/${mapId}/nodes/${nodeId}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  deleteNode: async (mapId: number, nodeId: string) => {
    return apiFetch<void>(`/map/mind-maps/${mapId}/nodes/${nodeId}/`, {
      method: 'DELETE'
    });
  },

  upsertPosition: async (nodeId: string, payload: MindNodePosition) => {
    return apiFetch<MindNodePosition>(`/map/nodes/${nodeId}/position/`, {
      method: 'PUT',
      body: payload
    });
  },

  createEdge: async (mapId: number, payload: MindEdge) => {
    return apiFetch<MindEdge>(`/map/mind-maps/${mapId}/edges/`, {
      method: 'POST',
      body: payload
    });
  },

  updateEdge: async (mapId: number, edgeId: string | number, payload: Partial<MindEdge>) => {
    return apiFetch<MindEdge>(`/map/mind-maps/${mapId}/edges/${edgeId}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  deleteEdge: async (mapId: number, edgeId: string | number) => {
    return apiFetch<void>(`/map/mind-maps/${mapId}/edges/${edgeId}/`, {
      method: 'DELETE'
    });
  },

  createProperty: async (payload: { node: string; title: string; value: string; delta?: string; order_index?: number; meta?: Record<string, unknown> }) => {
    return apiFetch(`/map/node-properties/`, {
      method: 'POST',
      body: payload
    });
  },

  updateProperty: async (id: number, payload: Partial<{ title: string; value: string; delta?: string; order_index?: number; meta?: Record<string, unknown> }>) => {
    return apiFetch(`/map/node-properties/${id}/`, {
      method: 'PATCH',
      body: payload
    });
  },

  deleteProperty: async (id: number) => {
    return apiFetch(`/map/node-properties/${id}/`, {
      method: 'DELETE'
    });
  }
};
