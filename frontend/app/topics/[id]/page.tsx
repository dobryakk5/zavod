'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { topicsApi } from '@/lib/api/topics';
import { trendsApi } from '@/lib/api/trends';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { TopicActions } from '@/components/topics/topic-actions';
import { TrendCard } from '@/components/trends/trend-card';
import { ArrowLeft, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';
import { useRole } from '@/lib/hooks';
import type { TopicDetail, TrendItem } from '@/lib/types';

interface TopicPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function TopicPage({ params }: TopicPageProps) {
  const router = useRouter();
  const { canEdit } = useRole();
  const [topic, setTopic] = useState<TopicDetail | null>(null);
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [topicId, setTopicId] = useState<number | null>(null);

  useEffect(() => {
    params.then((p) => setTopicId(parseInt(p.id)));
  }, [params]);

  useEffect(() => {
    if (topicId !== null) {
      loadTopic();
      loadTrends();
    }
  }, [topicId]);

  const loadTopic = async () => {
    if (topicId === null) return;
    try {
      const data = await topicsApi.get(topicId);
      setTopic(data);
    } catch (error) {
      toast.error('Не удалось загрузить тему');
    }
  };

  const loadTrends = async () => {
    if (topicId === null) return;
    setLoading(true);
    try {
      const data = await trendsApi.list({ topic: topicId });
      setTrends(data);
    } catch (error) {
      toast.error('Не удалось загрузить тренды');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (topicId === null) return;
    if (!confirm('Вы уверены, что хотите удалить эту тему?')) {
      return;
    }

    try {
      await topicsApi.delete(topicId);
      toast.success('Тема успешно удалена');
      router.push('/topics');
    } catch (error) {
      toast.error('Ошибка при удалении темы');
    }
  };

  if (!topic) {
    return <div className="container mx-auto py-8">Загрузка...</div>;
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/topics">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к темам
          </Button>
        </Link>

        {canEdit && (
          <div className="flex gap-2">
            <Button variant="destructive" size="sm" onClick={handleDelete}>
              <Trash2 className="h-4 w-4 mr-2" />
              Удалить
            </Button>
          </div>
        )}
      </div>

      {/* Topic Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">{topic.name}</h1>
        {topic.description && (
          <p className="text-gray-600 mb-4">{topic.description}</p>
        )}

        {/* Keywords */}
        {topic.keywords && topic.keywords.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold mb-2">Ключевые слова:</h3>
            <div className="flex flex-wrap gap-2">
              {topic.keywords.map((keyword, idx) => (
                <Badge key={idx} variant="secondary">
                  {keyword}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Sources */}
        {topic.sources && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold mb-2">Источники:</h3>
            <div className="flex flex-wrap gap-2">
              {topic.sources.google_trends && (
                <Badge variant="outline">Google Trends</Badge>
              )}
              {topic.sources.news_api && (
                <Badge variant="outline">News API</Badge>
              )}
              {topic.sources.youtube && (
                <Badge variant="outline">YouTube</Badge>
              )}
            </div>
          </div>
        )}

        {/* Actions */}
        {topicId !== null && (
          <div className="mt-4">
            <TopicActions topicId={topicId} />
          </div>
        )}
      </div>

      {/* Trends */}
      <div>
        <h2 className="text-2xl font-bold mb-4">
          Тренды ({trends.length})
        </h2>

        {loading && <div className="text-center py-8">Загрузка трендов...</div>}

        {!loading && trends.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            Нет найденных трендов. Используйте кнопку &quot;Поиск&quot; для поиска нового контента.
          </div>
        )}

        {!loading && trends.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {trends.map((trend) => (
              <TrendCard key={trend.id} trend={trend} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
