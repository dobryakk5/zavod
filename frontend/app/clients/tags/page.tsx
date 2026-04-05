import { CategoriesTab } from '@/app/products/categories-tab';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsTagsPage() {
  return (
    <ClientsSectionShell
      section="tags"
      title="Теги"
      description="Справочник CRM-тегов по целям, болям и опыту клиентов."
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <CategoriesTab />
      </div>
    </ClientsSectionShell>
  );
}
