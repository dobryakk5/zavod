'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ApiError } from '@/lib/api';
import { weeklySalesApi, type WeeklySalesPlan } from '@/lib/api/weeklySales';
import { Trash2 } from 'lucide-react';

type SalesWeekRow = {
  rowId: string;
  id?: number;
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
const timeFormatter = new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' });

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

const toInputValue = (value?: number | null) => (typeof value === 'number' ? String(value) : '');

const mapApiToRow = (item: WeeklySalesPlan): SalesWeekRow => ({
  rowId: `srv-${item.id}`,
  id: item.id,
  weekStart: item.week_start,
  coldLeadsPlan: toInputValue(item.cold_leads_plan),
  coldLeadsFact: toInputValue(item.cold_leads_fact),
  hotLeadsPlan: toInputValue(item.hot_leads_plan),
  hotLeadsFact: toInputValue(item.hot_leads_fact),
  salesPlan: toInputValue(item.sales_plan),
  salesFact: toInputValue(item.sales_fact)
});

const parseMetricValue = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseInt(trimmed, 10);
  if (Number.isNaN(parsed) || parsed < 0) return null;
  return parsed;
};

const buildPayload = (row: SalesWeekRow) => ({
  week_start: row.weekStart,
  cold_leads_plan: parseMetricValue(row.coldLeadsPlan),
  cold_leads_fact: parseMetricValue(row.coldLeadsFact),
  hot_leads_plan: parseMetricValue(row.hotLeadsPlan),
  hot_leads_fact: parseMetricValue(row.hotLeadsFact),
  sales_plan: parseMetricValue(row.salesPlan),
  sales_fact: parseMetricValue(row.salesFact)
});

const createRow = (weekStart: string): SalesWeekRow => ({
  rowId: crypto.randomUUID(),
  weekStart,
  coldLeadsPlan: '',
  coldLeadsFact: '',
  hotLeadsPlan: '',
  hotLeadsFact: '',
  salesPlan: '',
  salesFact: ''
});

const validateRows = (rows: SalesWeekRow[]) => {
  const seen = new Set<string>();
  for (const row of rows) {
    if (!row.weekStart) {
      return 'Укажите дату начала недели во всех строках.';
    }
    if (seen.has(row.weekStart)) {
      return 'Обнаружены одинаковые недели. Оставьте только одну строку на неделю.';
    }
    seen.add(row.weekStart);
  }
  return null;
};

export function SalesTab() {
  const [rows, setRows] = useState<SalesWeekRow[]>([]);
  const [deletedIds, setDeletedIds] = useState<number[]>([]);
  const [newWeekStart, setNewWeekStart] = useState(getCurrentWeekStart);
  const [addError, setAddError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const groups = useMemo(() => groupByMonth(rows), [rows]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const data = await weeklySalesApi.list();
        setRows(sortRows(data.map(mapApiToRow)));
        setDeletedIds([]);
        setDirty(false);
      } catch (err) {
        console.error('Failed to load weekly sales', err);
        setLoadError('Не удалось загрузить данные. Проверьте API /weekly-sales/.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

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
    setDirty(true);
    setNewWeekStart(getNextWeekStart(newWeekStart));
    setAddError(null);
    setSaveError(null);
  };

  const updateRow = (rowId: string, patch: Partial<SalesWeekRow>) => {
    setRows((prev) => sortRows(prev.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row))));
    setDirty(true);
    setSaveError(null);
  };

  const removeRow = (rowId: string) => {
    setRows((prev) => {
      const target = prev.find((row) => row.rowId === rowId);
      if (typeof target?.id === 'number') {
        const id = target.id;
        setDeletedIds((current) => (current.includes(id) ? current : [...current, id]));
      }
      return prev.filter((row) => row.rowId !== rowId);
    });
    setDirty(true);
    setSaveError(null);
  };

  const handleSave = async () => {
    if (saving) return;
    const validationError = validateRows(rows);
    if (validationError) {
      setSaveError(validationError);
      return;
    }

    setSaving(true);
    setSaveError(null);

    try {
      for (const id of deletedIds) {
        await weeklySalesApi.delete(id);
      }

      const nextRows = [...rows];
      for (let index = 0; index < nextRows.length; index += 1) {
        const row = nextRows[index];
        const payload = buildPayload(row);
        if (row.id) {
          const updated = await weeklySalesApi.update(row.id, payload);
          nextRows[index] = { ...row, ...mapApiToRow(updated), rowId: row.rowId };
        } else {
          const created = await weeklySalesApi.create(payload);
          nextRows[index] = { ...row, ...mapApiToRow(created), rowId: row.rowId };
        }
      }

      setRows(sortRows(nextRows));
      setDeletedIds([]);
      setDirty(false);
      setSavedAt(timeFormatter.format(new Date()));
    } catch (err) {
      console.error('Failed to save weekly sales', err);
      if (err instanceof ApiError) {
        setSaveError('Не удалось сохранить данные. Проверьте поля и повторите.');
      } else {
        setSaveError('Не удалось сохранить данные. Проверьте подключение и повторите.');
      }
    } finally {
      setSaving(false);
    }
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
        <div className="flex flex-wrap items-end justify-between gap-3">
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
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={handleAddWeek} disabled={!newWeekStart || saving}>
              Добавить неделю
            </Button>
            <Button variant="secondary" onClick={() => void handleSave()} disabled={!dirty || saving}>
              {saving ? 'Сохранение…' : 'Сохранить'}
            </Button>
          </div>
        </div>
        {addError ? <div className="text-xs text-destructive">{addError}</div> : null}
        {loadError ? <div className="text-xs text-destructive">{loadError}</div> : null}
        {saveError ? <div className="text-xs text-destructive">{saveError}</div> : null}
        {savedAt && !dirty ? (
          <div className="text-xs text-muted-foreground">Сохранено в {savedAt}</div>
        ) : null}
        <div className="text-xs text-muted-foreground">
          Выберите понедельник — неделя автоматически считается до воскресенья.
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border bg-card/70 px-4 py-6 text-sm text-muted-foreground shadow-sm">
          Загружаем данные...
        </div>
      ) : groups.length === 0 ? (
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
                  <TableRow key={row.rowId}>
                    <TableCell className="align-top">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Input
                            type="date"
                            value={row.weekStart}
                            onChange={(event) => updateRow(row.rowId, { weekStart: event.target.value })}
                            className="h-9 w-[160px]"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => removeRow(row.rowId)}
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
                        onChange={(event) => updateRow(row.rowId, { coldLeadsPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.coldLeadsFact}
                        onChange={(event) => updateRow(row.rowId, { coldLeadsFact: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.hotLeadsPlan}
                        onChange={(event) => updateRow(row.rowId, { hotLeadsPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.hotLeadsFact}
                        onChange={(event) => updateRow(row.rowId, { hotLeadsFact: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.salesPlan}
                        onChange={(event) => updateRow(row.rowId, { salesPlan: event.target.value })}
                        className="h-9 min-w-[96px] text-right tabular-nums"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min={0}
                        inputMode="numeric"
                        value={row.salesFact}
                        onChange={(event) => updateRow(row.rowId, { salesFact: event.target.value })}
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
