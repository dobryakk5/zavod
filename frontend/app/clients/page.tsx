'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar } from 'lucide-react';
import {
  crmContactsApi,
  crmEventsApi,
  type Contact,
  type Event,
} from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { chainsApi, type ChainCatalogItem } from '@/lib/api/chains';
import { DEFAULT_TENANT_TIMEZONE, formatInTenantTimezone, normalizeTenantTimezone } from '@/lib/timezone';
import { OperatorTasksTab } from './operator-tasks-tab';
import { ClientsTab } from '../products/clients-tab';
import { CategoriesTab } from '../products/categories-tab';
import ClientsSchedule from './clients-schedule';
import UnifiedInboxTab from './unified-inbox-tab';
import { DealsTab } from './deals-tab';

type ClientsStats = {
  upcomingEvents: number;
  nextEvents: Array<{
    id: number;
    title: string;
    start_time: string;
    contactName: string;
    contactId: number;
  }>;
  salesFunnel: SalesFunnelStats;
};

type SalesFunnelStageKey =
  | 'new_lead'
  | 'interest'
  | 'call'
  | 'payment_expected'
  | 'paid';

type SalesFunnelStageStat = {
  key: SalesFunnelStageKey;
  label: string;
  description: string;
  currentCount: number;
  reachedCount: number;
  stepConversionPct: number | null;
  overallConversionPct: number | null;
};

type LostReasonCode =
  | 'price'
  | 'timing'
  | 'no_response'
  | 'not_fit'
  | 'competitor'
  | 'priority_changed'
  | 'other';

type SalesFunnelLostReasonStat = {
  code: LostReasonCode;
  label: string;
  count: number;
};

type SalesFunnelStats = {
  totalLeads: number;
  archivedExcluded: number;
  dealsInWork: number;
  lostDeals: number;
  lostReasons: SalesFunnelLostReasonStat[];
  stages: SalesFunnelStageStat[];
};

const SALES_FUNNEL_STAGE_DEFS: Array<Pick<SalesFunnelStageStat, 'key' | 'label' | 'description'>> = [
  {
    key: 'new_lead',
    label: 'Новый лид',
    description: 'Контакт создан, без активности',
  },
  {
    key: 'interest',
    label: 'Интерес',
    description: 'Есть признаки интереса/обработки',
  },
  {
    key: 'call',
    label: 'Созвон',
    description: 'Есть встреча/созвон',
  },
  {
    key: 'payment_expected',
    label: 'Оплата ожидается',
    description: 'Есть pending-платёж',
  },
  {
    key: 'paid',
    label: 'Оплачено',
    description: 'Есть paid-платёж',
  },
];

const LOST_REASON_LABELS: Record<LostReasonCode, string> = {
  price: 'Дорого',
  timing: 'Не вовремя',
  no_response: 'Не отвечает',
  not_fit: 'Не подходит',
  competitor: 'Ушёл к конкуренту',
  priority_changed: 'Изменился приоритет',
  other: 'Другое',
};

function createEmptyFunnelCounts(): Record<SalesFunnelStageKey, number> {
  return {
    new_lead: 0,
    interest: 0,
    call: 0,
    payment_expected: 0,
    paid: 0,
  };
}

function createEmptySalesFunnelStats(): SalesFunnelStats {
  return {
    totalLeads: 0,
    archivedExcluded: 0,
    dealsInWork: 0,
    lostDeals: 0,
    lostReasons: [],
    stages: SALES_FUNNEL_STAGE_DEFS.map((stage) => ({
      ...stage,
      currentCount: 0,
      reachedCount: 0,
      stepConversionPct: null,
      overallConversionPct: null,
    })),
  };
}

function normalizeExplicitDealStage(raw: unknown): SalesFunnelStageKey | 'lost' | null {
  const value = String(raw ?? '').trim().toLowerCase();
  if (
    value === 'new_lead' ||
    value === 'interest' ||
    value === 'call' ||
    value === 'payment_expected' ||
    value === 'paid' ||
    value === 'lost'
  ) {
    return value;
  }
  return null;
}

