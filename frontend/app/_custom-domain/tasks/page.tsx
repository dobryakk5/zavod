import { notFound } from 'next/navigation';
import PublicTasksPage from '@/app/c/[client_id]/tasks/page-client';
import { resolveCustomDomainClientId } from '../_domain-resolver';

export default async function CustomDomainTasksPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicTasksPage resolvedClientId={clientId} useCustomDomainPaths />;
}
