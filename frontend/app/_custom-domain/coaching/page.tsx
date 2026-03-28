import { notFound } from 'next/navigation';
import CoachingPortalPage from '@/app/c/[client_id]/coaching/page-client';
import { resolveCustomDomainClientId } from '../_domain-resolver';

export default async function CustomDomainCoachingPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <CoachingPortalPage resolvedClientId={clientId} useCustomDomainPaths />;
}
