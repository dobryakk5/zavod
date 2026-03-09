import { notFound } from 'next/navigation';
import PublicProductCoursePage from '@/app/c/[client_id]/products/[product_id]/course/page-client';
import { resolveCustomDomainClientId } from '../../../_domain-resolver';

export default async function CustomDomainProductCoursePage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicProductCoursePage resolvedClientId={clientId} useCustomDomainPaths />;
}
