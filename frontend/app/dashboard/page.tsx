'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

type Summary = {
  total_posts: number;
  posts_scheduled: number;
  posts_published: number;
  by_platform: { platform: string; count: number }[];
};

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Summary>('/api/client/summary/')
      .then(setData)
      .catch((err) => {
        if (err instanceof Error && err.message === 'unauthorized') {
          router.push('/login');
        } else {
          setError('Не удалось загрузить данные');
        }
      });
  }, [router]);

  if (error) {
    return <div>{error}</div>;
  }

  if (!data) {
    return <div>Загрузка...</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Сводка по клиенту</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Всего постов</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{data.total_posts}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Запланировано</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{data.posts_scheduled}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Опубликовано</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-bold">{data.posts_published}</CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-2 text-lg font-semibold">По платформам</h2>
        <ul className="space-y-1 text-sm">
          {data.by_platform.map((item) => (
            <li key={item.platform}>
              {item.platform}: <span className="font-semibold">{item.count}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
