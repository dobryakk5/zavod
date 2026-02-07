import { apiFetch } from '../api';

export type ChainStatus = 'draft' | 'active' | 'paused' | 'archived';
export type ChainNodeType = 'start' | 'text' | 'photo' | 'buttons' | 'router' | 'timer';
export type ChainConditionType =
  | 'button_press'
  | 'text_contains'
  | 'text_regex'
  | 'timeout'
  | 'any_reply'
  | 'content_type'
  | 'has_media'
  | 'text_equals'
  | 'has_entities';

export type Chain = {
  id: number;
  tenant_id: number;
  name: string;
  description?: string | null;
  status: ChainStatus;
  start_node_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type ChainNode = {
  id: number;
  chain_id: number;
  node_type: ChainNodeType;
  payload: Record<string, unknown>;
  delay_seconds: number;
  pos_x: number;
  pos_y: number;
  created_at: string;
  updated_at: string;
};

export type ChainCondition = {
  id: number;
  edge_id: number;
  condition_type: ChainConditionType;
  params: Record<string, unknown>;
  created_at: string;
};

export type ChainEdge = {
  id: number;
  chain_id: number;
  source_node_id: number;
  source_port_id?: string | null;
  target_node_id: number;
  priority: number;
  created_at: string;
  updated_at: string;
  conditions?: ChainCondition[];
};

export type ChainGraph = {
  chain: Chain;
  nodes: ChainNode[];
  edges: ChainEdge[];
};

export const chainsApi = {
  getGraph: async (): Promise<ChainGraph> => {
    return apiFetch<ChainGraph>('/chains/current/graph/');
  },

  updateChain: async (payload: Partial<Pick<Chain, 'name' | 'description' | 'status' | 'start_node_id'>>): Promise<Chain> => {
    return apiFetch<Chain>('/chains/current/', {
      method: 'PATCH',
      body: payload,
    });
  },

  createNode: async (payload: Partial<ChainNode>): Promise<ChainNode> => {
    return apiFetch<ChainNode>('/chains/current/nodes/', {
      method: 'POST',
      body: payload,
    });
  },

  updateNode: async (nodeId: number, payload: Partial<ChainNode>): Promise<ChainNode> => {
    return apiFetch<ChainNode>(`/chains/current/nodes/${nodeId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  deleteNode: async (nodeId: number): Promise<void> => {
    return apiFetch<void>(`/chains/current/nodes/${nodeId}/`, {
      method: 'DELETE',
    });
  },

  createEdge: async (payload: Partial<ChainEdge>): Promise<ChainEdge> => {
    return apiFetch<ChainEdge>('/chains/current/edges/', {
      method: 'POST',
      body: payload,
    });
  },

  updateEdge: async (edgeId: number, payload: Partial<ChainEdge>): Promise<ChainEdge> => {
    return apiFetch<ChainEdge>(`/chains/current/edges/${edgeId}/`, {
      method: 'PATCH',
      body: payload,
    });
  },

  deleteEdge: async (edgeId: number): Promise<void> => {
    return apiFetch<void>(`/chains/current/edges/${edgeId}/`, {
      method: 'DELETE',
    });
  },

  listConditions: async (edgeId: number): Promise<ChainCondition[]> => {
    return apiFetch<ChainCondition[]>(`/chains/current/edges/${edgeId}/conditions/`);
  },

  createCondition: async (edgeId: number, payload: Partial<ChainCondition>): Promise<ChainCondition> => {
    return apiFetch<ChainCondition>(`/chains/current/edges/${edgeId}/conditions/`, {
      method: 'POST',
      body: payload,
    });
  },

  deleteCondition: async (edgeId: number, conditionId: number): Promise<void> => {
    return apiFetch<void>(`/chains/current/edges/${edgeId}/conditions/${conditionId}/`, {
      method: 'DELETE',
    });
  },
};
