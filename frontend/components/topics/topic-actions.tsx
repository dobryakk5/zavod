'use client';

import { topicsApi } from '@/lib/api/topics';
import { Button } from '@/components/ui/button';
import { useRole } from '@/lib/hooks';
import { toast } from 'sonner';
import { Search, FileText, Hash } from 'lucide-react';

interface TopicActionsProps {
  topicId: number;
}

export function TopicActions({ topicId }: TopicActionsProps) {
  const { canEdit } = useRole();

  const handleDiscoverContent = async () => {
    try {
      await topicsApi.discoverContent(topicId);
      toast.success('Поиск контента запущен');
    } catch (error) {
      toast.error('Ошибка при запуске поиска контента');
    }
  };

  const handleGeneratePosts = async () => {
    try {
      await topicsApi.generatePosts(topicId);
      toast.success('Генерация постов запущена');
    } catch (error) {
      toast.error('Ошибка при генерации постов');
    }
  };

  const handleGenerateSEO = async () => {
    try {
      await topicsApi.generateSEO(topicId);
      toast.success('Генерация SEO запущена');
    } catch (error) {
      toast.error('Ошибка при генерации SEO');
    }
  };

  return (
    <div className="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        onClick={handleDiscoverContent}
        disabled={!canEdit}
        title="Найти новый контент"
      >
        <Search className="h-4 w-4 mr-1" />
        Поиск
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={handleGeneratePosts}
        disabled={!canEdit}
        title="Сгенерировать посты"
      >
        <FileText className="h-4 w-4 mr-1" />
        Посты
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={handleGenerateSEO}
        disabled={!canEdit}
        title="Сгенерировать SEO"
      >
        <Hash className="h-4 w-4 mr-1" />
        SEO
      </Button>
    </div>
  );
}
