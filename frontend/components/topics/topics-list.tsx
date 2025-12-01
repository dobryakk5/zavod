'use client';

import { useState, useEffect } from 'react';
import { topicsApi } from '@/lib/api/topics';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { TopicActions } from './topic-actions';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import type { Topic } from '@/lib/types';

export function TopicsList() {
  const router = useRouter();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTopics();
  }, []);

  const loadTopics = async () => {
    setLoading(true);
    try {
      const data = await topicsApi.list();
      setTopics(data);
    } catch (error) {
      toast.error('Не удалось загрузить темы');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">Загрузка...</div>;
  }

  if (topics.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        Нет созданных тем
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Название</TableHead>
          <TableHead>Описание</TableHead>
          <TableHead>Ключевые слова</TableHead>
          <TableHead>Источники</TableHead>
          <TableHead className="text-right">Действия</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {topics.map((topic) => (
          <TableRow
            key={topic.id}
            className="cursor-pointer hover:bg-gray-50"
            onClick={() => router.push(`/topics/${topic.id}`)}
          >
            <TableCell className="font-medium">{topic.name}</TableCell>
            <TableCell className="max-w-xs truncate">
              {topic.description || '—'}
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {topic.keywords?.slice(0, 3).map((keyword, idx) => (
                  <Badge key={idx} variant="secondary" className="text-xs">
                    {keyword}
                  </Badge>
                ))}
                {(topic.keywords?.length || 0) > 3 && (
                  <Badge variant="outline" className="text-xs">
                    +{(topic.keywords?.length || 0) - 3}
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {topic.sources?.google_trends && (
                  <Badge variant="outline" className="text-xs">
                    Google Trends
                  </Badge>
                )}
                {topic.sources?.news_api && (
                  <Badge variant="outline" className="text-xs">
                    News API
                  </Badge>
                )}
                {topic.sources?.youtube && (
                  <Badge variant="outline" className="text-xs">
                    YouTube
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
              <TopicActions topicId={topic.id} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
