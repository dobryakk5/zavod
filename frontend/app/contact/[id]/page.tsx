'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  ArrowLeftIcon,
  CalendarIcon, 
  CheckIcon,
  Copy,
  DollarSignIcon, 
  FileTextIcon, 
  UserIcon, 
  EditIcon, 
  SaveIcon, 
  XIcon 
} from 'lucide-react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api';
import {
  crmContactsApi,
  crmCategoriesApi,
  crmEventTypesApi,
  crmEventsApi,
  crmPaymentsApi,
  crmNotesApi,
  crmContactTagsApi,
  type ContactServicePackageItem,
  type ContactTelegramInfo,
} from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { PaymentsTable } from '@/components/crm/payments-table';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  formatTenantDateTimeInput,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
} from '@/lib/timezone';

// Define types
type Contact = {
  id: number;
  name: string;
  email: string;
  phone: string;
  source?: string;
  category_id: number | null;
  status: 'active' | 'inactive' | 'archived';
  photo_url: string;
  notes: string;
  parent_id: number | null;
  created_at: string;
  updated_at: string;
};

type Event = {
  id: number;
  contact_id: number;
  event_type_id: number | null;
  title: string;
  description: string;
  start_time: string;
  end_time: string;
  location: string;
  status: 'scheduled' | 'completed' | 'cancelled' | 'no_show';
  notes: string;
  price?: number | null;
  created_at: string;
  updated_at: string;
};

type EventType = {
  id: number;
  name: string;
  description: string;
  duration_minutes: number;
  color: string;
  created_at: string;
};

type Category = {
  id: number;
  name: string;
  description: string;
  color: string;
  created_at: string;
  updated_at: string;
};

type Payment = {
  id: number;
  contact_id: number;
  event_id?: number | null;
  product_id: number | null;
  amount: number;
  currency: string;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  payment_method: string;
  transaction_id: string;
  description: string;
  planned_at: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
};

type Product = {
  id: number;
  name: string;
};

type Note = {
  id: number;
  contact_id: number;
  title: string;
  content: string;
  is_important: boolean;
  created_at: string;
  updated_at: string;
};

type ContactTag = {
  contact_id: number;
  tag_id: number;
  type: 'goal' | 'pain' | 'experience';
  value: string;
  description: string;
};

const buildGoogleCalendarLink = ({
  title,
  description,
  location,
  start,
  end,
}: {
  title: string;
  description?: string;
  location?: string;
  start: Date;
  end: Date;
}) => {
  const format = (d: Date) =>
    d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: title,
    dates: `${format(start)}/${format(end)}`,
    details: description || '',
    location: location || '',
  });

  return `https://www.google.com/calendar/render?${params.toString()}`;
};

