import { Suspense } from 'react';
import { DealsTab } from '../deals-tab';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsDealsPage() {
  return (
    <ClientsSectionShell
      section="deals"
      title="Сделки"
      description="Список и Kanban по сделкам с поддержкой фильтра по этапам воронки."
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <Suspense fallback={<p className="text-sm text-muted-foreground">Загрузка сделок...</p>}>
          <DealsTab />
        </Suspense>
      </div>
    </ClientsSectionShell>
  );
}
