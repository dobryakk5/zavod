import { notFound } from 'next/navigation';
import PublicEventPage from '@/app/c/[client_id]/events/[event_id]/page-client';
import { resolveCustomDomainClientId } from '../../_domain-resolver';

export default async function CustomDomainEventPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicEventPage resolvedClientId={clientId} useCustomDomainPaths />;
}
