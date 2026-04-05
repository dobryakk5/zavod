import FunnelPageClient from '../funnel-page-client';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsFunnelPage() {
  return (
    <ClientsSectionShell
      section="funnel"
      title="Воронка"
      description="Статистика по этапам продаж, переходам между стадиями и причинам потерь."
    >
      <FunnelPageClient />
    </ClientsSectionShell>
  );
}
