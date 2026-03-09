import { notFound } from 'next/navigation';
import ContactClientPage from '@/app/c/[client_id]/page-client';
import { resolveCustomDomainClientId } from './_domain-resolver';

export default async function CustomDomainHomePage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <ContactClientPage resolvedClientId={clientId} useCustomDomainPaths />;
}
