'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type ScheduleItem = {
  id: number;
  platform: string;
  post_title: string;
  planned_at: string;
  status: string;
};

export default function SchedulePage() {
  const router = useRouter();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadItems = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<ScheduleItem[]>('/api/schedules/');
        setItems(data);
      } catch (err) {
        const error = err as Error;
        if (error.message === 'unauthorized') {
          router.push('/login');
        } else {
          setError('Не удалось загрузить расписание');
        }
      } finally {
        setLoading(false);
      }
    };

    loadItems();
  }, [router]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Расписание</h1>

      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div>Загрузка...</div>}

      {!loading && items.length === 0 && <div className="text-sm text-muted-foreground">Запланированных публикаций нет.</div>}

      {!loading && items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Пост</TableHead>
              <TableHead>Платформа</TableHead>
              <TableHead>Когда</TableHead>
              <TableHead>Статус</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.post_title}</TableCell>
                <TableCell>{item.platform}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(item.planned_at).toLocaleString('ru-RU')}
                </TableCell>
                <TableCell>
                  <Badge>{item.status}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
