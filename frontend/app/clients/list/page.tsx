import { ClientsTab } from '@/app/products/clients-tab';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsListPage() {
  return (
    <ClientsSectionShell
      section="list"
      title="Клиенты"
      description="Список контактов, фильтры, теги и работа со статусами клиентов."
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <ClientsTab />
      </div>
    </ClientsSectionShell>
  );
}
