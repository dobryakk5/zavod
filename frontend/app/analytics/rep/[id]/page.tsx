'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, ArrowLeft, ChevronDown } from 'lucide-react';
import { analyticsApi, type WeeklySourceBatch, type WeeklySourceReport } from '@/lib/api/analytics';
import { Button } from '@/components/ui/button';

const statusLabels: Record<WeeklySourceReport['status'], string> = {
  pending: 'В очереди',
  in_progress: 'В работе',
  completed: 'Готово',
  failed: 'Ошибка',
};

const formatDuration = (seconds?: number | null): string | null => {
  if (!seconds || seconds <= 0) return null;
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) {
    return `${hrs}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${mins}:${String(secs).padStart(2, '0')}`;
};

const inferContentType = (report: WeeklySourceReport, url?: string | null): string | null => {
  if (!url) return null;
  const lower = url.toLowerCase();

  if (report.source_type === 'youtube') {
    if (lower.includes('shorts')) return 'shorts';
    return 'video';
  }

  if (report.source_type === 'instagram') {
    if (lower.includes('/reel/') || lower.includes('/reels/')) return 'reels';
    if (lower.includes('/p/')) return 'post';
    return 'post';
  }

  return null;
};

export default function WeeklyBatchPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [batch, setBatch] = useState<WeeklySourceBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [openReports, setOpenReports] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const load = async () => {
      if (!params?.id) return;
      setLoading(true);
      try {
        const data = await analyticsApi.getWeeklyBatch(params.id);
        setBatch(data);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Не удалось загрузить отчёт', error);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [params?.id]);

  const toggleReport = (reportId: number) => {
    setOpenReports((prev) => {
      const isOpen = Boolean(prev[reportId]);
      return isOpen ? {} : { [reportId]: true };
    });
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.push('/analytics')}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          Назад к отчётам
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Отчёт #{params?.id}</h1>
          {batch && (
            <p className="text-sm text-muted-foreground">
              Неделя с {new Date(batch.week_start).toLocaleDateString('ru-RU')}
            </p>
          )}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загружаем отчёт
        </div>
      ) : !batch ? (
        <p className="text-sm text-muted-foreground">Отчёт не найден.</p>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-semibold">
                  Неделя с {new Date(batch.week_start).toLocaleDateString('ru-RU')}
                </p>
                <p className="text-xs text-muted-foreground">ID: {batch.id}</p>
              </div>
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                {(batch.status === 'pending' || batch.status === 'in_progress') && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                )}
                {statusLabels[(batch.status || 'pending') as WeeklySourceReport['status']] || batch.status}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            {batch.reports?.map((report) => (
              <div key={report.id} className="rounded-lg border bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                <p className="text-sm font-semibold">
                  {report.source_type} · {report.source_value}
                </p>
                <p className="text-xs text-muted-foreground">
                  Неделя с {new Date(report.week_start).toLocaleDateString('ru-RU')}
                </p>
              </div>
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                {(report.status === 'pending' || report.status === 'in_progress') && (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                )}
                {statusLabels[report.status] || report.status}
              </span>
            </div>
            {report.error && (
              <p className="mt-2 text-xs text-red-600">Ошибка: {report.error}</p>
            )}
                {report.links?.length ? (
                  <div className="mt-3 space-y-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleReport(report.id)}
                      className="inline-flex items-center gap-2"
                    >
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${openReports[report.id] ? 'rotate-180' : ''}`}
                      />
                      {openReports[report.id] ? 'Скрыть посты' : `Показать посты (${report.links.length})`}
                    </Button>

                    {openReports[report.id] && (
                      <div className="space-y-2">
                        {report.links.map((link, idx) => {
                          const dateLabel = link.date
                            ? new Date(link.date).toLocaleDateString('ru-RU')
                            : 'Без даты';
                          const contentType = inferContentType(report, link.url);
                          const durationLabel =
                            report.source_type === 'youtube' ? formatDuration(link.duration_seconds) : null;
                          const labelParts = [dateLabel, contentType, durationLabel].filter(Boolean).join(' · ');
                          return (
                            <div key={`${report.id}-${idx}`} className="rounded border border-slate-100 p-2 text-sm">
                              <a
                                href={link.url || '#'}
                                className="text-blue-600 hover:underline"
                                target="_blank"
                                rel="noreferrer"
                              >
                                {labelParts || dateLabel}
                              </a>
                              <div className="mt-1 flex items-center justify-between">
                                <span className="text-sm text-slate-900">
                                  {link.idea || link.title || link.url || '—'}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {typeof link.text_length === 'number' ? `${link.text_length} символов` : '—'}
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {link.action || 'Как использовать: —'}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground">Нет постов за неделю.</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
