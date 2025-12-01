import React, {useState, useMemo, useEffect} from 'react';
import {Card, CardContent, CardHeader, CardTitle} from '@/components/ui/card';
import {Button} from '@/components/ui/button';
import {Popover, PopoverContent, PopoverTrigger} from '@/components/ui/popover';
import {Input} from '@/components/ui/input';
import {Dialog, DialogContent, DialogTrigger, DialogHeader, DialogTitle, DialogFooter} from '@/components/ui/dialog';

// dnd-kit
import {DndContext, closestCenter, type DragEndEvent} from '@dnd-kit/core';
import {arrayMove, SortableContext, rectSortingStrategy, useSortable} from '@dnd-kit/sortable';
import {CSS} from '@dnd-kit/utilities';

type CalendarItem = {
  id: string;
  title: string;
  time: string;
  excerpt: string;
};

type ItemsByDate = Record<string, CalendarItem[]>;

// --- Sortable Card ---
function SortableCard({item}: {item: CalendarItem}){
  const {attributes, listeners, setNodeRef, transform, transition} = useSortable({id: item.id});
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    touchAction: 'manipulation'
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <Card className="mb-3 shadow-sm">
        <CardHeader className="flex items-center justify-between gap-2 p-3">
          <CardTitle className="text-sm">{item.title}</CardTitle>
          <div className="text-xs text-slate-500">{item.time}</div>
        </CardHeader>
        <CardContent className="p-3 text-sm text-slate-700">{item.excerpt}</CardContent>
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
  // start from monday of the week containing 1st
  const start = new Date(d);
  start.setDate(1 - ((firstDay + 6) % 7));
  const cells = 42; // 6 weeks x 7
  return Array.from({length:cells}).map((_,i)=>{ const c = new Date(start); c.setDate(start.getDate()+i); return c; });
}

export default function ContentCalendarPage(){
  const [view, setView] = useState<'week' | 'month' | 'day'>('week');
  const [cursor, setCursor] = useState<Date>(new Date()); // focused date

  const weekDates = useMemo(()=> generateWeekDates(cursor), [cursor]);
  const monthDates = useMemo(()=> generateMonthDates(cursor), [cursor]);
  const dayKey = useMemo(()=> formatKey(cursor), [cursor]);

  // build initial demo columns keyed by ISO date
  const initialMap = useMemo<ItemsByDate>(()=>{ 
    const map: ItemsByDate = {};
    // fill for month view (42 cells) and week view
    const allDates = [...monthDates.slice(0,42)];
    allDates.forEach((d,i)=>{
      const k = formatKey(d);
      map[k] = Array.from({length: (i%3)}).map((_,j)=>({
        id: `${k}-card-${j}`,
        title: `Post ${k.slice(8)}.${j+1}`,
        time: `${9 + (j%3)}:00`,
        excerpt: 'Короткое описание поста — цель, канал, статус.'
      }));
    });
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [itemsByDate, setItemsByDate] = useState<ItemsByDate>(initialMap);

  useEffect(()=>{
    // ensure keys exist for currently visible dates
    const ensure = {...itemsByDate};
    const keys = view==='month' ? monthDates.map(d=>formatKey(d)) : view==='week' ? weekDates.map(d=>formatKey(d)) : [formatKey(cursor)];
    keys.forEach(k=>{ if(!ensure[k]) ensure[k]=[]; });
    setItemsByDate(ensure);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, cursor]);

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

  function onDragEnd(event: DragEndEvent){
    const {active, over} = event;
    if(!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    const fromKey = findContainer(activeId);
    // over can be a card id or a date key (we will set date nodes id to the date key)
    const toKey = itemsByDate[overId] ? overId : findContainer(overId);
    if(!fromKey || !toKey) return;

    if(fromKey === toKey){
      // reorder within same day
      const list = [...itemsByDate[fromKey]];
      const oldIndex = list.findIndex(i=>i.id===activeId);
      const newIndex = list.findIndex(i=>i.id===overId);
      if(oldIndex<0 || newIndex<0 || oldIndex===newIndex) return;
      list.splice(newIndex,0,list.splice(oldIndex,1)[0]);
      setItemsByDate({...itemsByDate, [fromKey]: list});
      return;
    }

    // move between days
    const fromList = [...itemsByDate[fromKey]];
    const item = fromList.splice(fromList.findIndex(i=>i.id===activeId),1)[0];
    const toList = [...(itemsByDate[toKey]||[])];
    toList.push(item);
    setItemsByDate({...itemsByDate, [fromKey]: fromList, [toKey]: toList});
  }

  // Renderers for views
  function WeekView(){
    const keys = weekDates.map(d=>formatKey(d));
    return (
      <div className="min-w-[1000px] grid grid-cols-7 gap-4">
        <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          {weekDates.map(d=>{
            const k = formatKey(d);
            const items = itemsByDate[k] || [];
            return (
              <div key={k} className="bg-slate-50 rounded-lg p-2" id={k}>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-medium">{d.toLocaleDateString(undefined,{weekday:'short', month:'short', day:'numeric'})}</div>
                  <div className="text-xs text-slate-500">{items.length} items</div>
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
            {monthDates.map(d=>{
              const k = formatKey(d);
              const items = itemsByDate[k] || [];
              const isCurrentMonth = d.getMonth() === cursor.getMonth();
              return (
                <div key={k} id={k} className={`border rounded p-2 min-h-[120px] ${isCurrentMonth? 'bg-white': 'bg-slate-50 text-slate-400'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs font-medium">{d.getDate()}</div>
                    <div className="text-xs text-slate-500">{items.length}</div>
                  </div>

                  <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
                    {items.slice(0,3).map(item=> <SortableCard key={item.id} item={item} />)}
                    {items.length>3 && <div className="text-xs text-slate-500 mt-2">+{items.length-3} more</div>}
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
          <div className="rounded-lg p-2 bg-white">
            <div className="flex items-center justify-between mb-4">
              <div className="text-lg font-semibold">{cursor.toLocaleDateString(undefined,{weekday:'long', month:'long', day:'numeric'})}</div>
              <div className="text-sm text-slate-500">{items.length} items</div>
            </div>

            <SortableContext items={items.map(i=>i.id)} strategy={rectSortingStrategy}>
              {items.map(item=> <SortableCard key={item.id} item={item} />)}
            </SortableContext>

          </div>
        </DndContext>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-full">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">Контент-календарь</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Button variant={view==='month' ? 'default' : 'ghost'} onClick={()=>setView('month')}>Month</Button>
            <Button variant={view==='week' ? 'default' : 'ghost'} onClick={()=>setView('week')}>Week</Button>
            <Button variant={view==='day' ? 'default' : 'ghost'} onClick={()=>setView('day')}>Day</Button>
          </div>

          <div className="flex items-center gap-2">
            <Button onClick={prev}>&larr;</Button>
            <div className="px-3 py-2 text-sm">{view==='month' ? cursor.toLocaleString(undefined,{month:'long', year:'numeric'}) : view==='week' ? `${weekDates[0].toLocaleDateString()} — ${weekDates[6].toLocaleDateString()}` : cursor.toLocaleDateString()}</div>
            <Button onClick={next}>&rarr;</Button>
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
