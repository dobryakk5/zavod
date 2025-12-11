'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRole } from '@/lib/hooks';
import { analyticsApi } from '@/lib/api/analytics';
import { clientApi } from '@/lib/api/client';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Loader2, CheckCircle, XCircle, RefreshCw, ExternalLink } from 'lucide-react';

type ChannelType = 'telegram' | 'instagram' | 'youtube' | 'vkontakte';
const CHANNEL_TYPES: ChannelType[] = ['telegram', 'instagram', 'youtube', 'vkontakte'];

const normalizeChannelType = (value?: string | null): ChannelType | undefined => {
  if (!value) return undefined;
  const normalized = value.trim().toLowerCase() as ChannelType;
  return CHANNEL_TYPES.includes(normalized) ? normalized : undefined;
};

interface AnalysisStatusResponse {
  task_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress?: number;
  result?: {
    channel_name: string;
    subscribers: number;
    avg_views: number;
    avg_reach: number;
    avg_engagement: number;
    top_posts: Array<{
      title: string;
      views: number;
      engagement: number;
      url: string;
    }>;
    keywords: string[];
    topics: string[];
    content_types: string[];
    posting_schedule: Array<{
      day: string;
      hour: number;
      posts_count: number;
    }>;
  };
  error?: string;
}

export default function AnalyticsPage() {
  const { canEdit } = useRole();
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelType>('telegram');
  const [initialSettings, setInitialSettings] = useState<{ url?: string; type?: ChannelType } | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null);
  const [polling, setPolling] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 30; // 5 minutes with 10s intervals

  useEffect(() => {
    const loadClientSettings = async () => {
      try {
        const settings = await clientApi.getSettings();
        const normalizedType = normalizeChannelType(settings.ai_analysis_channel_type);

        if (settings.ai_analysis_channel_url) {
          setChannelUrl(settings.ai_analysis_channel_url);
        }
        if (normalizedType) {
          setChannelType(normalizedType);
        }

        setInitialSettings({
          url: settings.ai_analysis_channel_url || undefined,
          type: normalizedType,
        });
      } catch (error) {
        console.error('Failed to load AI analysis settings', error);
        setSettingsError('Не удалось загрузить сохраненный канал из настроек клиента');
      }
    };

    loadClientSettings();
  }, []);

  // Polling effect
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (polling && taskId && attempts < maxAttempts) {
      interval = setInterval(async () => {
        try {
          const result = await analyticsApi.getAnalysisStatus(taskId);
          setStatus(result);
          
          if (result.status === 'completed' || result.status === 'failed') {
            setPolling(false);
            setAttempts(0);
            if (result.status === 'completed') {
              toast.success('Анализ канала завершен');
            } else {
              toast.error(result.error || 'Анализ не удался');
            }
          } else {
            setAttempts(prev => prev + 1);
          }
        } catch (error) {
          console.error('Polling error:', error);
          setPolling(false);
          setAttempts(0);
          toast.error('Ошибка при получении статуса анализа');
        }
      }, 10000); // Poll every 10 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [polling, taskId, attempts, maxAttempts]);

  const handleValidateChannel = async () => {
    const trimmedChannel = channelUrl.trim();
    if (!trimmedChannel) {
      toast.error('Введите URL канала или сохраните его в настройках клиента');
      return;
    }

    try {
      const result = await analyticsApi.validateChannel({
        channel_url: trimmedChannel,
        channel_type: channelType
      });
      
      if (result.valid) {
        toast.success('Канал валиден');
      } else {
        toast.error(result.error || 'Неверный URL канала');
      }
    } catch (error) {
      toast.error('Ошибка валидации канала');
    }
  };

  const handleAnalyzeChannel = async () => {
    const trimmedChannel = channelUrl.trim();
    if (!trimmedChannel) {
      toast.error('Введите URL канала или сохраните его в настройках клиента');
      return;
    }

    if (!canEdit) {
      toast.error('У вас нет прав для анализа каналов');
      return;
    }

    setIsAnalyzing(true);
    try {
      const result = await analyticsApi.analyzeChannel({
        channel_url: trimmedChannel,
        channel_type: channelType
      });

      if (result.success) {
        setTaskId(result.task_id || '');
        setPolling(true);
        setAttempts(0);
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

  const handleRetry = () => {
    if (taskId) {
      setPolling(true);
      setAttempts(0);
      setStatus(null);
    }
  };

  const getStatusIcon = (statusStr: string) => {
    switch (statusStr) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Аналитика канала</h1>
          <p className="text-gray-500 mt-2">
            Проанализируйте канал и получите рекомендации по контенту
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Analysis Form */}
        <Card>
          <CardHeader>
            <CardTitle>Анализ канала</CardTitle>
            <CardDescription>
              Используйте канал из настроек клиента или введите другой URL для единичного анализа
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              {initialSettings?.url ? (
                <>
                  Канал по умолчанию взят из&nbsp;
                  <Link href="/settings" className="text-blue-600 hover:underline">
                    настроек клиента
                  </Link>
                  : <span className="font-semibold break-all">{initialSettings.url}</span>
                </>
              ) : (
                <>
                  Чтобы не вводить данные каждый раз, заполните канал для AI анализа в&nbsp;
                  <Link href="/settings" className="text-blue-600 hover:underline">
                    настройках клиента
                  </Link>
                  .
                </>
              )}
            </div>
            {settingsError && (
              <p className="text-sm text-red-500">{settingsError}</p>
            )}

            <div className="space-y-2">
              <Label htmlFor="channelType">Тип канала</Label>
              <Select value={channelType} onValueChange={(value: ChannelType) => setChannelType(value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите тип канала" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="instagram">Instagram</SelectItem>
                  <SelectItem value="youtube">YouTube</SelectItem>
                  <SelectItem value="vkontakte">VKontakte</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="channelUrl">URL канала</Label>
              <Input
                id="channelUrl"
                placeholder="Введите URL канала"
                value={channelUrl}
                onChange={(e) => setChannelUrl(e.target.value)}
              />
            </div>

            <div className="flex gap-2">
              <Button onClick={handleValidateChannel} disabled={isAnalyzing || !channelUrl.trim()}>
                Проверить канал
              </Button>
              <Button 
                onClick={handleAnalyzeChannel} 
                disabled={isAnalyzing || !canEdit || !channelUrl.trim()}
                className="bg-blue-600 hover:bg-blue-700"
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

            {taskId && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Статус анализа</Label>
                  <Button variant="ghost" size="sm" onClick={handleRetry} disabled={polling}>
                    <RefreshCw className={`h-4 w-4 ${polling ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
                <div className="flex items-center gap-3">
                  {status ? getStatusIcon(status.status) : <Loader2 className="h-5 w-5 animate-spin" />}
                  <span className="font-medium">
                    {status ? status.status : 'pending'}
                  </span>
                </div>
                {status?.progress && (
                  <Progress value={status.progress} className="w-full" />
                )}
                {status?.error && (
                  <div className="text-red-500 text-sm">{status.error}</div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Analysis Results */}
        {status && status.status === 'completed' && status.result && (
          <div className="space-y-6">
            {/* Channel Info */}
            <Card>
              <CardHeader>
                <CardTitle>Информация о канале</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm text-gray-500">Название</Label>
                  <div className="font-semibold">{status.result.channel_name}</div>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-gray-500">Подписчики</Label>
                  <div className="font-semibold">{status.result.subscribers.toLocaleString()}</div>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-gray-500">Средние просмотры</Label>
                  <div className="font-semibold">{status.result.avg_views.toLocaleString()}</div>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-gray-500">Вовлеченность</Label>
                  <div className="font-semibold">{status.result.avg_engagement.toFixed(2)}%</div>
                </div>
              </CardContent>
            </Card>

            {/* Top Posts */}
            <Card>
              <CardHeader>
                <CardTitle>Топ посты</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {status.result.top_posts.map((post, index) => (
                    <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                      <div>
                        <div className="font-semibold">{post.title}</div>
                        <div className="text-sm text-gray-500">
                          Просмотры: {post.views.toLocaleString()} • Вовлеченность: {post.engagement.toFixed(2)}%
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => window.open(post.url, '_blank')}>
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Открыть
                      </Button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Keywords and Topics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Ключевые слова</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {status.result.keywords.map((keyword, index) => (
                      <Badge key={index} variant="secondary">{keyword}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Темы</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {status.result.topics.map((topic, index) => (
                      <Badge key={index} variant="outline">{topic}</Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Content Types */}
            <Card>
              <CardHeader>
                <CardTitle>Типы контента</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {status.result.content_types.map((type, index) => (
                    <Badge key={index} variant="default">{type}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Posting Schedule */}
            <Card>
              <CardHeader>
                <CardTitle>График публикаций</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-7 gap-2">
                  {status.result.posting_schedule.map((slot, index) => (
                    <div key={index} className="text-center p-2 border rounded">
                      <div className="font-semibold text-sm">{slot.day}</div>
                      <div className="text-2xl font-bold">{slot.hour}:00</div>
                      <div className="text-xs text-gray-500">{slot.posts_count} постов</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Status Messages */}
        {status && status.status === 'in_progress' && (
          <Card>
            <CardHeader>
              <CardTitle>Идет анализ...</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Пожалуйста, подождите. Анализ может занять несколько минут.</span>
              </div>
              {status.progress && (
                <Progress value={status.progress} className="w-full mt-4" />
              )}
            </CardContent>
          </Card>
        )}

        {status && status.status === 'failed' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-red-500">Анализ не удался</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div>Ошибка: {status.error || 'Неизвестная ошибка'}</div>
                <Button onClick={handleRetry} variant="outline">
                  Повторить попытку
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
