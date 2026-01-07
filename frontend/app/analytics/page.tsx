import { Suspense } from 'react';
import AnalyticsPageClient from './analytics-page-client';

function AnalyticsPageFallback() {
  return (
    <div className="container mx-auto py-8 space-y-4">
      <div className="h-8 w-48 rounded bg-gray-100 animate-pulse" />
      <div className="h-4 w-64 rounded bg-gray-100 animate-pulse" />
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<AnalyticsPageFallback />}>
      <AnalyticsPageClient />
    </Suspense>
  );
}
