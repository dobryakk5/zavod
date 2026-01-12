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
  author_influence_analysis?: AuthorInfluenceAnalysis | string;
};

export type AuthorInfluenceAnalysis = {
  short_overview?: string;
  core_value_drivers?: Array<{
    driver?: string;
    evidence?: string;
    marketing_use?: string;
  }>;
  influence_style?: {
    persuasion_method?: string;
    tone?: string;
    audience_relationship?: string;
    content_posture?: string;
  };
  risk_signals?: Array<{
    risk?: string;
    why?: string;
  }>;
  marketing_playbook?: {
    best_approach?: {
      angle?: string;
      message_framing?: string;
      tone?: string;
      cta_style?: string;
    };
    avoid?: {
      message_types?: string;
      promises?: string;
      wording_styles?: string;
    };
  };
  executive_summary?: string[];
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

export interface MergeAudienceResponse {
  success: boolean;
  message: string;
  client_profile: {
    avatar: string;
    pains: string;
    desires: string;
    objections: string;
  };
}

export interface WeeklySourceReport {
  id: number;
  source_type: 'telegram' | 'instagram' | 'youtube' | 'rss' | 'vkontakte';
  source_value: string;
  week_start: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  summary: string;
  links: Array<{
    title?: string;
    url?: string;
    date?: string | null;
    text_length?: number;
    duration_seconds?: number;
    idea?: string;
    action?: string;
  }>;
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface WeeklySourceBatch {
  id: number;
  week_start: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  reports?: WeeklySourceReport[];
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

  /**
   * Merge channel audience profile into client settings
   */
  mergeAudienceProfile: async (id: string | number): Promise<MergeAudienceResponse> => {
    return apiFetch<MergeAudienceResponse>(`/channel-analyses/${id}/merge_audience/`, {
      method: 'POST',
    });
  },

  /**
   * Delete a stored analysis record
   */
  deleteAnalysis: async (id: string | number): Promise<void> => {
    return apiFetch<void>(`/channel-analyses/${id}/`, {
      method: 'DELETE',
    });
  },

  /**
   * Запуск еженедельной аналитики по всем источникам
   */
  runWeeklySources: async (): Promise<{ success: boolean; task_id?: string; week_start?: string }> => {
    return apiFetch<{ success: boolean; task_id?: string; week_start?: string }>('/weekly-sources/run/', {
      method: 'POST',
    });
  },

  /**
   * Список отчётов по источникам
   */
  listWeeklySources: async (): Promise<WeeklySourceReport[]> => {
    return apiFetch<WeeklySourceReport[]>('/weekly-sources/');
  },

  /**
   * Список подборок
   */
  listWeeklyBatches: async (): Promise<WeeklySourceBatch[]> => {
    return apiFetch<WeeklySourceBatch[]>('/weekly-batches/');
  },

  /**
   * Детали подборки
   */
  getWeeklyBatch: async (id: string | number): Promise<WeeklySourceBatch> => {
    return apiFetch<WeeklySourceBatch>(`/weekly-batches/${id}/`);
  },
};
