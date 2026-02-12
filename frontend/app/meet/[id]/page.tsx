'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { CalendarIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api';
import { crmContactsApi, crmEventsApi, crmEventTypesApi, type Contact, type Event, type EventType } from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatTenantDateTimeInput,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
} from '@/lib/timezone';

export default function MeetEditPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const eventId = Number(id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contactId, setContactId] = useState<number | null>(null);
  const [contactName, setContactName] = useState<string>('');

  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [eventTitle, setEventTitle] = useState('');
  const [eventStart, setEventStart] = useState('');
  const [eventDuration, setEventDuration] = useState('60');
  const [eventEnd, setEventEnd] = useState('');
  const [eventLocation, setEventLocation] = useState('');
  const [eventDescription, setEventDescription] = useState('');
  const [eventPrice, setEventPrice] = useState('');
  const [eventTypeId, setEventTypeId] = useState<string>('none');
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);

  const eventStartInputRef = useRef<HTMLInputElement | null>(null);
  const eventEndInputRef = useRef<HTMLInputElement | null>(null);

  const eventTypesById = useMemo(() => {
    const map = new Map<number, EventType>();
    eventTypes.forEach((item) => map.set(item.id, item));
    return map;
  }, [eventTypes]);

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
    const loadData = async () => {
      if (!Number.isFinite(eventId)) {
        setError('Некорректный идентификатор встречи.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const [eventData, eventTypesData] = await Promise.all([
          crmEventsApi.detail(eventId),
          crmEventTypesApi.list(),
        ]);

        setContactId(eventData.contact_id);
        setEventTypes(eventTypesData);
        setEventTitle(eventData.title || 'Встреча');
        setEventDescription(eventData.description || '');
        setEventLocation(eventData.location || '');
        setEventPrice(
          typeof eventData.price === 'number' && Number.isFinite(eventData.price)
            ? String(eventData.price)
            : ''
        );
        setEventTypeId(eventData.event_type_id ? String(eventData.event_type_id) : 'none');

        const startDate = new Date(eventData.start_time);
        const endDate = new Date(eventData.end_time);
        if (!Number.isNaN(startDate.getTime())) {
          setEventStart(formatTenantDateTimeInput(startDate, tenantTimezone));
        }
        if (!Number.isNaN(endDate.getTime())) {
          setEventEnd(formatTenantDateTimeInput(endDate, tenantTimezone));
        }

        if (!Number.isNaN(startDate.getTime()) && !Number.isNaN(endDate.getTime())) {
          const diffMinutes = Math.round((endDate.getTime() - startDate.getTime()) / 60000);
          setEventDuration(diffMinutes > 0 ? String(diffMinutes) : '60');
        }
        if (eventData.contact_id) {
          try {
            const contactData: Contact = await crmContactsApi.detail(eventData.contact_id);
            setContactName(contactData.name || '');
          } catch (contactErr) {
            console.warn('Failed to load contact name:', contactErr);
          }
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить встречу.');
        }
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [eventId, router, tenantTimezone]);

  useEffect(() => {
    if (!eventStart) {
      setEventEnd('');
      return;
    }
    const durationValue = Number(eventDuration);
    if (!Number.isFinite(durationValue) || durationValue <= 0) {
      setEventEnd('');
      return;
    }
    const startUtc = localDateTimeStringToUtcISOString(eventStart, tenantTimezone);
    if (!startUtc) {
      setEventEnd('');
      return;
    }
    const endUtc = new Date(startUtc);
    endUtc.setMinutes(endUtc.getMinutes() + durationValue);
    if (Number.isNaN(endUtc.getTime())) {
      setEventEnd('');
      return;
    }
    setEventEnd(formatTenantDateTimeInput(endUtc, tenantTimezone));
  }, [eventStart, eventDuration, tenantTimezone]);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!contactId) return;

    if (!eventStart) {
      toast.error('Укажите дату начала');
      return;
    }

    const startUtc = localDateTimeStringToUtcISOString(eventStart, tenantTimezone);
    if (!startUtc) {
      toast.error('Некорректная дата начала');
      return;
    }

    let endPayload = eventEnd ? localDateTimeStringToUtcISOString(eventEnd, tenantTimezone) : '';
    if (!endPayload) {
      const durationValue = Number(eventDuration);
      const safeDuration = Number.isFinite(durationValue) && durationValue > 0 ? durationValue : 60;
      const computedEnd = new Date(startUtc);
      computedEnd.setMinutes(computedEnd.getMinutes() + safeDuration);
      endPayload = computedEnd.toISOString();
    }
    const priceRaw = eventPrice.trim();
    let pricePayload: number | null = null;
    if (priceRaw) {
      const parsedPrice = Number(priceRaw.replace(',', '.'));
      if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) {
        toast.error('Цена должна быть больше 0');
        return;
      }
      pricePayload = parsedPrice;
    }

    setSaving(true);
    try {
      await crmEventsApi.update(eventId, {
        title: eventTitle.trim() || 'Встреча',
        description: eventDescription.trim(),
        start_time: startUtc,
        end_time: endPayload,
        location: eventLocation.trim(),
        event_type_id: eventTypeId === 'none' ? null : Number(eventTypeId),
        price: pricePayload,
      });
      toast.success('Встреча обновлена');
      router.push(`/contact/${contactId}?tab=schedule`);
    } catch (err) {
      console.error('Error updating event:', err);
      toast.error('Не удалось сохранить встречу');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="animate-pulse">Загрузка встречи...</div>
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

  return (
    <div className="container mx-auto py-6">
      <div className="mb-4 text-sm text-muted-foreground">
        Встреча с клиентом: {contactName || '...'}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Редактирование встречи</CardTitle>
          <CardDescription>Измените данные встречи и сохраните</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="event-title">Название</Label>
              <Input
                id="event-title"
                value={eventTitle}
                onChange={(e) => setEventTitle(e.target.value)}
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
                  value={eventStart}
                  onChange={(e) => setEventStart(e.target.value)}
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
                  value={eventDuration}
                  onChange={(e) => setEventDuration(e.target.value)}
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
                  value={eventEnd}
                  onChange={(e) => setEventEnd(e.target.value)}
                  ref={eventEndInputRef}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="event-location">Место</Label>
                <Input
                  id="event-location"
                  value={eventLocation}
                  onChange={(e) => setEventLocation(e.target.value)}
                  placeholder="Онлайн / офис"
                />
              </div>
              <div className="space-y-2">
                <Label>Тип встречи</Label>
                <Select value={eventTypeId} onValueChange={setEventTypeId}>
                  <SelectTrigger>
                    <SelectValue
                      placeholder="Выберите тип"
                      aria-label={eventTypesById.get(Number(eventTypeId))?.name}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Без типа</SelectItem>
                    {eventTypes.map((eventType) => (
                      <SelectItem key={eventType.id} value={String(eventType.id)}>
                        {eventType.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-description">Описание</Label>
              <Textarea
                id="event-description"
                value={eventDescription}
                onChange={(e) => setEventDescription(e.target.value)}
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
                value={eventPrice}
                onChange={(e) => setEventPrice(e.target.value)}
                placeholder="Например, 3000"
              />
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={saving}>
                {saving ? 'Сохраняем...' : 'Сохранить и закрыть'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
