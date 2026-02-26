// TypeScript types for API models

export type PostStatus = 'draft' | 'ready' | 'approved' | 'scheduled' | 'published';
export type ScheduleStatus = 'pending' | 'in_progress' | 'published' | 'failed';
export type StoryStatus = 'draft' | 'ready' | 'approved' | 'generating_posts' | 'completed';
export type SEOStatus = 'pending' | 'generating' | 'completed' | 'failed';
export type ProductStatus = 'draft' | 'active';
export type ArticleStatus =
  | 'wordstat'
  | 'context_suggested'
  | 'context_selected'
  | 'outline_ready'
  | 'article_ready'
  | 'result_edited'
  | 'failed';

export type Platform = 'instagram' | 'telegram' | 'youtube' | 'vkontakte' | 'rss_zen';
export type ContentType = string; // Now supports custom types
export type Tone = string; // Now supports custom tones
export type Length = number;
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

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Post {
  id: number;
  title: string;
  hook_title?: string;
  status: PostStatus;
  created_at: string;
  platforms?: string[];
  template_name?: string | null;
  has_images?: boolean;
  has_videos?: boolean;
  next_scheduled_at?: string | null;
}

export interface Article {
  id: number;
  wordstat: string;
  wordstat_phrases?: string[];
  status: ArticleStatus;
  audience?: string | null;
  options_why_now?: string[];
  options_solution?: string[];
  selected_why_now?: string[];
  selected_solution?: string[];
  tripwire_product_id?: number | null;
  tripwire_product_name?: string | null;
  lead_product_id?: number | null;
  lead_product_name?: string | null;
  seo_blocks?: Record<
    string,
    {
      h2_title?: string;
      subquery?: string;
      keywords?: string[];
      micro_intent?: string;
      key_points?: string[] | string;
    }
  >;
  outline_markdown?: string;
  result_html?: string;
  created_at: string;
  updated_at?: string;
}

export type ArticleBlockStatus = 'draft' | 'blueprint_ready' | 'ready' | 'failed';

export interface ArticleBlock {
  id: number;
  order: number;
  block_key: string;
  h2_title: string;
  subquery: string;
  micro_intent: string;
  keywords: string[];
  key_points: string;
  prompt_template: string;
  prompt_used?: string | null;
  content: string;
  status: ArticleBlockStatus;
  regeneration_count: number;
  created_at: string;
  updated_at?: string;
}

export type BookSemanticsResponse = {
  success: boolean;
  saved?: boolean;
  semantic_set_id?: number;
  keywords_count?: number;
  groups_count?: number;
  error?: string;
};

export type ArticleSeoKeywordStat = {
  phrase: string;
  count?: number;
  freq?: number;
  cluster?: string | null;
};

export type ArticleSeoClusterCoverage = {
  cluster: string;
  found: number;
  total: number;
};

export type ArticleSeoAnalysis = {
  coverage_percent: number;
  total_keywords: number;
  found_keywords: ArticleSeoKeywordStat[];
  missing_keywords: ArticleSeoKeywordStat[];
  cluster_coverage: ArticleSeoClusterCoverage[];
  word_count: number;
};

export type ArticleSeoAiResult = {
  intent?: string;
  strengths?: string[];
  gaps?: string[];
  recommendations?: string[];
  keyword_advice?: {
    include?: string[];
    exclude?: string[];
    separate_article?: string[];
  };
  rewrite_plan?: {
    h1?: string;
    h2?: string[];
    h3?: string[];
    add_blocks?: string[];
    notes?: string[];
  };
  rewrite_text?: string;
};

export type ArticleSeoEvaluationResponse = {
  success: boolean;
  analysis: ArticleSeoAnalysis;
  source?: {
    url?: string;
    title?: string;
    meta_description?: string;
    headings?: Record<string, unknown>;
  };
  main_query?: string;
  ai?: ArticleSeoAiResult;
};

export interface PostMediaImage {
  id: number;
  image: string;
  alt_text?: string;
  order: number;
  created_at: string;
  updated_at: string;
  width?: number;
  height?: number;
}

