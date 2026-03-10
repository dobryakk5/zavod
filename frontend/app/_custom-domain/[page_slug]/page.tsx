import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ContactClientPage from '@/app/c/[client_id]/page-client';
import { resolveCustomDomainClientId } from '../_domain-resolver';
import { buildSitePageMetadata, resolvePublicClientSitePage } from '@/lib/server/client-site-pages';

type CustomDomainSitePageProps = {
  params: Promise<{ page_slug: string }>;
};

export async function generateMetadata({ params }: CustomDomainSitePageProps): Promise<Metadata> {
  const { page_slug: pageSlug } = await params;
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    return {};
  }
  const resolved = await resolvePublicClientSitePage(clientId, pageSlug);
  if (!resolved) {
    return {};
  }
  return buildSitePageMetadata(resolved.page, resolved.payload.clientName);
}

export default async function CustomDomainSitePage({ params }: CustomDomainSitePageProps) {
  const { page_slug: pageSlug } = await params;
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  const resolved = await resolvePublicClientSitePage(clientId, pageSlug);
  if (!resolved) {
    notFound();
  }
  return <ContactClientPage resolvedClientId={clientId} useCustomDomainPaths pageSlug={pageSlug} />;
}
