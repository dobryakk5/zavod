'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Calendar } from 'lucide-react';
import {
  crmContactsApi,
  crmDealsApi,
  crmEventsApi,
  type Deal,
} from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { DEFAULT_TENANT_TIMEZONE, formatInTenantTimezone, normalizeTenantTimezone } from '@/lib/timezone';

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
  | 'paid'
  | 'lost';

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
  {
    key: 'lost',
    label: 'Срыв',
    description: 'Возврат/потерянная сделка',
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
    lost: 0,
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

function resolveDealStage(deal: Deal): SalesFunnelStageKey {
  const normalized = normalizeExplicitDealStage(deal.stage);
  return normalized ?? 'new_lead';
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

function buildSalesFunnelStats(deals: Deal[]): SalesFunnelStats {
  const archivedExcluded = 0;
  const currentCounts = createEmptyFunnelCounts();
  const lostReasonCounts = new Map<LostReasonCode, number>();
  let lostDeals = 0;

  deals.forEach((deal) => {
    const stage = resolveDealStage(deal);
    currentCounts[stage] += 1;

    if (stage === 'lost') {
      lostDeals += 1;
      const reasonCode = normalizeLostReasonCode(deal.lost_reason_code);
      lostReasonCounts.set(reasonCode, (lostReasonCounts.get(reasonCode) ?? 0) + 1);
    }
  });

  const totalLeads = deals.length;
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

function formatEventTime(value: string, timeZone: string) {
  return formatInTenantTimezone(value, timeZone, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function FunnelPageClient() {
  const router = useRouter();
  const [stats, setStats] = useState<ClientsStats>(emptyStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);

  useEffect(() => {
    let isActive = true;

    const loadStats = async () => {
      setStatsLoading(true);
      setStatsError(null);

      try {
        const [contacts, events, deals, settings] = await Promise.all([
          crmContactsApi.list(),
          crmEventsApi.list(),
          crmDealsApi.list(),
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
          salesFunnel: buildSalesFunnelStats(deals),
        });
      } catch (loadError) {
        if (!isActive) return;
        console.error('Failed to load CRM funnel stats', loadError);
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

  const displayStats = useMemo(() => {
    if (statsLoading || statsError) {
      return {
        nextEvents: [],
        salesFunnel: createEmptySalesFunnelStats(),
      };
    }

    return {
      nextEvents: stats.nextEvents,
      salesFunnel: stats.salesFunnel,
    };
  }, [stats, statsError, statsLoading]);

  const openStageDeals = (stageKey: SalesFunnelStageKey) => {
    const params = new URLSearchParams();
    params.set('dealsView', 'list');
    params.set('funnelStage', stageKey);
    router.push(`/clients/deals?${params.toString()}`);
  };

  return (
    <div className="space-y-8">
      {statsError ? <p className="text-sm text-red-500">{statsError}</p> : null}

      <div className="rounded-lg bg-transparent">
        <div className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          {displayStats.nextEvents.length > 0 ? (
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
          ) : (
            <div>Ближайшая встреча: Нет запланированных встреч</div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border bg-white p-4 sm:p-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Воронка продаж</h2>
              <p className="text-sm text-muted-foreground">
                Лиды/сделки по стадиям и конверсия по этапам.
              </p>
            </div>
            {!statsLoading && !statsError ? (
              <div className="flex flex-wrap gap-2 text-xs">
                <div className="rounded-md border px-3 py-1.5">
                  Лидов в воронке: <span className="font-semibold">{displayStats.salesFunnel.totalLeads}</span>
                </div>
                <div className="rounded-md border px-3 py-1.5">
                  Сделок в работе: <span className="font-semibold">{displayStats.salesFunnel.dealsInWork}</span>
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
                  Потеряно сделок: <span className="font-semibold">{displayStats.salesFunnel.lostDeals}</span>
                </div>
              </div>
            ) : null}
          </div>

          {statsLoading ? (
            <div className="flex gap-3 overflow-x-auto pb-1 md:grid md:grid-cols-2 xl:grid-cols-6 md:overflow-visible md:pb-0">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={`funnel-skeleton-${index}`}
                  className="min-w-[240px] animate-pulse rounded-lg border p-4 md:min-w-0"
                >
                  <div className="h-3 w-24 rounded bg-slate-200" />
                  <div className="mt-3 h-7 w-12 rounded bg-slate-200" />
                  <div className="mt-3 h-2 w-full rounded bg-slate-100" />
                  <div className="mt-3 h-3 w-28 rounded bg-slate-200" />
                  <div className="mt-2 h-3 w-20 rounded bg-slate-200" />
                </div>
              ))}
            </div>
          ) : null}

          {!statsLoading && !statsError ? (
            <>
              <div
                className="flex gap-3 overflow-x-auto pb-1 snap-x snap-mandatory md:grid md:grid-cols-2 xl:grid-cols-6 md:overflow-visible md:pb-0"
                data-testid="funnel-stage-strip"
              >
                {displayStats.salesFunnel.stages.map((stage, index) => (
                  <button
                    key={stage.key}
                    type="button"
                    onClick={() => openStageDeals(stage.key)}
                    className="min-w-[240px] snap-start cursor-pointer rounded-lg border p-4 text-left transition-shadow hover:shadow-md md:min-w-0"
                    title={`Открыть сделки в этапе «${stage.label}»`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs text-muted-foreground">Этап {index + 1}</div>
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
                  </button>
                ))}
              </div>

              <div className="rounded-lg border p-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="text-sm font-medium">Причины потерь</div>
                    <div className="text-xs text-muted-foreground">
                      Учитываются сделки со стадией «Потеряно» и указанной причиной.
                    </div>
                  </div>
                  <div className="text-sm">
                    Всего потеряно: <span className="font-semibold">{displayStats.salesFunnel.lostDeals}</span>
                  </div>
                </div>
                {displayStats.salesFunnel.lostReasons.length === 0 ? (
                  <div className="mt-3 text-sm text-muted-foreground">
                    Пока нет данных. Причина появится после отметки сделки как «Потеряно».
                  </div>
                ) : (
                  <div className="mt-3 space-y-2 md:grid md:grid-cols-2 md:gap-2 md:space-y-0 xl:grid-cols-4">
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
                Воронка использует ту же стадию сделки, что и Kanban.
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
