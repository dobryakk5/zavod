'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError } from '@/lib/api';
import {
  analyticsApi,
  type ChannelAnalysisRecord,
  type WeeklySourceBatch,
  type ProjectChannelAnalysisDetail,
  type ProjectChannelAnalysisChannel,
  type ProjectChannelTimeseriesResponse,
  type ProjectChannelTimeseriesChannel,
} from '@/lib/api/analytics';
import { websitesApi, type WebsiteScan, type WebsiteScanStatus } from '@/lib/api/websites';
import { clientApi } from '@/lib/api/client';
import type { ClientSettings } from '@/lib/types';
import { useRole, useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Loader2, RefreshCw, Trash2 } from 'lucide-react';

const statusLabels: Record<WeeklySourceBatch['status'], string> = {
  pending: 'В очереди',
  in_progress: 'В работе',
  completed: 'Готово',
  failed: 'Ошибка',
};

const websiteScanStatusLabels: Record<WebsiteScanStatus, string> = {
  pending: 'В очереди',
  in_progress: 'В работе',
  completed: 'Готово',
  failed: 'Ошибка',
};

const channelTypeLabels: Record<ChannelAnalysisRecord['channel_type'], string> = {
  telegram: 'Telegram',
  instagram: 'Instagram',
  youtube: 'YouTube',
  vkontakte: 'VKontakte',
};

const channelInputLabels: Record<'telegram' | 'instagram' | 'youtube', string> = {
  telegram: 'Ссылка на Telegram канал',
  instagram: 'Ссылка на Instagram аккаунт',
  youtube: 'Ссылка на YouTube канал',
};

const channelPlaceholders: Record<'telegram' | 'instagram' | 'youtube', string> = {
  telegram: 'https://t.me/example или @example',
  instagram: 'https://www.instagram.com/username/',
  youtube: 'https://www.youtube.com/@channel или UCxxxxxxxx',
};

const channelHints: Record<'telegram' | 'instagram' | 'youtube', string> = {
  telegram: 'Можно указать ссылку на публичный канал или @username.',
  instagram: 'Поддерживаются публичные профили: ссылка, username или @username.',
  youtube: 'Подойдут ссылка на канал, @handle или ID вида UCxxxxxxxx.',
};

type MetricKey = 'subscribers' | 'views' | 'reactions' | 'comments';

type MetricOption = {
  key: MetricKey;
  label: string;
  dash: string;
  linecap?: 'butt' | 'round' | 'square';
};

const METRIC_OPTIONS: readonly MetricOption[] = [
  { key: 'subscribers', label: 'Подписчики', dash: '' },
  { key: 'views', label: 'Просмотры', dash: '6 4 1 4' },
  { key: 'reactions', label: 'Реакции', dash: '1 6', linecap: 'round' },
  { key: 'comments', label: 'Комментарии', dash: '6 4' },
];

const CHART_COLORS = ['#2563eb', '#16a34a', '#f97316', '#ef4444', '#0ea5e9', '#9333ea', '#84cc16', '#f59e0b', '#14b8a6'];

type ProjectChannelFields = Pick<
  ClientSettings,
  'project_telegram_channel' | 'project_instagram_channel' | 'project_youtube_channel'
>;

type SourceFields = Pick<
  ClientSettings,
  | 'telegram_source_channels'
  | 'rss_source_feeds'
  | 'youtube_source_channels'
  | 'instagram_source_accounts'
  | 'vkontakte_source_groups'
>;

const PROJECT_CHANNEL_CONFIG: Array<{
  key: keyof ProjectChannelFields;
  label: string;
  placeholder: string;
}> = [
  {
    key: 'project_telegram_channel',
    label: 'Telegram',
    placeholder: channelPlaceholders.telegram,
  },
  {
    key: 'project_instagram_channel',
    label: 'Instagram',
    placeholder: channelPlaceholders.instagram,
  },
  {
    key: 'project_youtube_channel',
    label: 'YouTube',
    placeholder: channelPlaceholders.youtube,
  },
];

const SOURCE_FIELD_CONFIG: Array<{
  key: keyof SourceFields;
  label: string;
  placeholder: string;
  description: string;
  fullWidth?: boolean;
}> = [
  {
    key: 'telegram_source_channels',
    label: 'Telegram каналы',
    placeholder: '@rian_ru, @tjournal',
    description: 'Указывайте @username или ссылку, через запятую.',
  },
  {
    key: 'rss_source_feeds',
    label: 'RSS / Atom фиды',
    placeholder: 'https://lenta.ru/rss, https://example.com/feed.xml',
    description: 'Полные URL фидов.',
  },
  {
    key: 'youtube_source_channels',
    label: 'YouTube каналы',
    placeholder: 'UC_x5XG1OV2P6uZZ5FSM9Ttw, @channel_handle',
    description: 'ID канала или @handle, через запятую.',
  },
  {
    key: 'instagram_source_accounts',
    label: 'Instagram аккаунты',
    placeholder: 'username1, username2',
    description: 'Список usernames.',
  },
  {
    key: 'vkontakte_source_groups',
    label: 'VK сообщества',
    placeholder: 'apiclub, https://vk.com/thecode',
    description: 'screen name или ссылка, через запятую.',
    fullWidth: true,
  },
];

