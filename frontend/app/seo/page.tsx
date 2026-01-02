import { Suspense } from 'react';
import SEOPageClient from './seo-page-client';

export default function SEOPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Загрузка...</div>}>
      <SEOPageClient />
    </Suspense>
  );
}

