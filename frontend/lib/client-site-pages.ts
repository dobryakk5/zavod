import {
  createDefaultClientPageTemplateConfig,
  normalizeClientPageTemplateConfig,
  type ClientPageTemplateConfig,
} from '@/lib/client-page-template';

export type ClientSitePage = {
  id: string;
  title: string;
  slug: string;
  meta_description?: string;
  og_image?: string;
  template_config: ClientPageTemplateConfig;
};

export type ClientSitePagesConfig = {
  site_pages: ClientSitePage[];
};

export const RESERVED_SITE_PAGE_SLUGS = new Set([
  'events',
  'products',
  'tasks',
  'edit',
  'quiz',
  'login',
  'logout',
  'api',
  'admin',
  'settings',
]);

const SITE_PAGE_TITLE_FALLBACK = 'Новая страница';

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
};

const ensureSitePageId = (rawValue: unknown, index: number): string => {
  const value = typeof rawValue === 'string' ? rawValue.trim() : '';
  if (value) {
    return value;
  }
  return `site-page-${index + 1}`;
};

const normalizePageTitle = (rawValue: unknown): string => {
  const value = typeof rawValue === 'string' ? rawValue.trim() : '';
  return value || SITE_PAGE_TITLE_FALLBACK;
};

const normalizeMetaText = (rawValue: unknown): string => {
  return typeof rawValue === 'string' ? rawValue.trim() : '';
};

const normalizeSlugValue = (rawValue: unknown): string => {
  return typeof rawValue === 'string' ? rawValue.trim().toLowerCase() : '';
};

export const slugifySitePageTitle = (rawValue: string): string => {
  const normalized = rawValue
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9\-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');

  return normalized;
};

export const isReservedSitePageSlug = (slug: string): boolean => {
  return RESERVED_SITE_PAGE_SLUGS.has(slug.trim().toLowerCase());
};

export const normalizeClientSitePage = (value: unknown, index: number): ClientSitePage | null => {
  if (!isRecord(value)) {
    return null;
  }

  const isHome = index === 0;
  const slug = isHome ? '' : normalizeSlugValue(value.slug);
  const title = normalizePageTitle(value.title);
  const templateConfig = normalizeClientPageTemplateConfig(value.template_config);

  return {
    id: ensureSitePageId(value.id, index),
    title,
    slug,
    meta_description: normalizeMetaText(value.meta_description),
    og_image: normalizeMetaText(value.og_image),
    template_config: templateConfig,
  };
};

export const normalizeClientSitePagesConfig = (value: unknown): ClientSitePagesConfig => {
  if (!isRecord(value)) {
    return { site_pages: [] };
  }

  const rawPages = Array.isArray(value.site_pages) ? value.site_pages : [];
  const pages = rawPages
    .map((item, index) => normalizeClientSitePage(item, index))
    .filter((item): item is ClientSitePage => item !== null);

  return {
    site_pages: pages.map((page, index) => ({
      ...page,
      slug: index === 0 ? '' : page.slug,
    })),
  };
};

export const createSitePageId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `site-page-${Date.now()}`;
};

export const createDefaultClientSitePage = (input?: Partial<ClientSitePage>): ClientSitePage => {
  return {
    id: input?.id?.trim() || createSitePageId(),
    title: input?.title?.trim() || SITE_PAGE_TITLE_FALLBACK,
    slug: input?.slug?.trim().toLowerCase() || '',
    meta_description: input?.meta_description?.trim() || '',
    og_image: input?.og_image?.trim() || '',
    template_config: normalizeClientPageTemplateConfig(input?.template_config ?? createDefaultClientPageTemplateConfig()),
  };
};

export const findClientSitePageBySlug = (
  pages: ClientSitePage[],
  slug: string | null | undefined,
): ClientSitePage | null => {
  if (!pages.length) {
    return null;
  }

  const normalizedSlug = normalizeSlugValue(slug);
  if (!normalizedSlug) {
    return pages[0] || null;
  }

  return pages.find((page, index) => index > 0 && page.slug === normalizedSlug) || null;
};

export const findClientSitePageById = (
  pages: ClientSitePage[],
  pageId: string | null | undefined,
): ClientSitePage | null => {
  const normalizedId = typeof pageId === 'string' ? pageId.trim() : '';
  if (!normalizedId) {
    return null;
  }
  return pages.find((page) => page.id === normalizedId) || null;
};

export const buildSitePagePublicPath = (clientId: number, slug: string, useCustomDomainPaths: boolean): string => {
  const normalizedSlug = normalizeSlugValue(slug);
  if (useCustomDomainPaths) {
    return normalizedSlug ? `/${normalizedSlug}` : '/';
  }
  return normalizedSlug ? `/c/${clientId}/${normalizedSlug}` : `/c/${clientId}`;
};

export const validateSitePages = (pages: ClientSitePage[]): string | null => {
  if (!pages.length) {
    return 'Добавьте хотя бы одну страницу.';
  }

  const seen = new Set<string>();
  for (const [index, page] of pages.entries()) {
    const title = page.title.trim();
    if (!title) {
      return `Заполните название страницы #${index + 1}.`;
    }

    if (index === 0) {
      if (page.slug.trim()) {
        return 'У главной страницы slug должен быть пустым.';
      }
      continue;
    }

    const slug = page.slug.trim().toLowerCase();
    if (!slug) {
      return `Заполните slug страницы «${title}».`;
    }
    if (isReservedSitePageSlug(slug)) {
      return `Slug «${slug}» зарезервирован.`;
    }
    if (seen.has(slug)) {
      return `Slug «${slug}» уже используется.`;
    }
    seen.add(slug);
  }

  return null;
};

export const validateSingleSitePageSlug = (
  pages: ClientSitePage[],
  pageId: string,
  slug: string,
): string | null => {
  const normalizedSlug = slug.trim().toLowerCase();
  if (!normalizedSlug) {
    return 'Slug обязателен.';
  }
  if (isReservedSitePageSlug(normalizedSlug)) {
    return `Slug «${normalizedSlug}» зарезервирован.`;
  }
  const duplicate = pages.some((page, index) => index > 0 && page.id !== pageId && page.slug === normalizedSlug);
  if (duplicate) {
    return `Slug «${normalizedSlug}» уже используется.`;
  }
  return null;
};

export const createNewSitePageDraft = (index: number): ClientSitePage => {
  return createDefaultClientSitePage({
    title: index === 0 ? 'Главная' : 'Новая страница',
    slug: index === 0 ? '' : 'new-page',
  });
};
