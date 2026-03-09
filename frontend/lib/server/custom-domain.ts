import { API_BASE_URL } from '@/lib/api';

const DOMAIN_RE = /^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$/;

export const normalizeDomain = (rawValue: string | null | undefined): string | null => {
  const value = String(rawValue || '').trim().toLowerCase().replace(/\.$/, '');
  if (!value || !DOMAIN_RE.test(value)) {
    return null;
  }
  return value;
};

export const getCustomDomainFromHeader = (headersValue: Headers): string | null => {
  const headerValue = headersValue.get('x-custom-domain');
  return normalizeDomain(headerValue);
};

export const resolveClientIdByCustomDomain = async (domain: string): Promise<number | null> => {
  const normalized = normalizeDomain(domain);
  if (!normalized) {
    return null;
  }

  const requestUrl = `${API_BASE_URL}/public/client-page/by-domain/?domain=${encodeURIComponent(normalized)}`;
  const response = await fetch(requestUrl, {
    method: 'GET',
    cache: 'no-store',
  });
  if (!response.ok) {
    return null;
  }
  const payload = (await response.json()) as { client?: { id?: number } };
  const candidate = Number(payload?.client?.id);
  if (!Number.isFinite(candidate) || candidate <= 0) {
    return null;
  }
  return candidate;
};
