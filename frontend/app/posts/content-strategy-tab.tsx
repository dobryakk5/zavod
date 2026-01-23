'use client';

import { useEffect, useMemo, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { contentStrategyApi, type WeeklyContentStrategy } from '@/lib/api/contentStrategy';
import { wordstatApi } from '@/lib/api/wordstat';
import { useRole } from '@/lib/hooks';
import type { WordstatCluster } from '@/lib/types';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';

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

type ContentStrategyRow = {
  rowId: string;
  id?: number;
  weekStart: string;
  comment: string;
  wordstatClusterIds: number[];
};

type ContentStrategyMonthGroup = {
  key: string;
  label: string;
  rows: ContentStrategyRow[];
};

const sortRows = (rows: ContentStrategyRow[]) =>
  [...rows].sort((a, b) => {
    if (!a.weekStart && !b.weekStart) return 0;
    if (!a.weekStart) return 1;
    if (!b.weekStart) return -1;
    return a.weekStart.localeCompare(b.weekStart);
  });

const groupByMonth = (rows: ContentStrategyRow[]) => {
  const sorted = sortRows(rows);
  const grouped: ContentStrategyMonthGroup[] = [];

  for (const row of sorted) {
    const monthKey = row.weekStart && row.weekStart.length >= 7 ? row.weekStart.slice(0, 7) : 'unknown';
    const label = monthKey === 'unknown' ? 'Без даты' : formatMonthLabel(monthKey);
    const last = grouped[grouped.length - 1];
    if (!last || last.key !== monthKey) {
      grouped.push({
        key: monthKey,
        label,
        rows: [row],
      });
    } else {
      last.rows.push(row);
    }
  }

  return grouped;
};

const mapApiToRow = (item: WeeklyContentStrategy): ContentStrategyRow => ({
  rowId: `srv-${item.id}`,
  id: item.id,
  weekStart: item.week_start,
  comment: item.comment ?? '',
  wordstatClusterIds: Array.isArray(item.wordstat_cluster_ids) ? item.wordstat_cluster_ids : [],
});

const buildPayload = (row: ContentStrategyRow) => ({
  week_start: row.weekStart,
  comment: row.comment?.trim() || '',
  wordstat_cluster_ids: row.wordstatClusterIds,
});

const createRow = (weekStart: string): ContentStrategyRow => ({
  rowId: crypto.randomUUID(),
  weekStart,
  comment: '',
  wordstatClusterIds: [],
});

const validateRows = (rows: ContentStrategyRow[]) => {
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

export function ContentStrategyTab() {
  const { canEdit } = useRole();
  const [rows, setRows] = useState<ContentStrategyRow[]>([]);
  const [deletedIds, setDeletedIds] = useState<number[]>([]);
  const [clusters, setClusters] = useState<WordstatCluster[]>([]);
  const [newWeekStart, setNewWeekStart] = useState(getCurrentWeekStart);
  const [addError, setAddError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const groups = useMemo(() => groupByMonth(rows), [rows]);

  const availableClusters = useMemo(
    () => clusters.filter((cluster) => !cluster.is_main),
    [clusters]
  );

  const clusterNameById = useMemo(() => {
    const map = new Map<number, string>();
    clusters.forEach((cluster) => {
      map.set(cluster.id, cluster.name);
    });
    return map;
  }, [clusters]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        const [strategyResult, clusterResult] = await Promise.allSettled([
          contentStrategyApi.list(),
          wordstatApi.listClusters(),
        ]);

        if (strategyResult.status === 'fulfilled') {
          setRows(sortRows(strategyResult.value.map(mapApiToRow)));
          setDeletedIds([]);
          setDirty(false);
        } else {
          setRows([]);
          setLoadError('Не удалось загрузить контент-стратегию. Проверьте API /content-strategy/.');
        }

        if (clusterResult.status === 'fulfilled') {
          setClusters(clusterResult.value);
        } else {
          setClusters([]);
        }
      } catch (err) {
        console.error('Failed to load content strategy', err);
        setLoadError('Не удалось загрузить контент-стратегию.');
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

  const updateRow = (rowId: string, patch: Partial<ContentStrategyRow>) => {
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
        await contentStrategyApi.delete(id);
      }

      const nextRows = [...rows];
      for (let index = 0; index < nextRows.length; index += 1) {
        const row = nextRows[index];
        const payload = buildPayload(row);
        if (row.id) {
          const updated = await contentStrategyApi.update(row.id, payload);
          nextRows[index] = { ...row, ...mapApiToRow(updated), rowId: row.rowId };
        } else {
          const created = await contentStrategyApi.create(payload);
          nextRows[index] = { ...row, ...mapApiToRow(created), rowId: row.rowId };
        }
      }

      setRows(sortRows(nextRows));
      setDeletedIds([]);
      setDirty(false);
      setSavedAt(timeFormatter.format(new Date()));
    } catch (err) {
      console.error('Failed to save content strategy', err);
      if (err instanceof ApiError) {
        setSaveError('Не удалось сохранить данные. Проверьте поля и повторите.');
      } else {
        setSaveError('Не удалось сохранить данные. Проверьте подключение и повторите.');
      }
    } finally {
      setSaving(false);
    }
  };

  const formatClusterSummary = (ids: number[]) => {
    if (!ids.length) return 'Выбрать';
    const names = ids.map((id) => clusterNameById.get(id) || `#${id}`);
    if (names.length <= 2) return names.join(', ');
    return `${names.slice(0, 2).join(', ')} +${names.length - 2}`;
  };

  const toggleCluster = (rowId: string, clusterId: number, checked: boolean) => {
    setRows((prev) =>
      sortRows(
        prev.map((row) => {
          if (row.rowId !== rowId) return row;
          const current = row.wordstatClusterIds;
          const next = checked
            ? Array.from(new Set([...current, clusterId]))
            : current.filter((id) => id !== clusterId);
          return { ...row, wordstatClusterIds: next };
        })
      )
    );
    setDirty(true);
    setSaveError(null);
  };

  const renderClusterDropdown = (row: ContentStrategyRow) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1 text-xs text-slate-600 transition hover:text-slate-900"
          disabled={!canEdit || saving}
          aria-label="Выбрать Wordstat кластеры"
        >
          <span className="truncate">{formatClusterSummary(row.wordstatClusterIds)}</span>
          <span className="text-[10px] text-slate-400">▾</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="border-slate-200 bg-white text-slate-900 dark:border-slate-200 dark:bg-white dark:text-slate-900"
      >
        {availableClusters.length === 0 ? (
          <DropdownMenuItem disabled className="text-slate-500">
            Нет доступных кластеров
          </DropdownMenuItem>
        ) : (
          availableClusters.map((cluster) => (
            <DropdownMenuCheckboxItem
              key={cluster.id}
              checked={row.wordstatClusterIds.includes(cluster.id)}
              onCheckedChange={(checked) => toggleCluster(row.rowId, cluster.id, Boolean(checked))}
            >
              {cluster.name}
            </DropdownMenuCheckboxItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <div className="text-sm font-medium">Контент-стратегия по неделям</div>
        <div className="text-xs text-muted-foreground">
          Комментарии и Wordstat-кластеры для каждой недели. Доступны только кластеры без отметки «Основной».
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
              disabled={!canEdit || saving}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={handleAddWeek} disabled={!canEdit || !newWeekStart || saving}>
              Добавить неделю
            </Button>
            <Button variant="secondary" onClick={() => void handleSave()} disabled={!canEdit || !dirty || saving}>
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
          Пока нет данных по неделям. Добавьте первую неделю для контент-стратегии.
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
                  <TableHead className="w-[200px]">Неделя</TableHead>
                  <TableHead>Комментарий</TableHead>
                  <TableHead className="w-[220px] text-right">Wordstat кластеры</TableHead>
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
                            disabled={!canEdit || saving}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => removeRow(row.rowId)}
                            aria-label="Удалить неделю"
                            title="Удалить неделю"
                            disabled={!canEdit || saving}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        <div className="text-xs text-muted-foreground">{formatWeekLabel(row.weekStart)}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Textarea
                        value={row.comment}
                        onChange={(event) => updateRow(row.rowId, { comment: event.target.value })}
                        placeholder="Комментарий для недели"
                        className="min-h-[72px]"
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right align-top">{renderClusterDropdown(row)}</TableCell>
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
