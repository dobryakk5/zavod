"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { PlusIcon, EditIcon, TrashIcon, XIcon, CopyIcon } from 'lucide-react';
import { crmCategoriesApi, crmContactsApi, crmPaymentsApi } from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { DEFAULT_TENANT_TIMEZONE, formatInTenantTimezone, normalizeTenantTimezone } from '@/lib/timezone';
import { toast } from 'sonner';

// Типы данных для новой CRM-схемы с иерархией
type Client = {
  id: number;
  name: string;
  email: string;
  phone: string;
  category_id: number | null;
  status: 'active' | 'inactive' | 'archived';
  photo_url: string;
  notes: string;
  parent_id: number | null; // Добавлено поле для связи с родительским клиентом
  created_at?: string;
  updated_at?: string;
};

type Payment = {
  id: number;
  contact_id: number;
  product_id: number | null;
  amount: number;
  currency: string;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  payment_method: string;
  transaction_id: string;
  description: string;
  planned_at?: string | null;
  paid_at?: string | null; // ISO string
  created_at?: string;
  updated_at?: string;
};

type Category = {
  id: number;
  name: string;
  description: string;
  color: string;
  created_at?: string;
  updated_at?: string;
};

type Props = {
  activeTab?: 'clients' | 'categories' | 'payments';
};

