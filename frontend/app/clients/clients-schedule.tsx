'use client';

import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { EditIcon, TrashIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { ApiError } from '@/lib/api';
import { clientApi } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  formatTimeRangeInTenantTimezone,
  formatTenantOffsetLabel,
  normalizeTenantTimezone,
  tenantDateToUtcISOString,
  toTenantDate,
} from '@/lib/timezone';
import { useCalendarDnD } from './useCalendarDnD';
import {
  crmAvailabilityEventsApi,
  crmContactsApi,
  crmEventsApi,
  crmEventTypesApi,
  type AvailabilityEvent,
  type Contact,
  type Event,
  type EventType,
} from '@/lib/api/crm';

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
  startDate: Date;
  startTimestamp: number;
  endTimestamp: number;
  kind: 'event';
};

type CalendarAvailabilityItem = {
  id: string;
  availabilityId: number;
  startDate: Date;
  time: string;
  startTimestamp: number;
  durationMinutes: number;
  repeatType: AvailabilityEvent['repeat_type'];
  kind: 'availability';
};

type CalendarItem = CalendarEventItem | CalendarAvailabilityItem;
type ItemsByDate = Record<string, CalendarItem[]>;

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

function formatTimeRange(start: string, end: string, timeZone: string) {
  return formatTimeRangeInTenantTimezone(start, end, timeZone);
}

function eventToCalendarItem(
  event: Event,
  contactsById: Map<number, Contact>,
  eventTypesById: Map<number, EventType>,
  timeZone: string
): CalendarEventItem | null {
  const startDate = toTenantDate(event.start_time, timeZone);
  if (Number.isNaN(startDate.getTime())) return null;
  const endDate = toTenantDate(event.end_time, timeZone);
  const endTimestamp = Number.isNaN(endDate.getTime())
    ? startDate.getTime() + 60 * 60 * 1000
    : endDate.getTime();
  const contactName = contactsById.get(event.contact_id)?.name || `Клиент #${event.contact_id}`;
  const eventType = event.event_type_id ? eventTypesById.get(event.event_type_id) : undefined;
  return {
    id: `event-${event.id}`,
    eventId: event.id,
    contactId: event.contact_id,
    title: event.title || 'Встреча',
    time: formatTimeRange(event.start_time, event.end_time, timeZone),
    contactName,
    status: event.status,
    location: event.location,
    eventTypeName: eventType?.name,
    eventTypeColor: eventType?.color,
    startDate,
    startTimestamp: startDate.getTime(),
    endTimestamp,
    kind: 'event',
  };
}

function formatTenantLocalDate(
  date: Date,
  timeZone: string,
  options: Intl.DateTimeFormatOptions
) {
  const utcValue = tenantDateToUtcISOString(date, timeZone);
  if (!utcValue) return '';
  return formatInTenantTimezone(utcValue, timeZone, options);
}

function formatAvailabilityTimeFromDate(startDate: Date, durationMinutes: number, timeZone: string) {
  if (Number.isNaN(startDate.getTime())) return '';
  const startTime = formatTenantLocalDate(startDate, timeZone, { hour: '2-digit', minute: '2-digit' });
  if (!durationMinutes || Number.isNaN(durationMinutes)) return startTime;
  const endDate = new Date(startDate.getTime() + durationMinutes * 60 * 1000);
  if (Number.isNaN(endDate.getTime())) return startTime;
  const endTime = formatTenantLocalDate(endDate, timeZone, { hour: '2-digit', minute: '2-digit' });
  return startTime === endTime ? startTime : `${startTime}–${endTime}`;
}

