import { apiFetch } from '../api';

export type TgstatCategory = {
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

export const tgstatApi = {
  listCategories() {
    return apiFetch<TgstatCategory[]>('/tgstat/categories/');
  },
  listTags(categorySlug: string) {
    return apiFetch<TgstatTag[]>(`/tgstat/tags/?category=${encodeURIComponent(categorySlug)}`);
  },
  listChannels(tagSlug: string) {
    return apiFetch<TgstatChannel[]>(`/tgstat/channels/?tag=${encodeURIComponent(tagSlug)}`);
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
};
