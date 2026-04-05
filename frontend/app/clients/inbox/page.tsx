import UnifiedInboxTab from '../unified-inbox-tab';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsInboxPage() {
  return (
    <ClientsSectionShell
      section="inbox"
      title="Входящие"
      description="Единый inbox по обращениям клиентов, каналам связи и SLA."
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <UnifiedInboxTab />
      </div>
    </ClientsSectionShell>
  );
}