export interface PostMediaVideo {
  id: number;
  video: string;
  caption?: string;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface PostDetail {
  id: number;
  title?: string;
  hook_title?: string;
  text?: string;
  image?: string;
  video?: string;
  image_prompt?: string;
  status: PostStatus;
  topic?: number;
  tags?: string[];
  source_links?: string[];
  wordstat_phrases_used?: string[];
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
  template?: number | null;
  template_name?: string | null;
  template_type?: string | null;
  images?: PostMediaImage[];
  videos?: PostMediaVideo[];
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
  is_system?: boolean;
  created_at: string;
  updated_at: string;
}

export interface Schedule {
  id: number;
  post: number;
  social_account: number;
  social_account_name?: string;
  platform: Platform;
  post_title: string;
  scheduled_at: string;
  status: ScheduleStatus;
}

export interface TelegramTask {
  id: number;
  contact_name: string | null;
  tg_name: string;
  message_text: string;
  received_at: string;
  rating: number | null;
}

export type OperatorTaskStatus = 'open' | 'in_progress' | 'done';

export interface OperatorTask {
  id: number;
  level_id: number | null;
  title: string;
  description: string | null;
  status: OperatorTaskStatus;
  priority: 1 | 2 | 3;
  created_by: number;
  created_by_username?: string | null;
  created_at: string;
  updated_at: string;
  history?: OperatorTaskHistory[];
}

export interface OperatorTaskHistory {
  id: number;
  task_id: number;
  note: string;
  status: OperatorTaskStatus | null;
  created_by: number;
  created_by_username?: string | null;
  created_at: string;
}

export interface SocialAccount {
  id: number;
  platform: Platform;
  name: string;
  access_token?: string;
  username?: string;
  is_active: boolean;
  extra?: Record<string, unknown>;
  created_at: string;
}

export interface VkIntegration {
  id: number;
  group_id: number;
  group_name?: string;
  screen_name?: string;
  status?: string;
  last_published_at?: string | null;
  created_at: string;
  updated_at?: string;
  owner_name?: string;
  owner_id?: number;
  extra?: Record<string, unknown>;
}

export interface ProductPackageConfig {
  name: string;
  description?: string | null;
  price?: number | null;
  kind?: 'regular' | 'service_package' | string | null;
  service_unit?: 'sessions' | 'minutes' | string | null;
  service_quantity?: number | null;
}

export interface ClientProduct {
  id: number;
  name: string;
  status?: ProductStatus;
  product_type_id?: number | null;
  product_type_name?: string | null;
  product_type?: ProductType | null;
  short_description?: string | null;
  digital_product_document_id?: number | null;
  digital_product_document_title?: string | null;
  packages?: ProductPackageConfig[] | null;
  structure?: ProductStructure | null;
  owner_id?: number;
  created_at?: string;
  updated_at?: string;
}

// ============================================================================
// Knowledge base
// ============================================================================

export interface KbUser {
  id: number;
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
}

export interface KbFolder {
  id: number;
  name: string;
  workspace: number;
  parent?: number | null;
  created_by?: KbUser | null;
  created_at: string;
  updated_at: string;
  position: number;
  documents_count?: number;
  subfolders_count?: number;
  children?: KbFolder[];
}

export interface KbTag {
  id: number;
  name: string;
  color?: string | null;
  workspace: number;
  created_at: string;
}

export interface KbDocumentList {
  id: number;
  title: string;
  icon?: string | null;
  cover_image?: string | null;
  document_type?: 'page' | 'product' | string;
  workspace: number;
  folder?: number | null;
  parent_document?: number | null;
  created_by?: KbUser | null;
  last_edited_by?: KbUser | null;
  created_at: string;
  updated_at: string;
  is_published: boolean;
  is_archived: boolean;
  is_template: boolean;
  position: number;
  tags?: KbTag[];
  child_count?: number;
  has_children?: boolean;
}

export interface KbDocumentDetail extends KbDocumentList {
  content: Record<string, unknown> | null;
  child_documents?: KbDocumentList[];
}

export interface KbDocumentVersion {
  id: number;
  document: number;
  content: Record<string, unknown> | null;
  title?: string | null;
  created_by?: KbUser | null;
  created_at: string;
  version_number: number;
}

export interface KbComment {
  id: number;
  document: number;
  parent_comment?: number | null;
  content: string;
  block_id?: string | null;
  created_by?: KbUser | null;
  created_at: string;
  updated_at: string;
  is_resolved: boolean;
  replies?: KbComment[];
  replies_count?: number;
}

export interface KbDocumentShare {
  id: number;
  document: number;
  share_token: string;
  permission: 'view' | 'comment' | 'edit';
  password?: string | null;
  expires_at?: string | null;
  created_by?: KbUser | null;
  created_at: string;
  is_active: boolean;
  visit_count: number;
  share_url: string;
  document_detail?: KbDocumentDetail;
}

export interface KbLinkPreview {
  title: string;
  description: string;
  favicon: string;
  url: string;
}

export interface ProductType {
  id: number;
  name: string;
  value?: string | null;
  goal?: string | null;
  requirements_name?: string | null;
  requirements_packages?: string | null;
  requirements_audience?: string | null;
  requirements_transformation?: string | null;
  requirements_metrics?: string | null;
  requirements_method?: string | null;
  requirements_lesson_format?: string | null;
  requirements_program_modules?: string | null;
  requirements_packaging?: string | null;
  owner_id?: number;
  is_deletable?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProductStructure {
  audience?: Array<{ parameter: string; value: string }>;
  transformation?: Array<{ was: string; became: string }>;
  metrics?: Array<{ metric: string; promise: string }>;
  method?: Array<{ component: string; template: string }>;
  lesson_format?: Array<{ stage: string; percent: number | null }>;
  program_modules?: Array<{ module: string; result: string }>;
  packaging?: { name?: string | null; slogan?: string | null; promise?: string | null };
  related_products?: Array<{
    id: number;
    name: string;
    product_type_id?: number | null;
    product_type_name?: string | null;
    short_description?: string | null;
  }>;
}

// Mind map domain
export interface MindMap {
  id: number;
  title: string;
  description?: string | null;
  type?: 'product' | 'website' | string;
  is_public: boolean;
  owner_id?: number;
  created_at?: string;
  updated_at?: string;
  nodes_count?: number;
  edges_count?: number;
}

export interface MindNodePosition {
  layout_name?: string;
  x: number;
  y: number;
}

export interface MindNode {
  id: string;
  map_id: number;
  text: string;
  color?: string | null;
  shape?: string | null;
  meta?: Record<string, unknown>;
  position?: MindNodePosition;
  created_at?: string;
  updated_at?: string;
  properties?: MindNodeProperty[];
}

export interface MindEdge {
  id?: number | string;
  map_id: number;
  from_node_id: string;
  to_node_id: string;
  type?: string;
  label?: string | null;
  meta?: Record<string, unknown>;
  created_at?: string;
}

export interface MindMapDetail extends MindMap {
  nodes: MindNode[];
  edges: MindEdge[];
}

export interface MindNodeProperty {
  id: number;
  node_id: string;
  title: string;
  value: string;
  delta?: string | null;
  order_index?: number;
  meta?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface ClientSettings {
  slug?: string;
  rag_assistant_enabled?: boolean;
  brand_name?: string;
  niche?: string;
  product_service?: string;
  client_page_config?: Record<string, unknown>;
  client_page_content?: Record<string, unknown>;
  timezone?: string;
  avatar?: string;
  pains?: string;
  desires?: string;
  objections?: string;
  expert_books?: string;
  telegram_client_channel?: string;
  logo?: string;
  website?: string;
  ai_analysis_channel_url?: string;
  ai_analysis_channel_type?: string;
  project_telegram_channel?: string;
  project_instagram_channel?: string;
  project_youtube_channel?: string;
  telegram_source_channels?: string;
  rss_source_feeds?: string;
  youtube_source_channels?: string;
  instagram_source_accounts?: string;
  vkontakte_source_groups?: string;
  last_image_generation_at?: string | null;
  last_video_generation_at?: string | null;
}

export interface ExpertBookItem {
  title: string;
  author?: string;
  reason?: string;
}

export interface ExpertBooksResponse {
  success: boolean;
  books?: ExpertBookItem[];
  text?: string;
  error?: string;
  saved?: boolean;
}

export interface ClientInfo {
  client: {
    id: number;
    name: string;
    slug: string;
    last_image_generation_at?: string | null;
    last_video_generation_at?: string | null;
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

export type GenerationEventType =
  | 'post'
  | 'article_write'
  | 'article_evaluate'
  | 'channel_analysis'
  | 'website_analysis'
  | 'weekly_collection'
  | 'seo_group'
  | 'wordstat_query'
  | 'google_query'
  | 'product'
  | 'product_map'
  | 'book_search'
  | 'semantic_phrases';

export interface GenerationEventSummary {
  counts: Partial<Record<GenerationEventType, number>>;
  limits: Partial<Record<GenerationEventType, number>>;
  is_trial: boolean;
}

export interface TaskResponse {
  success: boolean;
  message: string;
  task_id?: string;
  error?: string;
  status?: string;
}

export interface ProductGenerationResponse {
  success: boolean;
  message?: string;
  task_id?: string;
  error?: string;
  status?: string;
  result?: Record<string, unknown>;
  product?: ClientProduct;
}

export type SEOGroupType = 'seo_pains' | 'seo_desires' | 'seo_objections' | 'seo_avatar' | 'seo_keywords' | '';

export type WordstatResultType = 'top_request' | 'association' | 'favorite' | 'skip';

export interface WordstatResult {
  id: number;
  phrase: string;
  count: number;
  result_type: WordstatResultType;
  used_in_post: number;
  cluster?: number | null;
  cluster_name?: string | null;
}

export interface WordstatCluster {
  id: number;
  name: string;
  is_main?: boolean;
  phrases_count?: number;
  created_at?: string;
}

export interface WordstatQuery {
  id: number;
  client: number;
  group_name?: string;
  phrases: string[];
  request_phrase: string;
  total_count: number;
  include_parent: boolean;
  regions?: number[];
  devices?: string[];
  user_login?: string;
  limit_per_second?: number | null;
  daily_limit?: number | null;
  daily_limit_remaining?: number | null;
  created_at: string;
  results: WordstatResult[];
}

export interface SEOKeywordSet {
  id: number;
  client: number;
  client_name?: string;
  group_type: SEOGroupType;
  topic?: number | null;
  topic_name?: string | null;
  status: SEOStatus;
  keywords_list: string[];
  keyword_groups: Record<string, string[]>;
  ai_model?: string;
  prompt_used?: string;
  error_log?: string;
  created_at: string;
}

export type SemanticGroupScope = 'narrow' | 'normal' | 'wide' | string;
export type SemanticGroupStatus = 'draft' | 'approved' | 'archived' | string;
export type SemanticGroupSource = 'ai' | 'manual' | string;

export interface SemanticGroup {
  id: number;
  client: number;
  client_name?: string;
  parent?: number | null;
  name: string;
  description?: string;
  source_books?: string[];
  scope: SemanticGroupScope;
  expected_clusters?: number | null;
  status: SemanticGroupStatus;
  source: SemanticGroupSource;
  clusters_count?: number;
  created_at: string;
  updated_at: string;
}

export type SemanticClusterIntent = 'info' | 'commercial' | 'navigational' | 'brand' | string;

export interface SemanticCluster {
  id: number;
  client: number;
  semantic_group: number;
  name: string;
  description?: string;
  main_keyword?: string;
  intent?: SemanticClusterIntent;
  user_goal?: string;
  cta?: string;
  priority?: number | null;
  page_type?: string;
  url?: string;
  status?: string;
  phrases_count?: number;
  created_at: string;
  updated_at: string;
}

export type SemanticPhraseType = 'key' | 'lsi' | 'wordstat' | 'association' | string;

export interface SemanticPhrase {
  id: number;
  client: number;
  phrase: string;
  raw_phrase?: string | null;
  normalized_phrase?: string | null;
  comment?: string;
  type: SemanticPhraseType;
  intent?: SemanticClusterIntent;
  source?: string;
  frequency?: number | null;
  wordstat_id?: number | null;
  competition?: number | null;
  created_at: string;
  updated_at: string;
}

export type ProjectSemanticSource = 'expert_books' | string;

export interface ProjectSemanticSet {
  id: number;
  client: number;
  client_name?: string;
  source: ProjectSemanticSource;
  status: SEOStatus;
  books_text?: string;
  keywords_list: string[];
  keyword_groups: Record<string, string[]>;
  ai_model?: string;
  prompt_used?: string;
  error_log?: string;
  created_at: string;
  updated_at: string;
}

export interface GoogleCseSearchResult {
  position: number;
  title: string;
  url: string;
  domain: string;
  snippet?: string;
}

export interface GoogleCseSearchResponse {
  query: string;
  results: GoogleCseSearchResult[];
}

export interface GoogleCompetitorAiResult {
  input_url: string;
  base_url: string;
  is_competitor: boolean;
  one_liner: string;
  offers: string[];
  pricing: string;
  services_url?: string | null;
  prices_url?: string | null;
  evidence_urls: string[];
  error?: string | null;
}

export interface GoogleCompetitorsResolvedRow {
  position: number;
  title: string;
  url: string;
  domain: string;
  base_url: string;
  cached: boolean;
  analysis_status: 'pending' | 'in_progress' | 'completed' | 'failed' | string;
  analysis_error?: string;
  last_seen_query?: string;
  manual_category?: 'competitor' | 'informational' | 'indirect' | 'other' | null;
  manual_is_competitor?: boolean | null;
  is_competitor: boolean;
  one_liner: string;
  pricing: string;
  home_title: string;
  home_text: string;
  services_url?: string | null;
  prices_url?: string | null;
}

export interface GoogleCompetitorsResolveResponse {
  query: string;
  scheduled?: number;
  results: GoogleCompetitorsResolvedRow[];
}

export interface GoogleCompetitorsAnalyzeResponse {
  results: GoogleCompetitorAiResult[];
}

export interface GoogleCompetitorsStoreResponse {
  success: boolean;
  query: string;
  domains_seen: number;
  created: number;
  updated: number;
}

export interface GoogleCompetitorSiteRow {
  domain: string;
  base_url: string;
  first_seen_query: string;
  last_seen_query: string;
  created_at: string;
  updated_at: string;
}

export interface GoogleCompetitorSiteListResponse {
  results: GoogleCompetitorSiteRow[];
}


export interface GenerateVideoRequest {
  source?: 'image' | 'text';
  method?: 'wan' | 'veo';
}

export interface QuickPublishRequest {
  social_account_id: number;
}

export interface GenerateStoryRequest {
  episode_count?: number;
}
