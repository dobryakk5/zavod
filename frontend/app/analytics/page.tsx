'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { analyticsApi, type ChannelAnalysisRecord } from '@/lib/api/analytics';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Loader2 } from 'lucide-react';

type ChannelType = 'telegram' | 'instagram' | 'youtube' | 'vkontakte';

const channelTypeLabels: Record<ChannelType, string> = {
  telegram: 'Telegram',
  instagram: 'Instagram',
  youtube: 'YouTube',
  vkontakte: 'VKontakte',
};

export default function AnalyticsPage() {
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelType>('telegram');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [history, setHistory] = useState<ChannelAnalysisRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
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

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Аналитика канала</h1>
        <p className="text-gray-500 mt-2">
          Проанализируйте канал и получите рекомендации по контенту
        </p>
      </div>

      <div className="space-y-4 max-w-md">
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
                      <div className="flex flex-col gap-1">
                        <Progress value={item.progress} />
                        <span className="text-xs text-gray-500">{item.progress}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {new Date(item.created_at).toLocaleString('ru-RU')}
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
