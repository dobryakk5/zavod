import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ContactClientPage from './page-client';
import { buildSitePageMetadata, resolvePublicClientSitePage } from '@/lib/server/client-site-pages';

type ContactClientPageRouteProps = {
  params: Promise<{ client_id: string }>;
};

export async function generateMetadata({ params }: ContactClientPageRouteProps): Promise<Metadata> {
  const { client_id: rawClientId } = await params;
  const clientId = Number(rawClientId);
  if (!Number.isFinite(clientId) || clientId <= 0) {
    return {};
  }
  const resolved = await resolvePublicClientSitePage(clientId, '');
  if (!resolved) {
    return {};
  }
  return buildSitePageMetadata(resolved.page, resolved.payload.clientName);
}

export default async function ContactClientPageRoute({ params }: ContactClientPageRouteProps) {
  const { client_id: rawClientId } = await params;
  const clientId = Number(rawClientId);
  if (!Number.isFinite(clientId) || clientId <= 0) {
    notFound();
  }
  const resolved = await resolvePublicClientSitePage(clientId, '');
  if (!resolved) {
    notFound();
  }
  return <ContactClientPage resolvedClientId={clientId} />;
}