function MyProjectTab({ timeZone }: { timeZone: string }) {
  const { canEdit } = useRole();
  const [channels, setChannels] = useState<ProjectChannelFields>({
    project_telegram_channel: '',
    project_instagram_channel: '',
    project_youtube_channel: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [analysis, setAnalysis] = useState<ProjectChannelAnalysisDetail | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [analysisLaunching, setAnalysisLaunching] = useState(false);
  const [displayedProgress, setDisplayedProgress] = useState<number | null>(null);
  const [timeseries, setTimeseries] = useState<ProjectChannelTimeseriesResponse | null>(null);
  const [timeseriesLoading, setTimeseriesLoading] = useState(true);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<MetricKey[]>([
    'subscribers',
    'views',
    'reactions',
    'comments',
  ]);

  const formatDelta = (value: number) => {
    if (!value) return '0';
    return value > 0 ? `+${value}` : `${value}`;
  };

  const getDeltaClass = (value: number) => {
    if (value > 0) return 'text-green-600';
    if (value < 0) return 'text-red-600';
    return 'text-gray-400';
  };

  const loadTimeseries = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setTimeseriesLoading(true);
    }
    try {
      const data = await analyticsApi.getProjectChannelTimeseries();
      setTimeseries(data);
    } catch (error) {
      toast.error('Не удалось загрузить временные ряды');
    } finally {
      if (!options?.silent) {
        setTimeseriesLoading(false);
      }
    }
  }, []);

  const loadChannels = useCallback(async () => {
    setLoading(true);
    try {
      const data = await clientApi.getSettings();
      setChannels({
        project_telegram_channel: data.project_telegram_channel || '',
        project_instagram_channel: data.project_instagram_channel || '',
        project_youtube_channel: data.project_youtube_channel || '',
      });
    } catch (error) {
      toast.error('Не удалось загрузить каналы проекта');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadLatestAnalysis = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setAnalysisLoading(true);
    }
    try {
      const data = await analyticsApi.getLatestProjectChannelAnalysis();
      setAnalysis(data);
    } catch (error) {
      toast.error('Не удалось загрузить анализ проекта');
    } finally {
      if (!options?.silent) {
        setAnalysisLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadChannels();
    void loadLatestAnalysis();
    void loadTimeseries();
  }, [loadChannels, loadLatestAnalysis, loadTimeseries]);

  useEffect(() => {
    const shouldPoll = analysis?.status === 'pending' || analysis?.status === 'in_progress';
    if (!shouldPoll) return;

    const intervalId = setInterval(() => {
      void loadLatestAnalysis({ silent: true });
    }, 5000);

    return () => clearInterval(intervalId);
  }, [analysis?.status, loadLatestAnalysis]);

  useEffect(() => {
    if (!analysis) {
      setDisplayedProgress(null);
      return;
    }
    if (analysis.status === 'completed' || analysis.status === 'failed') {
      setDisplayedProgress(analysis.progress);
      return;
    }
    setDisplayedProgress((prev) => {
      const current = analysis.progress ?? 0;
      if (prev === null) return current;
      if (current > prev) return current;
      return Math.min(prev + 5, 95);
    });
  }, [analysis]);

  useEffect(() => {
    if (analysis?.status === 'completed') {
      void loadTimeseries({ silent: true });
    }
  }, [analysis?.status, loadTimeseries]);

  const handleChange = (key: keyof ProjectChannelFields, value: string) => {
    setChannels((prev) => ({ ...prev, [key]: value }));
  };

  const handleRunAnalysis = async () => {
    if (!canEdit || analysisLaunching) return;
    setAnalysisLaunching(true);
    try {
      await clientApi.updateSettings({
        project_telegram_channel: channels.project_telegram_channel,
        project_instagram_channel: channels.project_instagram_channel,
        project_youtube_channel: channels.project_youtube_channel,
      });
      const response = await analyticsApi.runProjectChannelAnalysis();
      if (response.success) {
        toast.success('Анализ проекта запущен');
        await loadLatestAnalysis({ silent: true });
      } else {
        toast.error(response.error || 'Не удалось запустить анализ проекта');
      }
    } catch (error) {
      toast.error('Не удалось запустить анализ проекта');
    } finally {
      setAnalysisLaunching(false);
    }
  };

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    try {
      await clientApi.updateSettings({
        project_telegram_channel: channels.project_telegram_channel,
        project_instagram_channel: channels.project_instagram_channel,
        project_youtube_channel: channels.project_youtube_channel,
      });
      toast.success('Каналы проекта сохранены');
    } catch (error) {
      toast.error('Не удалось сохранить каналы проекта');
    } finally {
      setSaving(false);
    }
  };

  const hasChannels = Object.values(channels).some((value) => value.trim());
  const analysisChannels = analysis?.result?.channels ?? [];
  const availableTimeseriesChannels = useMemo(() => timeseries?.channels ?? [], [timeseries?.channels]);
  const runs = useMemo(() => timeseries?.runs ?? [], [timeseries?.runs]);

  useEffect(() => {
    if (availableTimeseriesChannels.length === 0) {
      if (selectedChannels.length !== 0) {
        setSelectedChannels([]);
      }
      return;
    }
    setSelectedChannels((prev) => {
      if (prev.length) return prev;
      return availableTimeseriesChannels.map((channel) => channel.key);
    });
  }, [availableTimeseriesChannels, selectedChannels.length]);

  const channelMetaMap = useMemo(() => {
    const map = new Map<string, ProjectChannelTimeseriesChannel>();
    availableTimeseriesChannels.forEach((channel) => {
      map.set(channel.key, channel);
    });
    return map;
  }, [availableTimeseriesChannels]);

  const runChannelTotals = useMemo(() => {
    const runMap = new Map<
      number,
      Map<string, { views: number; reactions: number; comments: number; subscribers: number }>
    >();
    runs.forEach((run) => {
      const channelMap = new Map<string, { views: number; reactions: number; comments: number; subscribers: number }>();
      run.channels.forEach((channel) => {
        channelMap.set(channel.key, {
          views: channel.totals.views,
          reactions: channel.totals.reactions,
          comments: channel.totals.comments,
          subscribers: channel.totals.subscribers,
        });
      });
      runMap.set(run.run_id, channelMap);
    });
    return runMap;
  }, [runs]);

  const series = useMemo(() => {
    return selectedChannels.flatMap((channelKey) =>
      selectedMetrics.map((metric) => ({
        channelKey,
        metric,
        id: `${channelKey}:${metric}`,
      })),
    );
  }, [selectedChannels, selectedMetrics]);

  const maxValue = useMemo(() => {
    let max = 0;
    runs.forEach((run) => {
      const channelMap = runChannelTotals.get(run.run_id);
      if (!channelMap) return;
      selectedChannels.forEach((channelKey) => {
        const totals = channelMap.get(channelKey);
        if (!totals) return;
        selectedMetrics.forEach((metric) => {
          const value = totals[metric] ?? 0;
          if (value > max) max = value;
        });
      });
    });
    return max || 1;
  }, [runs, runChannelTotals, selectedChannels, selectedMetrics]);

  const buildPath = (points: Array<{ x: number; y: number | null }>) => {
    let path = '';
    let started = false;
    points.forEach((point) => {
      if (point.y === null) {
        started = false;
        return;
      }
      const cmd = started ? 'L' : 'M';
      path += `${cmd}${point.x},${point.y} `;
      started = true;
    });
    return path.trim();
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          Укажите ваши каналы (имя или ссылку). Для анализа конкурентов используйте вкладку «Один канал».
        </p>
      </div>

      <div className="max-w-xl rounded-lg border bg-white p-6 shadow-sm">
        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем каналы
          </div>
        ) : (
          <>
            <div className="grid gap-3">
              {PROJECT_CHANNEL_CONFIG.map((field) => (
                <div key={field.key} className="flex items-center gap-3">
                  <Label htmlFor={field.key} className="w-24 text-sm text-gray-600">
                    {field.label}
                  </Label>
                  <Input
                    id={field.key}
                    placeholder={field.placeholder}
                    value={channels[field.key] || ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    disabled={!canEdit}
                    className="flex-1"
                  />
                </div>
              ))}
            </div>

            <div className="mt-6 flex items-center gap-3">
              <Button onClick={handleSave} disabled={saving || !canEdit}>
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Сохраняем...
                  </>
                ) : (
                  'Сохранить каналы'
                )}
              </Button>
              {!canEdit && (
                <p className="text-sm text-muted-foreground">
                  Только владелец или редактор могут сохранять изменения.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-semibold">Анализ проекта</h3>
            <p className="text-sm text-muted-foreground">
              Снимок метрик по вашим каналам и дельта к прошлому запуску.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={handleRunAnalysis}
              disabled={!canEdit || analysisLaunching || !hasChannels}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {analysisLaunching ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Запускаем...
                </>
              ) : (
                'Запустить анализ'
              )}
            </Button>
            {!hasChannels && (
              <p className="text-sm text-muted-foreground">Заполните хотя бы один канал.</p>
            )}
          </div>
        </div>

        {analysisLoading ? (
          <div className="mt-6 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем анализ
          </div>
        ) : !analysis ? (
          <p className="mt-6 text-sm text-muted-foreground">Пока нет запусков анализа.</p>
        ) : (
          <div className="mt-6 space-y-6">
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>Статус:</span>
              <span className="font-medium text-gray-900">
                {statusLabels[analysis.status as WeeklySourceBatch['status']] || analysis.status}
              </span>
              <span className="text-gray-300">•</span>
              <span>{(displayedProgress ?? analysis.progress).toLocaleString('ru-RU')}%</span>
              {analysis.status === 'failed' && analysis.error?.trim() && (
                <span className="text-red-600">{analysis.error}</span>
              )}
            </div>

            {analysis.status === 'completed' && analysisChannels.length === 0 && (
              <p className="text-sm text-muted-foreground">Нет данных по каналам.</p>
            )}

            {analysisChannels.map((channel: ProjectChannelAnalysisChannel) => {
              const summary = channel.summary;
              const channelTitle = summary?.channel_name || channel.channel_url;
              const channelLink = summary?.profile_url || channel.channel_url;

              return (
                <div key={`${channel.channel_type}-${channel.channel_identifier}`} className="rounded-lg border p-4">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      {channelTypeLabels[channel.channel_type]}
                    </p>
                    <p className="text-lg font-semibold text-gray-900">{channelTitle}</p>
                    {channelLink && (
                      <a
                        href={channelLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-600 hover:underline break-all"
                      >
                        {channelLink}
                      </a>
                    )}
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-5">
                    {[
                      { label: 'Подписчики', value: summary.subscribers },
                      { label: 'Средние просмотры', value: summary.avg_views },
                      { label: 'Вовлеченность', value: `${summary.avg_engagement}%` },
                      { label: 'Средние реакции', value: summary.avg_reactions },
                      { label: 'Средние комментарии', value: summary.avg_comments },
                    ].map((metric) => (
                      <div key={metric.label} className="rounded border border-slate-100 p-3">
                        <p className="text-xs text-muted-foreground">{metric.label}</p>
                        <p className="text-lg font-semibold text-gray-900">
                          {typeof metric.value === 'number'
                            ? metric.value.toLocaleString('ru-RU')
                            : metric.value}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-4">
                    {[
                      { label: 'Постов', value: channel.totals.posts_count, delta: channel.delta.posts_count },
                      { label: 'Просмотры', value: channel.totals.views, delta: channel.delta.views },
                      { label: 'Реакции', value: channel.totals.reactions, delta: channel.delta.reactions },
                      { label: 'Комментарии', value: channel.totals.comments, delta: channel.delta.comments },
                    ].map((metric) => (
                      <div key={metric.label} className="rounded border border-slate-100 p-3">
                        <p className="text-xs text-muted-foreground">{metric.label}</p>
                        <p className="text-lg font-semibold text-gray-900">
                          {metric.value.toLocaleString('ru-RU')}
                        </p>
                        <p className={`text-xs ${getDeltaClass(metric.delta)}`}>
                          {formatDelta(metric.delta)}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6">
                    <h4 className="text-sm font-semibold text-gray-700">Посты</h4>
                    {channel.posts.length === 0 ? (
                      <p className="mt-3 text-sm text-muted-foreground">Нет данных по постам.</p>
                    ) : (
                      <div className="mt-3 rounded-lg border bg-white">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-gray-50">
                              <TableHead>Пост</TableHead>
                              <TableHead>Просмотры</TableHead>
                              <TableHead>Реакции</TableHead>
                              <TableHead>Комментарии</TableHead>
                              <TableHead className="w-32">Дата</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {channel.posts.map((post) => (
                              <TableRow key={post.external_id}>
                                <TableCell className="space-y-1">
                                  <div className="font-medium text-gray-900">
                                    {post.title || post.url || `Пост ${post.external_id}`}
                                  </div>
                                  {post.url && (
                                    <a
                                      href={post.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-xs text-blue-600 hover:underline break-all"
                                    >
                                      {post.url}
                                    </a>
                                  )}
                                  {post.is_new && (
                                    <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
                                      Новый
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <div className="text-sm text-gray-900">
                                    {post.views.toLocaleString('ru-RU')}
                                  </div>
                                  <div className={`text-xs ${getDeltaClass(post.delta_views)}`}>
                                    {formatDelta(post.delta_views)}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <div className="text-sm text-gray-900">
                                    {post.reactions.toLocaleString('ru-RU')}
                                  </div>
                                  <div className={`text-xs ${getDeltaClass(post.delta_reactions)}`}>
                                    {formatDelta(post.delta_reactions)}
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <div className="text-sm text-gray-900">
                                    {post.comments.toLocaleString('ru-RU')}
                                  </div>
                                  <div className={`text-xs ${getDeltaClass(post.delta_comments)}`}>
                                    {formatDelta(post.delta_comments)}
                                  </div>
                                </TableCell>
                                <TableCell className="text-sm text-gray-600">
                                  {post.published_at
                                    ? formatInTenantTimezone(post.published_at, timeZone, {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit',
                                      })
                                    : '—'}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-semibold">Динамика показателей</h3>
            <p className="text-sm text-muted-foreground">
              Выберите каналы и метрики — линии отобразятся на одном графике.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadTimeseries()} disabled={timeseriesLoading}>
            {timeseriesLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Обновить'}
          </Button>
        </div>

        {timeseriesLoading ? (
          <div className="mt-6 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем ряды
          </div>
        ) : availableTimeseriesChannels.length === 0 ? (
          <p className="mt-6 text-sm text-muted-foreground">Нет данных для построения графика.</p>
        ) : (
          <div className="mt-6 space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-3">
                <p className="text-sm font-semibold text-gray-700">Каналы</p>
                <div className="flex flex-wrap gap-3">
                  {availableTimeseriesChannels.map((channel, index) => {
                    const checked = selectedChannels.includes(channel.key);
                    const label = channel.channel_label || channel.channel_identifier;
                    return (
                      <label key={channel.key} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={checked}
                          onChange={() => {
                            setSelectedChannels((prev) =>
                              checked ? prev.filter((item) => item !== channel.key) : [...prev, channel.key],
                            );
                          }}
                        />
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                          />
                          {label}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-sm font-semibold text-gray-700">Метрики</p>
                <div className="flex flex-wrap gap-3">
                  {METRIC_OPTIONS.map((metric) => {
                    const checked = selectedMetrics.includes(metric.key);
                    return (
                      <label key={metric.key} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4"
                          checked={checked}
                          onChange={() => {
                            setSelectedMetrics((prev) =>
                              checked ? prev.filter((item) => item !== metric.key) : [...prev, metric.key],
                            );
                          }}
                        />
                        {metric.label}
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            {series.length === 0 ? (
              <p className="text-sm text-muted-foreground">Выберите хотя бы один канал и метрику.</p>
            ) : (
              <div className="space-y-3">
                <div className="w-full overflow-x-auto">
                  <svg viewBox="0 0 860 320" className="min-w-[600px] w-full">
                    <rect x="0" y="0" width="860" height="320" fill="white" />
                    {(() => {
                      const padding = { left: 60, right: 20, top: 20, bottom: 40 };
                      const plotWidth = 860 - padding.left - padding.right;
                      const plotHeight = 320 - padding.top - padding.bottom;
                      const xStep = runs.length > 1 ? plotWidth / (runs.length - 1) : 0;
                      const yScale = plotHeight / maxValue;
                      const yTicks = 4;
                      const xTicks = Math.min(runs.length, 6);
                      const xStepTicks = runs.length > 1 ? Math.floor((runs.length - 1) / (xTicks - 1 || 1)) : 1;

                      return (
                        <>
                          {Array.from({ length: yTicks + 1 }).map((_, idx) => {
                            const value = Math.round((maxValue / yTicks) * idx);
                            const y = padding.top + plotHeight - value * yScale;
                            return (
                              <g key={`y-${idx}`}>
                                <line x1={padding.left} y1={y} x2={860 - padding.right} y2={y} stroke="#e5e7eb" strokeDasharray="4 4" />
                                <text x={padding.left - 8} y={y + 4} textAnchor="end" className="fill-gray-400 text-[10px]">
                                  {value.toLocaleString('ru-RU')}
                                </text>
                              </g>
                            );
                          })}

                          {runs.map((run, index) => {
                            if (runs.length > 1 && index % xStepTicks !== 0) return null;
                            const x = padding.left + xStep * index;
                            return (
                              <g key={`x-${run.run_id}`}>
                                <line x1={x} y1={padding.top} x2={x} y2={padding.top + plotHeight} stroke="#f3f4f6" />
                                <text x={x} y={padding.top + plotHeight + 18} textAnchor="middle" className="fill-gray-400 text-[10px]">
                                  {formatInTenantTimezone(run.created_at, timeZone, {
                                    year: 'numeric',
                                    month: '2-digit',
                                    day: '2-digit',
                                  })}
                                </text>
                              </g>
                            );
                          })}

                          {series.map((item) => {
                            const channelIndex = availableTimeseriesChannels.findIndex((channel) => channel.key === item.channelKey);
                            const color = CHART_COLORS[(channelIndex >= 0 ? channelIndex : 0) % CHART_COLORS.length];
                            const metricMeta = METRIC_OPTIONS.find((metric) => metric.key === item.metric);
                            const points = runs.map((run, index) => {
                              const channelMap = runChannelTotals.get(run.run_id);
                              const totals = channelMap?.get(item.channelKey);
                              if (!totals) {
                                return { x: padding.left + xStep * index, y: null };
                              }
                              const value = totals[item.metric] ?? 0;
                              const y = padding.top + plotHeight - value * yScale;
                              return { x: padding.left + xStep * index, y };
                            });
                            const path = buildPath(points);
                            if (!path) return null;
                            return (
                              <path
                                key={item.id}
                                d={path}
                                fill="none"
                                stroke={color}
                                strokeWidth={2}
                                strokeDasharray={metricMeta?.dash || ''}
                                strokeLinecap={metricMeta?.linecap || 'round'}
                              />
                            );
                          })}
                        </>
                      );
                    })()}
                  </svg>
                </div>

                <div className="flex flex-wrap gap-3 text-xs text-gray-600">
                  {series.map((item) => {
                    const channel = channelMetaMap.get(item.channelKey);
                    const channelIndex = availableTimeseriesChannels.findIndex((entry) => entry.key === channel?.key);
                    const color = CHART_COLORS[(channelIndex >= 0 ? channelIndex : 0) % CHART_COLORS.length];
                    const metricMeta = METRIC_OPTIONS.find((metric) => metric.key === item.metric);
                    return (
                      <div key={item.id} className="inline-flex items-center gap-2 rounded-full border px-3 py-1">
                        <svg width="28" height="8" viewBox="0 0 28 8" aria-hidden="true">
                          <line
                            x1="2"
                            y1="4"
                            x2="26"
                            y2="4"
                            stroke={color}
                            strokeWidth="2"
                            strokeDasharray={metricMeta?.dash || ''}
                            strokeLinecap={metricMeta?.linecap || 'round'}
                          />
                        </svg>
                        <span>
                          {channel?.channel_label || channel?.channel_identifier || item.channelKey} · {metricMeta?.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function WeeklySourcesTab({ timeZone }: { timeZone: string }) {
  const { canEdit } = useRole();
  const [sources, setSources] = useState<SourceFields>({
    telegram_source_channels: '',
    rss_source_feeds: '',
    youtube_source_channels: '',
    instagram_source_accounts: '',
    vkontakte_source_groups: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [batches, setBatches] = useState<WeeklySourceBatch[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const loadSources = async () => {
    setLoading(true);
    try {
      const data = await clientApi.getSettings();
      setSources({
        telegram_source_channels: data.telegram_source_channels || '',
        rss_source_feeds: data.rss_source_feeds || '',
        youtube_source_channels: data.youtube_source_channels || '',
        instagram_source_accounts: data.instagram_source_accounts || '',
        vkontakte_source_groups: data.vkontakte_source_groups || '',
      });
    } catch (error) {
      toast.error('Не удалось загрузить источники');
    } finally {
      setLoading(false);
    }
  };

  const loadBatches = async () => {
    setBatchesLoading(true);
    try {
      const batchData = await analyticsApi.listWeeklyBatches();
      setBatches(batchData);
    } catch (error) {
      toast.error('Не удалось загрузить отчёты');
    } finally {
      setBatchesLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
    loadBatches();
  }, []);

  const handleChange = (key: keyof SourceFields, value: string) => {
    setSources((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    try {
      await clientApi.updateSettings({
        telegram_source_channels: sources.telegram_source_channels,
        rss_source_feeds: sources.rss_source_feeds,
        youtube_source_channels: sources.youtube_source_channels,
        instagram_source_accounts: sources.instagram_source_accounts,
        vkontakte_source_groups: sources.vkontakte_source_groups,
      });
      toast.success('Источники сохранены');
    } catch (error) {
      toast.error('Не удалось сохранить источники');
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!canEdit || running) return;
    setRunning(true);
    try {
      const response = await analyticsApi.runWeeklySources();
      if (response.success) {
        toast.success('Отчёт запускается, обновите страницу через пару минут.');
        await loadBatches();
      } else {
        toast.error('Не удалось создать отчёт');
      }
    } catch (error) {
      toast.error('Не удалось создать отчёт');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-lg border bg-white p-6 shadow-sm md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Подборка за неделю</h2>
          <p className="text-sm text-muted-foreground">
            Забираем посты из подключенных источников за последние 7 дней и просим AI дать краткий вывод.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={handleRun} disabled={running || !canEdit}>
            {running ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Запуск...
              </>
            ) : (
              'Запустить подборку'
            )}
          </Button>
          {!canEdit && <p className="text-xs text-muted-foreground">Требуется роль владельца или редактора</p>}
        </div>
      </div>

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-lg font-semibold">Подборки</p>
            <p className="text-sm text-muted-foreground">Последние запуски аналитики.</p>
          </div>
          <Button variant="outline" size="sm" onClick={loadBatches} disabled={batchesLoading}>
            {batchesLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Обновить'}
          </Button>
        </div>

        {batchesLoading ? (
          <div className="mt-6 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем подборки
          </div>
        ) : batches.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Пока нет подборок. Запустите подборку.</p>
        ) : (
          <div className="mt-4 space-y-2">
            {batches.map((batch) => (
              <a
                key={batch.id}
                href={`/analytics/rep/${batch.id}`}
                className="flex items-center justify-between rounded border border-slate-200 px-4 py-3 text-sm hover:bg-slate-50"
              >
                <div className="space-y-1">
                  <p className="font-medium text-slate-900">
                    Неделя с{' '}
                    {formatInTenantTimezone(batch.week_start, timeZone, {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                    })}
                  </p>
                  <p className="text-xs text-muted-foreground">ID подборки: {batch.id}</p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {statusLabels[batch.status as WeeklySourceBatch['status']] || batch.status}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold">Источники контента</h2>
          <p className="text-sm text-muted-foreground">Настройки подтягиваются из профиля клиента.</p>
        </div>

        {loading ? (
          <div className="mt-6 flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем источники
          </div>
        ) : (
          <>
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {SOURCE_FIELD_CONFIG.map((field) => (
                <div key={field.key} className={field.fullWidth ? 'md:col-span-2' : ''}>
                  <Label htmlFor={field.key}>{field.label}</Label>
                  <Textarea
                    id={field.key}
                    placeholder={field.placeholder}
                    value={sources[field.key] || ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    className="mt-2 min-h-[90px]"
                    disabled={!canEdit}
                  />
                  <p className="mt-2 text-xs text-muted-foreground">{field.description}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 flex items-center gap-3">
              <Button onClick={handleSave} disabled={saving || !canEdit}>
                {saving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Сохраняем...
                  </>
                ) : (
                  'Сохранить источники'
                )}
              </Button>
              {!canEdit && (
                <p className="text-sm text-muted-foreground">
                  Только владелец или редактор могут сохранять изменения.
                </p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

type WebsiteTabProps = {
  isActive: boolean;
  timeZone: string;
};

function WebsiteTab({ isActive, timeZone }: WebsiteTabProps) {
  const { canEdit } = useRole();
  const router = useRouter();
  const [baseUrl, setBaseUrl] = useState('');
  const [maxDepth, setMaxDepth] = useState(3);
  const [maxPages, setMaxPages] = useState(100);
  const [creating, setCreating] = useState(false);
  const [history, setHistory] = useState<WebsiteScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [rerunId, setRerunId] = useState<number | null>(null);
  const isHistoryTabActiveRef = useRef(false);
  const hasActiveScans = useMemo(
    () => history.some((scan) => scan.status === 'pending' || scan.status === 'in_progress'),
    [history],
  );

  const loadHistory = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent && isHistoryTabActiveRef.current) {
      setLoading(true);
    }
    try {
      const data = await websitesApi.listScans();
      if (isHistoryTabActiveRef.current) {
        setHistory(data);
      }
    } catch (error) {
      if (isHistoryTabActiveRef.current) {
        toast.error('Не удалось загрузить историю сканов');
      }
    } finally {
      if (!options?.silent && isHistoryTabActiveRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!isActive) return;
    isHistoryTabActiveRef.current = true;
    void loadHistory();
    return () => {
      isHistoryTabActiveRef.current = false;
    };
  }, [isActive, loadHistory]);

  useEffect(() => {
    if (!isActive || !hasActiveScans) return;
    const intervalId = setInterval(() => {
      void loadHistory({ silent: true });
    }, 5000);
    return () => clearInterval(intervalId);
  }, [hasActiveScans, isActive, loadHistory]);

  const handleCreate = async () => {
    if (!canEdit || creating) return;
    const trimmed = baseUrl.trim();
    if (!trimmed) {
      toast.error('Введите URL сайта');
      return;
    }

    setCreating(true);
    try {
      await websitesApi.createScan({
        base_url: trimmed,
        max_depth: Math.max(0, Math.min(10, Number(maxDepth) || 3)),
        max_pages: Math.max(1, Math.min(500, Number(maxPages) || 100)),
      });
      toast.success('Скан сайта запущен');
      setBaseUrl('');
      await loadHistory();
    } catch (error) {
      toast.error('Не удалось запустить скан');
    } finally {
      setCreating(false);
    }
  };

  const handleOpenMindMap = (scan: WebsiteScan) => {
    if (scan.status !== 'completed' || !scan.mind_map_id) return;
    router.push(`/map/${scan.mind_map_id}`);
  };

  const handleOpenList = (scanId: number) => {
    if (typeof window === 'undefined') return;
    window.open(`/analytics/website/${scanId}/list`, '_blank', 'noopener,noreferrer');
  };

  const handleDelete = async (scanId: number) => {
    if (!canEdit || deletingId === scanId) return;
    const confirmed =
      typeof window !== 'undefined' ? window.confirm('Удалить скан сайта и все найденные страницы?') : true;
    if (!confirmed) return;

    setDeletingId(scanId);
    try {
      await websitesApi.deleteScan(scanId);
      setHistory((prev) => prev.filter((item) => item.id !== scanId));
      toast.success('Скан удалён');
    } catch (error) {
      toast.error('Не удалось удалить скан');
    } finally {
      setDeletingId(null);
    }
  };

  const handleRerun = async (scanId: number) => {
    if (!canEdit || rerunId === scanId) return;
    setRerunId(scanId);
    try {
      const result = await websitesApi.rerunScan(scanId);
      if (result.success) {
        toast.success('Скан перезапущен');
        await loadHistory({ silent: true });
      } else {
        toast.error('Не удалось перезапустить скан');
      }
    } catch (error) {
      toast.error('Не удалось перезапустить скан');
    } finally {
      setRerunId(null);
    }
  };

  const formatScanProgress = (scan: WebsiteScan) => {
    const total =
      typeof scan.pages_total === 'number' && scan.pages_total > 0
        ? scan.pages_total
        : typeof scan.max_pages === 'number' && scan.max_pages > 0
          ? scan.max_pages
          : null;
    const done = typeof scan.pages_count === 'number' && scan.pages_count >= 0 ? scan.pages_count : 0;

    if (!total) return { label: `${done}`, percent: scan.progress };

    const percent =
      scan.status === 'completed'
        ? 100
        : Math.min(99, Math.max(0, Math.round((done / Math.max(1, total)) * 100)));

    let etaMinutes: number | null = null;
    if (scan.status === 'in_progress') {
      const remainingPages = Math.max(0, total - done);
      const remainingSeconds = remainingPages * 3;
      etaMinutes = Math.max(0, Math.ceil(remainingSeconds / 60));
    }

    const baseLabel = `${done}/${total}`;
    if (etaMinutes !== null) return { label: `${baseLabel} • Осталось минут: ~${etaMinutes}`, percent };
    return { label: baseLabel, percent };
  };

  return (
    <div className="space-y-8">
      <div className="max-w-xl space-y-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-semibold">Website</h2>
          <p className="text-sm text-muted-foreground">Строим дерево страниц (до 3 уровней / до 100 страниц).</p>
        </div>

        <div className="grid gap-3">
          <div className="space-y-2">
            <Label htmlFor="websiteUrl">URL сайта</Label>
            <Input
              id="websiteUrl"
              placeholder="https://example.com"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              disabled={!canEdit}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="maxDepth">Глубина</Label>
              <Input
                id="maxDepth"
                type="number"
                min={0}
                max={10}
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                disabled={!canEdit}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="maxPages">Лимит страниц</Label>
              <Input
                id="maxPages"
                type="number"
                min={1}
                max={500}
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                disabled={!canEdit}
              />
            </div>
          </div>

          <Button onClick={handleCreate} disabled={!canEdit || creating || !baseUrl.trim()}>
            {creating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Запускаем...
              </>
            ) : (
              'Запустить скан'
            )}
          </Button>
        </div>
      </div>

      <div>
        <div className="space-y-1">
          <h2 className="text-2xl font-semibold">История сканов</h2>
          <p className="text-gray-500 text-sm">Обновление включается, пока идут активные сканы.</p>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 mt-6">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем историю
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm text-gray-500 mt-4">Пока нет сканов. Запустите первый скан выше.</p>
        ) : (
          <div className="mt-6 rounded-lg border bg-white shadow-sm">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead>Сайт</TableHead>
                  <TableHead className="w-40">Открыть</TableHead>
                  <TableHead className="hidden md:table-cell w-40">Прогресс</TableHead>
                  <TableHead>Создан</TableHead>
                  <TableHead className="w-28 text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((item) => (
                  (() => {
                    const progressInfo = formatScanProgress(item);
                    return (
                  <TableRow key={item.id}>
                    <TableCell className="space-y-1">
                      <div className="font-medium text-gray-900">{item.base_url}</div>
                      {item.status === 'failed' && item.error?.trim() ? (
                        <div className="text-xs text-red-600">{item.error}</div>
                      ) : (
                        <div className="text-xs text-gray-500">{websiteScanStatusLabels[item.status]}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={item.status !== 'completed' || !item.mind_map_id}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenMindMap(item);
                          }}
                        >
                          Карта
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={item.status !== 'completed'}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenList(item.id);
                          }}
                        >
                          Список
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell w-40">
                      {item.status === 'failed' ? (
                        <div className="flex max-w-[160px] flex-col gap-1">
                          <Progress value={0} intent="error" />
                          <span className="text-xs text-gray-500">&nbsp;</span>
                        </div>
                      ) : (
                        <div className="flex max-w-[160px] flex-col gap-1">
                          <Progress value={progressInfo.percent} intent="default" />
                          <span className="text-xs text-gray-500">
                            {progressInfo.label}
                          </span>
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {formatInTenantTimezone(item.created_at, timeZone, {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                      })}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleRerun(item.id);
                          }}
                          disabled={rerunId === item.id || !canEdit}
                          title="Перезапустить"
                        >
                          {rerunId === item.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDelete(item.id);
                          }}
                          disabled={deletingId === item.id || !canEdit}
                          title="Удалить"
                        >
                          {deletingId === item.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4 text-red-600" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                    );
                  })()
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AnalyticsPageClient() {
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelAnalysisRecord['channel_type']>('telegram');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [history, setHistory] = useState<ChannelAnalysisRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const searchParams = useSearchParams();
  const initialTab = useMemo(() => {
    const tab = searchParams.get('tab');
    if (tab === 'single' || tab === 'project' || tab === 'weekly' || tab === 'website') return tab;
    return 'single';
  }, [searchParams]);
  const [activeTab, setActiveTab] = useState<'single' | 'project' | 'weekly' | 'website'>(initialTab);
  const router = useRouter();
  const isHistoryTabActiveRef = useRef(false);
  const hasActiveHistory = useMemo(
    () => history.some((item) => item.status === 'pending' || item.status === 'in_progress'),
    [history],
  );

  const loadHistory = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent && isHistoryTabActiveRef.current) {
      setIsHistoryLoading(true);
    }
    try {
      const data = await analyticsApi.listAnalyses();
      if (isHistoryTabActiveRef.current) {
        setHistory(data);
      }
    } catch (error) {
    } finally {
      if (!options?.silent && isHistoryTabActiveRef.current) {
        setIsHistoryLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (activeTab !== 'single') return;
    isHistoryTabActiveRef.current = true;
    void loadHistory();
    return () => {
      isHistoryTabActiveRef.current = false;
    };
  }, [activeTab, loadHistory]);

  useEffect(() => {
    if (activeTab !== 'single' || !hasActiveHistory) return;
    const intervalId = setInterval(() => {
      void loadHistory({ silent: true });
    }, 5000);
    return () => clearInterval(intervalId);
  }, [activeTab, hasActiveHistory, loadHistory]);

  const handleAnalyzeChannel = async () => {
    const trimmedChannel = channelUrl.trim();
    if (!trimmedChannel) {
      toast.error('Введите URL канала');
      return;
    }

    setIsAnalyzing(true);
    try {
      const result = await analyticsApi.analyzeChannel({
        channel_url: trimmedChannel,
        channel_type: channelType,
      });

      if (result.success) {
        toast.success('Анализ канала запущен');
        void loadHistory({ silent: true });
      } else {
        toast.error(result.error || 'Не удалось запустить анализ');
      }
    } catch (error) {
      if (error instanceof ApiError) {
        try {
          const payload = error.body ? JSON.parse(error.body) : null;
          const message = payload?.error || payload?.detail || payload?.message;
          if (message) {
            toast.error(String(message));
            return;
          }
        } catch {}
      }
      toast.error('Ошибка при запуске анализа');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleOpenAnalysis = (analysisId: number) => {
    router.push(`/analytics/${analysisId}`);
  };

  const handleDeleteAnalysis = async (analysisId: number, event?: MouseEvent) => {
    event?.stopPropagation();
    if (deletingId === analysisId) return;

    setDeletingId(analysisId);
    try {
      await analyticsApi.deleteAnalysis(analysisId);
      setHistory((prev) => prev.filter((item) => item.id !== analysisId));
      toast.success('Запись удалена из истории');
    } catch (error) {
      toast.error('Не удалось удалить анализ');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="mb-4">
        <h1 className="text-3xl font-bold">Аналитика</h1>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as 'single' | 'project' | 'weekly' | 'website')}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="single">Один канал</TabsTrigger>
          <TabsTrigger value="project">Мой проект</TabsTrigger>
          <TabsTrigger value="weekly">Подборка за неделю</TabsTrigger>
          <TabsTrigger value="website">Website</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="space-y-8">
          <div className="space-y-4 max-w-md">
            <p className="text-sm text-muted-foreground">Используйте для анализа каналов конкурентов.</p>
            <div className="space-y-2">
              <Label htmlFor="channelType">Тип канала</Label>
              <Select value={channelType} onValueChange={(value) => setChannelType(value as ChannelAnalysisRecord['channel_type'])}>
                <SelectTrigger id="channelType">
                  <SelectValue placeholder="Выберите платформу" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="instagram">Instagram</SelectItem>
                  <SelectItem value="youtube">YouTube</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="channelUrl">
                  {channelInputLabels[channelType as 'telegram' | 'instagram' | 'youtube'] ?? 'Ссылка на канал'}
                </Label>
                {channelType === 'telegram' ? (
                  <Link href="/analytics/tgstat" className="text-xs text-blue-600 hover:underline">
                    Или выбрать из списка
                  </Link>
                ) : null}
              </div>
              <Input
                id="channelUrl"
                placeholder={
                  channelPlaceholders[channelType as 'telegram' | 'instagram' | 'youtube'] ?? 'Введите URL канала'
                }
                value={channelUrl}
                onChange={(e) => setChannelUrl(e.target.value)}
              />
              <p className="text-xs text-gray-500">
                {channelHints[channelType as 'telegram' | 'instagram' | 'youtube'] ??
                  'Можно указать ссылку на публичный канал.'}
              </p>
            </div>

            <Button
              onClick={handleAnalyzeChannel}
              disabled={isAnalyzing || !channelUrl.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700"
            >
              {isAnalyzing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Запуск анализа...
                </>
              ) : (
                'Запустить анализ'
              )}
            </Button>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-semibold">История аналитики</h2>
                <p className="text-gray-500 text-sm">Список обновляется автоматически, пока есть активные задачи.</p>
              </div>
            </div>

            {isHistoryLoading ? (
              <div className="flex items-center gap-2 text-gray-500 mt-6">
                <Loader2 className="h-4 w-4 animate-spin" />
                Загружаем список
              </div>
            ) : history.length === 0 ? (
              <p className="text-sm text-gray-500 mt-4">Пока нет завершенных анализов. Запустите первый анализ выше.</p>
            ) : (
              <div className="mt-6 rounded-lg border bg-white shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead>Канал</TableHead>
                      <TableHead>Тип</TableHead>
                      <TableHead className="hidden md:table-cell">Прогресс</TableHead>
                      <TableHead>Создан</TableHead>
                      <TableHead className="w-24 text-right">Действия</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {history.map((item) => (
                      <TableRow key={item.id} className="cursor-pointer" onClick={() => handleOpenAnalysis(item.id)}>
                        <TableCell className="space-y-1">
                          <div className="font-medium text-gray-900">{item.channel_name || item.channel_url}</div>
                          <div className="text-xs text-gray-500">{item.channel_url}</div>
                          {item.status === 'failed' && item.error?.trim() ? (
                            <div className="text-xs text-red-600 break-all">{item.error}</div>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-sm text-gray-600">
                          {channelTypeLabels[item.channel_type] || item.channel_type}
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          {item.status === 'failed' ? (
                            <div className="flex flex-col gap-1">
                              <Progress value={0} intent="error" />
                              <span className="text-xs text-gray-500">&nbsp;</span>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-1">
                              <Progress value={item.progress} intent="default" />
                              <span className="text-xs text-gray-500">{item.progress}%</span>
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-gray-600">
                          {formatInTenantTimezone(item.created_at, tenantTimezone, {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(event) => handleDeleteAnalysis(item.id, event)}
                            disabled={deletingId === item.id}
                          >
                            {deletingId === item.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4 text-red-600" />
                            )}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="project">
          <MyProjectTab timeZone={tenantTimezone} />
        </TabsContent>

        <TabsContent value="weekly">
          <WeeklySourcesTab timeZone={tenantTimezone} />
        </TabsContent>

        <TabsContent value="website">
          <WebsiteTab isActive={activeTab === 'website'} timeZone={tenantTimezone} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
