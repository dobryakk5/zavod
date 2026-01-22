'use client';

import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Trash2 } from 'lucide-react';

type SalesWeekRow = {
  id: string;
  weekStart: string;
  coldLeadsPlan: string;
  coldLeadsFact: string;
  hotLeadsPlan: string;
  hotLeadsFact: string;
  salesPlan: string;
  salesFact: string;
};

type SalesMonthGroup = {
  key: string;
  label: string;
  rows: SalesWeekRow[];
};

const monthFormatter = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' });
const weekFormatter = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' });

const padNumber = (value: number) => String(value).padStart(2, '0');

const toDateInputValue = (value: Date) =>
  `${value.getFullYear()}-${padNumber(value.getMonth() + 1)}-${padNumber(value.getDate())}`;

const parseDate = (value: string) => new Date(`${value}T00:00:00`);

const isValidDate = (value: Date) => !Number.isNaN(value.getTime());

const addDays = (value: Date, days: number) => {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
};

const formatWeekLabel = (start: string) => {
  if (!start) return '—';
  const startDate = parseDate(start);
  if (!isValidDate(startDate)) return '—';
  const endDate = addDays(startDate, 6);
  const startLabel = weekFormatter.format(startDate);
  const endLabel = weekFormatter.format(endDate);
  return `${startLabel} — ${endLabel}`;
};

const formatMonthLabel = (monthKey: string) => {
  const monthDate = parseDate(`${monthKey}-01`);
  if (!isValidDate(monthDate)) return 'Без даты';
  return monthFormatter.format(monthDate);
};

const sortRows = (rows: SalesWeekRow[]) =>
  [...rows].sort((a, b) => {
    if (!a.weekStart && !b.weekStart) return 0;
    if (!a.weekStart) return 1;
    if (!b.weekStart) return -1;
    return a.weekStart.localeCompare(b.weekStart);
  });

const groupByMonth = (rows: SalesWeekRow[]) => {
  const sorted = sortRows(rows);
  const grouped: SalesMonthGroup[] = [];

  for (const row of sorted) {
    const monthKey = row.weekStart && row.weekStart.length >= 7 ? row.weekStart.slice(0, 7) : 'unknown';
    const label = monthKey === 'unknown' ? 'Без даты' : formatMonthLabel(monthKey);
    const last = grouped[grouped.length - 1];
    if (!last || last.key !== monthKey) {
      grouped.push({
        key: monthKey,
        label,
        rows: [row]
      });
    } else {
      last.rows.push(row);
    }
  }

  return grouped;
};

const getCurrentWeekStart = () => {
  const today = new Date();
  const dayIndex = (today.getDay() + 6) % 7;
  const monday = new Date(today);
  monday.setDate(today.getDate() - dayIndex);
  monday.setHours(0, 0, 0, 0);
  return toDateInputValue(monday);
};

const getNextWeekStart = (value: string) => {
  if (!value) return value;
  const base = parseDate(value);
  if (!isValidDate(base)) return value;
  return toDateInputValue(addDays(base, 7));
};

const createRow = (weekStart: string): SalesWeekRow => ({
  id: crypto.randomUUID(),
  weekStart,
  coldLeadsPlan: '',
  coldLeadsFact: '',
  hotLeadsPlan: '',
  hotLeadsFact: '',
  salesPlan: '',
  salesFact: ''
});

export function SalesTab() {
  const [rows, setRows] = useState<SalesWeekRow[]>([]);
  const [newWeekStart, setNewWeekStart] = useState(getCurrentWeekStart);
  const [addError, setAddError] = useState<string | null>(null);
  const groups = useMemo(() => groupByMonth(rows), [rows]);

  const handleAddWeek = () => {
    if (!newWeekStart) {
      setAddError('Укажите дату начала недели.');
      return;
    }

    if (rows.some((row) => row.weekStart === newWeekStart)) {
      setAddError('Эта неделя уже добавлена.');
      return;
    }

    setRows((prev) => sortRows([...prev, createRow(newWeekStart)]));
    setNewWeekStart(getNextWeekStart(newWeekStart));
    setAddError(null);
  };

  const updateRow = (rowId: string, patch: Partial<SalesWeekRow>) => {
    setRows((prev) => sortRows(prev.map((row) => (row.id === rowId ? { ...row, ...patch } : row))));
  };

  const removeRow = (rowId: string) => {
    setRows((prev) => prev.filter((row) => row.id !== rowId));
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <div className="text-sm font-medium">План/факт по неделям</div>
        <div className="text-xs text-muted-foreground">
          Холодные лиды, горячие лиды и продажи по неделям, сгруппированные по месяцам.
        </div>
      </div>

      <div className="space-y-3 rounded-xl border bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Дата начала недели</div>
            <Input
              type="date"
              value={newWeekStart}
              onChange={(event) => {
                setNewWeekStart(event.target.value);
                setAddError(null);
              }}
              className="h-9 w-[180px]"
            />
          </div>
          <Button onClick={handleAddWeek} disabled={!newWeekStart}>
            Добавить неделю
          </Button>
        </div>
        {addError ? <div className="text-xs text-destructive">{addError}</div> : null}
        <div className="text-xs text-muted-foreground">
          Выберите понедельник — неделя автоматически считается до воскресенья.
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-xl border bg-card/70 px-4 py-6 text-sm text-muted-foreground shadow-sm">
          Пока нет данных по неделям. Добавьте первую неделю для ввода план/факт.
        </div>
      ) : (
        groups.map((group) => (
          <div key={group.key} className="space-y-3 rounded-xl border bg-card/70 p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium capitalize">{group.label}</div>
              <div className="text-xs text-muted-foreground">Недели {group.rows.length}</div>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead rowSpan={2} className="w-[220px]">
                    Неделя
                  </TableHead>
                  <TableHead colSpan={2} className="text-center">
                    Лиды холодные
                  </TableHead>
                  <TableHead colSpan={2} className="text-center">
                    Лиды горячие
                  </TableHead>
                  <TableHead colSpan={2} className="text-center">
                    Продажи
                  </TableHead>
                </TableRow>
                <TableRow>
                  <TableHead className="text-right">План</TableHead>
                  <TableHead className="text-right">Факт</TableHead>
                  <TableHead className="text-right">План</TableHead>
                  <TableHead className="text-right">Факт</TableHead>
                  <TableHead className="text-right">План</TableHead>
                  <TableHead className="text-right">Факт</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="align-top">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Input
                            type="date"
                            value={row.weekStart}
                            onChange={(event) => updateRow(row.id, { weekStart: event.target.value })}
                            className="h-9 w-[160px]"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => removeRow(row.id)}
                            aria-label="Удалить неделю"
                            title="Удалить неделю"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <div className="text-xs text-muted-foreground">{formatWeekLabel(row.weekStart)}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.coldLeadsPlan}
                        onChange={(event) => updateRow(row.id, { coldLeadsPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.coldLeadsFact}
                        onChange={(event) => updateRow(row.id, { coldLeadsFact: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.hotLeadsPlan}
                        onChange={(event) => updateRow(row.id, { hotLeadsPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.hotLeadsFact}
                        onChange={(event) => updateRow(row.id, { hotLeadsFact: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.salesPlan}
                        onChange={(event) => updateRow(row.id, { salesPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.salesFact}
                        onChange={(event) => updateRow(row.id, { salesFact: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))
      )}
    </div>
  );
}
