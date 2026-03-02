'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { crmContactsApi, crmPaymentsApi, type Contact, type Payment } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ClientProduct } from '@/lib/types';

type DealsView = 'list' | 'kanban';
type DealStatus = Payment['status'];

const DEAL_STATUS_ORDER: DealStatus[] = ['pending', 'paid', 'failed', 'refunded'];

const DEAL_STATUS_LABELS: Record<DealStatus, string> = {
  pending: 'В ожидании',
  paid: 'Оплачено',
  failed: 'Ошибка',
  refunded: 'Возврат',
};

function formatDealAmount(value: Payment['amount'], currency: Payment['currency']): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${value} ${currency || 'RUB'}`;
}

function normalizeDealStatus(raw: unknown): DealStatus {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'pending' || value === 'paid' || value === 'failed' || value === 'refunded') return value;
  return 'pending';
}

function normalizePayment(raw: Payment): Payment {
  return {
    ...raw,
    event_id: raw.event_id ?? null,
    product_id: raw.product_id ?? null,
    currency: raw.currency || 'RUB',
    status: normalizeDealStatus(raw.status),
  };
}

function getContactLabel(contactId: number, contactsById: Map<number, Contact>): string {
  const contact = contactsById.get(contactId);
  if (!contact) return `Клиент #${contactId}`;
  if (!contact.parent_id) return contact.name || `Клиент #${contactId}`;
  const parent = contactsById.get(contact.parent_id);
  if (!parent) return contact.name || `Клиент #${contactId}`;
  return `${parent.name} → ${contact.name}`;
}

function getProductLabel(productId: number | null | undefined, productsById: Map<number, ClientProduct>): string {
  if (!productId) return 'Без продукта';
  const product = productsById.get(productId);
  return product?.name || `Продукт #${productId}`;
}

export function DealsTab() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [deals, setDeals] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<DealsView>('list');

  useEffect(() => {
    let isActive = true;

    const loadDeals = async () => {
      setLoading(true);
      setError(null);
      try {
        const [paymentsData, contactsData, productsData] = await Promise.all([
          crmPaymentsApi.list(),
          crmContactsApi.list(),
          clientProductsApi.list(),
        ]);
        if (!isActive) return;
        setDeals(paymentsData.map(normalizePayment));
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

  const rows = useMemo(() => {
    return [...deals].sort((a, b) => {
      const aTime = new Date(a.created_at || '').getTime();
      const bTime = new Date(b.created_at || '').getTime();
      if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return bTime - aTime;
      return b.id - a.id;
    });
  }, [deals]);

  const kanbanColumns = useMemo(() => {
    const columns = DEAL_STATUS_ORDER.reduce<Record<DealStatus, Payment[]>>((acc, status) => {
      acc[status] = [];
      return acc;
    }, {} as Record<DealStatus, Payment[]>);
    rows.forEach((deal) => {
      columns[normalizeDealStatus(deal.status)].push(deal);
    });
    return columns;
  }, [rows]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Загружаем сделки...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border bg-background p-1">
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

      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Сделки не найдены.</p>
      ) : view === 'list' ? (
        <div className="overflow-x-auto rounded-lg border">
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
              {rows.map((deal) => {
                const status = normalizeDealStatus(deal.status);
                return (
                  <tr key={deal.id} className="border-t">
                    <td className="px-4 py-2">
                      <Link href={`/clients/deals/${deal.id}`} className="font-medium hover:underline">
                        {getProductLabel(deal.product_id, productsById)}
                      </Link>
                    </td>
                    <td className="px-4 py-2">{getContactLabel(deal.contact_id, contactsById)}</td>
                    <td className="px-4 py-2">{DEAL_STATUS_LABELS[status]}</td>
                    <td className="px-4 py-2">{formatDealAmount(deal.amount, deal.currency)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-4">
          {DEAL_STATUS_ORDER.map((status) => (
            <div key={status} className="rounded-xl border bg-card/70 p-3 shadow-sm">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold">{DEAL_STATUS_LABELS[status]}</div>
                <Badge variant="secondary">{kanbanColumns[status].length}</Badge>
              </div>
              <div className="space-y-2 min-h-[120px]">
                {kanbanColumns[status].length === 0 ? (
                  <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">Пусто</div>
                ) : (
                  kanbanColumns[status].map((deal) => (
                    <div key={deal.id} className="rounded-lg border bg-background p-3 text-left shadow-sm">
                      <Link href={`/clients/deals/${deal.id}`} className="block truncate text-sm font-medium hover:underline">
                        {getProductLabel(deal.product_id, productsById)}
                      </Link>
                      <div className="mt-1 text-xs text-muted-foreground">{getContactLabel(deal.contact_id, contactsById)}</div>
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
