'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
import { crmContactsApi, crmEventsApi, crmEventTypesApi } from '@/lib/api/crm';
import type { Contact, Event, EventType } from '@/lib/api/crm';

type CalendarEventItem = {
  id: string;
  eventId: number;
  contactId: number;
  title: string;
  time: string;
  contactName: string;
  status: Event['status'];
  location: string;
  eventTypeName?: string;
  eventTypeColor?: string;
  startTimestamp: number;
};

type ItemsByDate = Record<string, CalendarEventItem[]>;

const statusLabels: Record<Event['status'], string> = {
  scheduled: 'Запланировано',
  completed: 'Завершено',
  cancelled: 'Отменено',
  no_show: 'Не явился',
};

const statusVariants: Record<Event['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  scheduled: 'default',
  completed: 'secondary',
  cancelled: 'destructive',
  no_show: 'outline',
};

function formatTimeRange(start: string, end: string) {
  const startDate = new Date(start);
  if (Number.isNaN(startDate.getTime())) return '';
  const startTime = startDate.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  const endDate = new Date(end);
  if (Number.isNaN(endDate.getTime())) return startTime;
  const endTime = endDate.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  return startTime === endTime ? startTime : `${startTime}–${endTime}`;
}

function eventToCalendarItem(
  event: Event,
  contactsById: Map<number, Contact>,
  eventTypesById: Map<number, EventType>
): CalendarEventItem | null {
  const startDate = new Date(event.start_time);
  if (Number.isNaN(startDate.getTime())) return null;
  const contactName = contactsById.get(event.contact_id)?.name || `Клиент #${event.contact_id}`;
  const eventType = event.event_type_id ? eventTypesById.get(event.event_type_id) : undefined;
  return {
    id: `event-${event.id}`,
    eventId: event.id,
    contactId: event.contact_id,
    title: event.title || 'Встреча',
    time: formatTimeRange(event.start_time, event.end_time),
    contactName,
    status: event.status,
    location: event.location,
    eventTypeName: eventType?.name,
    eventTypeColor: eventType?.color,
    startTimestamp: startDate.getTime(),
  };
}

function startOfWeek(d: Date) {
  const x = new Date(d);
  const day = x.getDay();
  const diff = (day + 6) % 7;
  x.setDate(x.getDate() - diff);
  x.setHours(0, 0, 0, 0);
  return x;
}

