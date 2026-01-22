import { apiFetch } from '../api';
import type {
  ClientInfo,
  ClientSettings,
  ClientSummary,
  BookSemanticsResponse,
  ExpertBooksResponse,
  GenerationEventSummary,
} from '../types';

export const clientApi = {
  /**
   * Get current client info and user role
   */
  info: async (): Promise<ClientInfo> => {
    return apiFetch<ClientInfo>('/client/info/');
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
};
