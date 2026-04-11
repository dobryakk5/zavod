'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, ArrowUpRight, ExternalLink } from 'lucide-react';
import { coachingApi, type CoachStats, type CoachingClient, type CoachingCompetency } from '@/lib/api/coaching';
import GroupsTab, { type GroupsTabHandle } from './groups-tab';
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
  const [activeTab, setActiveTab] = useState<'clients' | 'groups'>('clients');
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [quickAddValue, setQuickAddValue] = useState('');
  const [quickAddLoading, setQuickAddLoading] = useState(false);
  const [quickAddError, setQuickAddError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [coachCompetenciesLoading, setCoachCompetenciesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const quickAddInputRef = useRef<HTMLInputElement>(null);
  const groupsTabRef = useRef<GroupsTabHandle>(null);

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

  useEffect(() => {
    if (!quickAddOpen) {
      return;
    }

    quickAddInputRef.current?.focus();
  }, [quickAddOpen, activeTab]);

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

  const quickAddLabel = activeTab === 'clients' ? 'клиента' : 'группу';
  const quickAddPlaceholder = activeTab === 'clients' ? 'Новый клиент...' : 'Новая группа...';

  const resetQuickAdd = () => {
    setQuickAddOpen(false);
    setQuickAddValue('');
    setQuickAddError(null);
    setQuickAddLoading(false);
  };

  const handleTabChange = (nextTab: 'clients' | 'groups') => {
    if (nextTab === activeTab) {
      return;
    }
    setActiveTab(nextTab);
    resetQuickAdd();
  };

  const handleQuickAddToggle = () => {
    if (quickAddOpen) {
      resetQuickAdd();
      return;
    }

    setQuickAddOpen(true);
    setQuickAddValue('');
    setQuickAddError(null);
  };

  const handleQuickAddSubmit = async () => {
    const normalizedValue = normalizeDashboardEntityName(quickAddValue);
    if (!normalizedValue) {
      setQuickAddError(`Введите ${quickAddLabel}.`);
      return;
    }

    setQuickAddLoading(true);
    setQuickAddError(null);

    try {
      if (activeTab === 'clients') {
        const createdContact = await crmContactsApi.create({ name: normalizedValue });
        const createdClient = mapContactToDashboardClient(createdContact);
        setData((current) => {
          const clientExists = current.coachClients.some((client) => client.id === createdClient.id);
          return {
            ...current,
            coachClients: [createdClient, ...current.coachClients.filter((client) => client.id !== createdClient.id)],
            coachStats: current.coachStats
              ? {
                  ...current.coachStats,
                  activeClients: current.coachStats.activeClients + (clientExists ? 0 : 1),
                }
              : current.coachStats,
          };
        });
        setSelectedCoachClientId(createdClient.id);
      } else {
        if (!groupsTabRef.current) {
          throw new Error('GroupsTab is not ready');
        }
        await groupsTabRef.current.createGroup(normalizedValue);
      }

      resetQuickAdd();
    } catch {
      setQuickAddLoading(false);
      setQuickAddError(`Не удалось добавить ${quickAddLabel}.`);
    }
  };

  return (
    <div className="min-h-full rounded-none bg-[#f5f4f0] p-3 text-[#1a1a18] sm:rounded-[24px] sm:p-5">
      {error ? (
        <div className="mb-4 rounded-[8px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error}
        </div>
      ) : null}

      <div className="mx-auto flex max-w-6xl flex-col gap-[14px]">
        <div className="flex justify-start sm:justify-end">
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

        <section className={`${PANEL_CLASS} overflow-hidden`}>
          <div className="flex items-center gap-1 border-b border-[#e0ddd6]">
            {(['clients', 'groups'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => handleTabChange(tab)}
                className={`border-b-2 px-4 py-[10px] text-[12px] transition-colors ${
                  activeTab === tab
                    ? 'border-[#1a1a18] font-medium text-[#1a1a18]'
                    : 'border-transparent text-[#73726c] hover:text-[#1a1a18]'
                }`}
              >
                {tab === 'clients' ? 'Клиенты' : 'Группы'}
              </button>
            ))}
            <Link
              href="/clients"
              className="inline-flex items-center gap-1 px-2 py-[10px] text-[12px] font-medium text-[#2563eb] transition-colors hover:text-[#1d4ed8]"
            >
              <ArrowRight className="h-3 w-3" />
              <span>CRM</span>
            </Link>
            <button
              type="button"
              onClick={handleQuickAddToggle}
              className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#d8d4ca] text-[18px] leading-none text-[#1a1a18] transition-colors hover:border-[#1a1a18] hover:bg-[#f8f6f1]"
            >
              +
            </button>
          </div>

          {quickAddOpen ? (
            <div className="border-b border-[#e0ddd6] bg-[#f8f6f1] px-[14px] py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  ref={quickAddInputRef}
                  value={quickAddValue}
                  onChange={(event) => setQuickAddValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      void handleQuickAddSubmit();
                    }
                  }}
                  placeholder={quickAddPlaceholder}
                  className="min-w-0 flex-1 rounded-[6px] border-[0.5px] border-dashed border-[#d8d4ca] bg-white px-3 py-2 text-[16px] text-[#1a1a18] outline-none placeholder:text-[#a6a39a] focus:border-[#b4b2a9] sm:text-[12px]"
                />
                <button
                  type="button"
                  onClick={() => void handleQuickAddSubmit()}
                  disabled={quickAddLoading}
                  className="rounded-[6px] bg-[#1D9E75] px-3 py-2 text-[12px] text-[#E1F5EE] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 sm:py-[7px]"
                >
                  {quickAddLoading ? 'Добавляю...' : 'Добавить'}
                </button>
              </div>
              {quickAddError ? (
                <div className="mt-2 text-[12px] text-[#b2471f]">{quickAddError}</div>
              ) : null}
            </div>
          ) : null}

          {activeTab === 'clients' ? (
            <div className="grid gap-0 xl:grid-cols-2">
              <div className="border-b border-[#e0ddd6] p-[14px] xl:border-b-0 xl:border-r">
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
                  <EmptyQuickAddHint entityLabel="клиентов" />
                )}
              </div>

              <div className="p-[14px]">
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
                      <div className="mt-[10px] flex flex-wrap gap-x-2 gap-y-1 text-[11px] text-[#73726c]">
                        <span>Начало: {formatMonthYearCompact(selectedCoachClient.createdAt)}</span>
                        <span>Сессий: {selectedCoachClient.sessionsCount}</span>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="text-sm text-[#73726c]">Нет данных по компетенциям клиента.</div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-[14px]">
              <GroupsTab ref={groupsTabRef} clients={data.coachClients} />
            </div>
          )}
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
    <div className={`${PANEL_CLASS} min-h-[88px] px-[14px] py-3 sm:min-h-[80px]`}>
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
      className={`flex items-start gap-[10px] rounded-[8px] border-b border-[#e0ddd6] px-1 py-2.5 transition-colors last:border-b-0 sm:items-center sm:px-0 sm:py-[7px] ${
        selected ? 'bg-[#f7f2ff]' : 'hover:bg-[#f8f6f1]'
      }`}
    >
      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-medium ${avatarStyle}`}>
        {client.initials || getInitials(client.name)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-3">
          <Link
            href={`/coach/clients/${client.id}`}
            onClick={(event) => event.stopPropagation()}
            className={`min-w-0 shrink truncate text-[12px] font-medium transition-colors hover:text-[#5c52e0] ${
              selected ? 'text-[#5c52e0]' : 'text-[#1a1a18]'
            }`}
          >
            {getShortClientName(client.name)}
          </Link>
          <Link
            href={`/coach/clients/${client.id}`}
            aria-label={`Открыть страницу клиента ${client.name}`}
            onClick={(event) => event.stopPropagation()}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#d8d4ca] text-[#73726c] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0] sm:h-5 sm:w-5"
          >
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <div className="min-w-0 flex-1 text-[11px] leading-4 text-[#73726c]">
            {client.focus}
          </div>
          {pill ? (
            <span className={`shrink-0 rounded-full px-[7px] py-[2px] text-[10px] ${pill.className}`}>
              {pill.label}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ProgressRow({ item }: { item: CoachingCompetency }) {
  const color = getProgressColor(item.name, item.color);

  return (
    <div className="mb-[10px] last:mb-0">
      <div className="mb-1 flex items-start justify-between gap-3 text-[11px] leading-none text-[#73726c]">
        <span className="min-w-0 flex-1 leading-4">{item.name}</span>
        <span className="shrink-0">{item.score}%</span>
      </div>
      <div className="h-[5px] overflow-hidden rounded-[3px] bg-[#f1efe8]">
        <div className="h-full rounded-[3px]" style={{ width: `${item.score}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function TaskRow({ task }: { task: DashboardTask }) {
  return (
    <div className="flex items-start gap-2 border-b border-[#e0ddd6] py-[7px] text-[12px] last:border-b-0">
      <div
        className={`mt-0.5 flex h-[14px] w-[14px] shrink-0 items-center justify-center rounded-[3px] border ${
          task.done ? 'border-transparent bg-[#e1f5ee]' : 'border-[#d3d1c7]'
        }`}
      >
        {task.done ? (
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M2 5l2.5 2.5L8 3" stroke="#0f6e56" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          </svg>
        ) : null}
      </div>
      <span className="min-w-0 flex-1 leading-4 text-[#1a1a18]">{task.text}</span>
    </div>
  );
}

