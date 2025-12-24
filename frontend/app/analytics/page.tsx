'use client';

import { useEffect, useState, type MouseEvent } from 'react';
import { useRouter } from 'next/navigation';
import { analyticsApi, type ChannelAnalysisRecord } from '@/lib/api/analytics';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Loader2, Trash2 } from 'lucide-react';

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

export default function AnalyticsPage() {
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelAnalysisRecord['channel_type']>('telegram');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [history, setHistory] = useState<ChannelAnalysisRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const router = useRouter();

  useEffect(() => {
    let isMounted = true;
    let intervalId: ReturnType<typeof setInterval>;

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
      clearInterval(intervalId);
    };
  }, []);

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
        channel_type: channelType
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
    if (deletingId === analysisId) {
      return;
    }
    const confirmed = typeof window !== 'undefined' ? window.confirm('Удалить запись из истории аналитики?') : true;
    if (!confirmed) {
      return;
    }

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
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Аналитика каналов</h1>
        <p className="text-gray-500 mt-2">
          Проанализируйте свой канал и каналы конкурентов
        </p>
      </div>

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

      <div className="mt-12">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold">История аналитики</h2>
            <p className="text-gray-500 text-sm">Страница обновляет список каждые 5 секунд автоматически.</p>
          </div>
        </div>

        {isHistoryLoading ? (
          <div className="flex items-center gap-2 text-gray-500 mt-6">
            <Loader2 className="h-4 w-4 animate-spin" />
            Загружаем список анализов
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
                          <Progress
                            value={item.progress}
                            intent={item.status === 'failed' ? 'error' : 'default'}
                          />
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
    </div>
  );
}
