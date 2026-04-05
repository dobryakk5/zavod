import Link from 'next/link';
import { Button } from '@/components/ui/button';
import ClientsSchedule from '../clients-schedule';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsSchedulePage() {
  return (
    <ClientsSectionShell
      section="schedule"
      title="Расписание"
      description="Календарь встреч, слотов доступности и событий по продуктам."
      primaryAction={(
        <Button asChild variant="secondary">
          <Link href="/clients/schedule/tasks">Задачи</Link>
        </Button>
      )}
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <ClientsSchedule />
      </div>
    </ClientsSectionShell>
  );
}
