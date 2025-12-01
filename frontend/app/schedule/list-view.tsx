'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type ScheduleItem = {
  id: number;
  platform: string;
  post_title: string;
  planned_at: string;
  status: string;
};

export default function ScheduleListView() {
  const router = useRouter();
  const [items, setItems] = useState<ScheduleItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadItems = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<ScheduleItem[]>('/schedules/');
        setItems(data);
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

    loadItems();
  }, [router]);

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    in_progress: 'bg-blue-100 text-blue-800',
    published: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  };

  return (
    <div className="space-y-4">
      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div className="text-center py-8 text-slate-500">Загрузка...</div>}

      {!loading && items.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          Запланированных публикаций нет.
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="border rounded-lg">
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
                <TableRow key={item.id} className="hover:bg-slate-50">
                  <TableCell className="font-medium">{item.post_title}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{item.platform}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(item.planned_at).toLocaleString('ru-RU', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </TableCell>
                  <TableCell>
                    <Badge className={statusColors[item.status] || 'bg-gray-100 text-gray-800'}>
                      {item.status}
                    </Badge>
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
