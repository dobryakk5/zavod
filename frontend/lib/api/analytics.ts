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

export interface ChannelAnalysisShareResponse {
  success: boolean;
  share_token: string;
}

export interface ChannelAnalysisUnshareResponse {
  success: boolean;
}

export type ProjectChannelPostStat = {
  external_id: string;
  title: string;
  url: string;
  published_at?: string | null;
  views: number;
  reactions: number;
  comments: number;
  delta_views: number;
  delta_reactions: number;
  delta_comments: number;
  is_new: boolean;
};

export type ProjectChannelSummary = ChannelAnalysisResult & {
  channel_username?: string;
  profile_url?: string;
  bio?: string;
};

export type ProjectChannelAnalysisChannel = {
  channel_type: 'telegram' | 'instagram' | 'youtube';
  channel_url: string;
  channel_identifier: string;
  summary: ProjectChannelSummary;
  totals: {
    posts_count: number;
    views: number;
    reactions: number;
    comments: number;
  };
  delta: {
    posts_count: number;
    views: number;
    reactions: number;
    comments: number;
  };
  previous_run_id?: number | null;
  posts: ProjectChannelPostStat[];
};

export interface ProjectChannelAnalysisResult {
  channels: ProjectChannelAnalysisChannel[];
  generated_at?: string;
}

export interface ProjectChannelAnalysisRun {
  id: number;
  task_id?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectChannelAnalysisDetail extends ProjectChannelAnalysisRun {
  result: ProjectChannelAnalysisResult | null;
  error?: string;
}

export interface ProjectChannelAnalysisRunResponse {
  success: boolean;
  task_id?: string;
  run_id?: number;
  error?: string;
}

export interface ProjectChannelTimeseriesChannel {
  key: string;
  channel_type: 'telegram' | 'instagram' | 'youtube';
  channel_identifier: string;
  channel_label: string;
  channel_url?: string;
}

export interface ProjectChannelTimeseriesRun {
  run_id: number;
  created_at: string;
  channels: Array<
    ProjectChannelTimeseriesChannel & {
      totals: {
        posts_count: number;
        views: number;
        reactions: number;
        comments: number;
        subscribers: number;
      };
    }
  >;
}

export interface ProjectChannelTimeseriesResponse {
  runs: ProjectChannelTimeseriesRun[];
  channels: ProjectChannelTimeseriesChannel[];
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
  getAnalysisDetail: async (
    id: string | number,
    options?: { shareToken?: string }
  ): Promise<ChannelAnalysisDetail> => {
    const shareToken = options?.shareToken;
    const query = shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : '';
    return apiFetch<ChannelAnalysisDetail>(`/channel-analyses/${id}/${query}`);
  },

  /**
   * Enable sharing for the analysis and return a share token
   */
  shareAnalysis: async (id: string | number): Promise<ChannelAnalysisShareResponse> => {
    return apiFetch<ChannelAnalysisShareResponse>(`/channel-analyses/${id}/share/`, {
      method: 'POST',
    });
  },

  /**
   * Disable sharing for the analysis
   */
  unshareAnalysis: async (id: string | number): Promise<ChannelAnalysisUnshareResponse> => {
    return apiFetch<ChannelAnalysisUnshareResponse>(`/channel-analyses/${id}/unshare/`, {
      method: 'POST',
    });
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
   * Запуск анализа каналов проекта
   */
  runProjectChannelAnalysis: async (): Promise<ProjectChannelAnalysisRunResponse> => {
    return apiFetch<ProjectChannelAnalysisRunResponse>('/project-analyses/run/', {
      method: 'POST',
    });
  },

  /**
   * История запусков анализа проекта
   */
  listProjectChannelAnalyses: async (): Promise<ProjectChannelAnalysisRun[]> => {
    return apiFetch<ProjectChannelAnalysisRun[]>('/project-analyses/');
  },

  /**
   * Детали запуска анализа проекта
   */
  getProjectChannelAnalysisDetail: async (id: number | string): Promise<ProjectChannelAnalysisDetail> => {
    return apiFetch<ProjectChannelAnalysisDetail>(`/project-analyses/${id}/`);
  },

  /**
   * Последний запуск анализа проекта
   */
  getLatestProjectChannelAnalysis: async (): Promise<ProjectChannelAnalysisDetail | null> => {
    const response = await apiFetch<ProjectChannelAnalysisDetail | undefined>('/project-analyses/latest/');
    return response ?? null;
  },

  /**
   * Временные ряды для графика по каналам проекта
   */
  getProjectChannelTimeseries: async (): Promise<ProjectChannelTimeseriesResponse> => {
    return apiFetch<ProjectChannelTimeseriesResponse>('/project-analyses/timeseries/');
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
