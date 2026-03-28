'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { coachingApi, type CoachStats, type CoachingClient, type CoachingCompetency } from '@/lib/api/coaching';
import { crmContactsApi, crmDealsApi, crmEventsApi, type Contact, type Deal, type Event } from '@/lib/api/crm';
import type { CoachingClientStatus } from '@/lib/api/coaching';

type DashboardData = {
  contacts: Contact[];
  deals: Deal[];
  events: Event[];
  coachStats: CoachStats | null;
  coachClients: CoachingClient[];
  coachCompetencies: CoachingCompetency[];
};

type DashboardTask = {
  id: string;
  text: string;
  done: boolean;
};

const PANEL_CLASS = 'rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white';
const SPOTLIGHT_COMPETENCIES = ['Уверенность', 'Коммуникация', 'Границы', 'Цели и фокус'];
const EMPTY_DATA: DashboardData = {
  contacts: [],
  deals: [],
  events: [],
  coachStats: null,
  coachClients: [],
  coachCompetencies: [],
};

function formatDealStageLabel(stage: Deal['stage']) {
  if (stage === 'interest') return 'Есть интерес';
  if (stage === 'call') return 'Назначен созвон';
  if (stage === 'payment_expected') return 'Ожидается оплата';
  if (stage === 'paid') return 'Оплачено';
  if (stage === 'lost') return 'Сделка потеряна';
  return 'Новый клиент';
}