function EmptyQuickAddHint({ entityLabel }: { entityLabel: string }) {
  return (
    <div className="flex min-h-[160px] items-center justify-center rounded-[8px] border-[0.5px] border-dashed border-[#e0ddd6] bg-[#fbfaf7] p-4 text-center">
      <div className="max-w-[220px] text-[#73726c]">
        <div className="flex justify-center">
          <ArrowUpRight className="h-5 w-5 -translate-y-1 translate-x-8" />
        </div>
        <div className="text-[12px] leading-5">
          Для добавления {entityLabel} нажмите кнопку <span className="font-medium text-[#1a1a18]">"+"</span>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="min-h-full rounded-none bg-[#f5f4f0] p-3 sm:rounded-[24px] sm:p-5">
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

function normalizeDashboardEntityName(value: string) {
  return value.trim().replace(/\s+/g, ' ');
}

function mapContactToDashboardClient(contact: Contact): CoachingClient {
  const createdAt = contact.created_at || new Date().toISOString();
  return {
    id: String(contact.id),
    name: contact.name,
    initials: getInitials(contact.name),
    focus: '',
    intention: '',
    sessionsCount: 0,
    avgProgress: 0,
    nextSession: null,
    clientStatus: {
      kind: 'new',
      label: 'Новый',
      at: null,
    },
    coachId: '',
    createdAt,
  };
}
