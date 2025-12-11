import { apiFetch } from '../api';
import type { TaskResponse } from '../types';

export interface ChannelAnalysisRequest {
  channel_url: string;
  channel_type: 'telegram' | 'instagram' | 'youtube' | 'vkontakte';
}

export interface ChannelAnalysisResponse {
  success: boolean;
  message: string;
  task_id?: string;
  error?: string;
}

export interface AnalysisStatusResponse {
  task_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress?: number;
  result?: {
    channel_name: string;
    subscribers: number;
    avg_views: number;
    avg_reach: number;
    avg_engagement: number;
    top_posts: Array<{
      title: string;
      views: number;
      engagement: number;
      url: string;
    }>;
    keywords: string[];
    topics: string[];
    content_types: string[];
    posting_schedule: Array<{
      day: string;
      hour: number;
      posts_count: number;
    }>;
  };
  error?: string;
}

export const analyticsApi = {
  /**
   * Analyze a channel to extract insights
   */
  analyzeChannel: async (data: ChannelAnalysisRequest): Promise<ChannelAnalysisResponse> => {
    return apiFetch<ChannelAnalysisResponse>('/tg_channel/', {
      method: 'POST',
      body: { ...data, action: 'analyze' },
    });
  },

  /**
   * Get the status of an analysis task
   */
  getAnalysisStatus: async (taskId: string): Promise<AnalysisStatusResponse> => {
    return apiFetch<AnalysisStatusResponse>(`/tg_channel/?action=status&task_id=${encodeURIComponent(taskId)}`);
  },

  /**
   * Validate a channel URL
   */
  validateChannel: async (data: {
    channel_url: string;
    channel_type: 'telegram' | 'instagram' | 'youtube' | 'vkontakte';
  }): Promise<{ valid: boolean; error?: string }> => {
    return apiFetch<{ valid: boolean; error?: string }>('/tg_channel/', {
      method: 'POST',
      body: { ...data, action: 'validate' },
    });
  },
};
