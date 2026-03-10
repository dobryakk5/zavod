import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ContactClientPage from '@/app/c/[client_id]/page-client';
import { resolveCustomDomainClientId } from './_domain-resolver';
import { buildSitePageMetadata, resolvePublicClientSitePage } from '@/lib/server/client-site-pages';

export async function generateMetadata(): Promise<Metadata> {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    return {};
  }
  const resolved = await resolvePublicClientSitePage(clientId, '');
  if (!resolved) {
    return {};
  }
  return buildSitePageMetadata(resolved.page, resolved.payload.clientName);
}

export default async function CustomDomainHomePage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  const resolved = await resolvePublicClientSitePage(clientId, '');
  if (!resolved) {
    notFound();
  }
  return <ContactClientPage resolvedClientId={clientId} useCustomDomainPaths />;
}
