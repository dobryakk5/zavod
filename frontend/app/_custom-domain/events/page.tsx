import { notFound } from 'next/navigation';
import PublicEventsPage from '@/app/c/[client_id]/events/page-client';
import { resolveCustomDomainClientId } from '../_domain-resolver';

export default async function CustomDomainEventsPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicEventsPage resolvedClientId={clientId} useCustomDomainPaths />;
}
