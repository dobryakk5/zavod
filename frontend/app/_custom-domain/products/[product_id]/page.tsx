import { notFound } from 'next/navigation';
import PublicProductPage from '@/app/c/[client_id]/products/[product_id]/page-client';
import { resolveCustomDomainClientId } from '../../_domain-resolver';

export default async function CustomDomainProductPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicProductPage resolvedClientId={clientId} useCustomDomainPaths />;
}
