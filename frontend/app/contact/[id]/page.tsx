'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  CalendarIcon, 
  DollarSignIcon, 
  FileTextIcon, 
  UserIcon, 
  EditIcon, 
  SaveIcon, 
  XIcon 
} from 'lucide-react';
import { toast } from 'sonner';
import { crmContactsApi, crmEventTypesApi, crmEventsApi, crmPaymentsApi, crmNotesApi, crmContactTagsApi } from '@/lib/api/crm';
import { clientProductsApi } from '@/lib/api/clientProducts';

// Define types
type Contact = {
  id: number;
  name: string;
  email: string;
  phone: string;
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

export default function ContactDetailPage() {
  const { id } = useParams<{ id: string }>();
  const contactId = parseInt(id, 10);
  
  const [contact, setContact] = useState<Contact | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
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
  const getDefaultEventStart = () => {
    const now = new Date();
    const nextDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 12, 0, 0, 0);
    return new Date(nextDay.getTime() - nextDay.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  };
  const [newEventStart, setNewEventStart] = useState(getDefaultEventStart);
  const [newEventDuration, setNewEventDuration] = useState('60');
  const [newEventEnd, setNewEventEnd] = useState('');
  const [newEventLocation, setNewEventLocation] = useState('');
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
  const [newPaymentAmount, setNewPaymentAmount] = useState('');
  const [newPaymentCurrency, setNewPaymentCurrency] = useState('RUB');
  const [newPaymentPlannedAt, setNewPaymentPlannedAt] = useState(getDefaultEventStart);
  const [newPaymentPaid, setNewPaymentPaid] = useState(false);
  const [newPaymentProductId, setNewPaymentProductId] = useState<string>('none');
  const [savingPayment, setSavingPayment] = useState(false);
  const tagTypeLabels: Record<ContactTag['type'], string> = {
    goal: 'Цель',
    pain: 'Боль',
    experience: 'Опыт',
  };

  // Load contact data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [contactData, eventTypesData, productsData, eventsData, paymentsData, notesData, contactTagsData] = await Promise.all([
          crmContactsApi.detail(contactId),
          crmEventTypesApi.list(),
          clientProductsApi.list(),
          crmEventsApi.list(),
          crmPaymentsApi.list(),
          crmNotesApi.list(),
          crmContactTagsApi.list(contactId)
        ]);

        setContact(contactData);
        setEventTypes(eventTypesData);
        setProducts(productsData);
        
        // Filter events, payments, and notes for this contact
        setEvents(eventsData.filter(event => event.contact_id === contactId));
        setPayments(paymentsData.filter(payment => payment.contact_id === contactId));
        setNotes(notesData.filter(note => note.contact_id === contactId));
        setContactTags(contactTagsData);
        setTagDescriptions(
          contactTagsData.reduce<Record<number, string>>((acc, tag) => {
            acc[tag.tag_id] = tag.description || '';
            return acc;
          }, {})
        );
      } catch (err) {
        console.error('Error loading contact data:', err);
        setError('Не удалось загрузить данные контакта. Проверьте API /crm/contacts/, /crm/events/, /crm/payments/, /crm/notes/ и /crm/contact-tags/.');
      } finally {
        setLoading(false);
      }
    };

    if (!isNaN(contactId)) {
      fetchData();
    }
  }, [contactId]);

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
    const toLocalInput = (date: Date) =>
      new Date(date.getTime() - date.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);
    let startDate = newEventStart ? new Date(newEventStart) : new Date();
    if (Number.isNaN(startDate.getTime())) {
      startDate = new Date();
    }
    const startPayload = newEventStart || toLocalInput(startDate);
    const computedEnd = new Date(startDate.getTime() + durationValue * 60000);
    const endPayload = newEventEnd || toLocalInput(computedEnd);
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
      });
      setEvents((prev) =>
        [created, ...prev].sort(
          (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
        )
      );
      setNewEventTitle('');
      setNewEventDescription('');
      setNewEventStart(getDefaultEventStart());
      setNewEventDuration('60');
      setNewEventEnd('');
      setNewEventLocation('');
      setNewEventTypeId('none');
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
    const plannedAtPayload = newPaymentPlannedAt || null;
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
      setNewPaymentPlannedAt(getDefaultEventStart());
      setNewPaymentPaid(false);
      setNewPaymentProductId('none');
      toast.success('Платёж добавлен');
    } catch (err) {
      console.error('Error creating payment:', err);
      toast.error('Не удалось сохранить платёж');
    } finally {
      setSavingPayment(false);
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

  const eventTypesById = useMemo(() => {
    const map = new Map<number, EventType>();
    eventTypes.forEach((item) => map.set(item.id, item));
    return map;
  }, [eventTypes]);

  const productsById = useMemo(() => {
    const map = new Map<number, Product>();
    products.forEach((item) => map.set(item.id, item));
    return map;
  }, [products]);

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
    const end = new Date(newEventStart);
    end.setMinutes(end.getMinutes() + durationValue);
    if (Number.isNaN(end.getTime())) {
      setNewEventEnd('');
      return;
    }
    const local = new Date(end.getTime() - end.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    setNewEventEnd(local);
  }, [newEventStart, newEventDuration]);

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
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <UserIcon className="h-8 w-8" />
            {contact.name}
          </h1>
          <p className="text-muted-foreground">Детали контакта #{contact.id}</p>
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

      <Tabs defaultValue="overview" className="space-y-6">
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
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>О контакте</CardTitle>
              </CardHeader>
              <CardContent>
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
                  <div className="text-2xl font-bold">
                    {Math.round(payments.reduce((sum, payment) => sum + payment.amount, 0))} ₽
                  </div>
                  <div className="text-sm text-muted-foreground">Платежей на сумму</div>
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
                        <Label htmlFor={`tag-description-${tag.tag_id}`}>Описание</Label>
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
                  {events.map((event) => (
                    <Card key={event.id} className="p-4">
                      <div className="flex justify-between items-start">
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
                            <span>{new Date(event.start_time).toLocaleString('ru-RU')}</span>
                            <span>→</span>
                            <span>{new Date(event.end_time).toLocaleString('ru-RU')}</span>
                            <span>•</span>
                            <span>{event.location}</span>
                          </div>
                        </div>
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
                    </Card>
                  ))}
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
              {payments.length > 0 ? (
                <div className="space-y-4">
                  {payments.map((payment) => {
                    const metaItems: Array<{ key: string; content: string }> = [];

                    if (payment.payment_method) {
                      metaItems.push({ key: 'method', content: payment.payment_method });
                    }
                    if (payment.transaction_id) {
                      metaItems.push({ key: 'txn', content: `ID: ${payment.transaction_id}` });
                    }
                    if (payment.planned_at) {
                      metaItems.push({
                        key: 'planned',
                        content: `План: ${new Date(payment.planned_at).toLocaleDateString('ru-RU')}`,
                      });
                    }
                    if (payment.paid_at) {
                      metaItems.push({
                        key: 'paid',
                        content: `Оплачено: ${new Date(payment.paid_at).toLocaleDateString('ru-RU')}`,
                      });
                    }

                    return (
                      <Card key={payment.id} className="p-4">
                        <div className="flex justify-between items-center">
                          <div>
                            <h3 className="font-semibold">{payment.amount} {payment.currency}</h3>
                            {payment.product_id && productsById.get(payment.product_id)?.name && (
                              <p className="text-sm text-muted-foreground">
                                {productsById.get(payment.product_id)?.name}
                              </p>
                            )}
                            <p className="text-sm text-muted-foreground">{payment.description}</p>
                            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-muted-foreground">
                              {metaItems.map((item, index) => (
                                <span key={item.key}>
                                  {item.content}
                                  {index < metaItems.length - 1 && <span className="mx-2">•</span>}
                                </span>
                              ))}
                            </div>
                          </div>
                          <Badge 
                            variant={
                              payment.status === 'paid' ? 'secondary' : 
                              payment.status === 'pending' ? 'default' : 
                              payment.status === 'refunded' ? 'outline' : 'destructive'
                            }
                          >
                            {payment.status === 'paid' ? 'Оплачено' : 
                             payment.status === 'pending' ? 'В ожидании' : 
                             payment.status === 'refunded' ? 'Возвращено' : 'Ошибка'}
                          </Badge>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">Нет платежей</p>
              )}
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
                            {new Date(note.created_at).toLocaleString('ru-RU')}
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
    </div>
  );
}
