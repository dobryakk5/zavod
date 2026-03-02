'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { PaymentsTable } from '@/components/crm/payments-table';
import { toast } from 'sonner';
import { clientApi } from '@/lib/api/client';
import { crmContactsApi, crmDealsApi, crmPaymentsApi, type Contact, type Deal, type DealLossReasonCode, type Payment } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ClientProduct } from '@/lib/types';
import {
  DEFAULT_TENANT_TIMEZONE,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
} from '@/lib/timezone';

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

function toSelectIdValue(raw: unknown): string {
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? String(parsed) : 'none';
}

function formatIntegerAmount(value: unknown): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return '0';
  return new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 0,
  }).format(Math.round(parsed));
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

  const [deal, setDeal] = useState<Deal | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [contactId, setContactId] = useState<string>('none');
  const [productId, setProductId] = useState<string>('none');
  const [stage, setStage] = useState<DealStage>('new_lead');
  const [amount, setAmount] = useState<string>('');
  const [currency, setCurrency] = useState<string>('RUB');
  const [description, setDescription] = useState<string>('');
  const [lostReasonCode, setLostReasonCode] = useState<string>('none');
  const [lostReasonText, setLostReasonText] = useState<string>('');
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [newPaymentAmount, setNewPaymentAmount] = useState('');
  const [newPaymentCurrency, setNewPaymentCurrency] = useState('RUB');
  const [newPaymentPlannedAt, setNewPaymentPlannedAt] = useState('');
  const [newPaymentPaid, setNewPaymentPaid] = useState(false);
  const [savingPayment, setSavingPayment] = useState(false);
  const [paymentToEdit, setPaymentToEdit] = useState<Payment | null>(null);
  const [editingPaymentAmount, setEditingPaymentAmount] = useState('');
  const [editingPaymentStatus, setEditingPaymentStatus] = useState<Payment['status']>('pending');
  const [savingPaymentEdit, setSavingPaymentEdit] = useState(false);
  const [paymentLinkLoadingId, setPaymentLinkLoadingId] = useState<number | null>(null);
  const [paymentDeletingId, setPaymentDeletingId] = useState<number | null>(null);

  useEffect(() => {
    const loadTimezone = async () => {
      try {
        const settings = await clientApi.getSettings();
        setTenantTimezone(normalizeTenantTimezone(settings.timezone));
      } catch (error) {
        console.error('Failed to load client timezone:', error);
        setTenantTimezone(DEFAULT_TENANT_TIMEZONE);
      }
    };
    void loadTimezone();
  }, []);

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
        const [dealData, contactsData, productsData, paymentsData] = await Promise.all([
          crmDealsApi.detail(dealId),
          crmContactsApi.list(),
          clientProductsApi.list(),
          crmPaymentsApi.list(),
        ]);
        if (!isActive) return;

        const dealPayments = paymentsData.filter((payment) => payment.deal_id === dealData.id);
        setDeal({
          ...dealData,
          payments_count:
            typeof dealData.payments_count === 'number' ? dealData.payments_count : dealPayments.length,
        });
        setContacts(contactsData);
        setProducts(productsData);
        setPayments(dealPayments);

        setContactId(toSelectIdValue(dealData.contact_id));
        setProductId(toSelectIdValue(dealData.product_id));
        setStage(normalizeDealStage(dealData.stage));
        setAmount(String(dealData.amount ?? ''));
        setCurrency((dealData.currency || 'RUB').toUpperCase());
        setDescription(dealData.description || '');
        setLostReasonCode((dealData.lost_reason_code || '').trim() || 'none');
        setLostReasonText(dealData.lost_reason_text || '');
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
  const selectedContactId = useMemo(() => {
    const parsed = Number(contactId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [contactId]);
  const selectedProductId = useMemo(() => {
    const parsed = Number(productId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [productId]);
  const sortedPayments = useMemo(() => {
    return [...payments].sort((a, b) => {
      const aTime = new Date(a.created_at || '').getTime();
      const bTime = new Date(b.created_at || '').getTime();
      if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return bTime - aTime;
      return b.id - a.id;
    });
  }, [payments]);

  const handleSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);

    if (!dealId) {
      setSaveError('Некорректный ID сделки.');
      return;
    }

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
      const updated = await crmDealsApi.update(dealId, {
        contact_id: parsedContactId,
        product_id: parsedProductId,
        stage,
        amount: parsedAmount,
        currency: normalizedCurrency,
        description: description.trim(),
        lost_reason_code: stage === 'lost' ? (lostReasonCode as Exclude<DealLossReasonCode, ''>) : '',
        lost_reason_text: stage === 'lost' ? lostReasonText.trim() : '',
      });

      setDeal(updated);
      setStage(normalizeDealStage(updated.stage));
      setAmount(String(updated.amount ?? ''));
      setCurrency((updated.currency || 'RUB').toUpperCase());
      setDescription(updated.description || '');
      setLostReasonCode((updated.lost_reason_code || '').trim() || 'none');
      setLostReasonText(updated.lost_reason_text || '');
      setSaveSuccess('Сделка сохранена.');
    } catch (error) {
      console.error('Failed to save deal', error);
      setSaveError('Не удалось сохранить сделку.');
    } finally {
      setSaving(false);
    }
  };

  const handleCreatePayment = async () => {
    if (!deal) return;

    const parsedAmount = Number.parseFloat(newPaymentAmount.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      toast.error('Введите корректную сумму платежа.');
      return;
    }

    const normalizedCurrency = (newPaymentCurrency || 'RUB').toUpperCase();
    if (!CURRENCY_OPTIONS.includes(normalizedCurrency as (typeof CURRENCY_OPTIONS)[number])) {
      toast.error('Некорректная валюта.');
      return;
    }

    const plannedAtPayload = newPaymentPlannedAt
      ? localDateTimeStringToUtcISOString(`${newPaymentPlannedAt}T12:00`, tenantTimezone)
      : null;
    if (newPaymentPlannedAt && !plannedAtPayload) {
      toast.error('Некорректная плановая дата.');
      return;
    }

    const paidAtPayload = newPaymentPaid
      ? plannedAtPayload || new Date().toISOString()
      : null;
    setSavingPayment(true);
    try {
      const created = await crmPaymentsApi.create({
        contact_id: deal.contact_id,
        deal_id: deal.id,
        event_id: null,
        product_id: deal.product_id || null,
        amount: parsedAmount,
        currency: normalizedCurrency,
        status: newPaymentPaid ? 'paid' : 'pending',
        payment_method: '',
        transaction_id: '',
        description: '',
        planned_at: plannedAtPayload,
        paid_at: paidAtPayload,
      });
      setPayments((prev) => [created, ...prev]);
      setDeal((prev) =>
        prev
          ? {
              ...prev,
              payments_count: (prev.payments_count || 0) + 1,
            }
          : prev
      );
      setNewPaymentAmount('');
      setNewPaymentCurrency('RUB');
      setNewPaymentPlannedAt('');
      setNewPaymentPaid(false);
      toast.success('Платёж добавлен.');
    } catch (error) {
      console.error('Failed to create payment', error);
      toast.error('Не удалось создать платёж.');
    } finally {
      setSavingPayment(false);
    }
  };

  const handleStartEditPayment = (payment: Payment) => {
    setPaymentToEdit(payment);
    setEditingPaymentAmount(String(Math.round(Number(payment.amount) || 0)));
    setEditingPaymentStatus(payment.status);
  };

  const handleCancelEditPayment = () => {
    setPaymentToEdit(null);
    setEditingPaymentAmount('');
    setEditingPaymentStatus('pending');
  };

  const handleSavePaymentEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!paymentToEdit) return;

    const parsedAmount = Number(editingPaymentAmount.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      toast.error('Введите корректную сумму.');
      return;
    }

    setSavingPaymentEdit(true);
    try {
      const updated = await crmPaymentsApi.update(paymentToEdit.id, {
        amount: parsedAmount,
        status: editingPaymentStatus,
        paid_at:
          editingPaymentStatus === 'paid'
            ? paymentToEdit.paid_at ?? new Date().toISOString()
            : null,
      });
      setPayments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      handleCancelEditPayment();
      toast.success('Платёж обновлен.');
    } catch (error) {
      console.error('Failed to update payment', error);
      toast.error('Не удалось обновить платёж.');
    } finally {
      setSavingPaymentEdit(false);
    }
  };

  const handleDeletePayment = async (payment: Payment) => {
    const confirmed = window.confirm(
      `Удалить платеж на сумму ${formatIntegerAmount(payment.amount)} ${payment.currency}?`
    );
    if (!confirmed) return;

    setPaymentDeletingId(payment.id);
    try {
      await crmPaymentsApi.delete(payment.id);
      setPayments((prev) => prev.filter((item) => item.id !== payment.id));
      setDeal((prev) =>
        prev
          ? {
              ...prev,
              payments_count: Math.max(0, (prev.payments_count || 0) - 1),
            }
          : prev
      );
      toast.success('Платёж удалён.');
    } catch (error) {
      console.error('Failed to delete payment', error);
      toast.error('Не удалось удалить платёж.');
    } finally {
      setPaymentDeletingId(null);
    }
  };

  const handleCopyPaymentLink = async (payment: Payment) => {
    const numericAmount = Number(payment.amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      toast.error('Укажите корректную сумму платежа.');
      return;
    }

    setPaymentLinkLoadingId(payment.id);
    try {
      const metadata: Record<string, string> = {
        crm_payment_id: String(payment.id),
        crm_contact_id: String(payment.contact_id),
      };
      if (deal?.id) {
        metadata.crm_deal_id = String(deal.id);
      }

      const response = await crmPaymentsApi.generateYooKassaLink({
        amount: numericAmount,
        currency: payment.currency || 'RUB',
        description: (payment.description || '').trim() || `Оплата по сделке #${deal?.id || ''}`.trim(),
        metadata,
      });
      const paymentUrl = response.payment_url || response.confirmation_url;
      if (!paymentUrl) throw new Error('Payment URL was not returned');

      if (navigator.clipboard?.writeText && window.isSecureContext) {
        await navigator.clipboard.writeText(paymentUrl);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = paymentUrl;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      toast.success('Ссылка на оплату скопирована.');
    } catch (error) {
      console.error('Failed to generate payment link', error);
      toast.error('Не удалось сгенерировать ссылку оплаты.');
    } finally {
      setPaymentLinkLoadingId(null);
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

          <div className="space-y-4 rounded-lg border bg-slate-50/70 p-4">
            <div className="text-sm font-medium">
              Платежи по сделке
              {typeof deal?.payments_count === 'number' ? ` (${deal.payments_count})` : ''}
            </div>
            <div className="space-y-3 rounded-md border bg-white p-4">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="deal-payment-amount">Сумма</Label>
                  <Input
                    id="deal-payment-amount"
                    type="number"
                    min={0}
                    step="0.01"
                    value={newPaymentAmount}
                    onChange={(event) => setNewPaymentAmount(event.target.value)}
                    placeholder="0.00"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deal-payment-planned-at">Плановая дата оплаты</Label>
                  <Input
                    id="deal-payment-planned-at"
                    type="date"
                    value={newPaymentPlannedAt}
                    onChange={(event) => setNewPaymentPlannedAt(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="deal-payment-currency">Валюта</Label>
                  <Input
                    id="deal-payment-currency"
                    value={newPaymentCurrency}
                    onChange={(event) => setNewPaymentCurrency(event.target.value)}
                    placeholder="RUB"
                  />
                </div>
              </div>

              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={newPaymentPaid}
                    onChange={(event) => setNewPaymentPaid(event.target.checked)}
                  />
                  Оплачено
                </label>
              </div>

              <Button type="button" disabled={savingPayment} onClick={() => void handleCreatePayment()}>
                {savingPayment ? 'Сохраняем...' : 'Добавить платёж'}
              </Button>
            </div>

            <PaymentsTable
              payments={sortedPayments}
              contacts={contacts}
              tenantTimezone={tenantTimezone}
              paymentLinkLoadingId={paymentLinkLoadingId}
              paymentDeletingId={paymentDeletingId}
              onCopyPaymentLink={(payment) => void handleCopyPaymentLink(payment)}
              onEditPayment={(payment) => handleStartEditPayment(payment)}
              onDeletePayment={(payment) => void handleDeletePayment(payment)}
              emptyText="Нет платежей по этой сделке"
            />
          </div>

          {saveError ? <p className="text-sm text-red-500">{saveError}</p> : null}
          {saveSuccess ? <p className="text-sm text-emerald-600">{saveSuccess}</p> : null}

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              {selectedContactId ? (
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

      <Dialog
        open={paymentToEdit !== null}
        onOpenChange={(open) => {
          if (!open) handleCancelEditPayment();
        }}
      >
        <DialogContent className="sm:max-w-md bg-white text-black dark:bg-white dark:text-black">
          <DialogHeader>
            <DialogTitle className="text-black">Редактировать платёж</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSavePaymentEdit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-payment-amount">Сумма</Label>
              <Input
                id="edit-payment-amount"
                type="number"
                min={0}
                step="0.01"
                value={editingPaymentAmount}
                onChange={(event) => setEditingPaymentAmount(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Статус</Label>
              <Select value={editingPaymentStatus} onValueChange={(value) => setEditingPaymentStatus(value as Payment['status'])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">В ожидании</SelectItem>
                  <SelectItem value="paid">Оплачено</SelectItem>
                  <SelectItem value="failed">Ошибка</SelectItem>
                  <SelectItem value="refunded">Возврат</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={handleCancelEditPayment} disabled={savingPaymentEdit}>
                Отмена
              </Button>
              <Button type="submit" disabled={savingPaymentEdit}>
                {savingPaymentEdit ? 'Сохраняем...' : 'Сохранить'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
