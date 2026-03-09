import { headers } from 'next/headers';
import { getCustomDomainFromHeader, resolveClientIdByCustomDomain } from '@/lib/server/custom-domain';

export const resolveCustomDomainClientId = async (): Promise<number | null> => {
  const headerBag = await headers();
  const domain = getCustomDomainFromHeader(headerBag);
  if (!domain) {
    return null;
  }
  return resolveClientIdByCustomDomain(domain);
};
