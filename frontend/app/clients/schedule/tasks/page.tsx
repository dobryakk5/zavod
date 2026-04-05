import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { OperatorTasksTab } from '../../operator-tasks-tab';
import { ClientsSectionShell } from '../../section-shell';

export default function ClientsScheduleTasksPage() {
  return (
    <ClientsSectionShell
      section="schedule"
      title="Задачи операторов"
      description="Отдельная страница для задач, которые раньше были вкладкой внутри расписания."
      primaryAction={(
        <Button asChild variant="secondary">
          <Link href="/clients/schedule">Календарь</Link>
        </Button>
      )}
      backHref="/clients/schedule"
      backLabel="Назад к расписанию"
    >
      <div className="rounded-2xl bg-white p-4 sm:p-6">
        <OperatorTasksTab />
      </div>
    </ClientsSectionShell>
  );
}
