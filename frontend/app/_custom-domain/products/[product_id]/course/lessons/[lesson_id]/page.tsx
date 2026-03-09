import { notFound } from 'next/navigation';
import PublicProductCourseLessonPage from '@/app/c/[client_id]/products/[product_id]/course/lessons/[lesson_id]/page-client';
import { resolveCustomDomainClientId } from '../../../../../_domain-resolver';

export default async function CustomDomainProductCourseLessonPage() {
  const clientId = await resolveCustomDomainClientId();
  if (!clientId) {
    notFound();
  }
  return <PublicProductCourseLessonPage resolvedClientId={clientId} useCustomDomainPaths />;
}