function buildAvailabilityOccurrence(
  item: AvailabilityEvent,
  occurrenceDate: Date,
  occurrenceKey: string,
  timeZone: string
): CalendarAvailabilityItem | null {
  const baseStart = toTenantDate(item.start_time, timeZone);
  if (Number.isNaN(baseStart.getTime())) return null;
  const startDate = new Date(occurrenceDate);
  startDate.setHours(baseStart.getHours(), baseStart.getMinutes(), baseStart.getSeconds(), 0);
  return {
    id: `availability-${item.id}-${occurrenceKey}`,
    availabilityId: item.id,
    startDate,
    time: formatAvailabilityTimeFromDate(startDate, item.duration_minutes, timeZone),
    startTimestamp: startDate.getTime(),
    durationMinutes: item.duration_minutes,
    repeatType: item.repeat_type,
    kind: 'availability',
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
    <Card className={cn('shadow-sm', compact ? 'mb-2' : 'mb-3')} onClick={(event) => event.stopPropagation()}>
      <CardHeader className={cn(compact ? 'p-2' : 'p-3', 'space-y-1')}>
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <CardTitle className={cn('font-medium', compact ? 'text-xs' : 'text-sm')}>
              <Link
                href={`/contact/${item.contactId}?tab=schedule`}
                className="hover:underline focus-visible:underline focus-visible:outline-none"
              >
                {item.contactName}
              </Link>
            </CardTitle>
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

function AvailabilityCard({
  item,
  compact = false,
  onEdit,
}: {
  item: CalendarAvailabilityItem;
  compact?: boolean;
  onEdit?: (item: CalendarAvailabilityItem) => void;
}) {
  return (
    <Card
      className={cn('shadow-sm border-emerald-400', compact ? 'mb-2' : 'mb-3')}
      onClick={(event) => event.stopPropagation()}
    >
      <CardHeader className={cn(compact ? 'p-2' : 'p-3', 'space-y-1')}>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className={cn('font-medium', compact ? 'text-xs' : 'text-sm')}>
            {item.time || 'Доступно'}
          </CardTitle>
          <button
            type="button"
            className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-500 transition hover:text-slate-700"
            onClick={(event) => {
              event.stopPropagation();
              onEdit?.(item);
            }}
            aria-label="Редактировать доступное время"
          >
            <EditIcon className="h-3.5 w-3.5" />
          </button>
        </div>
      </CardHeader>
    </Card>
  );
}

type ViewMode = 'week' | 'month' | 'day';
type DayClickHandler = (date: Date, minutes?: number) => void;
const WEEK_HOUR_ROW_HEIGHT = 56;
const SLOT_MINUTES = 15;

type EventDropHandler = (eventId: number, targetDate: Date, targetMinutes: number) => void;

function getCalendarHourRange(items: CalendarItem[]) {
  if (!items.length) {
    return { startHour: 8, endHour: 18 };
  }

  let min = 24 * 60;
  let max = 0;
  let hasValid = false;

  for (const item of items) {
    const start = new Date(item.startTimestamp);
    if (Number.isNaN(start.getTime())) continue;
    hasValid = true;
    const duration =
      item.kind === 'availability'
        ? item.durationMinutes
        : Math.max(15, (item.endTimestamp - item.startTimestamp) / 60000);
    const startMin = start.getHours() * 60 + start.getMinutes();
    const endMin = startMin + duration;

    min = Math.min(min, startMin);
    max = Math.max(max, endMin);
  }

  if (!hasValid) {
    return { startHour: 8, endHour: 18 };
  }

  return {
    startHour: Math.max(0, Math.floor(min / 60) - 1),
    endHour: Math.min(24, Math.ceil(max / 60) + 1),
  };
}

function WeekViewContent({
  weekDates,
  itemsByDate,
  onDayClick,
  onItemEdit,
  onEventDrop,
  timeZone,
}: {
  weekDates: Date[];
  itemsByDate: ItemsByDate;
  onDayClick?: DayClickHandler;
  onItemEdit?: (item: CalendarItem) => void;
  onEventDrop?: EventDropHandler;
  timeZone: string;
}) {
  const todayKey = formatKey(toTenantDate(new Date(), timeZone));
  const weekItems = weekDates.flatMap((date) => itemsByDate[formatKey(date)] || []);
  const { startHour, endHour } = getCalendarHourRange(weekItems);
  const hours = Array.from({ length: Math.max(1, endHour - startHour) }, (_, i) => startHour + i);
  const totalMinutes = hours.length * 60;
  const pxPerMinute = WEEK_HOUR_ROW_HEIGHT / 60;
  const dnd = useCalendarDnD({ startHour, pxPerMinute, slotMinutes: SLOT_MINUTES });
  const offsetLabel = formatTenantOffsetLabel(timeZone);

  return (
    <div className="min-w-[1000px] rounded-lg border border-slate-200 overflow-hidden">
      <div className="grid grid-cols-[72px_repeat(7,1fr)] border-b border-slate-200 bg-white">
        <div className="px-2 py-2 text-xs text-slate-400">{offsetLabel}</div>
        {weekDates.map((d) => {
          const k = formatKey(d);
          const isToday = todayKey === k;
          return (
            <div key={k} className="border-l border-slate-200 py-2 text-center -ml-px">
              <div className="text-[10px] uppercase tracking-wide text-slate-400">
                {formatTenantLocalDate(d, timeZone, { weekday: 'short' })}
              </div>
              <div className="mt-1 text-sm font-semibold flex justify-center">
                <span
                  className={cn(
                    isToday
                      ? 'inline-flex h-6 min-w-[24px] items-center justify-center rounded-full border border-blue-500 px-1 text-blue-600'
                      : ''
                  )}
                >
                  {formatTenantLocalDate(d, timeZone, { day: 'numeric' })}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-[72px_repeat(7,1fr)]">
        <div className="border-r border-slate-200 bg-white">
          {hours.map((hour, index) => (
            <div
              key={hour}
              className={cn(
                'h-14 px-2 text-xs text-slate-500 border-b border-slate-200 flex items-start pt-1',
                index === hours.length - 1 && 'border-b-0'
              )}
            >
              {String(hour).padStart(2, '0')}:00
            </div>
          ))}
        </div>

        {weekDates.map((d, index) => {
          const k = formatKey(d);
          const items = itemsByDate[k] || [];
          const dayStart = new Date(d);
          dayStart.setHours(startHour, 0, 0, 0);
          const dayStartMs = dayStart.getTime();
          return (
            <div
              key={k}
              className={cn(
                'relative bg-white',
                onDayClick && 'cursor-pointer',
                index !== weekDates.length - 1 && 'border-r border-slate-200'
              )}
              onClick={(event) => {
                if (!onDayClick) return;
                const minutes = dnd.calcSlot(event, event.currentTarget, totalMinutes);
                onDayClick(d, minutes);
              }}
              onDragOver={(event) => dnd.onDragOver(event, event.currentTarget, k)}
              onDragLeave={dnd.onDragLeave}
              onDrop={(event) => {
                event.preventDefault();
                const raw = event.dataTransfer.getData('text/plain');
                const eventId = Number(raw);
                if (eventId && onEventDrop) {
                  const targetMinutes = dnd.calcSlot(event, event.currentTarget, totalMinutes);
                  onEventDrop(eventId, d, targetMinutes);
                }
                dnd.onDragEnd();
              }}
              style={{ height: hours.length * WEEK_HOUR_ROW_HEIGHT }}
            >
              <div className="absolute inset-0 pointer-events-none">
                {hours.map((hour, index) => (
                  <div
                    key={hour}
                    className={cn('h-14 border-b border-slate-200', index === hours.length - 1 && 'border-b-0')}
                  />
                ))}
              </div>
              {dnd.hoverMinutes !== null && dnd.ghost?.dayKey === k && (
                <div
                  className="absolute left-0 right-0 h-0.5 bg-blue-500 opacity-70 pointer-events-none"
                  style={{
                    top: (dnd.hoverMinutes - startHour * 60) * pxPerMinute,
                  }}
                />
              )}
              {dnd.ghost && dnd.ghost.dayKey === k && (
                <div
                  className="absolute left-1 right-1 rounded-md border-2 border-dashed border-blue-400 bg-blue-300/30 pointer-events-none z-20"
                  style={{
                    top: dnd.ghost.top,
                    height: dnd.ghost.height,
                  }}
                />
              )}
              {items.map((item) => {
                const durationMinutes =
                  item.kind === 'availability'
                    ? item.durationMinutes
                    : Math.max(15, Math.round((item.endTimestamp - item.startTimestamp) / 60000) || 60);
                const itemEndTimestamp =
                  item.kind === 'availability'
                    ? item.startTimestamp + durationMinutes * 60000
                    : item.endTimestamp;
                const startMinutes = (item.startTimestamp - dayStartMs) / 60000;
                const endMinutes = (itemEndTimestamp - dayStartMs) / 60000;
                const clampedStart = Math.max(0, startMinutes);
                const clampedEnd = Math.min(totalMinutes, Math.max(endMinutes, clampedStart + 15));
                const top = clampedStart * pxPerMinute;
                const height = Math.max(24, (clampedEnd - clampedStart) * pxPerMinute);

                return (
                  <div
                    key={item.id}
                    className={cn(
                      'absolute left-1 right-1 rounded-md border px-2 py-1 text-[11px] shadow-sm bg-white',
                      item.kind === 'availability' ? 'border-emerald-400' : 'border-amber-200 bg-amber-50',
                      item.kind === 'event' &&
                        dnd.draggingEventId === item.eventId &&
                        'opacity-0 pointer-events-none'
                    )}
                    style={{ top, height }}
                    onClick={(event) => event.stopPropagation()}
                    draggable={item.kind === 'event'}
                    onDragStart={(event) => {
                      if (item.kind !== 'event') return;
                      event.dataTransfer.setData('text/plain', String(item.eventId));
                      event.dataTransfer.effectAllowed = 'move';
                      const durationMinutes = Math.max(
                        15,
                        Math.round((item.endTimestamp - item.startTimestamp) / 60000) || 60
                      );
                      const ghostTop = ((item.startTimestamp - dayStartMs) / 60000) * pxPerMinute;
                      const ghostHeight = durationMinutes * pxPerMinute;
                      dnd.onDragStart(item.eventId, ghostTop, ghostHeight, k);
                    }}
                    onDragEnd={() => {
                      if (item.kind !== 'event') return;
                      dnd.onDragEnd();
                    }}
                  >
                    {item.kind === 'availability' ? (
                      <div className="flex items-center justify-between gap-2 text-emerald-900 font-medium">
                        <span className="truncate">{item.time || 'Доступно'}</span>
                        <button
                          type="button"
                          className="inline-flex h-5 w-5 items-center justify-center rounded text-emerald-700 transition hover:text-emerald-900"
                          onClick={(event) => {
                            event.stopPropagation();
                            onItemEdit?.(item);
                          }}
                          aria-label="Редактировать доступное время"
                        >
                          <EditIcon className="h-3 w-3" />
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <Link
                            href={`/contact/${item.contactId}?tab=schedule`}
                            className="truncate font-medium text-slate-900 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.contactName}
                          </Link>
                          <button
                            type="button"
                            className="inline-flex h-5 w-5 items-center justify-center rounded text-slate-500 transition hover:text-slate-700"
                            onClick={(event) => {
                              event.stopPropagation();
                              onItemEdit?.(item);
                            }}
                            aria-label="Редактировать встречу"
                          >
                            <EditIcon className="h-3 w-3" />
                          </button>
                        </div>
                        {item.time && <div className="text-[10px] text-slate-600">{item.time}</div>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonthViewContent({
  monthDates,
  itemsByDate,
  cursor,
  onDayClick,
  showAvailability,
  onItemEdit,
  timeZone,
}: {
  monthDates: Date[];
  itemsByDate: ItemsByDate;
  cursor: Date;
  onDayClick?: DayClickHandler;
  showAvailability: boolean;
  onItemEdit: (item: CalendarItem) => void;
  timeZone: string;
}) {
  const todayKey = formatKey(toTenantDate(new Date(), timeZone));

  return (
    <div className="min-w-[1000px] space-y-2">
      <div className="grid grid-cols-7 gap-0">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => (
          <div key={day} className="text-center text-xs font-medium text-slate-500 py-1">
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 divide-x divide-y border border-slate-200 rounded-lg overflow-hidden">
        {monthDates.map((d) => {
          const k = formatKey(d);
          const items = itemsByDate[k] || [];
          const visibleItems = showAvailability ? items : items.filter((item) => item.kind === 'event');
          const isCurrentMonth = d.getMonth() === cursor.getMonth();
          const isToday = todayKey === k;
          const containerClass = cn(
            'p-2 min-h-[120px]',
            isToday ? 'bg-blue-50' : isCurrentMonth ? 'bg-white' : 'bg-slate-50 text-slate-400',
            onDayClick && 'cursor-pointer'
          );

          return (
            <div key={k} className={containerClass} onClick={() => onDayClick?.(d)}>
              <div className="flex items-center justify-between mb-2">
                <div className={cn('text-xs font-medium', isToday && 'text-blue-600')}>
                  {formatTenantLocalDate(d, timeZone, { day: 'numeric' })}
                </div>
              </div>

              <div className="space-y-1 text-xs">
                {visibleItems.slice(0, 3).map((item) => {
                  const timeLabel = formatTenantLocalDate(new Date(item.startTimestamp), timeZone, {
                    hour: '2-digit',
                    minute: '2-digit',
                  });
                  const label = item.kind === 'availability' ? 'Доступно' : item.contactName;
                  return (
                    <div
                      key={item.id}
                      className={cn(
                        'flex items-center gap-2 truncate rounded px-1 py-0.5 transition hover:bg-slate-100 cursor-pointer',
                        item.kind === 'availability' && 'text-emerald-700'
                      )}
                      onClick={(event) => {
                        event.stopPropagation();
                        onItemEdit(item);
                      }}
                    >
                      <span className="text-slate-400">{timeLabel}</span>
                      <span className="truncate">{label}</span>
                    </div>
                  );
                })}
              </div>
              {visibleItems.length > 3 && (
                <div className="text-xs text-slate-500 mt-1 text-center">
                  +{visibleItems.length - 3} еще
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DayViewContent({
  cursor,
  itemsByDate,
  onDayClick,
  onItemEdit,
  onEventDrop,
  timeZone,
}: {
  cursor: Date;
  itemsByDate: ItemsByDate;
  onDayClick?: DayClickHandler;
  onItemEdit?: (item: CalendarItem) => void;
  onEventDrop?: EventDropHandler;
  timeZone: string;
}) {
  const k = formatKey(cursor);
  const items = itemsByDate[k] || [];
  const { startHour, endHour } = getCalendarHourRange(items);
  const hours = Array.from({ length: Math.max(1, endHour - startHour) }, (_, i) => startHour + i);
  const totalMinutes = hours.length * 60;
  const pxPerMinute = WEEK_HOUR_ROW_HEIGHT / 60;
  const dayStart = new Date(cursor);
  dayStart.setHours(startHour, 0, 0, 0);
  const dayStartMs = dayStart.getTime();
  const dnd = useCalendarDnD({ startHour, pxPerMinute, slotMinutes: SLOT_MINUTES });
  const offsetLabel = formatTenantOffsetLabel(timeZone);

  return (
    <div className="min-w-[600px] rounded-lg border border-slate-200 overflow-hidden">
      <div className="grid grid-cols-[72px_1fr] border-b border-slate-200 bg-white">
        <div className="px-2 py-2 text-xs text-slate-400">{offsetLabel}</div>
        <div className="py-2 text-center">
          <div className="text-[10px] uppercase tracking-wide text-slate-400">
            {formatTenantLocalDate(cursor, timeZone, { weekday: 'short' })}
          </div>
          <div className="mt-1 text-sm font-semibold text-slate-900">
            {formatTenantLocalDate(cursor, timeZone, { day: 'numeric' })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-[72px_1fr]">
        <div className="border-r border-slate-200 bg-white">
          {hours.map((hour, index) => (
            <div
              key={hour}
              className={cn(
                'h-14 px-2 text-xs text-slate-500 border-b border-slate-200 flex items-start pt-1',
                index === hours.length - 1 && 'border-b-0'
              )}
            >
              {String(hour).padStart(2, '0')}:00
            </div>
          ))}
        </div>
        <div
          className={cn('relative bg-white', onDayClick && 'cursor-pointer')}
          onClick={(event) => {
            if (!onDayClick) return;
            const minutes = dnd.calcSlot(event, event.currentTarget, totalMinutes);
            onDayClick(cursor, minutes);
          }}
          onDragOver={(event) => dnd.onDragOver(event, event.currentTarget)}
          onDragLeave={dnd.onDragLeave}
          onDrop={(event) => {
            event.preventDefault();
            const raw = event.dataTransfer.getData('text/plain');
            const eventId = Number(raw);
            if (eventId && onEventDrop) {
              const targetMinutes = dnd.calcSlot(event, event.currentTarget, totalMinutes);
              onEventDrop(eventId, cursor, targetMinutes);
            }
            dnd.onDragEnd();
          }}
          style={{ height: hours.length * WEEK_HOUR_ROW_HEIGHT }}
        >
          <div className="absolute inset-0 pointer-events-none">
            {hours.map((hour, index) => (
              <div
                key={hour}
                className={cn('h-14 border-b border-slate-200', index === hours.length - 1 && 'border-b-0')}
              />
            ))}
          </div>
          {dnd.hoverMinutes !== null && (
            <div
              className="absolute left-0 right-0 h-0.5 bg-blue-500 opacity-70 pointer-events-none"
              style={{
                top: (dnd.hoverMinutes - startHour * 60) * pxPerMinute,
              }}
            />
          )}
          {dnd.ghost && (
            <div
              className="absolute left-1 right-1 rounded-md border-2 border-dashed border-blue-400 bg-blue-300/30 pointer-events-none z-20"
              style={{
                top: dnd.ghost.top,
                height: dnd.ghost.height,
              }}
            />
          )}

          {items.map((item) => {
            const durationMinutes =
              item.kind === 'availability'
                ? item.durationMinutes
                : Math.max(15, Math.round((item.endTimestamp - item.startTimestamp) / 60000) || 60);
            const itemEndTimestamp =
              item.kind === 'availability'
                ? item.startTimestamp + durationMinutes * 60000
                : item.endTimestamp;
            const startMinutes = (item.startTimestamp - dayStartMs) / 60000;
            const endMinutes = (itemEndTimestamp - dayStartMs) / 60000;
            const clampedStart = Math.max(0, startMinutes);
            const clampedEnd = Math.min(totalMinutes, Math.max(endMinutes, clampedStart + 15));
            const top = clampedStart * pxPerMinute;
            const height = Math.max(24, (clampedEnd - clampedStart) * pxPerMinute);

            return (
              <div
                key={item.id}
                className={cn(
                  'absolute left-1 right-1 rounded-md border px-2 py-1 text-[11px] shadow-sm bg-white',
                  item.kind === 'availability' ? 'border-emerald-400' : 'border-amber-200 bg-amber-50',
                  item.kind === 'event' &&
                    dnd.draggingEventId === item.eventId &&
                    'opacity-0 pointer-events-none'
                )}
                style={{ top, height }}
                onClick={(event) => event.stopPropagation()}
                draggable={item.kind === 'event'}
                onDragStart={(event) => {
                  if (item.kind !== 'event') return;
                  event.dataTransfer.setData('text/plain', String(item.eventId));
                  event.dataTransfer.effectAllowed = 'move';
                  const durationMinutes = Math.max(
                    15,
                    Math.round((item.endTimestamp - item.startTimestamp) / 60000) || 60
                  );
                  const ghostTop = ((item.startTimestamp - dayStartMs) / 60000) * pxPerMinute;
                  const ghostHeight = durationMinutes * pxPerMinute;
                  dnd.onDragStart(item.eventId, ghostTop, ghostHeight);
                }}
                onDragEnd={() => {
                  if (item.kind !== 'event') return;
                  dnd.onDragEnd();
                }}
              >
                {item.kind === 'availability' ? (
                  <div className="flex items-center justify-between gap-2 text-emerald-900 font-medium">
                    <span className="truncate">{item.time || 'Доступно'}</span>
                    <button
                      type="button"
                      className="inline-flex h-5 w-5 items-center justify-center rounded text-emerald-700 transition hover:text-emerald-900"
                      onClick={(event) => {
                        event.stopPropagation();
                        onItemEdit?.(item);
                      }}
                      aria-label="Редактировать доступное время"
                    >
                      <EditIcon className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <div className="truncate font-medium text-slate-900">{item.contactName}</div>
                      <button
                        type="button"
                        className="inline-flex h-5 w-5 items-center justify-center rounded text-slate-500 transition hover:text-slate-700"
                        onClick={(event) => {
                          event.stopPropagation();
                          onItemEdit?.(item);
                        }}
                        aria-label="Редактировать встречу"
                      >
                        <EditIcon className="h-3 w-3" />
                      </button>
                    </div>
                    {item.time && <div className="text-[10px] text-slate-600">{item.time}</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function ClientsSchedule() {
  const router = useRouter();
  const [view, setView] = useState<ViewMode>('week');
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const cursorInitializedRef = useRef(false);
  const [cursor, setCursor] = useState<Date>(() => toTenantDate(new Date(), DEFAULT_TENANT_TIMEZONE));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [availabilityEvents, setAvailabilityEvents] = useState<AvailabilityEvent[]>([]);
  const [availabilityOpen, setAvailabilityOpen] = useState(false);
  const [availabilityDate, setAvailabilityDate] = useState<Date | null>(null);
  const [availabilityTime, setAvailabilityTime] = useState('10:00');
  const [availabilityDuration, setAvailabilityDuration] = useState('60');
  const [availabilityRepeat, setAvailabilityRepeat] = useState<0 | 1 | 2 | 3>(2);
  const [availabilitySaving, setAvailabilitySaving] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [availabilityEditingId, setAvailabilityEditingId] = useState<number | null>(null);
  const [showAvailabilityInMonth, setShowAvailabilityInMonth] = useState(false);
  const [monthEditOpen, setMonthEditOpen] = useState(false);
  const [monthEditItem, setMonthEditItem] = useState<CalendarItem | null>(null);
  const [monthEditDate, setMonthEditDate] = useState<Date | null>(null);
  const [monthEditTime, setMonthEditTime] = useState('10:00');
  const [monthEditDuration, setMonthEditDuration] = useState('60');
  const [monthEditSaving, setMonthEditSaving] = useState(false);
  const [monthEditDeleting, setMonthEditDeleting] = useState(false);
  const [monthEditError, setMonthEditError] = useState<string | null>(null);

  const normalizedTimezone = useMemo(() => normalizeTenantTimezone(tenantTimezone), [tenantTimezone]);
  const weekDates = useMemo(() => generateWeekDates(cursor), [cursor]);
  const monthDates = useMemo(() => generateMonthDates(cursor), [cursor]);

  useEffect(() => {
    if (!cursorInitializedRef.current) {
      setCursor(toTenantDate(new Date(), normalizedTimezone));
      cursorInitializedRef.current = true;
    }
  }, [normalizedTimezone]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [eventsData, contactsData, eventTypesData, availabilityData, settingsData] = await Promise.all([
          crmEventsApi.list(),
          crmContactsApi.list(),
          crmEventTypesApi.list(),
          crmAvailabilityEventsApi.list(),
          clientApi.getSettings(),
        ]);
        setEvents(eventsData);
        setContacts(contactsData);
        setEventTypes(eventTypesData);
        setAvailabilityEvents(availabilityData);
        setTenantTimezone(normalizeTenantTimezone(settingsData.timezone));
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
      const item = eventToCalendarItem(event, contactsById, eventTypesById, normalizedTimezone);
      if (!item) return;
      const key = formatKey(new Date(item.startTimestamp));
      if (!map[key]) map[key] = [];
      map[key].push(item);
    });

    availabilityEvents.forEach((event) => {
      const baseStart = toTenantDate(event.start_time, normalizedTimezone);
      if (Number.isNaN(baseStart.getTime())) return;
      const baseDateKey = formatKey(baseStart);
      const baseDay = new Date(baseStart);
      baseDay.setHours(0, 0, 0, 0);

      visibleDates.forEach((date) => {
        const dateKey = formatKey(date);
        const dateOnly = new Date(date);
        dateOnly.setHours(0, 0, 0, 0);
        if (dateOnly < baseDay) return;

        let matches = false;
        if (event.repeat_type === 1) {
          matches = true;
        } else if (event.repeat_type === 2) {
          matches = date.getDay() === baseStart.getDay();
        } else if (event.repeat_type === 3) {
          matches = date.getDate() === baseStart.getDate();
        } else {
          matches = dateKey === baseDateKey;
        }

        if (!matches) return;
        const item = buildAvailabilityOccurrence(event, date, dateKey, normalizedTimezone);
        if (!item) return;
        if (!map[dateKey]) map[dateKey] = [];
        map[dateKey].push(item);
      });
    });

    Object.values(map).forEach((items) => {
      const eventItems = items.filter((item) => item.kind === 'event') as CalendarEventItem[];
      if (eventItems.length) {
        const filtered = items.filter((item) => {
          if (item.kind === 'event') return true;
          const availabilityStart = item.startTimestamp;
          const availabilityEnd = item.startTimestamp + item.durationMinutes * 60 * 1000;
          return !eventItems.some(
            (eventItem) =>
              availabilityStart < eventItem.endTimestamp &&
              availabilityEnd > eventItem.startTimestamp
          );
        });
        items.length = 0;
        items.push(...filtered);
      }

      items.sort((a, b) => a.startTimestamp - b.startTimestamp);
    });

    return map;
  }, [events, contacts, eventTypes, availabilityEvents, view, cursor, weekDates, monthDates, normalizedTimezone]);

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

  function openAvailability(date: Date, minutes?: number, item?: CalendarAvailabilityItem) {
    setAvailabilityDate(date);
    setAvailabilityError(null);

    if (item) {
      // ✏️ редактирование
      setAvailabilityEditingId(item.availabilityId);
      setAvailabilityTime(
        `${String(item.startDate.getHours()).padStart(2, '0')}:${String(
          item.startDate.getMinutes()
        ).padStart(2, '0')}`
      );
      setAvailabilityDuration(String(item.durationMinutes));
      setAvailabilityRepeat(item.repeatType);
    } else {
      // ➕ создание
      setAvailabilityEditingId(null);
      if (minutes !== undefined) {
        const hours = Math.max(0, Math.min(23, Math.floor(minutes / 60)));
        const mins = Math.max(0, Math.min(59, minutes % 60));
        setAvailabilityTime(`${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`);
      } else {
        setAvailabilityTime('10:00');
      }
      setAvailabilityDuration('60');
      setAvailabilityRepeat(2); // 🔥 НА КАЖДОЙ НЕДЕЛЕ
    }

    setAvailabilityOpen(true);
  }


  function formatLocalDateTime(value: Date) {
    return tenantDateToUtcISOString(value, normalizedTimezone);
  }

  function formatDateInput(value: Date) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function parseDateInput(value: string) {
    const [year, month, day] = value.split('-').map((part) => Number(part));
    if (!year || !month || !day) return null;
    return new Date(year, month - 1, day);
  }

  function openMonthEdit(item: CalendarItem) {
    const startDate = new Date(item.startTimestamp);
    if (Number.isNaN(startDate.getTime())) return;
    const duration =
      item.kind === 'availability'
        ? item.durationMinutes
        : Math.max(15, Math.round((item.endTimestamp - item.startTimestamp) / 60000) || 60);
    setMonthEditItem(item);
    setMonthEditDate(startDate);
    setMonthEditTime(
      `${String(startDate.getHours()).padStart(2, '0')}:${String(startDate.getMinutes()).padStart(2, '0')}`
    );
    setMonthEditDuration(String(duration));
    setMonthEditError(null);
    setMonthEditOpen(true);
  }

  async function handleMonthEditSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!monthEditItem || !monthEditDate) return;

    const [hoursRaw, minutesRaw] = monthEditTime.split(':');
    const hours = Number(hoursRaw);
    const minutes = Number(minutesRaw);
    const duration = Number(monthEditDuration);

    if (Number.isNaN(hours) || Number.isNaN(minutes) || Number.isNaN(duration) || duration <= 0) {
      setMonthEditError('Проверьте дату, время и длительность.');
      return;
    }

    const start = new Date(monthEditDate);
    start.setHours(hours, minutes, 0, 0);

    setMonthEditSaving(true);
    setMonthEditError(null);
    try {
      if (monthEditItem.kind === 'availability') {
        const updated = await crmAvailabilityEventsApi.update(monthEditItem.availabilityId, {
          start_time: formatLocalDateTime(start),
          duration_minutes: duration,
        });
        setAvailabilityEvents((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      } else {
        const end = new Date(start.getTime() + duration * 60 * 1000);
        const updated = await crmEventsApi.update(monthEditItem.eventId, {
          start_time: formatLocalDateTime(start),
          end_time: formatLocalDateTime(end),
        });
        setEvents((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      }
      setMonthEditOpen(false);
      setMonthEditItem(null);
    } catch (err) {
      setMonthEditError('Не удалось сохранить изменения.');
    } finally {
      setMonthEditSaving(false);
    }
  }

  async function handleMonthEditDelete() {
    if (!monthEditItem) return;
    setMonthEditDeleting(true);
    setMonthEditError(null);
    try {
      if (monthEditItem.kind === 'availability') {
        await crmAvailabilityEventsApi.delete(monthEditItem.availabilityId);
        setAvailabilityEvents((prev) => prev.filter((item) => item.id !== monthEditItem.availabilityId));
      } else {
        await crmEventsApi.delete(monthEditItem.eventId);
        setEvents((prev) => prev.filter((item) => item.id !== monthEditItem.eventId));
      }
      setMonthEditOpen(false);
      setMonthEditItem(null);
    } catch (err) {
      setMonthEditError('Не удалось удалить запись.');
    } finally {
      setMonthEditDeleting(false);
    }
  }

  async function handleEventDrop(eventId: number, targetDate: Date, targetMinutes: number) {
    const eventItem = events.find((item) => item.id === eventId);
    if (!eventItem) return;
    const startDate = toTenantDate(eventItem.start_time, normalizedTimezone);
    const endDate = toTenantDate(eventItem.end_time, normalizedTimezone);
    const durationMinutes = Number.isNaN(endDate.getTime())
      ? 60
      : Math.max(15, Math.round((endDate.getTime() - startDate.getTime()) / 60000) || 60);

    const nextStart = new Date(targetDate);
    nextStart.setHours(
      Math.floor(targetMinutes / 60),
      targetMinutes % 60,
      0,
      0
    );
    const nextEnd = new Date(nextStart.getTime() + durationMinutes * 60 * 1000);

    const nextStartTime = formatLocalDateTime(nextStart);
    const nextEndTime = formatLocalDateTime(nextEnd);

    setEvents((prev) =>
      prev.map((item) =>
        item.id === eventId
          ? {
              ...item,
              start_time: nextStartTime,
              end_time: nextEndTime,
            }
          : item
      )
    );

    try {
      await crmEventsApi.update(eventId, {
        start_time: nextStartTime,
        end_time: nextEndTime,
      });
    } catch (err) {
      setEvents((prev) => prev.map((item) => (item.id === eventId ? eventItem : item)));
    }
  }
  async function handleAvailabilitySave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!availabilityDate) {
      setAvailabilityOpen(false);
      return;
    }

    const [hoursRaw, minutesRaw] = availabilityTime.split(':');
    const hours = Number(hoursRaw);
    const minutes = Number(minutesRaw);
    const duration = Number(availabilityDuration);

    if (Number.isNaN(hours) || Number.isNaN(minutes) || Number.isNaN(duration) || duration <= 0) {
      setAvailabilityError('Проверьте время и длительность.');
      return;
    }

    const start = new Date(availabilityDate);
    start.setHours(hours, minutes, 0, 0);

    setAvailabilityError(null);
    const payload = {
      start_time: formatLocalDateTime(start),
      duration_minutes: duration,
      repeat_type: availabilityRepeat,
    };

    const startMinutes = hours * 60 + minutes;
    const conflict = availabilityEvents.some((item) => {
      const itemStart = toTenantDate(item.start_time, normalizedTimezone);
      if (Number.isNaN(itemStart.getTime())) return false;

      const itemMinutes = itemStart.getHours() * 60 + itemStart.getMinutes();
      if (itemMinutes !== startMinutes) return false;

      if (availabilityEditingId && item.id === availabilityEditingId) {
        return false;
      }

      if (availabilityRepeat === 1) return true;
      if (availabilityRepeat === 2) {
        return item.repeat_type === 2 && itemStart.getDay() === start.getDay();
      }
      if (availabilityRepeat === 3) {
        return item.repeat_type === 3 && itemStart.getDate() === start.getDate();
      }
      if (availabilityRepeat === 0) {
        return formatKey(itemStart) === formatKey(start);
      }

      return false;
    });

    if (conflict) {
      setAvailabilityError('Свободное окно на это время уже существует');
      return;
    }

    setAvailabilitySaving(true);
    try {
      if (availabilityEditingId !== null) {
        const updated = await crmAvailabilityEventsApi.update(availabilityEditingId, payload);
        setAvailabilityEvents((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item))
        );
        setAvailabilityEditingId(null);
      } else {
        const created = await crmAvailabilityEventsApi.create(payload);
        setAvailabilityEvents((prev) => [created, ...prev]);
      }
      setAvailabilityOpen(false);
    } catch (err) {
      setAvailabilityError('Не удалось сохранить доступное время.');
    } finally {
      setAvailabilitySaving(false);
    }
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
                ? formatTenantLocalDate(cursor, normalizedTimezone, { month: 'long', year: 'numeric' })
                : view === 'week'
                ? `${formatTenantLocalDate(weekDates[0], normalizedTimezone, { day: 'numeric', month: 'short' })} — ${formatTenantLocalDate(weekDates[6], normalizedTimezone, { day: 'numeric', month: 'short' })}`
                : formatTenantLocalDate(cursor, normalizedTimezone, { day: 'numeric', month: 'long', year: 'numeric' })}
            </div>
            <Button onClick={next} size="sm" variant="outline">
              &rarr;
            </Button>
          </div>
        </div>
      </header>

      <div className="overflow-x-auto">
        {view === 'week' && (
          <WeekViewContent
            weekDates={weekDates}
            itemsByDate={itemsByDate}
            onDayClick={openAvailability}
            onItemEdit={openMonthEdit}
            onEventDrop={handleEventDrop}
            timeZone={normalizedTimezone}
          />
        )}
        {view === 'month' && (
          <MonthViewContent
            monthDates={monthDates}
            itemsByDate={itemsByDate}
            cursor={cursor}
            onDayClick={openAvailability}
            showAvailability={showAvailabilityInMonth}
            onItemEdit={openMonthEdit}
            timeZone={normalizedTimezone}
          />
        )}
        {view === 'day' && (
          <DayViewContent
            cursor={cursor}
            itemsByDate={itemsByDate}
            onDayClick={openAvailability}
            onItemEdit={openMonthEdit}
            onEventDrop={handleEventDrop}
            timeZone={normalizedTimezone}
          />
        )}
      </div>
      <div className="mt-4 text-sm text-slate-500">
        Кликните на свободное пространство дня, чтобы внести туда доступное для записи время.
      </div>
      {view === 'month' && (
        <label className="mt-3 inline-flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={showAvailabilityInMonth}
            onChange={(event) => setShowAvailabilityInMonth(event.target.checked)}
          />
          Отобразить свободные окошки
        </label>
      )}

      <Dialog open={availabilityOpen} onOpenChange={setAvailabilityOpen}>
        <DialogContent
          className="max-w-sm bg-white text-black dark:bg-white dark:text-black dark:border-gray-200 [&>button]:text-black dark:[&>button]:text-black"
          overlayClassName="bg-transparent"
        >
          <DialogHeader>
            <DialogTitle>
              {availabilityDate
                ? `${formatTenantLocalDate(availabilityDate, normalizedTimezone, {
                    day: 'numeric',
                    month: 'long',
                  })} - ${formatTenantLocalDate(availabilityDate, normalizedTimezone, { weekday: 'long' })}`
                : 'Доступное время'}
            </DialogTitle>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleAvailabilitySave}>
            {availabilityError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {availabilityError}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Время
                <Input
                  type="time"
                  className="mt-1"
                  value={availabilityTime}
                  onChange={(event) => setAvailabilityTime(event.target.value)}
                />
              </label>
              <label className="text-sm font-medium">
                Длительность, мин
                <Input
                  type="number"
                  min={5}
                  step={5}
                  className="mt-1"
                  value={availabilityDuration}
                  onChange={(event) => setAvailabilityDuration(event.target.value)}
                />
              </label>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <input
                  id="availability-repeat-daily"
                  name="availability-repeat"
                  type="radio"
                  className="h-4 w-4"
                  value="1"
                  checked={availabilityRepeat === 1}
                  onChange={() => setAvailabilityRepeat(1)}
                />
                <label htmlFor="availability-repeat-daily" className="text-sm">
                  Каждый день
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="availability-repeat-weekly"
                  name="availability-repeat"
                  type="radio"
                  className="h-4 w-4"
                  value="2"
                  checked={availabilityRepeat === 2}
                  onChange={() => setAvailabilityRepeat(2)}
                />
                <label htmlFor="availability-repeat-weekly" className="text-sm">
                  На каждой неделе
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="availability-repeat-monthly"
                  name="availability-repeat"
                  type="radio"
                  className="h-4 w-4"
                  value="3"
                  checked={availabilityRepeat === 3}
                  onChange={() => setAvailabilityRepeat(3)}
                />
                <label htmlFor="availability-repeat-monthly" className="text-sm">
                  В это число каждый месяц
                </label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="availability-repeat-none"
                  name="availability-repeat"
                  type="radio"
                  className="h-4 w-4"
                  value="0"
                  checked={availabilityRepeat === 0}
                  onChange={() => setAvailabilityRepeat(0)}
                />
                <label htmlFor="availability-repeat-none" className="text-sm">
                  Без повтора
                </label>
              </div>
            </div>

            <DialogFooter>
              <Button type="submit" disabled={availabilitySaving}>
                {availabilitySaving ? 'Сохранение...' : 'Сохранить'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={monthEditOpen}
        onOpenChange={(open) => {
          setMonthEditOpen(open);
          if (!open) {
            setMonthEditItem(null);
            setMonthEditError(null);
          }
        }}
      >
        <DialogContent
          className="max-w-sm bg-white text-black dark:bg-white dark:text-black dark:border-gray-200 [&>button]:text-black dark:[&>button]:text-black"
          overlayClassName="bg-transparent"
        >
          <DialogHeader>
            <DialogTitle>
              {monthEditItem?.kind === 'availability'
                ? 'Редактировать свободное окно'
                : 'Редактировать встречу'}
            </DialogTitle>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleMonthEditSave}>
            {monthEditError && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {monthEditError}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm font-medium">
                Дата
                <Input
                  type="date"
                  className="mt-1"
                  value={monthEditDate ? formatDateInput(monthEditDate) : ''}
                  onChange={(event) => {
                    const next = parseDateInput(event.target.value);
                    if (next) setMonthEditDate(next);
                  }}
                />
              </label>
              <label className="text-sm font-medium">
                Время
                <Input
                  type="time"
                  className="mt-1"
                  value={monthEditTime}
                  onChange={(event) => setMonthEditTime(event.target.value)}
                />
              </label>
            </div>
            <label className="text-sm font-medium">
              Длительность, мин
              <Input
                type="number"
                min={5}
                step={5}
                className="mt-1"
                value={monthEditDuration}
                onChange={(event) => setMonthEditDuration(event.target.value)}
              />
            </label>
            <DialogFooter className="sm:justify-between sm:items-end">
              <div className="flex flex-col items-start gap-2">
                {monthEditItem?.kind === 'event' && (
                  <Link
                    href={`/meet/${monthEditItem.eventId}`}
                    className="text-sm text-blue-600 underline-offset-4 hover:underline hover:text-blue-700"
                  >
                    Больше данных
                  </Link>
                )}
                <Button type="submit" disabled={monthEditSaving}>
                  {monthEditSaving ? 'Сохранение...' : 'Сохранить'}
                </Button>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleMonthEditDelete}
                  disabled={monthEditDeleting}
                >
                  {monthEditDeleting ? (
                    'Удаление...'
                  ) : (
                    <>
                      <TrashIcon className="mr-2 h-4 w-4" />
                      Удалить
                    </>
                  )}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
