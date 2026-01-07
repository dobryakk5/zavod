'use client';

import { useEffect, useMemo, useState, type MouseEvent } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  analyticsApi,
  type ChannelAnalysisRecord,
  type WeeklySourceBatch,
} from '@/lib/api/analytics';
import { websitesApi, type WebsiteScan, type WebsiteScanStatus } from '@/lib/api/websites';
import { clientApi } from '@/lib/api/client';
import type { ClientSettings } from '@/lib/types';
import { useRole } from '@/lib/hooks';
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

type SourceFields = Pick<
  ClientSettings,
  | 'telegram_source_channels'
  | 'rss_source_feeds'
  | 'youtube_source_channels'
  | 'instagram_source_accounts'
  | 'vkontakte_source_groups'
>;

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

function WeeklySourcesTab() {
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
                    Неделя с {new Date(batch.week_start).toLocaleDateString('ru-RU')}
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

function WebsiteTab() {
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

  const loadHistory = async (options?: { silent?: boolean }) => {
    if (!options?.silent) setLoading(true);
    try {
      const data = await websitesApi.listScans();
      setHistory(data);
    } catch (error) {
      toast.error('Не удалось загрузить историю сканов');
    } finally {
      if (!options?.silent) setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const load = async (silent = false) => {
      if (!isMounted) return;
      await loadHistory({ silent });
    };

    void load(false);
    intervalId = setInterval(() => void load(true), 5000);
    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

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
          <p className="text-gray-500 text-sm">Обновление каждые 5 секунд.</p>
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
                    <TableCell className="text-sm text-gray-600">{new Date(item.created_at).toLocaleDateString('ru-RU')}</TableCell>
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
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelAnalysisRecord['channel_type']>('telegram');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [history, setHistory] = useState<ChannelAnalysisRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const searchParams = useSearchParams();
  const initialTab = useMemo(() => {
    const tab = searchParams.get('tab');
    if (tab === 'single' || tab === 'weekly' || tab === 'website') return tab;
    return 'single';
  }, [searchParams]);
  const [activeTab, setActiveTab] = useState<'single' | 'weekly' | 'website'>(initialTab);
  const router = useRouter();

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (activeTab !== 'single') return;
    let isMounted = true;
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const fetchHistory = async () => {
      try {
        const data = await analyticsApi.listAnalyses();
        if (isMounted) {
          setHistory(data);
          setIsHistoryLoading(false);
        }
      } catch (error) {
        if (isMounted) {
          setIsHistoryLoading(false);
        }
      }
    };

    fetchHistory();
    intervalId = setInterval(fetchHistory, 5000);

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeTab]);

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
      } else {
        toast.error(result.error || 'Не удалось запустить анализ');
      }
    } catch (error) {
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
    const confirmed =
      typeof window !== 'undefined' ? window.confirm('Удалить запись из истории аналитики?') : true;
    if (!confirmed) return;

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
        <p className="text-gray-500 mt-2">Один канал, подборка за неделю или Website</p>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'single' | 'weekly' | 'website')} className="space-y-6">
        <TabsList>
          <TabsTrigger value="single">Один канал</TabsTrigger>
          <TabsTrigger value="weekly">Подборка за неделю</TabsTrigger>
          <TabsTrigger value="website">Website</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="space-y-8">
          <div className="space-y-4 max-w-md">
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
              <Label htmlFor="channelUrl">
                {channelInputLabels[channelType as 'telegram' | 'instagram' | 'youtube'] ?? 'Ссылка на канал'}
              </Label>
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
                <p className="text-gray-500 text-sm">Страница обновляет список каждые 5 секунд автоматически.</p>
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
                          {new Date(item.created_at).toLocaleString('ru-RU')}
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

        <TabsContent value="weekly">
          <WeeklySourcesTab />
        </TabsContent>

        <TabsContent value="website">
          <WebsiteTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
