'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { crmContactsApi, crmDealsApi, type Contact, type Deal } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ClientProduct } from '@/lib/types';
import { useIsMobileBreakpoint } from './use-mobile-breakpoint';

type DealsView = 'list' | 'kanban';
type DealStageKey = Deal['stage'];

const DEAL_STAGE_ORDER: DealStageKey[] = ['new_lead', 'interest', 'call', 'payment_expected', 'paid', 'lost'];

const DEAL_STAGE_LABELS: Record<DealStageKey, string> = {
  new_lead: 'Новый лид',
  interest: 'Интерес',
  call: 'Созвон',
  payment_expected: 'Оплата ожидается',
  paid: 'Оплачено',
  lost: 'Срыв',
};

function formatDealAmount(value: Deal['amount'], currency: Deal['currency']): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  const normalized = new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 0,
  }).format(Math.round(Number(value)));
  return `${normalized} ${currency || 'RUB'}`;
}

function normalizeDealStage(raw: unknown): DealStageKey {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'new_lead' || value === 'interest' || value === 'call' || value === 'payment_expected' || value === 'paid' || value === 'lost') {
    return value;
  }
  return 'new_lead';
}

function parseDealStage(raw: unknown): DealStageKey | null {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'new_lead' || value === 'interest' || value === 'call' || value === 'payment_expected' || value === 'paid' || value === 'lost') {
    return value;
  }
  return null;
}

function normalizeDeal(raw: Deal): Deal {
  return {
    ...raw,
    stage: normalizeDealStage(raw.stage),
    currency: (raw.currency || 'RUB').toUpperCase(),
  };
}

function getContactLabel(deal: Deal, contactsById: Map<number, Contact>): string {
  const contact = contactsById.get(deal.contact_id);
  if (!contact) return deal.contact_name || `Клиент #${deal.contact_id}`;
  if (!contact.parent_id) return contact.name || deal.contact_name || `Клиент #${deal.contact_id}`;
  const parent = contactsById.get(contact.parent_id);
  if (!parent) return contact.name || deal.contact_name || `Клиент #${deal.contact_id}`;
  return `${parent.name} → ${contact.name}`;
}

function getProductLabel(productId: number | null | undefined, productsById: Map<number, ClientProduct>): string {
  if (!productId) return 'Без продукта';
  const product = productsById.get(productId);
  return product?.name || `Продукт #${productId}`;
}

