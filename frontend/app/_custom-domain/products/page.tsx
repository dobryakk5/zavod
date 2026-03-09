import { notFound } from 'next/navigation';
import PublicProductsPage from '@/app/c/[client_id]/products/page-client';
import { resolveCustomDomainClientId } from '../_domain-resolver';

export default async function CustomDomainProductsPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicProductsPage resolvedClientId={clientId} useCustomDomainPaths />;
}
