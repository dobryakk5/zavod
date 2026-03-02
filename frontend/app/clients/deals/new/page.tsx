'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { crmContactsApi, crmDealsApi, type Contact, type Deal, type DealLossReasonCode } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ClientProduct } from '@/lib/types';

type DealStage = Deal['stage'];

const DEAL_STAGE_OPTIONS: Array<{ value: DealStage; label: string }> = [
  { value: 'new_lead', label: 'Новый лид' },
  { value: 'interest', label: 'Интерес' },
  { value: 'call', label: 'Созвон' },
  { value: 'payment_expected', label: 'Оплата ожидается' },
  { value: 'paid', label: 'Оплачено' },
  { value: 'lost', label: 'Срыв' },
];

const LOST_REASON_OPTIONS: Array<{ value: Exclude<DealLossReasonCode, ''>; label: string }> = [
  { value: 'price', label: 'Дорого' },
  { value: 'timing', label: 'Не вовремя' },
  { value: 'no_response', label: 'Не отвечает' },
  { value: 'not_fit', label: 'Не подходит' },
  { value: 'competitor', label: 'Ушёл к конкуренту' },
  { value: 'priority_changed', label: 'Изменился приоритет' },
  { value: 'other', label: 'Другое' },
];

const CURRENCY_OPTIONS = ['RUB', 'USD', 'EUR'] as const;

function normalizeDealStage(raw: unknown): DealStage {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'new_lead' || value === 'interest' || value === 'call' || value === 'payment_expected' || value === 'paid' || value === 'lost') {
    return value;
  }
  return 'new_lead';
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
  const searchParams = useSearchParams();
  const preselectedContactName = (searchParams.get('contactName') || '').trim();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [contactId, setContactId] = useState<string>('none');
  const [productId, setProductId] = useState<string>('none');
  const [stage, setStage] = useState<DealStage>('new_lead');
  const [amount, setAmount] = useState<string>('');
  const [currency, setCurrency] = useState<string>('RUB');
  const [description, setDescription] = useState<string>('');
  const [lostReasonCode, setLostReasonCode] = useState<string>('none');
  const [lostReasonText, setLostReasonText] = useState<string>('');

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
        const preselectedContactIdRaw = searchParams.get('contactId');
        const preselectedContactId = Number(preselectedContactIdRaw);
        if (
          Number.isFinite(preselectedContactId) &&
          preselectedContactId > 0 &&
          contactsData.some((item) => item.id === preselectedContactId)
        ) {
          setContactId(String(preselectedContactId));
        } else if (contactsData[0]) {
          setContactId(String(contactsData[0].id));
        }
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
  }, [searchParams]);

  const contactsById = useMemo(() => new Map<number, Contact>(contacts.map((contact) => [contact.id, contact])), [contacts]);
  const selectedProductId = useMemo(() => {
    const parsed = Number(productId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [productId]);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);

    const parsedContactId = Number(contactId);
    const parsedProductId = Number(productId);
    if (!Number.isFinite(parsedContactId) || parsedContactId <= 0) {
      setSaveError('Выберите клиента.');
      return;
    }
    if (!Number.isFinite(parsedProductId) || parsedProductId <= 0) {
      setSaveError('Выберите продукт.');
      return;
    }

    const parsedAmount = Number.parseFloat(amount.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount < 0) {
      setSaveError('Введите корректную сумму.');
      return;
    }

    const normalizedCurrency = currency.toUpperCase();
    if (!CURRENCY_OPTIONS.includes(normalizedCurrency as (typeof CURRENCY_OPTIONS)[number])) {
      setSaveError('Некорректная валюта.');
      return;
    }

    if (stage === 'lost' && lostReasonCode === 'none') {
      setSaveError('Укажите причину срыва.');
      return;
    }

    setSaving(true);
    try {
      const created = await crmDealsApi.create({
        contact_id: parsedContactId,
        product_id: parsedProductId,
        stage,
        amount: parsedAmount,
        currency: normalizedCurrency,
        description: description.trim(),
        lost_reason_code: stage === 'lost' ? (lostReasonCode as Exclude<DealLossReasonCode, ''>) : '',
        lost_reason_text: stage === 'lost' ? lostReasonText.trim() : '',
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
          <p className="text-sm text-muted-foreground">
            Сделка — отдельная сущность, платежи привязываются к ней позже
            {preselectedContactName ? ` · Клиент: ${preselectedContactName}` : ''}
          </p>
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
              <Select value={stage} onValueChange={(value) => setStage(normalizeDealStage(value))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DEAL_STAGE_OPTIONS.map((option) => (
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

            {stage === 'lost' ? (
              <div className="space-y-2">
                <Label>Причина срыва</Label>
                <Select value={lostReasonCode} onValueChange={setLostReasonCode}>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите причину" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Не выбрано</SelectItem>
                    {LOST_REASON_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
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

          {stage === 'lost' ? (
            <div className="space-y-2">
              <Label htmlFor="deal-lost-comment">Комментарий причины</Label>
              <Textarea
                id="deal-lost-comment"
                value={lostReasonText}
                onChange={(event) => setLostReasonText(event.target.value)}
                placeholder="Почему сделка сорвалась"
                rows={3}
              />
            </div>
          ) : null}

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