export function DealsTab() {
  const searchParams = useSearchParams();
  const isMobile = useIsMobileBreakpoint();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [view, setView] = useState<DealsView>('list');
  const [draggingDealId, setDraggingDealId] = useState<number | null>(null);
  const [kanbanDropStage, setKanbanDropStage] = useState<DealStageKey | null>(null);
  const [movingDealId, setMovingDealId] = useState<number | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadDeals = async () => {
      setLoading(true);
      setError(null);
      try {
        const [dealsData, contactsData, productsData] = await Promise.all([
          crmDealsApi.list(),
          crmContactsApi.list(),
          clientProductsApi.list(),
        ]);
        if (!isActive) return;
        setDeals(dealsData.map(normalizeDeal));
        setContacts(contactsData);
        setProducts(productsData);
      } catch (err) {
        console.error('Failed to load deals data', err);
        if (!isActive) return;
        setError('Не удалось загрузить сделки.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadDeals();

    return () => {
      isActive = false;
    };
  }, []);

  const contactsById = useMemo(() => new Map<number, Contact>(contacts.map((contact) => [contact.id, contact])), [contacts]);
  const productsById = useMemo(() => new Map<number, ClientProduct>(products.map((product) => [product.id, product])), [products]);
  const funnelStageFilter = useMemo(() => {
    const value = searchParams.get('funnelStage');
    return value ? parseDealStage(value) : null;
  }, [searchParams]);
  const viewFromQuery = useMemo(() => {
    const value = searchParams.get('dealsView');
    return value === 'kanban' ? 'kanban' : value === 'list' ? 'list' : null;
  }, [searchParams]);

  useEffect(() => {
    if (viewFromQuery) setView(viewFromQuery);
  }, [viewFromQuery]);

  useEffect(() => {
    if (isMobile) {
      setView('list');
    }
  }, [isMobile]);

  const rows = useMemo(() => {
    return [...deals].sort((a, b) => {
      const aTime = new Date(a.updated_at || a.created_at || '').getTime();
      const bTime = new Date(b.updated_at || b.created_at || '').getTime();
      if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return bTime - aTime;
      return b.id - a.id;
    });
  }, [deals]);

  const filteredRows = useMemo(() => {
    if (!funnelStageFilter) return rows;
    return rows.filter((deal) => deal.stage === funnelStageFilter);
  }, [funnelStageFilter, rows]);

  const kanbanColumns = useMemo(() => {
    const columns = DEAL_STAGE_ORDER.reduce<Record<DealStageKey, Deal[]>>((acc, stage) => {
      acc[stage] = [];
      return acc;
    }, {} as Record<DealStageKey, Deal[]>);
    filteredRows.forEach((deal) => {
      columns[deal.stage].push(deal);
    });
    return columns;
  }, [filteredRows]);

  const moveDealToStage = async (dealId: number, targetStage: DealStageKey) => {
    const currentDeal = deals.find((item) => item.id === dealId);
    if (!currentDeal) return;
    if (currentDeal.stage === targetStage) return;

    setMoveError(null);
    setMovingDealId(dealId);

    const prevDeals = deals;
    const optimistic = deals.map((item) =>
      item.id === dealId
        ? {
            ...item,
            stage: targetStage,
            lost_reason_code:
              targetStage === 'lost'
                ? (((item.lost_reason_code || '').trim() || 'other') as Deal['lost_reason_code'])
                : '',
            lost_reason_text: targetStage === 'lost' ? (item.lost_reason_text || '') : '',
          }
        : item
    );
    setDeals(optimistic);

    try {
      const updated = await crmDealsApi.update(dealId, {
        stage: targetStage,
        lost_reason_code:
          targetStage === 'lost'
            ? (((currentDeal.lost_reason_code || '').trim() || 'other') as Deal['lost_reason_code'])
            : '',
        lost_reason_text: targetStage === 'lost' ? (currentDeal.lost_reason_text || '') : '',
      });
      setDeals((items) => items.map((item) => (item.id === dealId ? normalizeDeal(updated) : item)));
    } catch (err) {
      console.error('Failed to move deal stage', err);
      setDeals(prevDeals);
      setMoveError('Не удалось изменить этап сделки.');
    } finally {
      setMovingDealId(null);
    }
  };

  if (loading) {
    return <p className="text-sm text-muted-foreground">Загружаем сделки...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  const effectiveView: DealsView = isMobile ? 'list' : view;

  return (
    <div className="space-y-4">
      {funnelStageFilter ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-slate-50 px-3 py-2 text-sm">
          <div>
            Фильтр по этапу воронки: <span className="font-medium">{DEAL_STAGE_LABELS[funnelStageFilter]}</span>
          </div>
          <Link href="/clients/deals" className="text-primary hover:underline">
            Сбросить фильтр
          </Link>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="hidden rounded-lg border bg-background p-1 md:inline-flex">
          <Button type="button" size="sm" variant={view === 'list' ? 'default' : 'ghost'} onClick={() => setView('list')}>
            Список
          </Button>
          <Button type="button" size="sm" variant={view === 'kanban' ? 'default' : 'ghost'} onClick={() => setView('kanban')}>
            Kanban
          </Button>
        </div>
        <Button asChild type="button">
          <Link href="/clients/deals/new" target="_blank" rel="noopener noreferrer">
            Добавить сделку
          </Link>
        </Button>
      </div>
      {moveError ? <p className="text-sm text-red-500">{moveError}</p> : null}

      {filteredRows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {funnelStageFilter ? 'Сделки по выбранному этапу не найдены.' : 'Сделки не найдены.'}
        </p>
      ) : effectiveView === 'list' ? (
        <>
          <div className="space-y-3 md:hidden" data-testid="deals-mobile-list">
            {filteredRows.map((deal) => (
              <Link
                key={deal.id}
                href={`/clients/deals/${deal.id}`}
                className="block rounded-xl border p-4 transition-colors hover:border-slate-300 hover:bg-slate-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-900">
                      {getProductLabel(deal.product_id, productsById)}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">{getContactLabel(deal, contactsById)}</div>
                  </div>
                  <Badge variant="secondary" className="shrink-0">
                    {DEAL_STAGE_LABELS[deal.stage]}
                  </Badge>
                </div>
                <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
                  <span>Сумма</span>
                  <span className="font-medium text-slate-900">{formatDealAmount(deal.amount, deal.currency)}</span>
                </div>
              </Link>
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded-lg border md:block">
            <table className="w-full text-sm">
              <thead className="bg-muted/40">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Продукт</th>
                  <th className="px-4 py-2 text-left font-medium">Имя</th>
                  <th className="px-4 py-2 text-left font-medium">Этап</th>
                  <th className="px-4 py-2 text-left font-medium">Сумма</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((deal) => (
                  <tr key={deal.id} className="border-t">
                    <td className="px-4 py-2">
                      <Link href={`/clients/deals/${deal.id}`} className="font-medium hover:underline">
                        {getProductLabel(deal.product_id, productsById)}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{getContactLabel(deal, contactsById)}</td>
                    <td className="px-4 py-2">{DEAL_STAGE_LABELS[deal.stage]}</td>
                    <td className="px-4 py-2">{formatDealAmount(deal.amount, deal.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="hidden gap-4 md:grid xl:grid-cols-6">
          {DEAL_STAGE_ORDER.map((stage) => (
            <div
              key={stage}
              className={`rounded-xl border bg-card/70 p-3 shadow-sm transition-colors ${
                kanbanDropStage === stage && draggingDealId !== null ? 'border-primary bg-primary/5' : ''
              }`}
              onDragOver={(event) => {
                event.preventDefault();
                setKanbanDropStage(stage);
              }}
              onDragLeave={(event) => {
                const related = event.relatedTarget as Node | null;
                if (related && event.currentTarget.contains(related)) return;
                setKanbanDropStage((prev) => (prev === stage ? null : prev));
              }}
              onDrop={(event) => {
                event.preventDefault();
                const draggedIdRaw = event.dataTransfer.getData('text/plain');
                const draggedId = Number.parseInt(draggedIdRaw, 10);
                const resolvedId =
                  Number.isFinite(draggedId) && draggedId > 0 ? draggedId : draggingDealId;
                setKanbanDropStage(null);
                setDraggingDealId(null);
                if (!resolvedId) return;
                void moveDealToStage(resolvedId, stage);
              }}
            >
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold">{DEAL_STAGE_LABELS[stage]}</div>
                <Badge variant="secondary">{kanbanColumns[stage].length}</Badge>
              </div>
              <div className="space-y-2 min-h-[120px]">
                {kanbanColumns[stage].length === 0 ? (
                  <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">Пусто</div>
                ) : (
                  kanbanColumns[stage].map((deal) => (
                    <div
                      key={deal.id}
                      draggable
                      onDragStart={(event) => {
                        setDraggingDealId(deal.id);
                        event.dataTransfer.setData('text/plain', String(deal.id));
                        event.dataTransfer.effectAllowed = 'move';
                      }}
                      onDragEnd={() => {
                        setDraggingDealId(null);
                        setKanbanDropStage(null);
                      }}
                      className={`rounded-lg border bg-background p-3 text-left shadow-sm cursor-grab active:cursor-grabbing ${
                        movingDealId === deal.id ? 'opacity-60' : ''
                      }`}
                    >
                      <Link href={`/clients/deals/${deal.id}`} className="block truncate text-sm font-medium hover:underline">
                        {getProductLabel(deal.product_id, productsById)}
                      </Link>
                      <div className="mt-1 text-xs text-muted-foreground">{getContactLabel(deal, contactsById)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatDealAmount(deal.amount, deal.currency)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
