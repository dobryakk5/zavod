import { Suspense } from 'react';
import PaymentProvidersPageClient from './payment-providers-page-client';

export default function PaymentProvidersPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Загрузка провайдеров...</div>}>
      <PaymentProvidersPageClient />
    </Suspense>
  );
}
