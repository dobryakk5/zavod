import { apiFetch } from '../api';
import type {
  ClientInfo,
  ClientSettings,
  ClientSummary,
  BookSemanticsResponse,
  ExpertBooksResponse,
  GenerationEventSummary,
  TeamOverview,
  CreateTeamInvitationResponse,
} from '../types';

export type CustomDomainVerifyResponse = {
  domain: string;
  verified: boolean;
  method: 'cname' | 'edge_ip' | 'none' | string;
  expected_cname: string;
  resolved_cname: string[];
  resolved_ips: string[];
  error?: string | null;
};

export const clientApi = {
  /**
   * Get current client info and user role
   */
  info: async (): Promise<ClientInfo> => {
    return apiFetch<ClientInfo>('/client/info/');
  },

  updateName: async (name: string): Promise<ClientInfo> => {
    return apiFetch<ClientInfo>('/client/info/', {
      method: 'PATCH',
      body: { name },
    });
  },

  setActiveClient: async (clientId: number): Promise<ClientInfo> => {
    return apiFetch<ClientInfo>('/client/active/', {
      method: 'POST',
      body: { client_id: clientId },
    });
  },

  /**
   * Get client summary statistics
   */
  summary: async (): Promise<ClientSummary> => {
    return apiFetch<ClientSummary>('/client/summary/');
  },

  /**
   * Get current client settings (excludes id and name)
   */
  getSettings: async (): Promise<ClientSettings> => {
    return apiFetch<ClientSettings>('/client/settings/');
  },

  /**
   * Update client settings (excludes id and name)
   */
  updateSettings: async (data: Partial<ClientSettings>): Promise<ClientSettings> => {
    return apiFetch<ClientSettings>('/client/settings/', {
      method: 'PATCH',
      body: data,
    });
  },

  verifyCustomDomain: async (domain?: string): Promise<CustomDomainVerifyResponse> => {
    const body = domain !== undefined ? { domain } : {};
    return apiFetch<CustomDomainVerifyResponse>('/client/custom-domain/verify/', {
      method: 'POST',
      body,
    });
  },

  /**
   * Generate expert book recommendations using AI
   */
  generateExpertBooks: async (payload: {
    pains?: string;
    desires?: string;
    avatar?: string;
    language?: string;
  }): Promise<ExpertBooksResponse> => {
    return apiFetch<ExpertBooksResponse>('/client/expert-books/', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Generate project semantics from expert books
   */
  generateBookSemantics: async (payload: {
    expert_books?: string;
    language?: string;
  }): Promise<BookSemanticsResponse> => {
    return apiFetch<BookSemanticsResponse>('/client/book-semantics/', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Get generation events summary for the active client
   */
  generationEventsSummary: async (): Promise<GenerationEventSummary> => {
    return apiFetch<GenerationEventSummary>('/client/generation-events/');
  },

  getTeam: async (): Promise<TeamOverview> => {
    return apiFetch<TeamOverview>('/client/team/');
  },

  createTeamInvitation: async (payload: {
    provider: 'telegram' | 'vk' | 'email';
    account_handle: string;
  }): Promise<CreateTeamInvitationResponse> => {
    return apiFetch<CreateTeamInvitationResponse>('/client/team/invitations/', {
      method: 'POST',
      body: payload,
    });
  },

  revokeTeamInvitation: async (inviteId: number): Promise<void> => {
    return apiFetch<void>(`/client/team/invitations/${inviteId}/`, {
      method: 'DELETE',
    });
  },

  removeTeamMember: async (userId: number): Promise<void> => {
    return apiFetch<void>(`/client/team/members/${userId}/`, {
      method: 'DELETE',
    });
  },
};
