'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { crmContactsApi, crmPaymentsApi, type Contact, type Payment } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ClientProduct } from '@/lib/types';

type DealStatus = Payment['status'];

const DEAL_STATUS_OPTIONS: Array<{ value: DealStatus; label: string }> = [
  { value: 'pending', label: 'В ожидании' },
  { value: 'paid', label: 'Оплачено' },
  { value: 'failed', label: 'Ошибка' },
  { value: 'refunded', label: 'Возврат' },
];

const CURRENCY_OPTIONS = ['RUB', 'USD', 'EUR'] as const;

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
    currency: (raw.currency || 'RUB').toUpperCase(),
    status: normalizeDealStatus(raw.status),
  };
}

function toDateTimeInputValue(value: string | null | undefined): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function fromDateTimeInputValue(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function getContactLabel(contactId: number, contactsById: Map<number, Contact>): string {
  const contact = contactsById.get(contactId);
  if (!contact) return `Клиент #${contactId}`;
  if (!contact.parent_id) return contact.name || `Клиент #${contactId}`;
  const parent = contactsById.get(contact.parent_id);
  if (!parent) return contact.name || `Клиент #${contactId}`;
  return `${parent.name} → ${contact.name}`;
}

export default function DealEditPage() {
  const params = useParams<{ id: string }>();
  const rawId = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const dealId = useMemo(() => {
    const parsed = Number(rawId);
    return Number.isFinite(parsed) ? parsed : null;
  }, [rawId]);

  const [deal, setDeal] = useState<Payment | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [contactId, setContactId] = useState<string>('none');
  const [productId, setProductId] = useState<string>('none');
  const [status, setStatus] = useState<DealStatus>('pending');
  const [amount, setAmount] = useState<string>('');
  const [currency, setCurrency] = useState<string>('RUB');
  const [plannedAt, setPlannedAt] = useState<string>('');
  const [paidAt, setPaidAt] = useState<string>('');
  const [paymentMethod, setPaymentMethod] = useState<string>('');
  const [description, setDescription] = useState<string>('');

  useEffect(() => {
    let isActive = true;

    const load = async () => {
      if (!dealId) {
        setLoadError('Некорректный ID сделки.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setLoadError(null);
      try {
        const [dealData, contactsData, productsData] = await Promise.all([
          crmPaymentsApi.detail(dealId),
          crmContactsApi.list(),
          clientProductsApi.list(),
        ]);
        if (!isActive) return;

        const normalizedDeal = normalizePayment(dealData);
        setDeal(normalizedDeal);
        setContacts(contactsData);
        setProducts(productsData);

        setContactId(String(normalizedDeal.contact_id));
        setProductId(normalizedDeal.product_id ? String(normalizedDeal.product_id) : 'none');
        setStatus(normalizedDeal.status);
        setAmount(String(normalizedDeal.amount ?? ''));
        setCurrency((normalizedDeal.currency || 'RUB').toUpperCase());
        setPlannedAt(toDateTimeInputValue(normalizedDeal.planned_at));
        setPaidAt(toDateTimeInputValue(normalizedDeal.paid_at));
        setPaymentMethod(normalizedDeal.payment_method || '');
        setDescription(normalizedDeal.description || '');
      } catch (error) {
        console.error('Failed to load deal page', error);
        if (!isActive) return;
        setLoadError('Не удалось загрузить сделку.');
      } finally {
        if (isActive) setLoading(false);
      }
    };

    void load();
    return () => {
      isActive = false;
    };
  }, [dealId]);

  const contactsById = useMemo(() => new Map<number, Contact>(contacts.map((contact) => [contact.id, contact])), [contacts]);
  const hasCurrentContact = contactId !== 'none' && contacts.some((contact) => String(contact.id) === contactId);
  const hasCurrentProduct = productId !== 'none' && products.some((product) => String(product.id) === productId);
  const selectedContactId = Number(contactId);
  const selectedProductId = useMemo(() => {
    const parsed = Number(productId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [productId]);

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);

    if (!dealId) {
      setSaveError('Некорректный ID сделки.');
      return;
    }
    if (contactId === 'none') {
      setSaveError('Выберите клиента.');
      return;
    }
    if (productId === 'none') {
      setSaveError('Выберите продукт.');
      return;
    }

    const parsedAmount = Number.parseFloat(amount.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      setSaveError('Введите корректную сумму.');
      return;
    }

    const normalizedCurrency = currency.toUpperCase();
    if (!CURRENCY_OPTIONS.includes(normalizedCurrency as (typeof CURRENCY_OPTIONS)[number])) {
      setSaveError('Некорректная валюта.');
      return;
    }

    const plannedAtIso = fromDateTimeInputValue(plannedAt);
    const paidAtIso = fromDateTimeInputValue(paidAt);
    if (status === 'paid' && paidAt && !paidAtIso) {
      setSaveError('Некорректная дата фактической оплаты.');
      return;
    }
    if (plannedAt && !plannedAtIso) {
      setSaveError('Некорректная плановая дата.');
      return;
    }

    setSaving(true);
    try {
      const updated = await crmPaymentsApi.update(dealId, {
        contact_id: Number(contactId),
        product_id: Number(productId),
        amount: parsedAmount,
        currency: normalizedCurrency,
        status,
        payment_method: paymentMethod.trim(),
        description: description.trim(),
        planned_at: plannedAtIso,
        paid_at: status === 'paid' ? (paidAtIso || deal?.paid_at || new Date().toISOString()) : null,
      });

      const normalizedDeal = normalizePayment(updated);
      setDeal(normalizedDeal);
      setStatus(normalizedDeal.status);
      setAmount(String(normalizedDeal.amount ?? ''));
      setCurrency((normalizedDeal.currency || 'RUB').toUpperCase());
      setPlannedAt(toDateTimeInputValue(normalizedDeal.planned_at));
      setPaidAt(toDateTimeInputValue(normalizedDeal.paid_at));
      setPaymentMethod(normalizedDeal.payment_method || '');
      setDescription(normalizedDeal.description || '');
      setSaveSuccess('Сделка сохранена.');
    } catch (error) {
      console.error('Failed to save deal', error);
      setSaveError('Не удалось сохранить сделку.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Редактирование сделки</h1>
          <p className="text-sm text-muted-foreground">{dealId ? `Сделка #${dealId}` : 'Сделка'}</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/clients?tab=deals">К списку сделок</Link>
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Загружаем сделку...</p>
      ) : loadError ? (
        <p className="text-sm text-red-500">{loadError}</p>
      ) : (
        <form onSubmit={handleSave} className="space-y-6 rounded-xl border bg-white p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Клиент</Label>
              <Select value={contactId} onValueChange={setContactId}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите клиента" />
                </SelectTrigger>
                <SelectContent>
                  {!hasCurrentContact && contactId !== 'none' ? (
                    <SelectItem value={contactId}>Клиент #{contactId}</SelectItem>
                  ) : null}
                  {contacts.map((contact) => (
                    <SelectItem key={contact.id} value={String(contact.id)}>
                      {getContactLabel(contact.id, contactsById)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Продукт</Label>
              <div className="flex items-center gap-2">
                <div className="min-w-0 flex-1">
                  <Select value={productId} onValueChange={setProductId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите продукт" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Не выбрано</SelectItem>
                      {!hasCurrentProduct && productId !== 'none' ? (
                        <SelectItem value={productId}>Продукт #{productId}</SelectItem>
                      ) : null}
                      {products.map((product) => (
                        <SelectItem key={product.id} value={String(product.id)}>
                          {product.name || `Продукт #${product.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {selectedProductId ? (
                  <Button asChild type="button" size="sm" variant="outline" className="shrink-0">
                    <Link href={`/product/${selectedProductId}`}>Открыть</Link>
                  </Button>
                ) : (
                  <Button type="button" size="sm" variant="outline" className="shrink-0" disabled>
                    Открыть
                  </Button>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Этап</Label>
              <Select value={status} onValueChange={(value) => setStatus(normalizeDealStatus(value))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DEAL_STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="deal-amount">Сумма</Label>
              <Input
                id="deal-amount"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="Например, 15000"
              />
            </div>

            <div className="space-y-2">
              <Label>Валюта</Label>
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCY_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="deal-method">Метод оплаты</Label>
              <Input
                id="deal-method"
                value={paymentMethod}
                onChange={(event) => setPaymentMethod(event.target.value)}
                placeholder="Например, card"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="deal-planned-at">Плановая дата оплаты</Label>
              <Input
                id="deal-planned-at"
                type="datetime-local"
                value={plannedAt}
                onChange={(event) => setPlannedAt(event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="deal-paid-at">Дата оплаты</Label>
              <Input
                id="deal-paid-at"
                type="datetime-local"
                value={paidAt}
                onChange={(event) => setPaidAt(event.target.value)}
                disabled={status !== 'paid'}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="deal-description">Описание</Label>
            <Textarea
              id="deal-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Комментарий к сделке"
              rows={4}
            />
          </div>

          <div className="rounded-md border bg-slate-50 px-3 py-2 text-sm text-muted-foreground">
            {deal?.event_id ? `Привязана к встрече #${deal.event_id}` : 'Сделка без привязки к встрече'}
          </div>

          {saveError ? <p className="text-sm text-red-500">{saveError}</p> : null}
          {saveSuccess ? <p className="text-sm text-emerald-600">{saveSuccess}</p> : null}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              {Number.isFinite(selectedContactId) && selectedContactId > 0 ? (
                <Button asChild variant="ghost" type="button">
                  <Link href={`/contact/${selectedContactId}`}>Открыть карточку клиента</Link>
                </Button>
              ) : null}
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? 'Сохраняем...' : 'Сохранить сделку'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
