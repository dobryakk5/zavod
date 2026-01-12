import { apiFetch } from '../api';
import type { Article, ArticleBlock, ArticleSeoEvaluationResponse, TaskResponse } from '../types';

export const articlesApi = {
  list: async (): Promise<Article[]> => {
    return apiFetch<Article[]>('/articles/');
  },

  get: async (id: number): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/`);
  },

  start: async (phrase: string): Promise<Article> => {
    return apiFetch<Article>('/articles/start/', {
      method: 'POST',
      body: { phrase },
    });
  },

  generateContext: async (id: number, payload: { force?: boolean } = {}): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/generate_context/`, {
      method: 'POST',
      body: payload,
    });
  },

  generateOutline: async (
    id: number,
    payload: {
      selected_why_now: string[];
      selected_solution: string[];
      tripwire_product_id?: number | null;
      tripwire_product_name?: string | null;
      lead_product_id?: number | null;
      lead_product_name?: string | null;
    }
  ): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/generate_outline/`, {
      method: 'POST',
      body: payload,
    });
  },

  saveChoices: async (
    id: number,
    payload: {
      selected_why_now: string[];
      selected_solution: string[];
      tripwire_product_id?: number | null;
      tripwire_product_name?: string | null;
      lead_product_id?: number | null;
      lead_product_name?: string | null;
    }
  ): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/save_choices/`, {
      method: 'POST',
      body: payload,
    });
  },

  updateWordstat: async (id: number, wordstat: string): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/update_wordstat/`, {
      method: 'POST',
      body: { wordstat },
    });
  },

  updateAudience: async (id: number, audience: string): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/update_audience/`, {
      method: 'POST',
      body: { audience },
    });
  },

  updateOutline: async (id: number, outline_markdown: string): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/update_outline/`, {
      method: 'POST',
      body: { outline_markdown },
    });
  },

  generateSeoBlocks: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/articles/${id}/generate_seo_blocks/`, {
      method: 'POST',
      body: {},
    });
  },

  generateBlocks: async (id: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/articles/${id}/generate_blocks/`, {
      method: 'POST',
      body: {},
    });
  },

  saveSeoBlocks: async (id: number, seo_blocks: Record<string, unknown>): Promise<Article> => {
    return apiFetch<Article>(`/articles/${id}/save_seo_blocks/`, {
      method: 'POST',
      body: { seo_blocks },
    });
  },

  listBlocks: async (id: number): Promise<ArticleBlock[]> => {
    return apiFetch<ArticleBlock[]>(`/articles/${id}/blocks/`);
  },

  updateBlock: async (
    articleId: number,
    payload: {
      block_id: number;
      h2_title?: string;
      subquery?: string;
      micro_intent?: string;
      keywords?: string[];
      key_points?: string;
      content?: string;
      prompt_template?: string;
    }
  ): Promise<ArticleBlock> => {
    return apiFetch<ArticleBlock>(`/articles/${articleId}/blocks_update/`, {
      method: 'POST',
      body: payload,
    });
  },

  generateBlock: async (articleId: number, blockId: number): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/articles/${articleId}/blocks_generate/`, {
      method: 'POST',
      body: { block_id: blockId },
    });
  },

  generationStatus: async (taskId: string): Promise<TaskResponse> => {
    return apiFetch<TaskResponse>(`/articles/generation-status/?task_id=${encodeURIComponent(taskId)}`);
  },

  evaluate: async (payload: {
    text?: string;
    url?: string;
    wordstat?: string;
    action?: 'analyze' | 'recommend' | 'rewrite';
  }): Promise<ArticleSeoEvaluationResponse> => {
    return apiFetch<ArticleSeoEvaluationResponse>('/articles/evaluate/', {
      method: 'POST',
      body: payload,
    });
  },
};
