import { Suspense } from 'react';
import TgstatPageClient from './tgstat-page-client';

function TgstatPageFallback() {
  return <div className="container mx-auto py-8">Загружаем категории...</div>;
}

export default function TgstatPage() {
  return (
    <Suspense fallback={<TgstatPageFallback />}>
      <TgstatPageClient />
    </Suspense>
  );
}
