'use client';

import React, {useState, useMemo, useEffect} from 'react';
import {Card, CardContent, CardHeader, CardTitle} from '@/components/ui/card';
import {Button} from '@/components/ui/button';
import {Badge} from '@/components/ui/badge';
import {ApiError, apiFetch} from '@/lib/api';
import {useRouter} from 'next/navigation';

// dnd-kit
import {DndContext, closestCenter, type DragEndEvent} from '@dnd-kit/core';
import {SortableContext, rectSortingStrategy, useSortable} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';

type ScheduleItem = {
  id: number;
  platform: string;
  post_title: string;
  planned_at: string;
  status: string;
  post: number;
};

type CalendarItem = {
  id: string;
  scheduleId: number;
  title: string;
  time: string;
  platform: string;
  status: string;
  excerpt: string;
};

type ItemsByDate = Record<string, CalendarItem[]>;

// --- Sortable Card ---
function SortableCard({item}: {item: CalendarItem}){
  const {attributes, listeners, setNodeRef, transform, transition} = useSortable({id: item.id});
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    touchAction: 'manipulation' as const
  };

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    in_progress: 'bg-blue-100 text-blue-800',
    published: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Card className="mb-3 shadow-sm cursor-move hover:shadow-md transition-shadow">
        <CardHeader className="flex flex-row items-center justify-between gap-2 p-3">
          <CardTitle className="text-sm font-medium">{item.title}</CardTitle>
          <div className="text-xs text-slate-500">{item.time}</div>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          <div className="flex items-center gap-2 text-xs">
            <Badge variant="outline" className="text-xs">{item.platform}</Badge>
            <Badge className={statusColors[item.status] || 'bg-gray-100 text-gray-800'}>{item.status}</Badge>
          </div>
        </CardContent>
      </Card>
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

function formatKey(d: Date){ return d.toISOString().slice(0,10); }

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

function scheduleToCalendarItem(schedule: ScheduleItem): CalendarItem {
  const date = new Date(schedule.planned_at);
  const time = date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});

  return {
    id: `schedule-${schedule.id}`,
    scheduleId: schedule.id,
    title: schedule.post_title,
    time,
    platform: schedule.platform,
    status: schedule.status,
    excerpt: `${schedule.platform} • ${schedule.status}`
  };
}

export default function ContentCalendarPage(){
  const router = useRouter();
  const [view, setView] = useState<'week' | 'month' | 'day'>('week');
  const [cursor, setCursor] = useState<Date>(new Date());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);

  const weekDates = useMemo(()=> generateWeekDates(cursor), [cursor]);
  const monthDates = useMemo(()=> generateMonthDates(cursor), [cursor]);

  // Load schedules from API
  useEffect(() => {
    const loadSchedules = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<ScheduleItem[]>('/schedules/');
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
      const date = new Date(schedule.planned_at);
      const key = formatKey(date);
      if (!map[key]) map[key] = [];
      map[key].push(scheduleToCalendarItem(schedule));
    });

    return map;
  }, [schedules, view, cursor, weekDates, monthDates]);

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
      await apiFetch(`/schedules-manage/${scheduleId}/`, {
        method: 'PATCH',
        body: { planned_at: newDate }
      });

      // Reload schedules after update
      const data = await apiFetch<ScheduleItem[]>('/schedules/');
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

  function onDragEnd(event: DragEndEvent){
    const {active, over} = event;
    if(!over) return;
    const activeId = active.id as string;
    const overId = over.id as string;

    const fromKey = findContainer(activeId);
    const toKey = itemsByDate[overId] ? overId : findContainer(overId);
    if(!fromKey || !toKey) return;

    if(fromKey === toKey) return; // Same day, no need to update

    // Find the item being moved
    const item = itemsByDate[fromKey].find(i => i.id === activeId);
    if (!item) return;

    // Update the schedule with new date
    const newDate = new Date(toKey);
    const originalTime = itemsByDate[fromKey].find(i => i.id === activeId)?.time || '12:00';
    const [hours, minutes] = originalTime.split(':');
    newDate.setHours(parseInt(hours), parseInt(minutes));

    updateScheduleDate(item.scheduleId, newDate.toISOString());
  }

  // Renderers for views
  function WeekView(){
    return (
      <div className="min-w-[1000px] grid grid-cols-7 gap-4">
        <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          {weekDates.map(d=>{
            const k = formatKey(d);
            const items = itemsByDate[k] || [];
            const isToday = formatKey(new Date()) === k;

            return (
              <div key={k} className={`rounded-lg p-2 ${isToday ? 'bg-blue-50' : 'bg-slate-50'}`} id={k}>
                <div className="flex items-center justify-between mb-2">
                  <div className={`text-sm font-medium ${isToday ? 'text-blue-600' : ''}`}>
                    {d.toLocaleDateString('ru-RU',{weekday:'short', day:'numeric'})}
                  </div>
                  <div className="text-xs text-slate-500">{items.length}</div>
                </div>

                <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
                  {items.map(item=> <SortableCard key={item.id} item={item} />)}
                </SortableContext>
              </div>
            );
          })}
        </DndContext>
      </div>
    );
  }

  function MonthView(){
    return (
      <div className="min-w-[1000px]">
        <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <div className="grid grid-cols-7 gap-2">
            {/* Header with day names */}
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(day => (
              <div key={day} className="text-center text-xs font-medium text-slate-500 pb-2">
                {day}
              </div>
            ))}

            {monthDates.map(d=>{
              const k = formatKey(d);
              const items = itemsByDate[k] || [];
              const isCurrentMonth = d.getMonth() === cursor.getMonth();
              const isToday = formatKey(new Date()) === k;

              return (
                <div
                  key={k}
                  id={k}
                  className={`border rounded p-2 min-h-[120px] ${
                    isToday ? 'bg-blue-50 border-blue-300' :
                    isCurrentMonth ? 'bg-white' : 'bg-slate-50 text-slate-400'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className={`text-xs font-medium ${isToday ? 'text-blue-600' : ''}`}>
                      {d.getDate()}
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
                </div>
              );
            })}
          </div>
        </DndContext>
      </div>
    );
  }

  function DayView(){
    const k = formatKey(cursor);
    const items = itemsByDate[k] || [];
    return (
      <div className="min-w-[600px]">
        <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <div className="rounded-lg p-4 bg-white border">
            <div className="flex items-center justify-between mb-4">
              <div className="text-lg font-semibold">
                {cursor.toLocaleDateString('ru-RU',{weekday:'long', day:'numeric', month:'long'})}
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
          </div>
        </DndContext>
      </div>
    );
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
                ? cursor.toLocaleString('ru-RU',{month:'long', year:'numeric'})
                : view==='week'
                ? `${weekDates[0].toLocaleDateString('ru-RU', {day:'numeric', month:'short'})} — ${weekDates[6].toLocaleDateString('ru-RU', {day:'numeric', month:'short'})}`
                : cursor.toLocaleDateString('ru-RU', {day:'numeric', month:'long', year:'numeric'})
              }
            </div>
            <Button onClick={next} size="sm" variant="outline">&rarr;</Button>
          </div>
        </div>
      </header>

      <div className="overflow-x-auto">
        {view==='week' && <WeekView />}
        {view==='month' && <MonthView />}
        {view==='day' && <DayView />}
      </div>
    </div>
  );
}
