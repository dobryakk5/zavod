import { apiFetch } from '../api';

export interface ChannelAnalysisRequest {
  channel_url: string;
  channel_type: 'telegram' | 'instagram' | 'youtube' | 'vkontakte';
}

export type ChannelAnalysisResult = {
  channel_name: string;
  subscribers: number;
  avg_views: number;
  avg_engagement: number;
  avg_reactions: number;
  avg_comments: number;
  top_posts: Array<{
    title: string;
    views: number;
    engagement: number;
    reactions: number;
    comments: number;
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
  audience_profile?: {
    avatar: string;
    pains: string;
    desires: string;
    objections: string;
  };
};

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
  result?: ChannelAnalysisResult;
  error?: string;
}

export interface ChannelAnalysisRecord {
  id: number;
  channel_url: string;
  channel_type: 'telegram' | 'instagram' | 'youtube' | 'vkontakte';
  task_id?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  channel_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChannelAnalysisDetail extends ChannelAnalysisRecord {
  result: ChannelAnalysisResult | null;
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

  /**
   * List previously analyzed channels
   */
  listAnalyses: async (): Promise<ChannelAnalysisRecord[]> => {
    return apiFetch<ChannelAnalysisRecord[]>('/channel-analyses/');
  },

  /**
   * Get stored analysis details
   */
  getAnalysisDetail: async (id: string | number): Promise<ChannelAnalysisDetail> => {
    return apiFetch<ChannelAnalysisDetail>(`/channel-analyses/${id}/`);
  },
};
