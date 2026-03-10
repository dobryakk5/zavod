import type { Metadata } from 'next';
import { API_BASE_URL } from '@/lib/api';
import {
  findClientSitePageBySlug,
  normalizeClientSitePagesConfig,
  type ClientSitePage,
} from '@/lib/client-site-pages';
import type { ClientSettings } from '@/lib/types';

export type PublicClientSitePagePayload = {
  clientId: number;
  clientName: string;
  settings: Partial<ClientSettings> | null;
  pages: ClientSitePage[];
};

const fetchPublicClientSettings = async (clientId: number): Promise<PublicClientSitePagePayload | null> => {
  const response = await fetch(`${API_BASE_URL}/public/client-page/${clientId}/`, {
    method: 'GET',
    cache: 'no-store',
  });
  if (!response.ok) {
    return null;
  }

  const payload = (await response.json()) as {
    client?: { id?: number; name?: string };
    settings?: Partial<ClientSettings> | null;
  };
  const resolvedId = Number(payload?.client?.id ?? clientId);
  if (!Number.isFinite(resolvedId) || resolvedId <= 0) {
    return null;
  }

  const settings = payload?.settings ?? null;
  const config = normalizeClientSitePagesConfig(settings?.client_page_config);

  return {
    clientId: resolvedId,
    clientName: String(payload?.client?.name || '').trim(),
    settings,
    pages: config.site_pages,
  };
};

export const getPublicClientSitePagePayload = fetchPublicClientSettings;

export const resolvePublicClientSitePage = async (
  clientId: number,
  slug?: string | null,
): Promise<{ payload: PublicClientSitePagePayload; page: ClientSitePage } | null> => {
  const payload = await fetchPublicClientSettings(clientId);
  if (!payload || !payload.pages.length) {
    return null;
  }
  const page = findClientSitePageBySlug(payload.pages, slug);
  if (!page) {
    return null;
  }
  return { payload, page };
};

export const buildSitePageMetadata = (page: ClientSitePage, fallbackTitle?: string): Metadata => {
  const title = page.title.trim() || fallbackTitle || 'Страница';
  const description = (page.meta_description || '').trim();
  const ogImage = (page.og_image || '').trim();

  const metadata: Metadata = {
    title,
  };

  if (description) {
    metadata.description = description;
  }

  if (ogImage) {
    metadata.openGraph = {
      title,
      description: description || undefined,
      images: [{ url: ogImage }],
    };
    metadata.twitter = {
      card: 'summary_large_image',
      title,
      description: description || undefined,
      images: [ogImage],
    };
  }

  return metadata;
};
