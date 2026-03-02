'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
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

export default function DealCreatePage() {
  const router = useRouter();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
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
      setLoading(true);
      setLoadError(null);
      try {
        const [contactsData, productsData] = await Promise.all([crmContactsApi.list(), clientProductsApi.list()]);
        if (!isActive) return;
        setContacts(contactsData);
        setProducts(productsData);
        if (contactsData[0]) setContactId(String(contactsData[0].id));
        if (productsData[0]) setProductId(String(productsData[0].id));
      } catch (error) {
        console.error('Failed to load create-deal page', error);
        if (!isActive) return;
        setLoadError('Не удалось загрузить данные для создания сделки.');
      } finally {
        if (isActive) setLoading(false);
      }
    };
    void load();
    return () => {
      isActive = false;
    };
  }, []);

  const contactsById = useMemo(() => new Map<number, Contact>(contacts.map((contact) => [contact.id, contact])), [contacts]);
  const selectedProductId = useMemo(() => {
    const parsed = Number(productId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [productId]);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);

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
      const created = await crmPaymentsApi.create({
        contact_id: Number(contactId),
        product_id: Number(productId),
        event_id: null,
        amount: parsedAmount,
        currency: normalizedCurrency,
        status,
        payment_method: paymentMethod.trim(),
        transaction_id: `deal_${Date.now()}`,
        description: description.trim(),
        planned_at: plannedAtIso,
        paid_at: status === 'paid' ? (paidAtIso || new Date().toISOString()) : null,
      });
      router.replace(`/clients/deals/${created.id}`);
    } catch (error) {
      console.error('Failed to create deal', error);
      setSaveError('Не удалось создать сделку.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl py-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Новая сделка</h1>
          <p className="text-sm text-muted-foreground">Сделка создаётся как платеж с привязкой к продукту</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/clients?tab=deals">К списку сделок</Link>
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Загружаем форму...</p>
      ) : loadError ? (
        <p className="text-sm text-red-500">{loadError}</p>
      ) : (
        <form onSubmit={handleCreate} className="space-y-6 rounded-xl border bg-white p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Клиент</Label>
              <Select value={contactId} onValueChange={setContactId}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите клиента" />
                </SelectTrigger>
                <SelectContent>
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
                    <Link href={`/product/${selectedProductId}`} target="_blank" rel="noopener noreferrer">
                      Открыть
                    </Link>
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

          {saveError ? <p className="text-sm text-red-500">{saveError}</p> : null}

          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? 'Создаём...' : 'Создать сделку'}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
