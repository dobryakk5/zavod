'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError } from '@/lib/api';
import { telegramTasksApi } from '@/lib/api/telegramTasks';
import type { TelegramTask } from '@/lib/types';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type SortKey = 'received_at' | 'rating' | 'message_text' | 'tg_name';
type SortDirection = 'asc' | 'desc';

const defaultSort: { key: SortKey; direction: SortDirection } = {
  key: 'received_at',
  direction: 'desc',
};

const defaultDirectionForKey = (key: SortKey): SortDirection =>
  key === 'received_at' || key === 'rating' ? 'desc' : 'asc';

export default function ScheduleTasksView() {
  const router = useRouter();
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [items, setItems] = useState<TelegramTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState(defaultSort);

  useEffect(() => {
    const loadItems = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await telegramTasksApi.list();
        setItems(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить задачи');
        }
      } finally {
        setLoading(false);
      }
    };

    loadItems();
  }, [router]);

  const sortedItems = useMemo(() => {
    const copy = [...items];

    const compareNullable = (a: number | string | null | undefined, b: number | string | null | undefined) => {
      if (a == null && b == null) return 0;
      if (a == null) return 1;
      if (b == null) return -1;
      if (a < b) return -1;
      if (a > b) return 1;
      return 0;
    };

    copy.sort((a, b) => {
      let result = 0;
      switch (sort.key) {
        case 'received_at': {
          const aTime = new Date(a.received_at).getTime();
          const bTime = new Date(b.received_at).getTime();
          result = aTime - bTime;
          break;
        }
        case 'rating':
          result = compareNullable(a.rating, b.rating);
          break;
        case 'message_text':
          result = compareNullable(a.message_text?.toLowerCase() ?? '', b.message_text?.toLowerCase() ?? '');
          break;
        case 'tg_name':
          result = compareNullable(a.tg_name?.toLowerCase() ?? '', b.tg_name?.toLowerCase() ?? '');
          break;
        default:
          result = 0;
      }
      return sort.direction === 'asc' ? result : -result;
    });

    return copy;
  }, [items, sort.direction, sort.key]);

  const handleSort = (key: SortKey) => {
    setSort((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { key, direction: defaultDirectionForKey(key) };
    });
  };

  const sortIndicator = (key: SortKey) => {
    if (sort.key !== key) return null;
    return sort.direction === 'asc' ? ' ▲' : ' ▼';
  };

  return (
    <div className="space-y-4">
      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div className="text-center py-8 text-slate-500">Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          Сообщений из Telegram пока нет.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-48">
                  <button
                    type="button"
                    className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left"
                    onClick={() => handleSort('received_at')}
                  >
                    Дата{sortIndicator('received_at')}
                  </button>
                </TableHead>
                <TableHead className="w-32">
                  <button
                    type="button"
                    className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left"
                    onClick={() => handleSort('rating')}
                  >
                    Оценка{sortIndicator('rating')}
                  </button>
                </TableHead>
                <TableHead>
                  <button
                    type="button"
                    className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left"
                    onClick={() => handleSort('message_text')}
                  >
                    Комментарий{sortIndicator('message_text')}
                  </button>
                </TableHead>
                <TableHead className="w-48">
                  <button
                    type="button"
                    className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0 text-left"
                    onClick={() => handleSort('tg_name')}
                  >
                    Клиент{sortIndicator('tg_name')}
                  </button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedItems.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatInTenantTimezone(item.received_at, tenantTimezone, {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </TableCell>
                  <TableCell className="font-medium">
                    {item.rating != null ? `${item.rating}/10` : '—'}
                  </TableCell>
                  <TableCell>
                    {item.message_text ? (
                      <span className="whitespace-pre-wrap">{item.message_text}</span>
                    ) : (
                      <span className="text-sm text-muted-foreground">Пожеланий нет.</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {item.tg_name ? `@${item.tg_name}` : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