function formatKey(d: Date) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function generateWeekDates(refDate: Date) {
  const start = startOfWeek(refDate);
  return Array.from({ length: 7 }).map((_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

function generateMonthDates(refDate: Date) {
  const d = new Date(refDate.getFullYear(), refDate.getMonth(), 1);
  const firstDay = d.getDay();
  const start = new Date(d);
  start.setDate(1 - ((firstDay + 6) % 7));
  const cells = 42;
  return Array.from({ length: cells }).map((_, i) => {
    const c = new Date(start);
    c.setDate(start.getDate() + i);
    return c;
  });
}

function EventCard({ item, compact = false }: { item: CalendarEventItem; compact?: boolean }) {
  return (
    <Card className={cn('shadow-sm', compact ? 'mb-2' : 'mb-3')}>
      <CardHeader className={cn(compact ? 'p-2' : 'p-3', 'space-y-1')}>
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <CardTitle className={cn('font-medium', compact ? 'text-xs' : 'text-sm')}>
              <Link
                href={`/contact/${item.contactId}?tab=schedule`}
                className="hover:underline focus-visible:underline focus-visible:outline-none"
              >
                {item.title}
              </Link>
            </CardTitle>
            <div className={cn('text-slate-500', compact ? 'text-[11px]' : 'text-xs')}>
              {item.contactName}
            </div>
            {!compact && item.eventTypeName && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span
                  className="inline-flex h-2 w-2 rounded-full"
                  style={{ backgroundColor: item.eventTypeColor || '#94a3b8' }}
                  aria-hidden="true"
                />
                <span>{item.eventTypeName}</span>
              </div>
            )}
          </div>
          {item.time && (
            <div className={cn('text-slate-500', compact ? 'text-[11px]' : 'text-xs')}>
              {item.time}
            </div>
          )}
        </div>
        {!compact && (
          <div className="flex items-center gap-2 text-xs">
            <Badge variant={statusVariants[item.status]}>
              {statusLabels[item.status]}
            </Badge>
            {item.location && <span className="text-slate-500">{item.location}</span>}
          </div>
        )}
      </CardHeader>
    </Card>
  );
}

type ViewMode = 'week' | 'month' | 'day';

function WeekViewContent({ weekDates, itemsByDate }: { weekDates: Date[]; itemsByDate: ItemsByDate }) {
  const todayKey = formatKey(new Date());

  return (
    <div className="min-w-[1000px] grid grid-cols-7 gap-4">
      {weekDates.map((d) => {
        const k = formatKey(d);
        const items = itemsByDate[k] || [];
        const isToday = todayKey === k;
        const containerClass = cn(
          'rounded-lg p-2 min-h-[160px]',
          isToday ? 'bg-blue-50' : 'bg-slate-50'
        );

        return (
          <div key={k} className={containerClass}>
            <div className="flex items-center justify-between mb-2">
              <div className={cn('text-sm font-medium', isToday && 'text-blue-600')}>
                {d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric' })}
              </div>
              <div className="text-xs text-slate-500">{items.length}</div>
            </div>
            {items.map((item) => (
              <EventCard key={item.id} item={item} compact />
            ))}
          </div>
        );
      })}
    </div>
  );
}

function MonthViewContent({
  monthDates,
  itemsByDate,
  cursor,
}: {
  monthDates: Date[];
  itemsByDate: ItemsByDate;
  cursor: Date;
}) {
  const todayKey = formatKey(new Date());

  return (
    <div className="min-w-[1000px]">
      <div className="grid grid-cols-7 gap-2">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
          <div key={day} className="text-center text-xs font-medium text-slate-500 pb-2">
            {day}
          </div>
        ))}

        {monthDates.map((d) => {
          const k = formatKey(d);
          const items = itemsByDate[k] || [];
          const isCurrentMonth = d.getMonth() === cursor.getMonth();
          const isToday = todayKey === k;
          const containerClass = cn(
            'border rounded p-2 min-h-[120px]',
            isToday
              ? 'bg-blue-50 border-blue-300'
              : isCurrentMonth
              ? 'bg-white'
              : 'bg-slate-50 text-slate-400'
          );

          return (
            <div key={k} className={containerClass}>
              <div className="flex items-center justify-between mb-2">
                <div className={cn('text-xs font-medium', isToday && 'text-blue-600')}>
                  {d.getDate()}
                </div>
                {items.length > 0 && (
                  <div className="text-xs text-slate-500">{items.length}</div>
                )}
              </div>

              {items.slice(0, 2).map((item) => (
                <EventCard key={item.id} item={item} compact />
              ))}
              {items.length > 2 && (
                <div className="text-xs text-slate-500 mt-1 text-center">
                  +{items.length - 2} еще
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DayViewContent({ cursor, itemsByDate }: { cursor: Date; itemsByDate: ItemsByDate }) {
  const k = formatKey(cursor);
  const items = itemsByDate[k] || [];

  return (
    <div className="min-w-[600px]">
      <div className="rounded-lg p-4 bg-white border min-h-[300px]">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold">
            {cursor.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
          </div>
          <div className="text-sm text-slate-500">{items.length} встреч</div>
        </div>

        {items.length > 0 ? (
          items.map((item) => <EventCard key={item.id} item={item} />)
        ) : (
          <div className="text-center text-slate-400 py-8">
            Встреч на этот день нет
          </div>
        )}
      </div>
    </div>
  );
}

export default function ClientsSchedule() {
  const router = useRouter();
  const [view, setView] = useState<ViewMode>('week');
  const [cursor, setCursor] = useState<Date>(new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);

  const weekDates = useMemo(() => generateWeekDates(cursor), [cursor]);
  const monthDates = useMemo(() => generateMonthDates(cursor), [cursor]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [eventsData, contactsData, eventTypesData] = await Promise.all([
          crmEventsApi.list(),
          crmContactsApi.list(),
          crmEventTypesApi.list(),
        ]);
        setEvents(eventsData);
        setContacts(contactsData);
        setEventTypes(eventTypesData);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить расписание встреч');
        }
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [router]);

  const itemsByDate = useMemo<ItemsByDate>(() => {
    const map: ItemsByDate = {};
    const visibleDates = view === 'month' ? monthDates : view === 'week' ? weekDates : [cursor];
    visibleDates.forEach((d) => {
      map[formatKey(d)] = [];
    });

    const contactsById = new Map(contacts.map((contact) => [contact.id, contact]));
    const eventTypesById = new Map(eventTypes.map((eventType) => [eventType.id, eventType]));

    events.forEach((event) => {
      const item = eventToCalendarItem(event, contactsById, eventTypesById);
      if (!item) return;
      const key = formatKey(new Date(item.startTimestamp));
      if (!map[key]) map[key] = [];
      map[key].push(item);
    });

    Object.values(map).forEach((items) => {
      items.sort((a, b) => a.startTimestamp - b.startTimestamp);
    });

    return map;
  }, [events, contacts, eventTypes, view, cursor, weekDates, monthDates]);

  function prev() {
    const nextCursor = new Date(cursor);
    if (view === 'month') nextCursor.setMonth(nextCursor.getMonth() - 1);
    else if (view === 'week') nextCursor.setDate(nextCursor.getDate() - 7);
    else nextCursor.setDate(nextCursor.getDate() - 1);
    setCursor(nextCursor);
  }

  function next() {
    const nextCursor = new Date(cursor);
    if (view === 'month') nextCursor.setMonth(nextCursor.getMonth() + 1);
    else if (view === 'week') nextCursor.setDate(nextCursor.getDate() + 7);
    else nextCursor.setDate(nextCursor.getDate() + 1);
    setCursor(nextCursor);
  }

  if (loading) {
    return (
      <div className="p-6 max-w-full">
        <div className="flex items-center justify-center py-12">
          <div className="text-slate-500">Загрузка расписания...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-full">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold">Календарь встреч</h2>
          {error && <div className="text-sm text-red-500 mt-1">{error}</div>}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Button
              variant={view === 'month' ? 'default' : 'ghost'}
              onClick={() => setView('month')}
              size="sm"
            >
              Месяц
            </Button>
            <Button
              variant={view === 'week' ? 'default' : 'ghost'}
              onClick={() => setView('week')}
              size="sm"
            >
              Неделя
            </Button>
            <Button
              variant={view === 'day' ? 'default' : 'ghost'}
              onClick={() => setView('day')}
              size="sm"
            >
              День
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <Button onClick={prev} size="sm" variant="outline">
              &larr;
            </Button>
            <div className="px-3 py-1 text-sm font-medium min-w-[200px] text-center">
              {view === 'month'
                ? cursor.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })
                : view === 'week'
                ? `${weekDates[0].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} — ${weekDates[6].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}`
                : cursor.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
            </div>
            <Button onClick={next} size="sm" variant="outline">
              &rarr;
            </Button>
          </div>
        </div>
      </header>

      <div className="overflow-x-auto">
        {view === 'week' && <WeekViewContent weekDates={weekDates} itemsByDate={itemsByDate} />}
        {view === 'month' && (
          <MonthViewContent monthDates={monthDates} itemsByDate={itemsByDate} cursor={cursor} />
        )}
        {view === 'day' && <DayViewContent cursor={cursor} itemsByDate={itemsByDate} />}
      </div>
    </div>
  );
}
