import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ContactClientPage from '../page-client';
import { buildSitePageMetadata, resolvePublicClientSitePage } from '@/lib/server/client-site-pages';

type ClientSitePageRouteProps = {
  params: Promise<{ client_id: string; page_slug: string }>;
};

export async function generateMetadata({ params }: ClientSitePageRouteProps): Promise<Metadata> {
  const { client_id: rawClientId, page_slug: pageSlug } = await params;
  const clientId = Number(rawClientId);
  if (!Number.isFinite(clientId) || clientId <= 0) {
    return {};
  }
  const resolved = await resolvePublicClientSitePage(clientId, pageSlug);
  if (!resolved) {
    return {};
  }
  return buildSitePageMetadata(resolved.page, resolved.payload.clientName);
}

export default async function ClientSitePageRoute({ params }: ClientSitePageRouteProps) {
  const { client_id: rawClientId, page_slug: pageSlug } = await params;
  const clientId = Number(rawClientId);
  if (!Number.isFinite(clientId) || clientId <= 0) {
    notFound();
  }
  const resolved = await resolvePublicClientSitePage(clientId, pageSlug);
  if (!resolved) {
    notFound();
  }
  return <ContactClientPage resolvedClientId={clientId} pageSlug={pageSlug} />;
}
