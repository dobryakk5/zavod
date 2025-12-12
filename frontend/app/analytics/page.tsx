'use client';

import { useState } from 'react';
import { analyticsApi } from '@/lib/api/analytics';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2 } from 'lucide-react';

type ChannelType = 'telegram' | 'instagram' | 'youtube' | 'vkontakte';

export default function AnalyticsPage() {
  const [channelUrl, setChannelUrl] = useState('');
  const [channelType, setChannelType] = useState<ChannelType>('telegram');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

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
    </div>
  );
}
