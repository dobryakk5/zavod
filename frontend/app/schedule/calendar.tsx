'use client';

import React, {useState, useMemo, useEffect, useRef} from 'react';
import {Card, CardContent, CardHeader, CardTitle} from '@/components/ui/card';
import {Button} from '@/components/ui/button';
import {Badge} from '@/components/ui/badge';
import {ApiError} from '@/lib/api';
import {schedulesApi} from '@/lib/api/schedules';
import {useRouter} from 'next/navigation';
import type {Schedule} from '@/lib/types';
import {cn} from '@/lib/utils';
import Link from 'next/link';
import {useTenantTimezone} from '@/lib/hooks';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  normalizeTenantTimezone,
  tenantDateToUtcISOString,
  toTenantDate,
} from '@/lib/timezone';

// dnd-kit
import {
  DndContext,
  closestCenter,
  DragOverlay,
  PointerSensor,
  type DragEndEvent,
  type DragStartEvent,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {SortableContext, rectSortingStrategy, useSortable} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';

type ScheduleItem = Schedule;

type CalendarItem = {
  id: string;
  scheduleId: number;
  postId: number;
  title: string;
  time: string;
  platform: string;
  status: string;
  excerpt: string;
};

type ItemsByDate = Record<string, CalendarItem[]>;

function CalendarCard({item}: {item: CalendarItem}){
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    in_progress: 'bg-blue-100 text-blue-800',
    published: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  return (
    <Card className="mb-3 shadow-sm cursor-move hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-center justify-between gap-2 p-3">
        <CardTitle className="text-sm font-medium text-blue-600">
          <Link
            href={`/posts/${item.postId}`}
            className="hover:underline focus-visible:underline focus-visible:outline-none"
            onPointerDown={(event) => event.stopPropagation()}
            onClick={(event) => event.stopPropagation()}
          >
            {item.title}
          </Link>
        </CardTitle>
        <div className="text-xs text-slate-500">{item.time}</div>
      </CardHeader>
      <CardContent className="p-3 pt-0">
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="text-xs">{item.platform}</Badge>
          <Badge className={statusColors[item.status] || 'bg-gray-100 text-gray-800'}>{item.status}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Droppable container ---
function DroppableContainer({
  id,
  className,
  children,
}: {
  id: string;
  className?: string;
  children: React.ReactNode;
}) {
  const {setNodeRef, isOver} = useDroppable({id});

  return (
    <div
      ref={setNodeRef}
      id={id}
      className={cn(className, isOver && 'ring-2 ring-blue-400 ring-offset-1')}
    >
      {children}
    </div>
  );
}

// --- Sortable Card ---
function SortableCard({item}: {item: CalendarItem}){
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({id: item.id});
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    touchAction: 'manipulation' as const,
    zIndex: isDragging ? 50 : undefined,
    opacity: isDragging ? 0.2 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <CalendarCard item={item} />
    </div>
  );
}

// --- Helpers ---
function startOfWeek(d: Date){
  const x = new Date(d);
  const day = x.getDay();
  const diff = (day + 6) % 7;
  x.setDate(x.getDate() - diff);
  x.setHours(0,0,0,0);
  return x;
}

function formatKey(d: Date){
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseDateKey(value: string){
  const [yearRaw, monthRaw, dayRaw] = value.split('-');
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  if (!year || !month || !day) return null;
  return {year, month, day};
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

function generateWeekDates(refDate: Date){
  const start = startOfWeek(refDate);
  return Array.from({length:7}).map((_,i)=>{ const d=new Date(start); d.setDate(start.getDate()+i); return d; });
}

function generateMonthDates(refDate: Date){
  const d = new Date(refDate.getFullYear(), refDate.getMonth(), 1);
  const firstDay = d.getDay();
  const start = new Date(d);
  start.setDate(1 - ((firstDay + 6) % 7));
  const cells = 42; // 6 weeks x 7
  return Array.from({length:cells}).map((_,i)=>{ const c = new Date(start); c.setDate(start.getDate()+i); return c; });
}

function scheduleToCalendarItem(schedule: ScheduleItem, timeZone: string): CalendarItem {
  const time = formatInTenantTimezone(schedule.scheduled_at, timeZone, {
    hour: '2-digit',
    minute: '2-digit',
  });

  return {
    id: `schedule-${schedule.id}`,
    scheduleId: schedule.id,
    postId: schedule.post,
    title: schedule.post_title,
    time,
    platform: schedule.platform,
    status: schedule.status,
    excerpt: `${schedule.platform} • ${schedule.status}`
  };
}

type WeekViewProps = {
  weekDates: Date[];
  itemsByDate: ItemsByDate;
  timeZone: string;
};

function WeekViewContent({weekDates, itemsByDate, timeZone}: WeekViewProps){
  const todayKey = formatKey(toTenantDate(new Date(), timeZone));

  return (
    <div className="min-w-[1000px] grid grid-cols-7 gap-4">
      {weekDates.map(d=>{
        const k = formatKey(d);
        const items = itemsByDate[k] || [];
        const isToday = todayKey === k;
        const containerClass = cn(
          'rounded-lg p-2 min-h-[160px]',
          isToday ? 'bg-blue-50' : 'bg-slate-50'
        );

        return (
          <DroppableContainer key={k} id={k} className={containerClass}>
            <div className="flex items-center justify-between mb-2">
              <div className={`text-sm font-medium ${isToday ? 'text-blue-600' : ''}`}>
                {formatTenantLocalDate(d, timeZone, {weekday:'short', day:'numeric'})}
              </div>
              <div className="text-xs text-slate-500">{items.length}</div>
            </div>

            <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
              {items.map(item=> <SortableCard key={item.id} item={item} />)}
            </SortableContext>
          </DroppableContainer>
        );
      })}
    </div>
  );
}

type MonthViewProps = {
  monthDates: Date[];
  itemsByDate: ItemsByDate;
  cursor: Date;
  timeZone: string;
};

function MonthViewContent({monthDates, itemsByDate, cursor, timeZone}: MonthViewProps){
  const todayKey = formatKey(toTenantDate(new Date(), timeZone));

  return (
    <div className="min-w-[1000px]">
      <div className="grid grid-cols-7 gap-2">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(day => (
          <div key={day} className="text-center text-xs font-medium text-slate-500 pb-2">
            {day}
          </div>
        ))}

        {monthDates.map(d=>{
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
            <DroppableContainer
              key={k}
              id={k}
              className={containerClass}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`text-xs font-medium ${isToday ? 'text-blue-600' : ''}`}>
                  {formatTenantLocalDate(d, timeZone, {day:'numeric'})}
                </div>
                {items.length > 0 && (
                  <div className="text-xs text-slate-500">{items.length}</div>
                )}
              </div>

              <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
                {items.slice(0,2).map(item=> <SortableCard key={item.id} item={item} />)}
                {items.length > 2 && (
                  <div className="text-xs text-slate-500 mt-1 text-center">
                    +{items.length - 2} еще
                  </div>
                )}
              </SortableContext>
            </DroppableContainer>
          );
        })}
      </div>
    </div>
  );
}

type DayViewProps = {
  cursor: Date;
  itemsByDate: ItemsByDate;
  timeZone: string;
};

function DayViewContent({cursor, itemsByDate, timeZone}: DayViewProps){
  const k = formatKey(cursor);
  const items = itemsByDate[k] || [];

  return (
    <div className="min-w-[600px]">
      <DroppableContainer id={k} className="rounded-lg p-4 bg-white border min-h-[300px]">
        <div className="flex items-center justify-between mb-4">
          <div className="text-lg font-semibold">
            {formatTenantLocalDate(cursor, timeZone, {weekday:'long', day:'numeric', month:'long'})}
          </div>
          <div className="text-sm text-slate-500">{items.length} публикаций</div>
        </div>

        <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
          {items.length > 0 ? (
            items.map(item=> <SortableCard key={item.id} item={item} />)
          ) : (
            <div className="text-center text-slate-400 py-8">
              Публикаций на этот день нет
            </div>
          )}
        </SortableContext>
      </DroppableContainer>
    </div>
  );
}

export default function ContentCalendarPage(){
  const router = useRouter();
  const {timezone: tenantTimezone, loading: tenantTimezoneLoading} = useTenantTimezone();
  const normalizedTimezone = useMemo(() => normalizeTenantTimezone(tenantTimezone), [tenantTimezone]);
  const [view, setView] = useState<'week' | 'month' | 'day'>('week');
  const cursorInitializedRef = useRef(false);
  const [cursor, setCursor] = useState<Date>(() => toTenantDate(new Date(), DEFAULT_TENANT_TIMEZONE));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const weekDates = useMemo(()=> generateWeekDates(cursor), [cursor]);
  const monthDates = useMemo(()=> generateMonthDates(cursor), [cursor]);

  useEffect(() => {
    if (tenantTimezoneLoading) return;
    if (!cursorInitializedRef.current) {
      setCursor(toTenantDate(new Date(), normalizedTimezone));
      cursorInitializedRef.current = true;
    }
  }, [normalizedTimezone, tenantTimezoneLoading]);

  // Load schedules from API
  useEffect(() => {
    const loadSchedules = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await schedulesApi.list();
        setSchedules(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить расписание');
        }
      } finally {
        setLoading(false);
      }
    };

    loadSchedules();
  }, [router]);

  // Group schedules by date
  const itemsByDate = useMemo<ItemsByDate>(() => {
    const map: ItemsByDate = {};

    // Initialize empty arrays for all visible dates
    const visibleDates = view === 'month' ? monthDates : view === 'week' ? weekDates : [cursor];
    visibleDates.forEach(d => {
      map[formatKey(d)] = [];
    });

    // Distribute schedules into dates
    schedules.forEach(schedule => {
      const date = toTenantDate(schedule.scheduled_at, normalizedTimezone);
      const key = formatKey(date);
      if (!map[key]) map[key] = [];
      map[key].push(scheduleToCalendarItem(schedule, normalizedTimezone));
    });

    return map;
  }, [schedules, view, cursor, weekDates, monthDates, normalizedTimezone]);

  const activeItem = useMemo(() => {
    if (!activeId) return null;
    for (const key of Object.keys(itemsByDate)) {
      const match = itemsByDate[key].find((item) => item.id === activeId);
      if (match) return match;
    }
    return null;
  }, [activeId, itemsByDate]);
  const sensors = useSensors(useSensor(PointerSensor));

  function prev(){
    const c = new Date(cursor);
    if(view==='month') c.setMonth(c.getMonth()-1);
    else if(view==='week') c.setDate(c.getDate()-7);
    else c.setDate(c.getDate()-1);
    setCursor(c);
  }

  function next(){
    const c = new Date(cursor);
    if(view==='month') c.setMonth(c.getMonth()+1);
    else if(view==='week') c.setDate(c.getDate()+7);
    else c.setDate(c.getDate()+1);
    setCursor(c);
  }

  function findContainer(id: string){
    for(const key of Object.keys(itemsByDate)){
      if(itemsByDate[key].some(it=>it.id===id)) return key;
    }
    return null;
  }

  async function updateScheduleDate(scheduleId: number, newDate: string) {
    try {
      await schedulesApi.update(scheduleId, { scheduled_at: newDate });
      const data = await schedulesApi.list();
      setSchedules(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push('/login');
      } else {
        console.error('Failed to update schedule:', err);
        setError('Не удалось обновить расписание');
      }
    }
  }

  function onDragStart(event: DragStartEvent){
    setActiveId(event.active.id as string);
  }

  function onDragCancel(){
    setActiveId(null);
  }

  function onDragEnd(event: DragEndEvent){
    setActiveId(null);
    const {active, over} = event;
    if(!over) return;
    const activeItemId = active.id as string;
    const overId = over.id as string;

    const fromKey = findContainer(activeItemId);
    const toKey = itemsByDate[overId] ? overId : findContainer(overId);
    if(!fromKey || !toKey) return;

    if(fromKey === toKey) return; // Same day, no need to update

    // Find the item being moved
    const item = itemsByDate[fromKey].find(i => i.id === activeItemId);
    if (!item) return;

    // Update the schedule with new date
    const dateParts = parseDateKey(toKey);
    if (!dateParts) return;

    const originalTime = item.time || '12:00';
    const [hoursRaw, minutesRaw] = originalTime.split(':');
    const hours = Number(hoursRaw);
    const minutes = Number(minutesRaw);
    const safeHours = Number.isFinite(hours) ? hours : 12;
    const safeMinutes = Number.isFinite(minutes) ? minutes : 0;
    const newDate = new Date(dateParts.year, dateParts.month - 1, dateParts.day, safeHours, safeMinutes, 0, 0);

    const newDateIso = tenantDateToUtcISOString(newDate, normalizedTimezone);
    if (!newDateIso) return;

    // Optimistically update UI so the post moves instantly
    setSchedules(prev =>
      prev.map(schedule =>
        schedule.id === item.scheduleId ? {...schedule, scheduled_at: newDateIso} : schedule
      )
    );

    updateScheduleDate(item.scheduleId, newDateIso);
  }

  if (loading) {
    return (
      <div className="p-6 max-w-full">
        <div className="flex items-center justify-center py-12">
          <div className="text-slate-500">Загрузка календаря...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-full">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Контент-календарь</h1>
          {error && <div className="text-sm text-red-500 mt-1">{error}</div>}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Button
              variant={view==='month' ? 'default' : 'ghost'}
              onClick={()=>setView('month')}
              size="sm"
            >
              Месяц
            </Button>
            <Button
              variant={view==='week' ? 'default' : 'ghost'}
              onClick={()=>setView('week')}
              size="sm"
            >
              Неделя
            </Button>
            <Button
              variant={view==='day' ? 'default' : 'ghost'}
              onClick={()=>setView('day')}
              size="sm"
            >
              День
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <Button onClick={prev} size="sm" variant="outline">&larr;</Button>
            <div className="px-3 py-1 text-sm font-medium min-w-[200px] text-center">
              {view==='month'
                ? formatTenantLocalDate(cursor, normalizedTimezone, {month:'long', year:'numeric'})
                : view==='week'
                ? `${formatTenantLocalDate(weekDates[0], normalizedTimezone, {day:'numeric', month:'short'})} — ${formatTenantLocalDate(weekDates[6], normalizedTimezone, {day:'numeric', month:'short'})}`
                : formatTenantLocalDate(cursor, normalizedTimezone, {day:'numeric', month:'long', year:'numeric'})
              }
            </div>
            <Button onClick={next} size="sm" variant="outline">&rarr;</Button>
          </div>
        </div>
      </header>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
        onDragStart={onDragStart}
        onDragCancel={onDragCancel}
      >
        <div className="overflow-x-auto">
          {view==='week' && (
            <WeekViewContent weekDates={weekDates} itemsByDate={itemsByDate} timeZone={normalizedTimezone} />
          )}
          {view==='month' && (
            <MonthViewContent
              monthDates={monthDates}
              itemsByDate={itemsByDate}
              cursor={cursor}
              timeZone={normalizedTimezone}
            />
          )}
          {view==='day' && (
            <DayViewContent cursor={cursor} itemsByDate={itemsByDate} timeZone={normalizedTimezone} />
          )}
        </div>
        <DragOverlay>
          {activeItem ? <CalendarCard item={activeItem} /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
