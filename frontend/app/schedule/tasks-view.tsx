'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError } from '@/lib/api';
import { telegramTasksApi } from '@/lib/api/telegramTasks';
import type { TelegramTask } from '@/lib/types';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';

export default function ScheduleTasksView() {
  const router = useRouter();
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [items, setItems] = useState<TelegramTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        <div className="space-y-3">
          {items.map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
              <div className="text-xs text-muted-foreground">
                {formatInTenantTimezone(item.received_at, tenantTimezone, {
                  day: 'numeric',
                  month: 'long',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
                {item.tg_name ? ` • @${item.tg_name}` : ''}
              </div>
              <div className="mt-2 whitespace-pre-wrap">{item.message_text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