function normalizeLostReasonCode(raw: unknown): LostReasonCode {
  const value = String(raw ?? '').trim().toLowerCase();
  if (
    value === 'price' ||
    value === 'timing' ||
    value === 'no_response' ||
    value === 'not_fit' ||
    value === 'competitor' ||
    value === 'priority_changed'
  ) {
    return value;
  }
  return 'other';
}

function toPercent(numerator: number, denominator: number): number | null {
  if (denominator <= 0) return null;
  return (numerator / denominator) * 100;
}

function formatPercent(value: number | null): string {
  if (value == null) return '—';
  if (value === 0 || value >= 10) return `${Math.round(value)}%`;
  return `${value.toFixed(1)}%`;
}

function buildSalesFunnelStats(contacts: Contact[]): SalesFunnelStats {
  const archivedExcluded = 0;
  const currentCounts = createEmptyFunnelCounts();
  const lostReasonCounts = new Map<LostReasonCode, number>();
  let lostDeals = 0;

  contacts.forEach((contact) => {
    const explicitDealStage = normalizeExplicitDealStage(contact.deal_stage);
    if (explicitDealStage && explicitDealStage !== 'lost') {
      currentCounts[explicitDealStage] += 1;
    } else if (!explicitDealStage) {
      currentCounts.new_lead += 1;
    }

    if (explicitDealStage === 'lost') {
      lostDeals += 1;
      const reasonCode = normalizeLostReasonCode(contact.deal_loss_reason_code);
      lostReasonCounts.set(reasonCode, (lostReasonCounts.get(reasonCode) ?? 0) + 1);
    }
  });

  const totalLeads = contacts.length;
  const reachedCounts = createEmptyFunnelCounts();
  SALES_FUNNEL_STAGE_DEFS.forEach((stage, index) => {
    const reached = SALES_FUNNEL_STAGE_DEFS.slice(index).reduce((sum, item) => sum + currentCounts[item.key], 0);
    reachedCounts[stage.key] = reached;
  });

  const stages = SALES_FUNNEL_STAGE_DEFS.map((stage, index) => {
    const prevStage = index > 0 ? SALES_FUNNEL_STAGE_DEFS[index - 1] : null;
    const reachedCount = reachedCounts[stage.key];
    const prevReachedCount = prevStage ? reachedCounts[prevStage.key] : 0;

    return {
      ...stage,
      currentCount: currentCounts[stage.key],
      reachedCount,
      stepConversionPct: prevStage ? toPercent(reachedCount, prevReachedCount) : null,
      overallConversionPct: toPercent(reachedCount, totalLeads),
    };
  });

  const lostReasons = [...lostReasonCounts.entries()]
    .map(([code, count]) => ({
      code,
      count,
      label: LOST_REASON_LABELS[code],
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));

  return {
    totalLeads,
    archivedExcluded,
    dealsInWork:
      currentCounts.new_lead +
      currentCounts.interest +
      currentCounts.call +
      currentCounts.payment_expected,
    lostDeals,
    lostReasons,
    stages,
  };
}

const emptyStats: ClientsStats = {
  upcomingEvents: 0,
  nextEvents: [],
  salesFunnel: createEmptySalesFunnelStats(),
};

const CLIENTS_TABS = [
  'clients',
  'deals',
  'schedule',
  'service-level',
  'categories',
  'welcome-chain',
] as const;
type ClientsTabValue = (typeof CLIENTS_TABS)[number];

const CLIENTS_SCHEDULE_TABS = ['calendar', 'tasks'] as const;
type ClientsScheduleTabValue = (typeof CLIENTS_SCHEDULE_TABS)[number];

function isClientsTabValue(value: string | null): value is ClientsTabValue {
  return !!value && CLIENTS_TABS.includes(value as ClientsTabValue);
}

function isClientsScheduleTabValue(value: string | null): value is ClientsScheduleTabValue {
  return !!value && CLIENTS_SCHEDULE_TABS.includes(value as ClientsScheduleTabValue);
}

function formatEventTime(value: string, timeZone: string) {
  return formatInTenantTimezone(value, timeZone, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ClientsPage() {
  return (
    <Suspense fallback={<ClientsPageFallback />}>
      <ClientsPageContent />
    </Suspense>
  );
}

function ClientsPageFallback() {
  return (
    <div className="container mx-auto py-6">
      <div className="rounded-xl border bg-white p-6 text-sm text-muted-foreground">
        Загрузка CRM...
      </div>
    </div>
  );
}

function ClientsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [stats, setStats] = useState<ClientsStats>(emptyStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const [chatbotChains, setChatbotChains] = useState<ChainCatalogItem[]>([]);
  const [chatbotChainsLoading, setChatbotChainsLoading] = useState(true);
  const [chatbotChainsError, setChatbotChainsError] = useState<string | null>(null);

  const activeClientsTab = useMemo<ClientsTabValue>(() => {
    const tab = searchParams.get('tab');
    if (tab === 'payments') return 'deals';
    return isClientsTabValue(tab) ? tab : 'clients';
  }, [searchParams]);

  const activeScheduleTab = useMemo<ClientsScheduleTabValue>(() => {
    const tab = searchParams.get('scheduleTab');
    return isClientsScheduleTabValue(tab) ? tab : 'calendar';
  }, [searchParams]);

  const updateQuery = (patch: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(patch).forEach(([key, value]) => {
      if (value == null || value === '') {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    });
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname);
  };

  useEffect(() => {
    let isActive = true;

    const loadStats = async () => {
      setStatsLoading(true);
      setStatsError(null);

      try {
        const [contacts, events, settings] = await Promise.all([
          crmContactsApi.list(),
          crmEventsApi.list(),
          clientApi.getSettings(),
        ]);

        if (!isActive) return;

        setTenantTimezone(normalizeTenantTimezone(settings.timezone));
        const now = new Date();

        const contactsById = new Map(contacts.map((contact) => [contact.id, contact.name]));
        const upcomingEventsSorted = events
          .filter((event) => {
            if (event.status !== 'scheduled') return false;
            const startDate = new Date(event.start_time);
            return !Number.isNaN(startDate.getTime()) && startDate >= now;
          })
          .sort((a, b) => {
            const aTime = new Date(a.start_time).getTime();
            const bTime = new Date(b.start_time).getTime();
            return aTime - bTime;
          });
        const nextEvents = upcomingEventsSorted.slice(0, 1).map((event) => ({
          id: event.id,
          title: event.title || 'Встреча',
          start_time: event.start_time,
          contactName: contactsById.get(event.contact_id) || `Клиент #${event.contact_id}`,
          contactId: event.contact_id,
        }));

        setStats({
          upcomingEvents: upcomingEventsSorted.length,
          nextEvents,
          salesFunnel: buildSalesFunnelStats(contacts),
        });
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load CRM stats', err);
        setStatsError('Не удалось загрузить статистику CRM.');
      } finally {
        if (isActive) {
          setStatsLoading(false);
        }
      }
    };

    void loadStats();

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;

    const loadChatbotChains = async () => {
      setChatbotChainsLoading(true);
      setChatbotChainsError(null);
      try {
        const items = await chainsApi.list();
        if (!isActive) return;
        setChatbotChains(items);
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load chatbot chains', err);
        setChatbotChainsError('Не удалось загрузить список цепочек.');
      } finally {
        if (isActive) {
          setChatbotChainsLoading(false);
        }
      }
    };

    void loadChatbotChains();

    return () => {
      isActive = false;
    };
  }, []);

  const displayStats = useMemo(() => {
    if (statsLoading || statsError) {
      return {
        totalClients: null,
        upcomingEvents: null,
        nextEvents: [],
        salesFunnel: createEmptySalesFunnelStats(),
      };
    }

    return {
      upcomingEvents: stats.upcomingEvents,
      nextEvents: stats.nextEvents,
      salesFunnel: stats.salesFunnel,
    };
  }, [stats, statsError, statsLoading]);

  return (
    <div className="container mx-auto py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Управление клиентами</h1>
        <p className="text-muted-foreground mt-2">
          Управление клиентами, расписанием и платежами
        </p>
        {statsError && (
          <p className="text-sm text-red-500 mt-2">{statsError}</p>
        )}
      </div>

      <div className="mb-8">
        <div className="rounded-lg bg-transparent">
          <div className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {displayStats.nextEvents.length > 0 && (
              <div>
                Ближайшая встреча:{' '}
                {formatEventTime(displayStats.nextEvents[0].start_time, tenantTimezone)} ·{' '}
                {displayStats.nextEvents[0].title} ·{' '}
                <Link
                  href={`/contact/${displayStats.nextEvents[0].contactId}`}
                  className="text-blue-600 hover:underline"
                >
                  {displayStats.nextEvents[0].contactName}
                </Link>
              </div>
            )}
            {displayStats.nextEvents.length === 0 && (
              <div>Ближайшая встреча: Нет запланированных встреч</div>
            )}
          </div>
        </div>
      </div>

      <div className="mb-8 rounded-xl border bg-white p-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Воронка продаж</h2>
              <p className="text-sm text-muted-foreground">
                Лиды/сделки по стадиям и конверсия по этапам (как в Kanban, по полю стадии сделки)
              </p>
            </div>
            {!statsLoading && !statsError && (
              <div className="flex flex-wrap gap-2 text-xs">
                <div className="rounded-md border px-3 py-1.5">
                  Лидов в воронке: <span className="font-semibold">{displayStats.salesFunnel.totalLeads}</span>
                </div>
                <div className="rounded-md border px-3 py-1.5">
                  Сделок в работе:{' '}
                  <span className="font-semibold">{displayStats.salesFunnel.dealsInWork}</span>
                </div>
                <div className="rounded-md border px-3 py-1.5">
                  Конверсия в оплату:{' '}
                  <span className="font-semibold">
                    {formatPercent(
                      displayStats.salesFunnel.stages.find((stage) => stage.key === 'paid')
                        ?.overallConversionPct ?? null
                    )}
                  </span>
                </div>
                <div className="rounded-md border px-3 py-1.5">
                  Потеряно сделок:{' '}
                  <span className="font-semibold">{displayStats.salesFunnel.lostDeals}</span>
                </div>
              </div>
            )}
          </div>

          {statsLoading && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
              {Array.from({ length: 5 }).map((_, index) => (
                <div
                  key={`funnel-skeleton-${index}`}
                  className="rounded-lg border p-4 animate-pulse"
                >
                  <div className="h-3 w-24 rounded bg-slate-200" />
                  <div className="mt-3 h-7 w-12 rounded bg-slate-200" />
                  <div className="mt-3 h-2 w-full rounded bg-slate-100" />
                  <div className="mt-3 h-3 w-28 rounded bg-slate-200" />
                  <div className="mt-2 h-3 w-20 rounded bg-slate-200" />
                </div>
              ))}
            </div>
          )}

          {!statsLoading && !statsError && (
            <>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
                {displayStats.salesFunnel.stages.map((stage, index) => (
                  <div key={stage.key} className="rounded-lg border p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs text-muted-foreground">
                          Этап {index + 1}
                        </div>
                        <div className="mt-1 text-sm font-medium">{stage.label}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-semibold leading-none">{stage.currentCount}</div>
                        <div className="mt-1 text-[11px] text-muted-foreground">в стадии</div>
                      </div>
                    </div>

                    <div className="mt-3 h-2 rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-slate-900"
                        style={{ width: `${Math.max(0, Math.min(100, stage.overallConversionPct ?? 0))}%` }}
                      />
                    </div>

                    <p className="mt-3 text-[11px] text-muted-foreground">{stage.description}</p>

                    <div className="mt-3 space-y-1 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Дошли до этапа</span>
                        <span className="font-medium">{stage.reachedCount}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">Из предыдущего</span>
                        <span className="font-medium">{formatPercent(stage.stepConversionPct)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-muted-foreground">От всех лидов</span>
                        <span className="font-medium">{formatPercent(stage.overallConversionPct)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="rounded-lg border p-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-sm font-medium">Причины потерь</div>
                    <div className="text-xs text-muted-foreground">
                      Учитываются контакты со стадией сделки «Потеряно» и указанной причиной
                    </div>
                  </div>
                  <div className="text-sm">
                    Всего потеряно: <span className="font-semibold">{displayStats.salesFunnel.lostDeals}</span>
                  </div>
                </div>
                {displayStats.salesFunnel.lostReasons.length === 0 ? (
                  <div className="mt-3 text-sm text-muted-foreground">
                    Пока нет данных. Причина появится после отметки сделки как «Потеряно» в карточке контакта.
                  </div>
                ) : (
                  <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                    {displayStats.salesFunnel.lostReasons.map((reason) => (
                      <div key={reason.code} className="rounded-md border bg-slate-50 px-3 py-2">
                        <div className="text-xs text-muted-foreground">{reason.label}</div>
                        <div className="mt-1 text-xl font-semibold">{reason.count}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="text-xs text-muted-foreground">
                Воронка использует ту же стадию сделки, что и Kanban (поле `deal_stage` у контакта).
              </div>
            </>
          )}
        </div>
      </div>

      <Tabs
        value={activeClientsTab}
        onValueChange={(value) => {
          const nextTab = value as ClientsTabValue;
          updateQuery({
            tab: nextTab,
            scheduleTab: nextTab === 'schedule' ? activeScheduleTab : null,
          });
        }}
        className="space-y-3"
      >
        <TabsList className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="deals">Сделки</TabsTrigger>
          <TabsTrigger value="schedule">Расписание</TabsTrigger>
          <TabsTrigger value="service-level">Входящие</TabsTrigger>
          <TabsTrigger value="categories">Теги</TabsTrigger>
          <TabsTrigger value="welcome-chain">ChatBot</TabsTrigger>
        </TabsList>

        <TabsContent value="clients" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <ClientsTab />
          </div>
        </TabsContent>

        <TabsContent value="deals" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <DealsTab />
          </div>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <Tabs
              value={activeScheduleTab}
              onValueChange={(value) => {
                updateQuery({
                  tab: 'schedule',
                  scheduleTab: value,
                });
              }}
              className="space-y-4"
            >
              <TabsList>
                <TabsTrigger value="calendar">Календарь</TabsTrigger>
                <TabsTrigger value="tasks">Задачи</TabsTrigger>
              </TabsList>

              <TabsContent value="calendar">
                <ClientsSchedule />
              </TabsContent>

              <TabsContent value="tasks">
                <OperatorTasksTab />
              </TabsContent>
            </Tabs>
          </div>
        </TabsContent>

        <TabsContent value="service-level" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <UnifiedInboxTab />
          </div>
        </TabsContent>

        <TabsContent value="categories" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <CategoriesTab />
          </div>
        </TabsContent>

        <TabsContent value="welcome-chain" className="space-y-6">
          <div className="bg-white rounded-lg p-6 space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Цепочки ChatBot</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Выберите цепочку и откройте отдельную страницу редактора.
              </p>
            </div>

            {chatbotChainsLoading && (
              <p className="text-sm text-muted-foreground">Загрузка цепочек...</p>
            )}

            {chatbotChainsError && (
              <p className="text-sm text-red-500">{chatbotChainsError}</p>
            )}

            {!chatbotChainsLoading && !chatbotChainsError && (
              <div className="space-y-3">
                {chatbotChains.map((chain) => (
                  <Link
                    key={chain.id}
                    href={`/clients/chatbot/${chain.id}`}
                    className="block rounded-lg border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div>
                      <div className="font-medium text-slate-900">{chain.title}</div>
                      <div className="text-xs text-slate-500 mt-1">
                        ID: {chain.id} · Статус: {chain.status}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
