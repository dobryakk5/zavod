// TypeScript types for API models

export type PostStatus = 'draft' | 'ready' | 'approved' | 'scheduled' | 'published';
export type ScheduleStatus = 'pending' | 'in_progress' | 'published' | 'failed';
export type StoryStatus = 'draft' | 'ready' | 'approved' | 'generating_posts' | 'completed';
export type SEOStatus = 'pending' | 'generating' | 'completed' | 'failed';

export type Platform = 'instagram' | 'telegram' | 'youtube';
export type ContentType = string; // Now supports custom types
export type Tone = string; // Now supports custom tones
export type Length = 'short' | 'medium' | 'long';
export type Language = string;

export type TrendSource =
  | 'google_trends'
  | 'google_news_rss'
  | 'telegram'
  | 'youtube'
  | 'rss_feed'
  | 'instagram'
  | 'vkontakte'
  | 'news_api'
  | 'manual';

export type UserRole = 'owner' | 'editor' | 'viewer';

export interface Post {
  id: number;
  title: string;
  status: PostStatus;
  created_at: string;
  platforms?: string[];
}

export interface PostDetail {
  id: number;
  title?: string;
  text?: string;
  image?: string;
  video?: string;
  image_prompt?: string;
  status: PostStatus;
  topic?: number;
  tags?: string[];
  source_links?: string[];
  platforms?: string[];
  publish_text?: boolean;
  publish_image?: boolean;
  publish_video?: boolean;
  story?: number;
  episode_number?: number;
  generated_by?: string;
  regeneration_count?: number;
  scheduled_time?: string;
  created_at: string;
  updated_at?: string;
}

export interface Topic {
  id: number;
  name: string;
  description?: string;
  keywords?: string[];
  is_active: boolean;
  sources?: {
    google_trends?: boolean;
    news_api?: boolean;
    youtube?: boolean;
    telegram?: boolean;
    rss?: boolean;
  };
  created_at: string;
}

export interface TopicDetail extends Topic {
  enabled_sources?: string[];
}

export interface TrendItem {
  id: number;
  topic: number;
  topic_name?: string;
  source: TrendSource;
  title: string;
  description?: string;
  url?: string;
  relevance_score?: number;
  is_used?: boolean;
  used_for_post?: number;
  used_for_post_title?: string;
  discovered_at?: string;
}

export interface TrendItemDetail extends TrendItem {
  extra?: Record<string, unknown>;
}

export interface Story {
  id: number;
  title: string;
  trend_item: number;
  trend_title: string;
  template?: number;
  template_name?: string;
  episode_count: number;
  status: StoryStatus;
  generated_by?: string;
  created_at: string;
}

export interface StoryDetail extends Story {
  episodes: Array<{
    order: number;
    title: string;
  }>;
  updated_at: string;
}

export interface ContentTemplate {
  id: number;
  name: string;
  type: ContentType;
  tone: Tone;
  length: Length;
  language: Language;
  seo_prompt_template: string;
  trend_prompt_template: string;
  additional_instructions: string;
  is_default: boolean;
  include_hashtags: boolean;
  max_hashtags: number;
  created_at: string;
  updated_at: string;
}

export interface Schedule {
  id: number;
  platform: Platform;
  post_title: string;
  scheduled_at: string;
  status: ScheduleStatus;
}

export interface SocialAccount {
  id: number;
  platform: Platform;
  name: string;
  username?: string;
  is_active: boolean;
  extra?: Record<string, unknown>;
  created_at: string;
}

export interface ClientSettings {
  slug?: string;
  timezone?: string;
  avatar?: string;
  logo?: string;
  website?: string;
  description?: string;
  default_language?: string;
  pains?: string;
  desires?: string;
  objections?: string;
  telegram_api_id?: string;
  telegram_api_hash?: string;
  telegram_source_channels?: string;
  rss_source_feeds?: string;
  youtube_api_key?: string;
  youtube_source_channels?: string;
  instagram_access_token?: string;
  instagram_source_accounts?: string;
  vkontakte_access_token?: string;
  vkontakte_source_groups?: string;
}

export interface ClientInfo {
  client: {
    id: number;
    name: string;
    slug: string;
  };
  role: UserRole;
}

export interface ClientSummary {
  total_posts: number;
  posts_scheduled: number;
  posts_published: number;
  by_platform: Array<{
    platform: string;
    count: number;
  }>;
}

export interface TaskResponse {
  success: boolean;
  message: string;
  task_id?: string;
  error?: string;
}

export interface GenerateImageRequest {
  model: 'pollinations' | 'nanobanana' | 'huggingface' | 'flux2';
}

export interface QuickPublishRequest {
  social_account_id: number;
}

export interface GenerateStoryRequest {
  episode_count?: number;
}