export default function NewClientsEditor({ activeTab = 'clients' }: Props) {
  const [clients, setClients] = useState<Client[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [paymentToEdit, setPaymentToEdit] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [paymentLinkLoadingId, setPaymentLinkLoadingId] = useState<number | null>(null);
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);

  useEffect(() => {
    let isActive = true;

    const loadData = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const [contactsData, paymentsData, categoriesData] = await Promise.all([
          crmContactsApi.list(),
          crmPaymentsApi.list(),
          crmCategoriesApi.list(),
        ]);

        if (!isActive) return;

        setClients(contactsData);
        setPayments(paymentsData.map(normalizePayment));
        setCategories(categoriesData);
        try {
          const settings = await clientApi.getSettings();
          if (!isActive) return;
          setTenantTimezone(normalizeTenantTimezone(settings.timezone));
        } catch (settingsError) {
          console.warn('Failed to load tenant timezone for CRM editor', settingsError);
          if (!isActive) return;
          setTenantTimezone(DEFAULT_TENANT_TIMEZONE);
        }
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load CRM contacts/payments', err);
        setLoadError('Не удалось загрузить данные CRM. Проверьте API /crm/contacts/, /crm/payments/ и /crm/categories/.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadData();

    return () => {
      isActive = false;
    };
  }, []);

  if (loading) {
    return <div className="p-6">Загрузка редактора клиентов...</div>;
  }

  const getClientFullName = (client: Client) => {
    return client.name;
  };

  // Функция для получения родительского клиента
  const getParentClient = (childId: number) => {
    const childClient = clients.find(client => client.id === childId);
    if (childClient && childClient.parent_id) {
      return clients.find(client => client.id === childClient.parent_id);
    }
    return null;
  };

  const handleCopyPaymentLink = async (payment: Payment, paymentClient?: Client) => {
    const numericAmount = Number.parseFloat(String(payment.amount).replace(',', '.'));
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
      if (paymentClient?.name) {
        metadata.crm_contact_name = paymentClient.name;
      }
      if (paymentClient?.email) {
        metadata.email = paymentClient.email;
      }

      const description = (payment.description || '').trim() || (
        paymentClient ? `Оплата от клиента ${paymentClient.name}` : 'Оплата от клиента'
      );

      const response = await crmPaymentsApi.generateYooKassaLink({
        amount: numericAmount,
        currency: payment.currency || 'RUB',
        description,
        metadata,
      });

      const paymentUrl = response.payment_url || response.confirmation_url;
      if (!paymentUrl) {
        throw new Error('Payment URL was not returned');
      }

      await copyTextToClipboard(paymentUrl);
      toast.success('Ссылка на оплату скопирована.');
    } catch (err) {
      console.error('Failed to generate YooKassa payment link', err);
      toast.error('Не удалось сгенерировать ссылку оплаты.');
    } finally {
      setPaymentLinkLoadingId(null);
    }
  };

  // Render only the active tab content
  if (activeTab === 'clients') {
    return (
      <div className="space-y-6">
        {loadError && (
          <p className="text-sm text-red-500">{loadError}</p>
        )}
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-semibold">Список клиентов</h2>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <PlusIcon className="mr-2 h-4 w-4" />
                Добавить клиента
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Добавить нового клиента</DialogTitle>
                <DialogDescription>
                  Заполните информацию о новом клиенте
                </DialogDescription>
              </DialogHeader>
              <NewClientForm
                clients={clients}
                categories={categories}
                onSave={(newClients) =>
                  setClients((prev) =>
                    [...newClients, ...prev].sort((a, b) => a.name.localeCompare(b.name, 'ru-RU'))
                  )
                }
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>
    );
  } else if (activeTab === 'categories') {
    return (
      <div className="space-y-6">
        {loadError && (
          <p className="text-sm text-red-500">{loadError}</p>
        )}
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Категории клиентов</h2>
          <Button variant="outline" size="sm" disabled>
            Добавить категорию
          </Button>
        </div>

        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">Категории пока не добавлены.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {categories.map((category) => {
              const count = clients.filter((client) => client.category_id === category.id).length;
              return (
                <Card key={category.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{category.name}</CardTitle>
                      <Badge
                        variant="outline"
                        style={{ borderColor: category.color, color: category.color }}
                      >
                        {count}
                      </Badge>
                    </div>
                    <CardDescription>{category.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div
                      className="h-2 w-full rounded-full"
                      style={{ backgroundColor: `${category.color}33` }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.min(100, (count / Math.max(clients.length, 1)) * 100)}%`,
                          backgroundColor: category.color
                        }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {clients.length === 0 ? 'Нет клиентов' : `Доля: ${Math.round((count / clients.length) * 100)}%`}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    );
  } else if (activeTab === 'payments') {
    return (
      <div className="space-y-6">
        {loadError && (
          <p className="text-sm text-red-500">{loadError}</p>
        )}
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-semibold">Платежи</h2>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <PlusIcon className="mr-2 h-4 w-4" />
                Добавить платеж
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-white text-black dark:bg-white dark:text-black">
              <DialogHeader>
                <DialogTitle className="text-black">Добавить новый платеж</DialogTitle>
                <DialogDescription className="text-slate-600 dark:text-slate-600">
                  Зарегистрируйте платеж от клиента
                </DialogDescription>
              </DialogHeader>
              <NewPaymentForm
                clients={clients}
                onSave={(newPayment) => setPayments((prev) => [normalizePayment(newPayment), ...prev])}
              />
            </DialogContent>
          </Dialog>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Клиент</TableHead>
                <TableHead>Сумма</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Дата оплаты</TableHead>
                <TableHead>Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map((payment) => {
                const client = clients.find(c => c.id === payment.contact_id);
                return (
                  <TableRow key={payment.id}>
                    <TableCell className="font-medium">
                      {client ? (
                        client.parent_id ? (
                          <>
                            <span className="text-muted-foreground text-sm">{getParentClient(client.id)?.name} → </span>
                            {getClientFullName(client)}
                          </>
                        ) : (
                          getClientFullName(client)
                        )
                      ) : 'Неизвестный'}
                    </TableCell>
                    <TableCell className="font-semibold">{payment.amount} {payment.currency}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          payment.status === 'paid' ? 'secondary' :
                          payment.status === 'pending' ? 'default' :
                          payment.status === 'refunded' ? 'outline' : 'destructive'
                        }
                      >
                        {payment.status === 'paid' ? 'Оплачено' :
                         payment.status === 'pending' ? 'В ожидании' :
                         payment.status === 'refunded' ? 'Возврат' : 'Ошибка'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {payment.paid_at
                        ? formatInTenantTimezone(payment.paid_at, tenantTimezone, {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                          })
                        : '-'}
                    </TableCell>
                    <TableCell>
                      <div className="flex space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleCopyPaymentLink(payment, client)}
                          aria-label="Скопировать ссылку оплаты"
                          disabled={paymentLinkLoadingId === payment.id}
                        >
                          <CopyIcon className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPaymentToEdit(payment)}
                          aria-label="Редактировать платёж"
                        >
                          <EditIcon className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                          <TrashIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        <Dialog open={!!paymentToEdit} onOpenChange={(open) => !open && setPaymentToEdit(null)}>
          <DialogContent className="bg-white text-black dark:bg-white dark:text-black">
            <DialogHeader>
              <DialogTitle className="text-black">Редактировать платёж</DialogTitle>
              <DialogDescription className="text-slate-600 dark:text-slate-600">
                Измените данные платежа и сохраните
              </DialogDescription>
            </DialogHeader>
            {paymentToEdit && (
              <EditPaymentForm
                payment={paymentToEdit}
                clients={clients}
                onSave={(updated) => {
                  setPayments((prev) => prev.map((p) => (p.id === updated.id ? normalizePayment(updated) : p)));
                  setPaymentToEdit(null);
                }}
                onCancel={() => setPaymentToEdit(null)}
              />
            )}
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // Default fallback
  return (
    <div className="text-center py-8 text-muted-foreground">
      Выберите вкладку для просмотра содержимого
    </div>
  );
}

// Формы для добавления новых элементов
function NewClientForm({ clients, categories, onSave }: {
  clients: Client[],
  categories: Category[],
  onSave: (clients: Client[]) => void
}) {
  const [nameInput, setNameInput] = useState('');
  const [nameChips, setNameChips] = useState<string[]>([]);
  const [nameError, setNameError] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [categoryId, setCategoryId] = useState<string>('none');
  const [status, setStatus] = useState<'active' | 'inactive' | 'archived'>('active');
  const [notes, setNotes] = useState('');
  const [parentId, setParentId] = useState<number | null>(null); // Добавлено поле для выбора родительского клиента

  useEffect(() => {
    if (categories.length === 0) {
      if (categoryId !== 'none') setCategoryId('none');
      return;
    }
    const exists = categories.some((category) => String(category.id) === categoryId);
    if (!exists) {
      setCategoryId(String(categories[0].id));
    }
  }, [categories, categoryId]);

  const normalizeName = (value: string) => value.trim().replace(/\s+/g, ' ');

  const addNames = (rawNames: string[]) => {
    const cleaned = rawNames
      .map((item) => normalizeName(item))
      .filter((item) => item.length > 0);
    if (cleaned.length === 0) return;
    setNameChips((prev) => {
      const existing = new Set(prev.map((item) => item.toLowerCase()));
      const next = [...prev];
      cleaned.forEach((item) => {
        const key = item.toLowerCase();
        if (!existing.has(key)) {
          existing.add(key);
          next.push(item);
        }
      });
      return next;
    });
    setNameError('');
  };

  const handlePasteNames = (event: React.ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData('text');
    if (!text) return;
    event.preventDefault();
    addNames(text.split(/\r?\n|\t/));
    setNameInput('');
  };

  const handleNameKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      addNames([nameInput]);
      setNameInput('');
      return;
    }
    if (event.key === 'Backspace' && nameInput.length === 0 && nameChips.length > 0) {
      event.preventDefault();
      setNameChips((prev) => prev.slice(0, -1));
    }
  };

  const handleNameBlur = () => {
    if (nameInput.trim().length === 0) return;
    addNames([nameInput]);
    setNameInput('');
  };

  const removeChip = (value: string) => {
    setNameChips((prev) => prev.filter((item) => item !== value));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const pendingInput = normalizeName(nameInput);
    const namesToCreate = [...nameChips, ...(pendingInput ? [pendingInput] : [])];
    if (namesToCreate.length === 0) {
      setNameError('Введите хотя бы одно имя.');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    setNameError('');

    try {
      const createdClients = await Promise.all(
        namesToCreate.map((clientName) =>
          crmContactsApi.create({
            name: clientName,
            email,
            phone,
            category_id: categoryId === 'none' ? null : Number(categoryId),
            status,
            photo_url: '',
            notes,
            parent_id: parentId,
          })
        )
      );

      onSave(createdClients);
      setNameInput('');
      setNameChips([]);
      setEmail('');
      setPhone('');
      setNotes('');
    } catch (err) {
      console.error('Failed to create clients', err);
      setSubmitError('Не удалось создать клиента. Проверьте API /crm/contacts/.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name-input">Имя</Label>
        <div
          className={`flex min-h-10 w-full flex-wrap items-center gap-2 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${nameError ? 'border-red-500 focus-within:ring-red-500' : ''} max-h-32 overflow-y-auto`}
        >
          {nameChips.map((chip) => (
            <span
              key={chip}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-foreground"
            >
              <span className="max-w-[12rem] truncate">{chip}</span>
              <button
                type="button"
                onClick={() => removeChip(chip)}
                className="rounded-full p-0.5 text-muted-foreground transition hover:text-foreground"
                aria-label={`Удалить ${chip}`}
              >
                <XIcon className="h-3 w-3" />
              </button>
            </span>
          ))}
          <input
            id="name-input"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={handleNameKeyDown}
            onPaste={handlePasteNames}
            onBlur={handleNameBlur}
            placeholder={nameChips.length === 0 ? 'Введите имя или вставьте столбец' : ''}
            className="min-w-[160px] flex-1 border-0 bg-transparent p-0 text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Вставьте столбец из Excel — каждое имя станет отдельным тегом.
        </p>
        {nameError ? (
          <p className="text-xs text-red-500">{nameError}</p>
        ) : null}
        {submitError ? (
          <p className="text-xs text-red-500">{submitError}</p>
        ) : null}
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input 
          id="email" 
          type="email" 
          value={email} 
          onChange={(e) => setEmail(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="phone">Телефон</Label>
        <Input 
          id="phone" 
          value={phone} 
          onChange={(e) => setPhone(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="category">Категория</Label>
        <Select value={categoryId} onValueChange={setCategoryId}>
          <SelectTrigger>
            <SelectValue placeholder="Без категории" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Без категории</SelectItem>
            {categories.map((category) => (
              <SelectItem key={category.id} value={String(category.id)}>
                {category.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="parent">Родительский клиент (необязательно)</Label>
        <Select 
          value={parentId?.toString() || ""} 
          onValueChange={(val) => setParentId(val ? Number(val) : null)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Выберите родительский клиент" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Без родителя</SelectItem>
            {clients
              .filter(client => client.parent_id === null) // Только родительские клиенты
              .map((client) => (
                <SelectItem key={client.id} value={client.id.toString()}>
                  {getClientFullName(client)}
                </SelectItem>
              ))
            }
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="status">Статус</Label>
        <Select value={status} onValueChange={(val: 'active' | 'inactive' | 'archived') => setStatus(val)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Активный</SelectItem>
            <SelectItem value="inactive">Неактивный</SelectItem>
            <SelectItem value="archived">В архиве</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="notes">Заметки</Label>
        <Input 
          id="notes" 
          value={notes} 
          onChange={(e) => setNotes(e.target.value)} 
        />
      </div>
      
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? 'Сохраняем...' : 'Добавить клиента'}
      </Button>
    </form>
  );
}

function NewPaymentForm({ clients, onSave }: { 
  clients: Client[], 
  onSave: (payment: Payment) => void 
}) {
  const selectableClients = clients.filter((client) => isFiniteNumber(client.id));
  const [clientId, setClientId] = useState<number | null>(() => getSafeNumber(clients[0]?.id));
  const [amount, setAmount] = useState<number | ''>('');
  const [currency, setCurrency] = useState('RUB');
  const [status, setStatus] = useState<'pending' | 'paid' | 'failed' | 'refunded'>('pending');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [description, setDescription] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (selectableClients.length === 0) {
      if (clientId !== null) setClientId(null);
      return;
    }
    if (clientId === null || !selectableClients.some((client) => client.id === clientId)) {
      setClientId(selectableClients[0].id);
    }
  }, [selectableClients, clientId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (clientId === null) {
      setSubmitError('Выберите клиента для платежа.');
      return;
    }
    const parsedAmount = typeof amount === 'number' ? amount : Number.NaN;
    if (!Number.isFinite(parsedAmount)) {
      setSubmitError('Введите корректную сумму платежа.');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const created = await crmPaymentsApi.create({
        contact_id: clientId,
        product_id: null,
        amount: parsedAmount,
        currency,
        status,
        payment_method: paymentMethod,
        transaction_id: 'txn_' + Date.now().toString(),
        description,
        planned_at: null,
        paid_at: status === 'paid' ? new Date().toISOString() : null,
      });

      onSave(created);
      setAmount('');
      setCurrency('RUB');
      setStatus('pending');
      setPaymentMethod('');
      setDescription('');
    } catch (err) {
      console.error('Failed to create payment', err);
      setSubmitError('Не удалось создать платеж. Проверьте API /crm/payments/.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="client">Клиент</Label>
        <Select
          value={toSelectValue(clientId)}
          onValueChange={(val) => {
            const parsed = Number(val);
            setClientId(Number.isFinite(parsed) ? parsed : null);
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Выберите клиента" />
          </SelectTrigger>
          <SelectContent>
            {selectableClients.map((client) => (
              <SelectItem key={client.id} value={String(client.id)}>
                {client.parent_id ? (
                  <>
                    <span className="text-muted-foreground text-sm">{getParentClientName(client, clients)} → </span>
                    {getClientFullName(client)}
                  </>
                ) : (
                  getClientFullName(client)
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="amount">Сумма</Label>
        <Input 
          id="amount" 
          type="number" 
          value={amount} 
          onChange={(e) => {
            const raw = e.target.value;
            if (!raw) {
              setAmount('');
              return;
            }
            const parsed = Number.parseFloat(raw.replace(',', '.'));
            setAmount(Number.isFinite(parsed) ? parsed : '');
          }} 
          required 
          step="0.01"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="currency">Валюта</Label>
        <Select value={currency} onValueChange={setCurrency}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="RUB">RUB</SelectItem>
            <SelectItem value="USD">USD</SelectItem>
            <SelectItem value="EUR">EUR</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="status">Статус</Label>
        <Select 
          value={status} 
          onValueChange={(val: 'pending' | 'paid' | 'failed' | 'refunded') => setStatus(val)}
        >
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
      
      <div className="space-y-2">
        <Label htmlFor="method">Метод оплаты</Label>
        <Input 
          id="method" 
          value={paymentMethod} 
          onChange={(e) => setPaymentMethod(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">Описание</Label>
        <Input 
          id="description" 
          value={description} 
          onChange={(e) => setDescription(e.target.value)} 
        />
      </div>
      
      {submitError ? (
        <p className="text-xs text-red-500">{submitError}</p>
      ) : null}
      <Button type="submit" className="w-full" disabled={isSubmitting || clients.length === 0}>
        {isSubmitting ? 'Сохраняем...' : 'Добавить платеж'}
      </Button>
    </form>
  );
}

function EditPaymentForm({
  payment,
  clients,
  onSave,
  onCancel,
}: {
  payment: Payment;
  clients: Client[];
  onSave: (payment: Payment) => void;
  onCancel: () => void;
}) {
  const selectableClients = clients.filter((client) => isFiniteNumber(client.id));
  const [clientId, setClientId] = useState<number | null>(() => getSafeNumber(payment.contact_id));
  const [amount, setAmount] = useState<number | ''>(() => (
    Number.isFinite(payment.amount) ? payment.amount : ''
  ));
  const [currency, setCurrency] = useState(payment.currency ?? 'RUB');
  const [status, setStatus] = useState<'pending' | 'paid' | 'failed' | 'refunded'>(
    payment.status ?? 'pending'
  );
  const [paymentMethod, setPaymentMethod] = useState(payment.payment_method ?? '');
  const [description, setDescription] = useState(payment.description ?? '');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (selectableClients.length === 0) {
      if (clientId !== null) setClientId(null);
      return;
    }
    if (clientId === null || !selectableClients.some((client) => client.id === clientId)) {
      setClientId(selectableClients[0].id);
    }
  }, [selectableClients, clientId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (clientId === null) {
      setSubmitError('Выберите клиента для платежа.');
      return;
    }
    const parsedAmount = typeof amount === 'number' ? amount : Number.NaN;
    if (!Number.isFinite(parsedAmount)) {
      setSubmitError('Введите корректную сумму платежа.');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const updated = await crmPaymentsApi.update(payment.id, {
        contact_id: clientId,
        amount: parsedAmount,
        currency,
        status,
        payment_method: paymentMethod,
        description,
        paid_at: status === 'paid' ? (payment.paid_at ?? new Date().toISOString()) : null,
      });
      onSave(updated);
    } catch (err) {
      console.error('Failed to update payment', err);
      setSubmitError('Не удалось сохранить платёж. Проверьте API /crm/payments/.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="edit-client">Клиент</Label>
        <Select
          value={toSelectValue(clientId)}
          onValueChange={(val) => {
            const parsed = Number(val);
            setClientId(Number.isFinite(parsed) ? parsed : null);
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Выберите клиента" />
          </SelectTrigger>
          <SelectContent>
            {selectableClients.map((client) => (
              <SelectItem key={client.id} value={String(client.id)}>
                {client.parent_id ? (
                  <>
                    <span className="text-muted-foreground text-sm">{getParentClientName(client, clients)} → </span>
                    {getClientFullName(client)}
                  </>
                ) : (
                  getClientFullName(client)
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-amount">Сумма</Label>
        <Input
          id="edit-amount"
          type="number"
          value={amount}
          onChange={(e) => {
            const raw = e.target.value;
            if (!raw) {
              setAmount('');
              return;
            }
            const parsed = Number.parseFloat(raw.replace(',', '.'));
            setAmount(Number.isFinite(parsed) ? parsed : '');
          }}
          required
          step="0.01"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-currency">Валюта</Label>
        <Select value={currency} onValueChange={setCurrency}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="RUB">RUB</SelectItem>
            <SelectItem value="USD">USD</SelectItem>
            <SelectItem value="EUR">EUR</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-status">Статус</Label>
        <Select
          value={status}
          onValueChange={(val: 'pending' | 'paid' | 'failed' | 'refunded') => setStatus(val)}
        >
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
      <div className="space-y-2">
        <Label htmlFor="edit-method">Метод оплаты</Label>
        <Input
          id="edit-method"
          value={paymentMethod}
          onChange={(e) => setPaymentMethod(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-description">Описание</Label>
        <Input
          id="edit-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      {submitError ? (
        <p className="text-xs text-red-500">{submitError}</p>
      ) : null}
      <div className="flex gap-2 justify-end">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
          Отмена
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}

// Вспомогательные функции
const isFiniteNumber = (value: unknown): value is number => (
  typeof value === 'number' && Number.isFinite(value)
);

const getSafeNumber = (value: unknown): number | null => (
  isFiniteNumber(value) ? value : null
);

const toSelectValue = (value: number | null | undefined): string => (
  isFiniteNumber(value) ? String(value) : ''
);

const normalizeNumericAmount = (value: unknown): number => {
  const parsed = Number.parseFloat(String(value).replace(',', '.'));
  return Number.isFinite(parsed) ? parsed : 0;
};

const normalizePayment = (payment: Payment): Payment => ({
  ...payment,
  amount: normalizeNumericAmount(payment.amount),
});

const getClientFullName = (client: Client) => {
  return client.name;
};

const getParentClientName = (client: Client, allClients: Client[]): string => {
  if (!client.parent_id) return '';
  const parent = allClients.find(c => c.id === client.parent_id);
  return parent ? parent.name : '';
};

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  if (typeof document === 'undefined') {
    throw new Error('Clipboard is unavailable');
  }

  const textArea = document.createElement('textarea');
  textArea.value = value;
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textArea);
  if (!copied) {
    throw new Error('Copy command failed');
  }
};
