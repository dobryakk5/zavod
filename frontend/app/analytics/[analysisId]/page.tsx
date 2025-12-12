'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { analyticsApi, type ChannelAnalysisDetail, type ChannelAnalysisRecord } from '@/lib/api/analytics';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

type PageProps = {
  params: {
    analysisId: string;
  };
};

const statusLabels: Record<ChannelAnalysisRecord['status'], string> = {
  pending: 'В очереди',
  in_progress: 'В работе',
  completed: 'Готово',
  failed: 'Ошибка',
};

const statusClasses: Record<ChannelAnalysisRecord['status'], string> = {
  pending: 'bg-gray-200 text-gray-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

const DAY_NAMES_RU: Record<string, string> = {
  Monday: 'Понедельник',
  Tuesday: 'Вторник',
  Wednesday: 'Среда',
  Thursday: 'Четверг',
  Friday: 'Пятница',
  Saturday: 'Суббота',
  Sunday: 'Воскресенье',
};

export default function AnalysisDetailPage({ params }: PageProps) {
  const resolvedParams = typeof params?.then === 'function' ? use(params) : params;
  const router = useRouter();
  const [analysis, setAnalysis] = useState<ChannelAnalysisDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const formatNumber = (value?: number | null) => (value ?? 0).toLocaleString('ru-RU');
  const formatDateTime = (value: string) => new Date(value).toLocaleString('ru-RU');

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      setIsLoading(true);
      try {
        const data = await analyticsApi.getAnalysisDetail(resolvedParams.analysisId);
        if (isMounted) {
          setAnalysis(data);
        }
      } catch (error) {
        toast.error('Не удалось загрузить результаты анализа');
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    load();
    return () => {
      isMounted = false;
    };
  }, [resolvedParams.analysisId]);

  const result = analysis?.result ?? null;
  const audienceProfile = result?.audience_profile;

  if (isLoading) {
    return (
      <div className="container mx-auto flex h-[60vh] items-center justify-center">
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          Загружаем аналитику канала...
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="container mx-auto py-10">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-700">
          Не удалось получить данные анализа. Попробуйте вернуться к списку и открыть запись снова.
        </div>
        <Button variant="link" className="mt-4 px-0" onClick={() => router.push('/analytics')}>
          Вернуться к аналитике
        </Button>
      </div>
    );
  }

  const channelTitle = analysis.channel_name || analysis.channel_url;

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Канал</p>
          <p className="text-2xl font-semibold text-gray-900">{channelTitle}</p>
          <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
            <a
              href={analysis.channel_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline break-all"
            >
              {analysis.channel_url}
            </a>
            <span className="text-gray-300">•</span>
            <span>Обновлено {formatDateTime(analysis.updated_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge className={statusClasses[analysis.status]}>{statusLabels[analysis.status]}</Badge>
          <Button variant="outline" onClick={() => router.push('/analytics')}>
            Вернуться к аналитике
          </Button>
        </div>
      </div>

      {result ? (
        <>
          <section>
            <h2 className="text-2xl font-semibold mb-4">Ключевые метрики</h2>
            <div className="divide-y divide-gray-100 rounded-xl border bg-white">
              {[
                { title: 'Подписчики', value: formatNumber(result.subscribers) },
                { title: 'Средние просмотры', value: formatNumber(result.avg_views) },
                { title: 'Средняя вовлеченность', value: `${result.avg_engagement}%` },
                { title: 'Средние реакции', value: formatNumber(result.avg_reactions) },
                { title: 'Средние комментарии', value: formatNumber(result.avg_comments) },
              ].map((metric) => (
                <div key={metric.title} className="flex flex-col gap-1 px-6 py-4">
                  <p className="text-sm text-gray-500">{metric.title}</p>
                  <p className="text-2xl font-semibold text-gray-900">{metric.value}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Темы и форматы</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <TagList label="Ключевые слова" items={result.keywords} />
                <TagList label="Темы" items={result.topics} />
                <TagList label="Типы контента" items={result.content_types} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Когда чаще публикуют контент:</CardTitle>
              </CardHeader>
              <CardContent>
                {result.posting_schedule.length === 0 ? (
                  <p className="text-sm text-gray-500">Недостаточно данных для формирования расписания.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50">
                        <TableHead>День</TableHead>
                        <TableHead>Час</TableHead>
                        <TableHead>Постов</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.posting_schedule.slice(0, 5).map((slot, index) => (
                        <TableRow key={`${slot.day}-${slot.hour}-${index}`}>
                          <TableCell>{DAY_NAMES_RU[slot.day] || slot.day}</TableCell>
                          <TableCell>{slot.hour}:00</TableCell>
                          <TableCell>{slot.posts_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </section>

          <section>
            <Card>
              <CardHeader>
                <CardTitle>Топ посты</CardTitle>
              </CardHeader>
              <CardContent>
                {result.top_posts.length === 0 ? (
                  <p className="text-sm text-gray-500">Данные о постах отсутствуют.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50">
                        <TableHead>Название</TableHead>
                        <TableHead>Просмотры</TableHead>
                        <TableHead>Реакции</TableHead>
                        <TableHead>Комментарии</TableHead>
                        <TableHead>Вовлеченность</TableHead>
                        <TableHead>Ссылка</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.top_posts.map((post, index) => (
                        <TableRow key={`${post.url}-${index}`}>
                          <TableCell className="max-w-md">
                            <p className="font-medium text-gray-900">{post.title}</p>
                          </TableCell>
                          <TableCell>{formatNumber(post.views)}</TableCell>
                          <TableCell>{formatNumber(post.reactions)}</TableCell>
                          <TableCell>{formatNumber(post.comments)}</TableCell>
                          <TableCell>{post.engagement}%</TableCell>
                          <TableCell>
                            {post.url ? (
                              <a
                                href={post.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 underline"
                              >
                                Открыть
                              </a>
                            ) : (
                              <span className="text-gray-400">нет ссылки</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </section>

          <section>
            <Card>
              <CardHeader>
                <CardTitle>Целевая аудитория</CardTitle>
                <p className="text-sm text-gray-500">К кому обращаются на канале</p>
              </CardHeader>
              <CardContent>
                {audienceProfile && Object.values(audienceProfile).some((value) => value?.trim()) ? (
                  <dl className="space-y-4">
                    {[
                      { label: 'Аватар клиента', key: 'avatar' },
                      { label: 'Боли', key: 'pains' },
                      { label: 'Хотелки', key: 'desires' },
                      { label: 'Возражения и страхи', key: 'objections' },
                    ].map((item) => (
                      <div key={item.key} className="space-y-1">
                        <dt className="text-sm font-medium text-gray-500">{item.label}</dt>
                        <dd className="text-base text-gray-900 whitespace-pre-line">
                          {audienceProfile?.[item.key as keyof typeof audienceProfile]?.trim() || '—'}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="text-sm text-gray-500">
                    Данные ещё не собраны. Запустите анализ канала повторно, чтобы получить портрет аудитории.
                  </p>
                )}
              </CardContent>
            </Card>
          </section>
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Результаты анализа</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              Анализ еще выполняется или завершился ошибкой. Как только результат будет готов, он появится на этой
              странице.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

type TagListProps = {
  label: string;
  items: string[];
};

const TagList = ({ label, items }: TagListProps) => (
  <div>
    <p className="text-sm font-medium text-gray-500">{label}</p>
    {items.length === 0 ? (
      <p className="text-sm text-gray-400 mt-1">Нет данных</p>
    ) : (
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item, index) => (
          <span key={`${item}-${index}`} className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700">
            {item}
          </span>
        ))}
      </div>
    )}
  </div>
);