const buildAppleCalendarLink = ({
  title,
  description,
  location,
  start,
  end,
  uid,
}: {
  title: string;
  description?: string;
  location?: string;
  start: Date;
  end: Date;
  uid?: string;
}) => {
  const params = new URLSearchParams({
    title,
    description: description || '',
    location: location || '',
    start: start.toISOString(),
    end: end.toISOString(),
  });
  if (uid) {
    params.set('uid', uid);
  }
  return `/api/calendar/ics?${params.toString()}`;
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

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const contactId = parseInt(id, 10);
  
  const [contact, setContact] = useState<Contact | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [servicePackages, setServicePackages] = useState<ContactServicePackageItem[]>([]);
  const [servicePackagesError, setServicePackagesError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [contactTags, setContactTags] = useState<ContactTag[]>([]);
  const [tagDescriptions, setTagDescriptions] = useState<Record<number, string>>({});
  const [savingTagId, setSavingTagId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [newNoteTitle, setNewNoteTitle] = useState('');
  const [newNoteContent, setNewNoteContent] = useState('');
  const [newNoteImportant, setNewNoteImportant] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventDescription, setNewEventDescription] = useState('');
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const getDefaultEventStart = useCallback((tz: string) => {
    const normalizedTz = normalizeTenantTimezone(tz);
    const nowUtc = new Date().toISOString();
    const nowLocal = formatTenantDateTimeInput(nowUtc, normalizedTz);
    if (!nowLocal) return '';
    const [datePart] = nowLocal.split('T');
    if (!datePart) return '';
    const [year, month, day] = datePart.split('-').map((part) => Number(part));
    if (!year || !month || !day) return '';
    const nextDay = new Date(year, month - 1, day + 1, 12, 0, 0, 0);
    const yyyy = String(nextDay.getFullYear()).padStart(4, '0');
    const mm = String(nextDay.getMonth() + 1).padStart(2, '0');
    const dd = String(nextDay.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}T12:00`;
  }, []);
  const defaultEventStartRef = useRef(getDefaultEventStart(DEFAULT_TENANT_TIMEZONE));
  const defaultPaymentStartRef = useRef(defaultEventStartRef.current);
  const [newEventStart, setNewEventStart] = useState(defaultEventStartRef.current);
  const [newEventDuration, setNewEventDuration] = useState('60');
  const [newEventEnd, setNewEventEnd] = useState('');
  const [newEventLocation, setNewEventLocation] = useState('');
  const [newEventPrice, setNewEventPrice] = useState('');
  const [newEventTypeId, setNewEventTypeId] = useState<string>('none');
  const [savingEvent, setSavingEvent] = useState(false);
  const eventStartInputRef = useRef<HTMLInputElement | null>(null);
  const eventEndInputRef = useRef<HTMLInputElement | null>(null);
  const [eventTypeSelectOpen, setEventTypeSelectOpen] = useState(false);
  const [addingEventType, setAddingEventType] = useState(false);
  const [newEventTypeName, setNewEventTypeName] = useState('');
  const [newEventTypeDuration, setNewEventTypeDuration] = useState('60');
  const [savingEventType, setSavingEventType] = useState(false);
  const newEventTypeInputRef = useRef<HTMLInputElement | null>(null);
  const [editingEventTypeId, setEditingEventTypeId] = useState<number | null>(null);
  const [editingEventTypeName, setEditingEventTypeName] = useState('');
  const [savingEventTypeEdit, setSavingEventTypeEdit] = useState(false);
  const editEventTypeInputRef = useRef<HTMLInputElement | null>(null);
  const [categoryId, setCategoryId] = useState<string>('none');
  const [categorySelectOpen, setCategorySelectOpen] = useState(false);
  const [addingCategory, setAddingCategory] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [savingCategory, setSavingCategory] = useState(false);
  const newCategoryInputRef = useRef<HTMLInputElement | null>(null);
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editingCategoryName, setEditingCategoryName] = useState('');
  const [savingCategoryEdit, setSavingCategoryEdit] = useState(false);
  const editCategoryInputRef = useRef<HTMLInputElement | null>(null);
  const [savingCategoryAssignment, setSavingCategoryAssignment] = useState(false);
  const [sourceValue, setSourceValue] = useState('');
  const [savingSource, setSavingSource] = useState(false);
  const [newPaymentAmount, setNewPaymentAmount] = useState('');
  const [newPaymentCurrency, setNewPaymentCurrency] = useState('RUB');
  const [newPaymentPlannedAt, setNewPaymentPlannedAt] = useState(defaultPaymentStartRef.current);
  const [newPaymentPaid, setNewPaymentPaid] = useState(false);
  const [newPaymentProductId, setNewPaymentProductId] = useState<string>('none');
  const [savingPayment, setSavingPayment] = useState(false);
  const [paymentToEdit, setPaymentToEdit] = useState<Payment | null>(null);
  const [editingPaymentAmount, setEditingPaymentAmount] = useState('');
  const [editingPaymentStatus, setEditingPaymentStatus] = useState<Payment['status']>('pending');
  const [savingPaymentEdit, setSavingPaymentEdit] = useState(false);
  const [paymentLinkLoadingId, setPaymentLinkLoadingId] = useState<number | null>(null);
  const [paymentDeletingId, setPaymentDeletingId] = useState<number | null>(null);

  const refreshServicePackages = useCallback(async () => {
    if (Number.isNaN(contactId)) return;
    try {
      const response = await crmContactsApi.servicePackages(contactId);
      setServicePackages(Array.isArray(response.items) ? response.items : []);
      setServicePackagesError(null);
    } catch (err) {
      console.error('Failed to load service packages:', err);
      setServicePackages([]);
      setServicePackagesError('Не удалось загрузить остатки пакетов услуг.');
    }
  }, [contactId]);
  const [activeTab, setActiveTab] = useState<'overview' | 'schedule' | 'payments' | 'notes'>('overview');
  const [telegramInfo, setTelegramInfo] = useState<ContactTelegramInfo | null>(null);
  const [telegramInfoError, setTelegramInfoError] = useState<string | null>(null);
  const [telegramDialogOpen, setTelegramDialogOpen] = useState(false);
  const tagTypeLabels: Record<ContactTag['type'], string> = {
    goal: 'Цель',
    pain: 'Боль',
    experience: 'Опыт',
  };
  const defaultCategoryColor = '#4A90E2';

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab === 'overview' || tab === 'schedule' || tab === 'payments' || tab === 'notes') {
      setActiveTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    const loadTimezone = async () => {
      try {
        const settings = await clientApi.getSettings();
        setTenantTimezone(normalizeTenantTimezone(settings.timezone));
      } catch (err) {
        console.error('Failed to load client timezone:', err);
        setTenantTimezone(DEFAULT_TENANT_TIMEZONE);
      }
    };
    loadTimezone();
  }, []);

  useEffect(() => {
    const nextDefault = getDefaultEventStart(tenantTimezone);
    if (newEventStart === defaultEventStartRef.current) {
      setNewEventStart(nextDefault);
    }
    if (newPaymentPlannedAt === defaultPaymentStartRef.current) {
      setNewPaymentPlannedAt(nextDefault);
    }
    defaultEventStartRef.current = nextDefault;
    defaultPaymentStartRef.current = nextDefault;
  }, [getDefaultEventStart, newEventStart, newPaymentPlannedAt, tenantTimezone]);

  // Load contact data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const telegramInfoPromise = crmContactsApi
          .telegramLink(contactId)
          .then((data) => ({ data, error: null as string | null }))
          .catch((err) => {
            let message = 'Не удалось получить ссылку.';
            if (err instanceof ApiError) {
              if (err.body) {
                try {
                  const parsed = JSON.parse(err.body);
                  if (parsed && typeof parsed.error === 'string') {
                    message = parsed.error;
                  } else {
                    message = err.body;
                  }
                } catch {
                  message = err.body;
                }
              } else {
                message = `Ошибка ${err.status}`;
              }
            } else if (err instanceof Error && err.message) {
              message = err.message;
            }
            return { data: null as ContactTelegramInfo | null, error: message };
          });
        const servicePackagesPromise = crmContactsApi
          .servicePackages(contactId)
          .then((data) => ({ data, error: null as string | null }))
          .catch((err) => {
            console.error('Failed to load contact service packages:', err);
            return {
              data: { contact_id: contactId, items: [] as ContactServicePackageItem[] },
              error: 'Не удалось загрузить остатки пакетов услуг.',
            };
          });
        const [
          contactData,
          categoriesData,
          eventTypesData,
          productsData,
          eventsData,
          paymentsData,
          notesData,
          contactTagsData,
          telegramInfoData,
          servicePackagesData,
        ] = await Promise.all([
          crmContactsApi.detail(contactId),
          crmCategoriesApi.list(),
          crmEventTypesApi.list(),
          clientProductsApi.list(),
          crmEventsApi.list(),
          crmPaymentsApi.list(),
          crmNotesApi.list(),
          crmContactTagsApi.list(contactId),
          telegramInfoPromise,
          servicePackagesPromise,
        ]);

        setContact(contactData);
        setCategories(categoriesData);
        setEventTypes(eventTypesData);
        setProducts(productsData);
        
        // Filter events, payments, and notes for this contact
        setEvents(eventsData.filter(event => event.contact_id === contactId));
        setPayments(paymentsData.filter(payment => payment.contact_id === contactId));
        setServicePackages(Array.isArray(servicePackagesData.data.items) ? servicePackagesData.data.items : []);
        setServicePackagesError(servicePackagesData.error);
        setNotes(notesData.filter(note => note.contact_id === contactId));
        setContactTags(contactTagsData);
        setTelegramInfo(telegramInfoData.data);
        setTelegramInfoError(telegramInfoData.error);
        setTagDescriptions(
          contactTagsData.reduce<Record<number, string>>((acc, tag) => {
            acc[tag.tag_id] = tag.description || '';
            return acc;
          }, {})
        );
      } catch (err) {
        console.error('Error loading contact data:', err);
        setError('Не удалось загрузить данные контакта. Проверьте API /crm/contacts/, /crm/categories/, /crm/event-types/, /crm/events/, /crm/payments/, /crm/notes/ и /crm/contact-tags/.');
      } finally {
        setLoading(false);
      }
    };

    if (!isNaN(contactId)) {
      fetchData();
    }
  }, [contactId]);

  useEffect(() => {
    setCategoryId(contact?.category_id ? String(contact.category_id) : 'none');
  }, [contact?.category_id]);

  useEffect(() => {
    setSourceValue(contact?.source ?? '');
  }, [contact?.source]);

  const handleFieldEdit = (field: string, currentValue?: string | null) => {
    setEditingField(field);
    setEditValue(currentValue ?? '');
  };

  const handleSaveField = async () => {
    if (!contact || !editingField) return;

    try {
      let updatedContact: Contact;
      
      if (editingField === 'name') {
        updatedContact = await crmContactsApi.update(contact.id, { name: editValue });
      } else if (editingField === 'email') {
        updatedContact = await crmContactsApi.update(contact.id, { email: editValue });
      } else if (editingField === 'phone') {
        updatedContact = await crmContactsApi.update(contact.id, { phone: editValue });
      } else if (editingField === 'notes') {
        updatedContact = await crmContactsApi.update(contact.id, { notes: editValue });
      } else {
        throw new Error('Invalid field for editing');
      }

      setContact(updatedContact);
      setEditingField(null);
      setEditValue('');
      toast.success('Успешно', {
        description: 'Данные обновлены',
      });
    } catch (err) {
      console.error('Error updating contact:', err);
      toast.error('Ошибка', {
        description: 'Не удалось обновить данные',
      });
    }
  };

  const handleCopyTelegramLink = async () => {
    const link = telegramInfo?.link;
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = link;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    setTelegramDialogOpen(false);
  };

  const handleCancelEdit = () => {
    setEditingField(null);
    setEditValue('');
  };

  const handleCreateNote = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!contact) return;
    const title = newNoteTitle.trim();
    setSavingNote(true);
    try {
      const created = await crmNotesApi.create({
        contact_id: contact.id,
        title: title || 'Без заголовка',
        content: newNoteContent.trim(),
        is_important: newNoteImportant,
      });
      setNotes((prev) => [created, ...prev]);
      setNewNoteTitle('');
      setNewNoteContent('');
      setNewNoteImportant(false);
      toast.success('Заметка добавлена');
    } catch (err) {
      console.error('Error creating note:', err);
      toast.error('Не удалось сохранить заметку');
    } finally {
      setSavingNote(false);
    }
  };

  const handleCreateEvent = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!contact) return;
    const hasAnyField =
      newEventTitle.trim() ||
      newEventDescription.trim() ||
      newEventStart ||
      newEventEnd ||
      newEventLocation.trim() ||
      newEventTypeId !== 'none';
    if (!hasAnyField) {
      toast.error('Заполните хотя бы одно поле');
      return;
    }
    const title = newEventTitle.trim() || 'Встреча';
    const durationRaw = Number(newEventDuration);
    const durationValue = Number.isFinite(durationRaw) && durationRaw > 0 ? durationRaw : 60;
    const startPayload = newEventStart
      ? localDateTimeStringToUtcISOString(newEventStart, tenantTimezone)
      : '';
    const endPayload = newEventEnd
      ? localDateTimeStringToUtcISOString(newEventEnd, tenantTimezone)
      : '';
    const priceRaw = newEventPrice.trim();
    let pricePayload: number | null = null;
    if (priceRaw) {
      const parsedPrice = Number(priceRaw.replace(',', '.'));
      if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
        toast.error('Цена должна быть больше 0');
        return;
      }
      pricePayload = parsedPrice;
    }
    if (!startPayload || !endPayload) {
      toast.error('Некорректная дата или время встречи');
      return;
    }
    setSavingEvent(true);
    try {
      const created = await crmEventsApi.create({
        contact_id: contact.id,
        event_type_id: newEventTypeId === 'none' ? null : Number(newEventTypeId),
        title,
        description: newEventDescription.trim(),
        start_time: startPayload,
        end_time: endPayload,
        location: newEventLocation.trim(),
        status: 'scheduled',
        notes: '',
        price: pricePayload,
      });
      setEvents((prev) =>
        [created, ...prev].sort(
          (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
        )
      );
      setNewEventTitle('');
      setNewEventDescription('');
      setNewEventStart(getDefaultEventStart(tenantTimezone));
      setNewEventDuration('60');
      setNewEventEnd('');
      setNewEventLocation('');
      setNewEventPrice('');
      setNewEventTypeId('none');
      void refreshServicePackages();
      toast.success('Встреча добавлена');
    } catch (err) {
      console.error('Error creating event:', err);
      toast.error('Не удалось сохранить встречу');
    } finally {
      setSavingEvent(false);
    }
  };

  const handleCreatePayment = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!contact) return;
    const hasAnyField =
      newPaymentAmount.trim() ||
      newPaymentPlannedAt ||
      newPaymentPaid ||
      newPaymentProductId !== 'none';
    if (!hasAnyField) {
      toast.error('Заполните хотя бы одно поле');
      return;
    }
    const amountValue = Number(newPaymentAmount);
    const amount = Number.isFinite(amountValue) ? amountValue : 0;
    const plannedAtUtc = newPaymentPlannedAt
      ? localDateTimeStringToUtcISOString(newPaymentPlannedAt, tenantTimezone)
      : '';
    if (newPaymentPlannedAt && !plannedAtUtc) {
      toast.error('Некорректная дата планового платежа');
      return;
    }
    const plannedAtPayload = plannedAtUtc || null;
    const paidAtPayload = newPaymentPaid
      ? plannedAtPayload || new Date().toISOString()
      : null;
    const status = newPaymentPaid ? 'paid' : 'pending';
    const productId = newPaymentProductId === 'none' ? null : Number(newPaymentProductId);
    setSavingPayment(true);
    try {
      const created = await crmPaymentsApi.create({
        contact_id: contact.id,
        product_id: productId,
        amount,
        currency: newPaymentCurrency || 'RUB',
        status,
        payment_method: '',
        transaction_id: '',
        description: '',
        planned_at: plannedAtPayload,
        paid_at: paidAtPayload,
      });
      setPayments((prev) => [created, ...prev]);
      setNewPaymentAmount('');
      setNewPaymentCurrency('RUB');
      setNewPaymentPlannedAt(getDefaultEventStart(tenantTimezone));
      setNewPaymentPaid(false);
      setNewPaymentProductId('none');
      void refreshServicePackages();
      toast.success('Платёж добавлен');
    } catch (err) {
      console.error('Error creating payment:', err);
      toast.error('Не удалось сохранить платёж');
    } finally {
      setSavingPayment(false);
    }
  };

  const handleCopyPaymentLink = async (payment: Payment) => {
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
      if (contact?.name) {
        metadata.crm_contact_name = contact.name;
      }
      if (contact?.email) {
        metadata.email = contact.email;
      }

      const description = (payment.description || '').trim() || (
        contact ? `Оплата от клиента ${contact.name}` : 'Оплата от клиента'
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

  const handleDeletePayment = async (payment: Payment) => {
    const confirmed = window.confirm(`Удалить платеж на сумму ${payment.amount} ${payment.currency}?`);
    if (!confirmed) return;

    setPaymentDeletingId(payment.id);
    try {
      await crmPaymentsApi.delete(payment.id);
      setPayments((prev) => prev.filter((item) => item.id !== payment.id));
      void refreshServicePackages();
      toast.success('Платёж удалён');
    } catch (err) {
      console.error('Failed to delete payment:', err);
      toast.error('Не удалось удалить платёж');
    } finally {
      setPaymentDeletingId(null);
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

  const handleSavePaymentEdit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!paymentToEdit) return;

    const parsedAmount = Number(editingPaymentAmount.replace(',', '.'));
    if (!Number.isFinite(parsedAmount) || parsedAmount < 0) {
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
      void refreshServicePackages();
      toast.success('Платёж обновлен');
      handleCancelEditPayment();
    } catch (err) {
      console.error('Failed to update payment:', err);
      toast.error('Не удалось обновить платёж');
    } finally {
      setSavingPaymentEdit(false);
    }
  };

  const handleTagDescriptionChange = (tagId: number, value: string) => {
    setTagDescriptions((prev) => ({ ...prev, [tagId]: value }));
  };

  const handleSaveTagDescription = async (tagId: number) => {
    if (!contact) return;
    const description = tagDescriptions[tagId] ?? '';
    setSavingTagId(tagId);
    try {
      await crmContactTagsApi.upsert({
        contact_id: contact.id,
        tag_id: tagId,
        description,
      });
      setContactTags((prev) =>
        prev.map((tag) => (tag.tag_id === tagId ? { ...tag, description } : tag))
      );
      toast.success('Успешно', {
        description: 'Описание тега обновлено',
      });
    } catch (err) {
      console.error('Error updating tag description:', err);
      toast.error('Ошибка', {
        description: 'Не удалось обновить описание тега',
      });
    } finally {
      setSavingTagId(null);
    }
  };

  const handleStartAddEventType = () => {
    setAddingEventType(true);
    setEditingEventTypeId(null);
    setEventTypeSelectOpen(true);
    setTimeout(() => newEventTypeInputRef.current?.focus(), 0);
  };

  const handleCancelAddEventType = () => {
    setAddingEventType(false);
    setNewEventTypeName('');
    setNewEventTypeDuration('60');
  };

  const handleStartEditEventType = (eventType: EventType) => {
    setEditingEventTypeId(eventType.id);
    setEditingEventTypeName(eventType.name);
    setAddingEventType(false);
    setEventTypeSelectOpen(true);
    setTimeout(() => editEventTypeInputRef.current?.focus(), 0);
  };

  const handleCancelEditEventType = () => {
    setEditingEventTypeId(null);
    setEditingEventTypeName('');
  };

  const handleCreateEventType = async () => {
    const name = newEventTypeName.trim();
    if (!name) {
      toast.error('Введите название типа встречи');
      return;
    }
    const durationValue = Number(newEventTypeDuration);
    if (!Number.isFinite(durationValue) || durationValue <= 0) {
      toast.error('Укажите длительность в минутах');
      return;
    }
    setSavingEventType(true);
    try {
      const created = await crmEventTypesApi.create({
        name,
        description: '',
        duration_minutes: durationValue,
        color: '#4A90E2',
      });
      setEventTypes((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewEventTypeId(String(created.id));
      setAddingEventType(false);
      setNewEventTypeName('');
      setNewEventTypeDuration('60');
      setEventTypeSelectOpen(false);
      toast.success('Тип встречи добавлен');
    } catch (err) {
      console.error('Error creating event type:', err);
      toast.error('Не удалось добавить тип встречи');
    } finally {
      setSavingEventType(false);
    }
  };

  const handleSaveEventType = async () => {
    if (!editingEventTypeId) return;
    const name = editingEventTypeName.trim();
    if (!name) {
      toast.error('Введите название типа встречи');
      return;
    }
    setSavingEventTypeEdit(true);
    try {
      const updated = await crmEventTypesApi.update(editingEventTypeId, { name });
      setEventTypes((prev) =>
        prev
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((a, b) => a.name.localeCompare(b.name))
      );
      setEditingEventTypeId(null);
      setEditingEventTypeName('');
      toast.success('Тип встречи обновлен');
    } catch (err) {
      console.error('Error updating event type:', err);
      toast.error('Не удалось обновить тип встречи');
    } finally {
      setSavingEventTypeEdit(false);
    }
  };

  const handleStartAddCategory = () => {
    setAddingCategory(true);
    setEditingCategoryId(null);
    setCategorySelectOpen(true);
    setTimeout(() => newCategoryInputRef.current?.focus(), 0);
  };

  const handleCancelAddCategory = () => {
    setAddingCategory(false);
    setNewCategoryName('');
  };

  const handleStartEditCategory = (category: Category) => {
    setEditingCategoryId(category.id);
    setEditingCategoryName(category.name);
    setAddingCategory(false);
    setCategorySelectOpen(true);
    setTimeout(() => editCategoryInputRef.current?.focus(), 0);
  };

  const handleCancelEditCategory = () => {
    setEditingCategoryId(null);
    setEditingCategoryName('');
  };

  const handleCreateCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      toast.error('Введите название категории');
      return;
    }
    setSavingCategory(true);
    try {
      const created = await crmCategoriesApi.create({
        name,
        description: '',
        color: defaultCategoryColor,
      });
      setCategories((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewCategoryName('');
      setAddingCategory(false);
      setCategorySelectOpen(false);
      toast.success('Категория добавлена');
      if (contact) {
        await handleAssignCategory(String(created.id), { silent: true });
      }
    } catch (err) {
      console.error('Error creating category:', err);
      toast.error('Не удалось добавить категорию');
    } finally {
      setSavingCategory(false);
    }
  };

  const handleSaveCategory = async () => {
    if (!editingCategoryId) return;
    const name = editingCategoryName.trim();
    if (!name) {
      toast.error('Введите название категории');
      return;
    }
    setSavingCategoryEdit(true);
    try {
      const updated = await crmCategoriesApi.update(editingCategoryId, { name });
      setCategories((prev) =>
        prev
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((a, b) => a.name.localeCompare(b.name))
      );
      setEditingCategoryId(null);
      setEditingCategoryName('');
      toast.success('Категория обновлена');
    } catch (err) {
      console.error('Error updating category:', err);
      toast.error('Не удалось обновить категорию');
    } finally {
      setSavingCategoryEdit(false);
    }
  };

  const handleAssignCategory = async (value: string, options?: { silent?: boolean }) => {
    if (!contact) return;
    const previousValue = categoryId;
    setCategoryId(value);
    setSavingCategoryAssignment(true);
    try {
      const updated = await crmContactsApi.update(contact.id, {
        category_id: value === 'none' ? null : Number(value),
      });
      setContact(updated);
      if (!options?.silent) {
        toast.success('Категория обновлена');
      }
    } catch (err) {
      console.error('Error updating contact category:', err);
      toast.error('Не удалось обновить категорию');
      setCategoryId(previousValue);
    } finally {
      setSavingCategoryAssignment(false);
    }
  };

  const saveSource = useCallback(
    async (value: string) => {
      if (!contact) return;
      if (value === (contact.source ?? '')) return;

      setSavingSource(true);
      try {
        const updated = await crmContactsApi.update(contact.id, { source: value });
        setContact(updated);
      } catch (err) {
        console.error('Error updating contact source:', err);
        toast.error('Не удалось обновить источник');
        setSourceValue(contact.source ?? '');
      } finally {
        setSavingSource(false);
      }
    },
    [contact]
  );

  useEffect(() => {
    if (!contact || savingSource) return;
    if (sourceValue === (contact.source ?? '')) return;

    const timer = window.setTimeout(() => {
      void saveSource(sourceValue);
    }, 700);

    return () => window.clearTimeout(timer);
  }, [contact, saveSource, savingSource, sourceValue]);

  const eventTypesById = useMemo(() => {
    const map = new Map<number, EventType>();
    eventTypes.forEach((item) => map.set(item.id, item));
    return map;
  }, [eventTypes]);

  const categoriesById = useMemo(() => {
    const map = new Map<number, Category>();
    categories.forEach((item) => map.set(item.id, item));
    return map;
  }, [categories]);

  const paymentEventDateById = useMemo(() => {
    const map = new Map<number, string>();
    events.forEach((event) => {
      if (event.start_time) {
        map.set(event.id, event.start_time);
      }
    });
    return map;
  }, [events]);

  const paymentPlanFact = useMemo(() => {
    return payments.reduce(
      (acc, payment) => {
        const amount = Number(payment.amount);
        if (!Number.isFinite(amount)) {
          return acc;
        }
        if (payment.status === 'pending') {
          acc.plan += amount;
        } else if (payment.status === 'paid') {
          acc.fact += amount;
        }
        return acc;
      },
      { plan: 0, fact: 0 }
    );
  }, [payments]);

  useEffect(() => {
    if (!newEventStart) {
      setNewEventEnd('');
      return;
    }
    const durationValue = Number(newEventDuration);
    if (!Number.isFinite(durationValue) || durationValue <= 0) {
      setNewEventEnd('');
      return;
    }
    const startUtcIso = localDateTimeStringToUtcISOString(newEventStart, tenantTimezone);
    if (!startUtcIso) {
      setNewEventEnd('');
      return;
    }
    const endUtc = new Date(startUtcIso);
    if (Number.isNaN(endUtc.getTime())) {
      setNewEventEnd('');
      return;
    }
    endUtc.setMinutes(endUtc.getMinutes() + durationValue);
    const endLocal = formatTenantDateTimeInput(endUtc, tenantTimezone);
    setNewEventEnd(endLocal);
  }, [newEventStart, newEventDuration, tenantTimezone]);

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="animate-pulse">Загрузка данных контакта...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-6">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          {error}
        </div>
      </div>
    );
  }

  if (!contact) {
    return (
      <div className="container mx-auto py-6">
        <div className="text-center text-muted-foreground">Контакт не найден</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-start gap-3">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="mt-0.5 shrink-0"
            onClick={() => router.push('/clients')}
            aria-label="Вернуться к списку клиентов"
            title="К списку клиентов"
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
          <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <UserIcon className="h-8 w-8" />
            {contact.name}
          </h1>
          <p className="text-muted-foreground">Детали контакта #{contact.id}</p>
          </div>
        </div>
        <Badge 
          variant={
            contact.status === 'active' ? 'default' : 
            contact.status === 'inactive' ? 'secondary' : 'destructive'
          }
        >
          {contact.status === 'active' ? 'Активный' : 
           contact.status === 'inactive' ? 'Неактивный' : 'В архиве'}
        </Badge>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Обзор</TabsTrigger>
          <TabsTrigger value="schedule">Расписание</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
          <TabsTrigger value="notes">Заметки</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UserIcon className="h-5 w-5" />
                  Личная информация
                </CardTitle>
                <CardDescription>Основные данные контакта</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Имя</Label>
                  {editingField === 'name' ? (
                    <div className="flex items-center gap-2">
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-40"
                      />
                      <Button size="sm" onClick={handleSaveField}>
                        <SaveIcon className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                        <XIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span>{contact.name}</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleFieldEdit('name', contact.name)}
                      >
                        <EditIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <Label>Email</Label>
                  {editingField === 'email' ? (
                    <div className="flex items-center gap-2">
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-40"
                      />
                      <Button size="sm" onClick={handleSaveField}>
                        <SaveIcon className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                        <XIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span>{contact.email}</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleFieldEdit('email', contact.email)}
                      >
                        <EditIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <Label>Телефон</Label>
                  {editingField === 'phone' ? (
                    <div className="flex items-center gap-2">
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="w-40"
                      />
                      <Button size="sm" onClick={handleSaveField}>
                        <SaveIcon className="h-4 w-4" />
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                        <XIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span>{contact.phone}</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        onClick={() => handleFieldEdit('phone', contact.phone)}
                      >
                        <EditIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>

                <div className="space-y-[1px]">
                  <div className="flex items-center justify-between">
                    <Label>Telegram</Label>
                    <div className="flex items-center gap-2">
                      <span>
                        {telegramInfo?.tg_name
                          ? (telegramInfo.tg_name.startsWith('@') ? telegramInfo.tg_name : `@${telegramInfo.tg_name}`)
                          : 'Не подключен'}
                      </span>
                      {telegramInfo?.is_connected && (
                        <span className="inline-flex h-9 w-9 items-center justify-center">
                          <CheckIcon className="h-4 w-4 text-emerald-500" />
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <Button
                      type="button"
                      variant="link"
                      className="h-auto px-0 text-xs text-muted-foreground"
                      onClick={() => setTelegramDialogOpen(true)}
                    >
                      Подключить клиента к боту
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>О контакте</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Категория</Label>
                  <Select
                    value={categoryId}
                    onValueChange={(value) => void handleAssignCategory(value)}
                    open={categorySelectOpen}
                    onOpenChange={(open) => {
                      setCategorySelectOpen(open);
                      if (!open) {
                        setAddingCategory(false);
                        setEditingCategoryId(null);
                        setEditingCategoryName('');
                      }
                    }}
                  >
                    <SelectTrigger className="w-48" disabled={savingCategoryAssignment}>
                      <SelectValue
                        placeholder="Без категории"
                        aria-label={categoriesById.get(Number(categoryId))?.name}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Без категории</SelectItem>
                      {categories.map((category) =>
                        editingCategoryId === category.id ? (
                          <div key={category.id} className="space-y-2 px-2 py-2">
                            <Input
                              ref={editCategoryInputRef}
                              value={editingCategoryName}
                              onChange={(e) => setEditingCategoryName(e.target.value)}
                              placeholder="Название категории"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  void handleSaveCategory();
                                }
                                if (e.key === 'Escape') {
                                  e.preventDefault();
                                  handleCancelEditCategory();
                                }
                              }}
                            />
                            <div className="flex gap-2">
                              <Button type="button" size="sm" disabled={savingCategoryEdit} onClick={handleSaveCategory}>
                                {savingCategoryEdit ? 'Сохраняем...' : 'Сохранить'}
                              </Button>
                              <Button type="button" size="sm" variant="ghost" onClick={handleCancelEditCategory}>
                                Отмена
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <SelectItem
                            key={category.id}
                            value={String(category.id)}
                            className="group relative pr-10 [&>span]:right-8"
                          >
                            <span className="flex items-center gap-2">
                              <span
                                className="inline-flex h-2 w-2 rounded-full"
                                style={{ backgroundColor: category.color || defaultCategoryColor }}
                              />
                              <span className="block w-full truncate pr-6">{category.name}</span>
                            </span>
                            <button
                              type="button"
                              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
                              onPointerDown={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                              }}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                handleStartEditCategory(category);
                              }}
                              aria-label="Переименовать категорию"
                            >
                              <EditIcon className="h-3.5 w-3.5" />
                            </button>
                          </SelectItem>
                        )
                      )}
                      <div className="my-1 h-px bg-border" />
                      {addingCategory ? (
                        <div className="space-y-2 px-2 py-2">
                          <Input
                            ref={newCategoryInputRef}
                            value={newCategoryName}
                            onChange={(e) => setNewCategoryName(e.target.value)}
                            placeholder="Новая категория"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                void handleCreateCategory();
                              }
                              if (e.key === 'Escape') {
                                e.preventDefault();
                                handleCancelAddCategory();
                              }
                            }}
                          />
                          <div className="flex gap-2">
                            <Button type="button" size="sm" disabled={savingCategory} onClick={handleCreateCategory}>
                              {savingCategory ? 'Сохраняем...' : 'Добавить'}
                            </Button>
                            <Button type="button" size="sm" variant="ghost" onClick={handleCancelAddCategory}>
                              Отмена
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="w-full px-2 py-2 text-left text-sm text-primary hover:bg-accent rounded"
                          onClick={(e) => {
                            e.preventDefault();
                            handleStartAddCategory();
                          }}
                        >
                          + Добавить категорию
                        </button>
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <Label htmlFor="contact-source">Источник</Label>
                  <Input
                    id="contact-source"
                    value={sourceValue}
                    onChange={(e) => setSourceValue(e.target.value)}
                    placeholder="сарафан или сайт или"
                    className="w-48"
                  />
                </div>
                {editingField === 'notes' ? (
                  <div className="space-y-2">
                    <Input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      placeholder="Введите заметки..."
                    />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSaveField}>
                        <SaveIcon className="h-4 w-4 mr-2" />
                        Сохранить
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                        <XIcon className="h-4 w-4 mr-2" />
                        Отмена
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between">
                    <p className="text-sm text-muted-foreground whitespace-pre-line flex-grow">
                      {contact.notes || 'Нет заметок'}
                    </p>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => handleFieldEdit('notes', contact.notes)}
                    >
                      <EditIcon className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Статистика</CardTitle>
              <CardDescription>Информация о взаимодействиях с контактом</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-lg border bg-card p-4">
                  <div className="text-2xl font-bold">{events.length}</div>
                  <div className="text-sm text-muted-foreground">Событий</div>
                </div>
                <div className="rounded-lg border bg-card p-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <div className="text-xs text-muted-foreground">План</div>
                      <div className="text-2xl font-bold">{Math.round(paymentPlanFact.plan)} ₽</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Факт</div>
                      <div className="text-2xl font-bold">{Math.round(paymentPlanFact.fact)} ₽</div>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border bg-card p-4">
                  <div className="text-2xl font-bold">{notes.length}</div>
                  <div className="text-sm text-muted-foreground">Заметок</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Теги контакта</CardTitle>
              <CardDescription>Описание для каждого тега</CardDescription>
            </CardHeader>
            <CardContent>
              {contactTags.length > 0 ? (
                <div className="space-y-4">
                  {contactTags.map((tag) => (
                    <div key={tag.tag_id} className="space-y-3 rounded-lg border bg-card p-4">
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-semibold">{tag.value}</div>
                        <Badge variant="outline">{tagTypeLabels[tag.type]}</Badge>
                      </div>
                      <div className="space-y-2">
                        <Textarea
                          id={`tag-description-${tag.tag_id}`}
                          value={tagDescriptions[tag.tag_id] ?? ''}
                          onChange={(e) => handleTagDescriptionChange(tag.tag_id, e.target.value)}
                          placeholder="Добавьте описание"
                          rows={3}
                        />
                      </div>
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          onClick={() => handleSaveTagDescription(tag.tag_id)}
                          disabled={savingTagId === tag.tag_id}
                        >
                          {savingTagId === tag.tag_id ? 'Сохраняем...' : 'Сохранить'}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-6">У контакта пока нет тегов</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Новая встреча</CardTitle>
              <CardDescription>Запланируйте встречу для контакта</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateEvent} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="event-title">Название</Label>
                  <Input
                    id="event-title"
                    value={newEventTitle}
                    onChange={(e) => setNewEventTitle(e.target.value)}
                    placeholder="Например, консультация"
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2">
                    <div className="flex items-center">
                      <Label htmlFor="event-start">Начало</Label>
                      <button
                        type="button"
                        className="ml-[10px] inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground shadow-none transition-shadow hover:shadow hover:text-foreground"
                        onClick={() => eventStartInputRef.current?.showPicker?.()}
                        onMouseDown={(e) => e.preventDefault()}
                        aria-label="Выбрать дату начала"
                      >
                        <CalendarIcon className="h-4 w-4" />
                      </button>
                    </div>
                    <Input
                      id="event-start"
                      type="datetime-local"
                      value={newEventStart}
                      onChange={(e) => setNewEventStart(e.target.value)}
                      ref={eventStartInputRef}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="event-duration">Длительность (мин)</Label>
                      <span className="inline-flex h-6 w-6" aria-hidden="true" />
                    </div>
                    <Input
                      id="event-duration"
                      type="number"
                      min={1}
                      value={newEventDuration}
                      onChange={(e) => setNewEventDuration(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center">
                      <Label htmlFor="event-end">Окончание</Label>
                      <button
                        type="button"
                        className="ml-[10px] inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground shadow-none transition-shadow hover:shadow hover:text-foreground"
                        onClick={() => eventEndInputRef.current?.showPicker?.()}
                        onMouseDown={(e) => e.preventDefault()}
                        aria-label="Выбрать дату окончания"
                      >
                        <CalendarIcon className="h-4 w-4" />
                      </button>
                    </div>
                    <Input
                      id="event-end"
                      type="datetime-local"
                      value={newEventEnd}
                      onChange={(e) => setNewEventEnd(e.target.value)}
                      ref={eventEndInputRef}
                    />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="event-location">Место</Label>
                    <Input
                      id="event-location"
                      value={newEventLocation}
                      onChange={(e) => setNewEventLocation(e.target.value)}
                      placeholder="Онлайн / офис"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Тип встречи</Label>
                    <Select
                      value={newEventTypeId}
                      onValueChange={setNewEventTypeId}
                      open={eventTypeSelectOpen}
                      onOpenChange={(open) => {
                        setEventTypeSelectOpen(open);
                        if (!open) {
                          setAddingEventType(false);
                          setEditingEventTypeId(null);
                          setEditingEventTypeName('');
                        }
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Без типа" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">Без типа</SelectItem>
                        {eventTypes.map((eventType) =>
                          editingEventTypeId === eventType.id ? (
                            <div key={eventType.id} className="space-y-2 px-2 py-2">
                              <Input
                                ref={editEventTypeInputRef}
                                value={editingEventTypeName}
                                onChange={(e) => setEditingEventTypeName(e.target.value)}
                                placeholder="Название типа"
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    void handleSaveEventType();
                                  }
                                  if (e.key === 'Escape') {
                                    e.preventDefault();
                                    handleCancelEditEventType();
                                  }
                                }}
                              />
                              <div className="flex gap-2">
                                <Button type="button" size="sm" disabled={savingEventTypeEdit} onClick={handleSaveEventType}>
                                  {savingEventTypeEdit ? 'Сохраняем...' : 'Сохранить'}
                                </Button>
                                <Button type="button" size="sm" variant="ghost" onClick={handleCancelEditEventType}>
                                  Отмена
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <SelectItem
                              key={eventType.id}
                              value={String(eventType.id)}
                              className="group relative pr-10 [&>span]:right-8"
                            >
                              <span className="block w-full truncate pr-6">{eventType.name}</span>
                              <button
                                type="button"
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
                                onPointerDown={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                }}
                                onClick={(e) => {
                                  e.preventDefault();
                                  e.stopPropagation();
                                  handleStartEditEventType(eventType);
                                }}
                                aria-label="Переименовать тип встречи"
                              >
                                <EditIcon className="h-3.5 w-3.5" />
                              </button>
                            </SelectItem>
                          )
                        )}
                        <div className="my-1 h-px bg-border" />
                        {addingEventType ? (
                          <div className="space-y-2 px-2 py-2">
                            <Input
                              ref={newEventTypeInputRef}
                              value={newEventTypeName}
                              onChange={(e) => setNewEventTypeName(e.target.value)}
                              placeholder="Новый тип"
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault();
                                  void handleCreateEventType();
                                }
                                if (e.key === 'Escape') {
                                  e.preventDefault();
                                  handleCancelAddEventType();
                                }
                              }}
                            />
                            <Input
                              type="number"
                              min={1}
                              value={newEventTypeDuration}
                              onChange={(e) => setNewEventTypeDuration(e.target.value)}
                              placeholder="Длительность, мин"
                            />
                            <div className="flex gap-2">
                              <Button type="button" size="sm" disabled={savingEventType} onClick={handleCreateEventType}>
                                {savingEventType ? 'Сохраняем...' : 'Добавить'}
                              </Button>
                              <Button type="button" size="sm" variant="ghost" onClick={handleCancelAddEventType}>
                                Отмена
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="w-full px-2 py-2 text-left text-sm text-primary hover:bg-accent rounded"
                            onClick={(e) => {
                              e.preventDefault();
                              handleStartAddEventType();
                            }}
                          >
                            + Добавить новое
                          </button>
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="event-description">Описание</Label>
                  <Textarea
                    id="event-description"
                    value={newEventDescription}
                    onChange={(e) => setNewEventDescription(e.target.value)}
                    placeholder="Краткое описание"
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="event-price">Цена (если есть)</Label>
                  <Input
                    id="event-price"
                    type="number"
                    min={0}
                    step="0.01"
                    value={newEventPrice}
                    onChange={(e) => setNewEventPrice(e.target.value)}
                    placeholder="Например, 5000"
                  />
                </div>
                <Button type="submit" disabled={savingEvent}>
                  {savingEvent ? 'Сохраняем...' : 'Добавить встречу'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarIcon className="h-5 w-5" />
                События и расписание
              </CardTitle>
              <CardDescription>Предстоящие и прошедшие встречи с контактом</CardDescription>
            </CardHeader>
            <CardContent>
              {events.length > 0 ? (
                <div className="space-y-4">
                  {events.map((event) => {
                    const startDate = new Date(event.start_time);
                    const endDate = new Date(event.end_time);
                    const hasValidDates =
                      !Number.isNaN(startDate.getTime()) && !Number.isNaN(endDate.getTime());
                    const eventDate = formatInTenantTimezone(event.start_time, tenantTimezone, {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                    });
                    const startTime = formatInTenantTimezone(event.start_time, tenantTimezone, {
                      hour: '2-digit',
                      minute: '2-digit',
                    });
                    const endTime = formatInTenantTimezone(event.end_time, tenantTimezone, {
                      hour: '2-digit',
                      minute: '2-digit',
                    });
                    const title = event.title || 'Встреча';
                    const googleLink = hasValidDates
                      ? buildGoogleCalendarLink({
                        title,
                        description: event.description || '',
                        location: event.location || '',
                        start: startDate,
                        end: endDate,
                      })
                      : null;
                    const appleLink = hasValidDates
                      ? buildAppleCalendarLink({
                        title,
                        description: event.description || '',
                        location: event.location || '',
                        start: startDate,
                        end: endDate,
                        uid: `contact-${contactId}-event-${event.id}`,
                      })
                      : null;

                    return (
                      <Card
                        key={event.id}
                        className="p-4 transition-colors hover:bg-muted/50 cursor-pointer"
                        role="button"
                        tabIndex={0}
                        onClick={() => router.push(`/meet/${event.id}`)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            router.push(`/meet/${event.id}`);
                          }
                        }}
                      >
                        <div className="flex justify-between items-start gap-4">
                          <div>
                            <h3 className="font-semibold">{event.title}</h3>
                            {eventTypesById.get(event.event_type_id ?? -1)?.name && (
                              <p className="text-sm text-muted-foreground">
                                {eventTypesById.get(event.event_type_id ?? -1)?.name}
                              </p>
                            )}
                            {event.description && (
                              <p className="text-sm text-muted-foreground">{event.description}</p>
                            )}
                            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                              <span>Дата: {eventDate}</span>
                              <span>•</span>
                              <span>Время: {startTime}-{endTime}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            {googleLink && appleLink && (
                              <Popover>
                                <PopoverTrigger asChild>
                                  <button
                                    type="button"
                                    className="text-xs text-muted-foreground hover:text-foreground hover:underline"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    Добавить в календарь
                                  </button>
                                </PopoverTrigger>
                                <PopoverContent side="top" align="end" className="w-40 p-2">
                                  <div className="flex flex-col gap-1 text-xs">
                                    <a
                                      href={googleLink}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="rounded px-2 py-1 hover:bg-muted"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      Google
                                    </a>
                                    <a
                                      href={appleLink}
                                      className="rounded px-2 py-1 hover:bg-muted"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      Apple
                                    </a>
                                  </div>
                                </PopoverContent>
                              </Popover>
                            )}
                            <Badge 
                              variant={
                                event.status === 'scheduled' ? 'default' : 
                                event.status === 'completed' ? 'secondary' : 
                                event.status === 'cancelled' ? 'destructive' : 'outline'
                              }
                            >
                              {event.status === 'scheduled' ? 'Запланировано' : 
                               event.status === 'completed' ? 'Завершено' : 
                               event.status === 'cancelled' ? 'Отменено' : 'Не явился'}
                            </Badge>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">Нет запланированных событий</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="payments" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Пакеты услуг</CardTitle>
              <CardDescription>Остаток оплаченных пакетов по этому контакту</CardDescription>
            </CardHeader>
            <CardContent>
              {servicePackagesError && (
                <div className="mb-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {servicePackagesError}
                </div>
              )}
              {servicePackages.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Оплаченных пакетов услуг пока нет.
                </p>
              ) : (
                <div className="space-y-3">
                  {servicePackages.map((item) => {
                    const servicePackage = item.service_package;
                    const remainingLabel = (servicePackage?.remaining_label || '').trim() || '—';
                    const usedLabel = (servicePackage?.used_label || '').trim() || '—';
                    const totalLabel = (servicePackage?.total_label || '').trim() || '—';
                    const modeLabel =
                      servicePackage?.mode === 'minutes' ? 'Пакет по времени' : 'Пакет по количеству';
                    const isExhausted = Boolean(servicePackage?.is_exhausted);
                    const paidAtLabel = item.paid_at
                      ? formatInTenantTimezone(item.paid_at, tenantTimezone, {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—';

                    return (
                      <div key={item.purchase_id} className="rounded-lg border p-4 space-y-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <div className="font-medium">{item.product_name || `Продукт #${item.product_id}`}</div>
                            <div className="text-xs text-muted-foreground">{modeLabel}</div>
                          </div>
                          <Badge variant={isExhausted ? 'destructive' : 'secondary'}>
                            {isExhausted ? 'Закончился' : 'Активен'}
                          </Badge>
                        </div>
                        <div className="grid gap-2 text-sm sm:grid-cols-3">
                          <div>
                            <div className="text-xs text-muted-foreground">Осталось</div>
                            <div className="font-medium">{remainingLabel}</div>
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground">Израсходовано</div>
                            <div>{usedLabel}</div>
                          </div>
                          <div>
                            <div className="text-xs text-muted-foreground">Всего</div>
                            <div>{totalLabel}</div>
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Оплата: {paidAtLabel}
                          {item.amount ? ` · ${item.amount} ${item.currency || 'RUB'}` : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Новый платёж</CardTitle>
              <CardDescription>Добавьте плановый или оплаченный платёж</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreatePayment} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-[3fr_3fr_1fr]">
                  <div className="space-y-2">
                    <Label htmlFor="payment-amount">Сумма</Label>
                    <Input
                      id="payment-amount"
                      type="number"
                      min={0}
                      step="0.01"
                      value={newPaymentAmount}
                      onChange={(e) => setNewPaymentAmount(e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="payment-planned-at">Плановая дата оплаты</Label>
                    <Input
                      id="payment-planned-at"
                      type="datetime-local"
                      value={newPaymentPlannedAt}
                      onChange={(e) => setNewPaymentPlannedAt(e.target.value)}
                      placeholder="Завтра в 12:00"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="payment-currency">Валюта</Label>
                    <Input
                      id="payment-currency"
                      value={newPaymentCurrency}
                      onChange={(e) => setNewPaymentCurrency(e.target.value)}
                      placeholder="RUB"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Продукт</Label>
                  <Select value={newPaymentProductId} onValueChange={setNewPaymentProductId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Без продукта" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Без продукта</SelectItem>
                      {products.map((product) => (
                        <SelectItem key={product.id} value={String(product.id)}>
                          {product.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={newPaymentPaid}
                    onChange={(e) => setNewPaymentPaid(e.target.checked)}
                  />
                  Оплачено
                </label>
                <Button type="submit" disabled={savingPayment}>
                  {savingPayment ? 'Сохраняем...' : 'Добавить платёж'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSignIcon className="h-5 w-5" />
                Платежи
              </CardTitle>
              <CardDescription>Финансовые транзакции по контакту</CardDescription>
            </CardHeader>
            <CardContent>
              <PaymentsTable
                payments={payments}
                contacts={[contact]}
                tenantTimezone={tenantTimezone}
                eventDateById={paymentEventDateById}
                paymentLinkLoadingId={paymentLinkLoadingId}
                paymentDeletingId={paymentDeletingId}
                onCopyPaymentLink={(payment) => void handleCopyPaymentLink(payment)}
                onEditPayment={(payment) => handleStartEditPayment(payment)}
                onDeletePayment={(payment) => void handleDeletePayment(payment)}
                emptyText="Нет платежей"
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notes" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Новая заметка</CardTitle>
              <CardDescription>Добавьте новую заметку для этого контакта</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateNote} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="note-title">Заголовок</Label>
                  <Input
                    id="note-title"
                    value={newNoteTitle}
                    onChange={(e) => setNewNoteTitle(e.target.value)}
                    placeholder="Короткий заголовок"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="note-content">Текст</Label>
                  <Textarea
                    id="note-content"
                    value={newNoteContent}
                    onChange={(e) => setNewNoteContent(e.target.value)}
                    placeholder="Подробности заметки"
                    rows={4}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={newNoteImportant}
                    onChange={(e) => setNewNoteImportant(e.target.checked)}
                  />
                  Важная заметка
                </label>
                <Button type="submit" disabled={savingNote}>
                  {savingNote ? 'Сохраняем...' : 'Добавить заметку'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileTextIcon className="h-5 w-5" />
                Заметки
              </CardTitle>
              <CardDescription>Важная информация и комментарии</CardDescription>
            </CardHeader>
            <CardContent>
              {notes.length > 0 ? (
                <div className="space-y-4">
                  {notes.map((note) => (
                    <Card key={note.id} className="p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold">{note.title}</h3>
                            {note.is_important && (
                              <Badge variant="destructive">Важно</Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-2 whitespace-pre-line">
                            {note.content}
                          </p>
                          <p className="text-xs text-muted-foreground mt-2">
                            {formatInTenantTimezone(note.created_at, tenantTimezone, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">Нет заметок</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={telegramDialogOpen} onOpenChange={setTelegramDialogOpen}>
        <DialogContent className="sm:max-w-md bg-white text-black dark:bg-white dark:text-black dark:border-gray-200 [&>button]:text-black dark:[&>button]:text-black">
          <DialogHeader>
            <DialogTitle className="text-black dark:text-black">Подключение к Telegram</DialogTitle>
            <DialogDescription className="text-black dark:text-black">
              Отправьте эту ссылку для подключения к телеграм боту.
            </DialogDescription>
          </DialogHeader>
          {telegramInfoError ? (
            <div className="rounded-md border border-black/10 bg-white p-3 text-sm text-black dark:border-black/10 dark:bg-white dark:text-black break-all">
              {telegramInfoError}
            </div>
          ) : (
            <button
              type="button"
              onClick={handleCopyTelegramLink}
              className="flex w-full items-start justify-between gap-3 rounded-md border border-black/10 bg-white p-3 text-left text-sm text-black transition hover:bg-gray-50 dark:border-black/10 dark:bg-white dark:text-black dark:hover:bg-gray-50"
            >
              <span className="break-all">{telegramInfo?.link || 'Ссылка недоступна.'}</span>
              <Copy className="mt-0.5 h-4 w-4 shrink-0 text-black/60" />
            </button>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={paymentToEdit !== null}
        onOpenChange={(open) => {
          if (!open) {
            handleCancelEditPayment();
          }
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
                step="1"
                value={editingPaymentAmount}
                onChange={(e) => setEditingPaymentAmount(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-payment-status">Статус</Label>
              <Select
                value={editingPaymentStatus}
                onValueChange={(value) => setEditingPaymentStatus(value as Payment['status'])}
              >
                <SelectTrigger id="edit-payment-status">
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