function formatNewClientsSummary(count: number) {
  const mod10 = count % 10;
  const mod100 = count % 100;

  if (mod10 === 1 && mod100 !== 11) {
    return `+${count} новый клиент за 30 дней`;
  }

  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `+${count} новых клиента за 30 дней`;
  }

  return `+${count} новых клиентов за 30 дней`;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData>(EMPTY_DATA);
  const [selectedCoachClientId, setSelectedCoachClientId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [coachCompetenciesLoading, setCoachCompetenciesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadDashboard = async () => {
      setLoading(true);
      setError(null);

      const results = await Promise.allSettled([
        crmContactsApi.list(),
        crmDealsApi.list(),
        crmEventsApi.list(),
        coachingApi.getCoachStats(),
        coachingApi.getCoachClients(),
      ]);

      if (!isActive) return;

      const [contactsResult, dealsResult, eventsResult, coachStatsResult, coachClientsResult] = results;
      const coachClients = coachClientsResult.status === 'fulfilled' ? coachClientsResult.value : [];

      setData({
        contacts: contactsResult.status === 'fulfilled' ? contactsResult.value : [],
        deals: dealsResult.status === 'fulfilled' ? dealsResult.value : [],
        events: eventsResult.status === 'fulfilled' ? eventsResult.value : [],
        coachStats: coachStatsResult.status === 'fulfilled' ? coachStatsResult.value : null,
        coachClients,
        coachCompetencies: [],
      });
      setSelectedCoachClientId((current) => {
        if (current && coachClients.some((client) => client.id === current)) {
          return current;
        }
        return coachClients[0]?.id ?? null;
      });

      const failedRequests = results.filter((result) => result.status === 'rejected').length;
      if (failedRequests === results.length) {
        setError('Не удалось загрузить данные dashboard.');
      } else if (failedRequests > 0) {
        setError('Часть данных загрузить не удалось. Остальной обзор доступен.');
      }

      setLoading(false);
    };

    void loadDashboard();

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;

    const loadCompetencies = async () => {
      if (!selectedCoachClientId) {
        setCoachCompetenciesLoading(false);
        setData((current) => ({ ...current, coachCompetencies: [] }));
        return;
      }

      setCoachCompetenciesLoading(true);
      try {
        const competencies = await coachingApi.getCoachClientCompetencies(selectedCoachClientId);
        if (!isActive) return;
        setData((current) => ({ ...current, coachCompetencies: competencies }));
      } catch {
        if (!isActive) return;
        setData((current) => ({ ...current, coachCompetencies: [] }));
      } finally {
        if (isActive) {
          setCoachCompetenciesLoading(false);
        }
      }
    };

    void loadCompetencies();

    return () => {
      isActive = false;
    };
  }, [selectedCoachClientId]);

  const visibleClients = useMemo(() => data.coachClients.slice(0, 4), [data.coachClients]);
  const selectedCoachClient = visibleClients.find((client) => client.id === selectedCoachClientId) ?? visibleClients[0] ?? null;
  const progressItems = useMemo(() => getProgressItems(data.coachCompetencies), [data.coachCompetencies]);
  const newClientsSummary = useMemo(() => {
    const threshold = Date.now() - 30 * 24 * 60 * 60 * 1000;
    const count = data.coachClients.filter((client) => {
      const createdAt = new Date(client.createdAt).getTime();
      return Number.isFinite(createdAt) && createdAt >= threshold;
    }).length;

    return count > 0 ? formatNewClientsSummary(count) : undefined;
  }, [data.coachClients]);
  const dashboardTasks = useMemo(
    () => getDashboardTasks(data.contacts, data.deals, data.events),
    [data.contacts, data.deals, data.events],
  );

  if (loading) {
    return <LoadingState />;
  }

  return (
    <div className="min-h-full rounded-[24px] bg-[#f5f4f0] p-4 text-[#1a1a18] sm:p-5">
      {error ? (
        <div className="mb-4 rounded-[8px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      ) : null}

      <div className="mx-auto flex max-w-6xl flex-col gap-[14px]">
        <div className="flex justify-end">
          <span className="inline-flex w-fit rounded-full bg-[#eaf3de] px-[7px] py-[2px] text-[10px] font-medium leading-none text-[#3b6d11]">
            {data.coachStats?.sessionsToday ?? 0} {pluralizeSessions(data.coachStats?.sessionsToday ?? 0)} сегодня
          </span>
        </div>

        <section className="grid gap-[10px] md:grid-cols-3">
          <StatCard
            label="Активных клиентов"
            value={String(data.coachStats?.activeClients ?? visibleClients.length)}
            sub={newClientsSummary}
          />
          <StatCard
            label="Выполнено заданий"
            value={String(data.coachStats?.completedTasks ?? 0)}
            sub="за последние 30 дней"
          />
          <StatCard
            label="Средний прогресс"
            value={`+${data.coachStats?.avgProgress ?? 0}%`}
            sub="по всем клиентам"
          />
        </section>

        <section className="grid gap-[14px] xl:grid-cols-2">
          <div className={`${PANEL_CLASS} p-[14px]`}>
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="text-[13px] font-medium">Клиенты</div>
              <Link
                href="/clients/new"
                aria-label="Добавить клиента"
                className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-[#d8d4ca] bg-white text-[16px] leading-none text-[#4f4b45] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0]"
              >
                +
              </Link>
            </div>
            {visibleClients.length > 0 ? (
              <div>
                {visibleClients.map((client, index) => (
                  <ClientRow
                    key={client.id}
                    client={client}
                    index={index}
                    selected={client.id === selectedCoachClient?.id}
                    onSelect={() => setSelectedCoachClientId(client.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-sm text-[#73726c]">Нет клиентов для отображения.</div>
            )}
          </div>

          <div className={`${PANEL_CLASS} p-[14px]`}>
            <div className="mb-3 text-[13px] font-medium leading-none">
              {selectedCoachClient ? getProgressTitle(selectedCoachClient.name) : 'Прогресс клиента'}
            </div>
            {coachCompetenciesLoading ? (
              <div className="text-sm text-[#73726c]">Обновляю компетенции клиента...</div>
            ) : progressItems.length > 0 ? (
              <div>
                {progressItems.map((item) => (
                  <ProgressRow key={item.id} item={item} />
                ))}
                {selectedCoachClient ? (
                  <div className="mt-[10px] text-[11px] text-[#73726c]">
                    Начало: {formatMonthYearCompact(selectedCoachClient.createdAt)} · Сессий: {selectedCoachClient.sessionsCount}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-[#73726c]">Нет данных по компетенциям клиента.</div>
            )}
          </div>
        </section>

        <section className={`${PANEL_CLASS} p-[14px]`}>
          <div className="mb-3 text-[13px] font-medium">Задания клиентов на эту неделю</div>
          {dashboardTasks.length > 0 ? (
            <div className="grid gap-x-5 md:grid-cols-2">
              {dashboardTasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </div>
          ) : (
            <div className="text-sm text-[#73726c]">Нет задач для отображения.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className={`${PANEL_CLASS} min-h-[80px] px-[14px] py-3`}>
      <div className="mb-1 text-[11px] text-[#73726c]">{label}</div>
      <div className="text-[22px] font-medium leading-none text-[#1a1a18]">{value}</div>
      {sub ? <div className="mt-1 text-[11px] text-[#73726c]">{sub}</div> : null}
    </div>
  );
}

function ClientRow({
  client,
  index,
  selected,
  onSelect,
}: {
  client: CoachingClient;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const avatarStyle = getAvatarStyle(index);
  const pill = getClientPill(client.clientStatus);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
      className={`flex items-center gap-[10px] border-b border-[#e0ddd6] py-[7px] transition-colors last:border-b-0 ${
        selected ? 'bg-[#f7f2ff]' : 'hover:bg-[#f8f6f1]'
      }`}
    >
      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-medium ${avatarStyle}`}>
        {client.initials || getInitials(client.name)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <div className={`min-w-0 truncate text-[12px] font-medium ${selected ? 'text-[#5c52e0]' : 'text-[#1a1a18]'}`}>
            {getShortClientName(client.name)}
          </div>
          <Link
            href={`/coach/clients/${client.id}`}
            aria-label={`Открыть страницу клиента ${client.name}`}
            onClick={(event) => event.stopPropagation()}
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#d8d4ca] text-[#73726c] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0]"
          >
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
        <div className="truncate text-[11px] text-[#73726c]">{client.focus}</div>
      </div>
      {pill ? (
        <span className={`ml-auto rounded-full px-[7px] py-[2px] text-[10px] ${pill.className}`}>
          {pill.label}
        </span>
      ) : null}
    </div>
  );
}

function ProgressRow({ item }: { item: CoachingCompetency }) {
  const color = getProgressColor(item.name, item.color);

  return (
    <div className="mb-[10px] last:mb-0">
      <div className="mb-1 flex items-center justify-between text-[11px] leading-none text-[#73726c]">
        <span>{item.name}</span>
        <span>{item.score}%</span>
      </div>
      <div className="h-[5px] overflow-hidden rounded-[3px] bg-[#f1efe8]">
        <div className="h-full rounded-[3px]" style={{ width: `${item.score}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function TaskRow({ task }: { task: DashboardTask }) {
  return (
    <div className="flex items-center gap-2 border-b border-[#e0ddd6] py-[7px] text-[12px] last:border-b-0">
      <div
        className={`flex h-[14px] w-[14px] shrink-0 items-center justify-center rounded-[3px] border ${
          task.done ? 'border-transparent bg-[#e1f5ee]' : 'border-[#d3d1c7]'
        }`}
      >
        {task.done ? (
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M2 5l2.5 2.5L8 3" stroke="#0f6e56" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          </svg>
        ) : null}
      </div>
      <span className="truncate text-[#1a1a18]">{task.text}</span>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="min-h-full rounded-[24px] bg-[#f5f4f0] p-4 sm:p-5">
      <div className="mx-auto max-w-6xl animate-pulse space-y-[14px]">
        <div className="flex items-center justify-between">
          <div className="h-5 w-44 rounded bg-[#e7e2d8]" />
          <div className="h-5 w-24 rounded-full bg-[#e7e2d8]" />
        </div>
        <div className="grid gap-[10px] md:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <div key={item} className="h-20 rounded-[8px] bg-[#e7e2d8]" />
          ))}
        </div>
        <div className="grid gap-[14px] xl:grid-cols-2">
          <div className="h-64 rounded-[8px] bg-[#e7e2d8]" />
          <div className="h-64 rounded-[8px] bg-[#e7e2d8]" />
        </div>
        <div className="h-40 rounded-[8px] bg-[#e7e2d8]" />
      </div>
    </div>
  );
}

function getProgressItems(competencies: CoachingCompetency[]) {
  const preferred = SPOTLIGHT_COMPETENCIES
    .map((name) => competencies.find((item) => item.name === name))
    .filter((item): item is CoachingCompetency => Boolean(item));
  const remaining = competencies.filter((item) => !preferred.some((preferredItem) => preferredItem.id === item.id));
  return [...preferred, ...remaining].slice(0, 4);
}

function getDashboardTasks(contacts: Contact[], deals: Deal[], events: Event[]): DashboardTask[] {
  const contactsById = new Map(contacts.map((contact) => [contact.id, contact]));
  const now = Date.now();
  const upcomingSessions = [...events]
    .filter((event) => event.status === 'scheduled')
    .filter((event) => {
      const timestamp = new Date(event.start_time).getTime();
      return Number.isFinite(timestamp) && timestamp >= now;
    })
    .sort((left, right) => new Date(left.start_time).getTime() - new Date(right.start_time).getTime());
  const paidDeals = deals.filter((deal) => deal.stage === 'paid');
  const activeDeals = deals.filter((deal) => (
    deal.stage === 'interest' || deal.stage === 'call' || deal.stage === 'payment_expected'
  ));

  const tasks: DashboardTask[] = [];

  if (paidDeals[0]) {
    const contact = contactsById.get(paidDeals[0].contact_id);
    tasks.push({
      id: `paid-${paidDeals[0].id}`,
      text: `${getFirstName(contact?.name || 'Клиент')} · Оплата подтверждена`,
      done: true,
    });
  }

  if (upcomingSessions[0]) {
    const contact = contactsById.get(upcomingSessions[0].contact_id);
    tasks.push({
      id: `session-${upcomingSessions[0].id}`,
      text: `${getFirstName(contact?.name || 'Клиент')} · Подготовить сессию`,
      done: false,
    });
  }

  if (paidDeals[1]) {
    const contact = contactsById.get(paidDeals[1].contact_id);
    tasks.push({
      id: `paid-${paidDeals[1].id}`,
      text: `${getFirstName(contact?.name || 'Клиент')} · Оплачено`,
      done: true,
    });
  }

  if (activeDeals[0]) {
    const contact = contactsById.get(activeDeals[0].contact_id);
    tasks.push({
      id: `deal-${activeDeals[0].id}`,
      text: `${getFirstName(contact?.name || 'Клиент')} · ${formatDealStageLabel(activeDeals[0].stage)}`,
      done: false,
    });
  }

  const seen = new Set<string>();
  return tasks.filter((task) => {
    if (seen.has(task.id)) return false;
    seen.add(task.id);
    return true;
  }).slice(0, 4);
}

function getClientPill(status: CoachingClientStatus) {
  switch (status?.kind) {
    case 'today':
      return { label: 'Сегодня', className: 'bg-[#faeeda] text-[#633806]' };
    case 'tomorrow':
      return { label: 'Завтра', className: 'bg-[#faeeda] text-[#633806]' };
    case 'milestone':
      return { label: 'Прорыв', className: 'bg-[#eaf3de] text-[#3b6d11]' };
    case 'new':
      return { label: 'Новый', className: 'bg-[#e6f1fb] text-[#185fa5]' };
    case 'overdue':
      return { label: 'Просрочено', className: 'bg-[#fde7e1] text-[#b2471f]' };
    default:
      return null;
  }
}

function getAvatarStyle(index: number) {
  const styles = [
    'bg-[#e1f5ee] text-[#0f6e56]',
    'bg-[#eaf3de] text-[#3b6d11]',
    'bg-[#faeeda] text-[#633806]',
    'bg-[#e6f1fb] text-[#185fa5]',
  ];
  return styles[index % styles.length];
}

function getProgressColor(name: string, fallback?: string) {
  if (name === 'Уверенность') return '#1D9E75';
  if (name === 'Коммуникация') return '#7F77DD';
  if (name === 'Границы') return '#D85A30';
  if (name === 'Цели и фокус') return '#378ADD';
  return fallback || '#378ADD';
}

function getShortClientName(name: string) {
  const [firstName, lastName] = name.split(/\s+/);
  return lastName ? `${firstName} ${lastName[0]}.` : firstName;
}

function getFirstName(name: string) {
  return name.split(/\s+/)[0] || name;
}

function toGenitive(firstName: string) {
  if (firstName.endsWith('я')) return `${firstName.slice(0, -1)}и`;
  if (firstName.endsWith('а')) {
    const stem = firstName.slice(0, -1);
    const lastStemLetter = stem.slice(-1).toLowerCase();
    return `${stem}${['г', 'к', 'х', 'ж', 'ч', 'ш', 'щ'].includes(lastStemLetter) ? 'и' : 'ы'}`;
  }
  return firstName;
}

function getProgressTitle(name: string) {
  const [firstName, lastName] = name.split(/\s+/);
  const firstNameGenitive = toGenitive(firstName || name);
  return lastName ? `Прогресс ${firstNameGenitive} ${lastName[0]}.` : `Прогресс ${firstNameGenitive}`;
}

function formatMonthYearCompact(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { month: 'short', year: 'numeric' })
    .format(new Date(value))
    .replace('.', '')
    .replace(' г.', '')
    .trim();
}

function pluralizeSessions(value: number) {
  const mod10 = value % 10;
  const mod100 = value % 100;
  if (mod10 === 1 && mod100 !== 11) return 'сессия';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'сессии';
  return 'сессий';
}

function getInitials(name: string) {
  const parts = name
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 2);

  if (parts.length === 0) return 'К';
  return parts.map((part) => part[0]?.toUpperCase() ?? '').join('') || 'К';
}
