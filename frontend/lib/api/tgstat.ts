import { apiFetch } from '../api';

export type TgstatCategory = {
  id: number;
  slug: string;
  title: string;
  url: string;
};

export type TgstatTag = {
  slug: string;
  title: string;
  url: string;
  category_slug: string;
  more_channels_count?: number | null;
};

export type TgstatChannel = {
  id: number;
  tag_slug: string;
  tag_id?: number | null;
  username?: string | null;
  title?: string | null;
  subscribers?: number | null;
  url?: string | null;
};

export type TgstatRecommendationTag = {
  slug: string;
  title: string;
  reason?: string | null;
};

export type TgstatRecommendationCategory = {
  category_slug: string;
  category_title: string;
  tags: TgstatRecommendationTag[];
};

export type TgstatRecommendationResponse = {
  success: boolean;
  niche?: string;
  product_service?: string;
  recommendations: TgstatRecommendationCategory[];
  error?: string;
  details?: string;
};

export const tgstatApi = {
  listCategories() {
    return apiFetch<TgstatCategory[]>('/tgstat/categories/');
  },
  listTags(categoryId: number) {
    return apiFetch<TgstatTag[]>(`/tgstat/tags/?category_id=${encodeURIComponent(categoryId)}`);
  },
  listChannels(tagSlug: string) {
    return apiFetch<TgstatChannel[]>(`/tgstat/channels/?tag=${encodeURIComponent(tagSlug)}`);
  },
  listChannelsByCategory(categoryId: number) {
    return apiFetch<TgstatChannel[]>(`/tgstat/channels/?category_id=${encodeURIComponent(categoryId)}`);
  },
  getRecommendations() {
    return apiFetch<TgstatRecommendationResponse>('/tgstat/recommendations/', {
      method: 'POST',
    });
  },
  listFavorites() {
    return apiFetch<TgstatChannel[]>('/tgstat/favorites/');
  },
  addFavorite(channelId: number) {
    return apiFetch<{ success: boolean; tgstat_channels: number[] }>('/tgstat/favorites/', {
      method: 'POST',
      body: {
        channel_id: channelId,
      },
    });
  },
  removeFavorite(channelId: number) {
    return apiFetch<{ success: boolean; tgstat_channels: number[] }>('/tgstat/favorites/', {
      method: 'DELETE',
      body: {
        channel_id: channelId,
      },
    });
  },
};
