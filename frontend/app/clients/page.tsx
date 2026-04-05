import Link from 'next/link';
import { redirect } from 'next/navigation';
import { ClientsSectionShell } from './section-shell';
import { CLIENTS_SECTION_LINKS } from './navigation';

type ClientsPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function getSingleValue(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return typeof value[0] === 'string' ? value[0] : null;
  }
  return typeof value === 'string' ? value : null;
}

function withQuery(pathname: string, params: Record<string, string | null>): string {
  const nextParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      nextParams.set(key, value);
    }
  });

  const query = nextParams.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function resolveLegacyClientsRoute(params?: Record<string, string | string[] | undefined>): string | null {
  if (!params) return null;

  const tab = getSingleValue(params.tab);
  const scheduleTab = getSingleValue(params.scheduleTab);
  const funnelStage = getSingleValue(params.funnelStage);
  const dealsView = getSingleValue(params.dealsView);

  if (!tab && !scheduleTab && !funnelStage && !dealsView) {
    return null;
  }

  if (!tab && (funnelStage || dealsView)) {
    return withQuery('/clients/deals', {
      funnelStage,
      dealsView,
    });
  }

  if (tab === 'clients') return '/clients/list';
  if (tab === 'deals' || tab === 'payments') {
    return withQuery('/clients/deals', {
      funnelStage,
      dealsView,
    });
  }
  if (tab === 'schedule') {
    return scheduleTab === 'tasks' ? '/clients/schedule/tasks' : '/clients/schedule';
  }
  if (tab === 'service-level') return '/clients/inbox';
  if (tab === 'categories') return '/clients/tags';
  if (tab === 'welcome-chain') return '/clients/chatbot';

  return null;
}

export default async function ClientsPage({ searchParams }: ClientsPageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const legacyRoute = resolveLegacyClientsRoute(resolvedSearchParams);

  if (legacyRoute) {
    redirect(legacyRoute);
  }

  return (
    <ClientsSectionShell
      title="CRM"
      description="Откройте нужный раздел: контакты, сделки, расписание, inbox, теги, ChatBot и воронку."
      showBackButton={false}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {CLIENTS_SECTION_LINKS.map((section) => (
          <Link
            key={section.href}
            href={section.href}
            className="rounded-2xl border bg-white p-4 transition-colors hover:border-slate-300 hover:bg-slate-50 sm:p-5"
          >
            <div className="text-base font-semibold text-slate-900 sm:text-lg">{section.title}</div>
            <p className="mt-2 text-sm text-slate-600">{section.description}</p>
          </Link>
        ))}
      </div>
    </ClientsSectionShell>
  );
}
