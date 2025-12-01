'use client';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GenerateFromTrendMenu } from './generate-from-trend-menu';
import type { TrendItem } from '@/lib/types';

interface TrendCardProps {
  trend: TrendItem;
}

export function TrendCard({ trend }: TrendCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{trend.title}</CardTitle>
            <CardDescription className="mt-1">
              Источник: {trend.source}
            </CardDescription>
          </div>
          {trend.is_used && (
            <Badge variant="secondary">Использован</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-gray-600 line-clamp-3">
          {trend.description || 'Нет описания'}
        </p>
        {trend.url && (
          <a
            href={trend.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline mt-2 inline-block"
          >
            Открыть источник →
          </a>
        )}
      </CardContent>
      <CardFooter className="flex items-center justify-between">
        <span className="text-xs text-gray-500">
          {trend.discovered_at && new Date(trend.discovered_at).toLocaleDateString('ru-RU')}
        </span>
        <GenerateFromTrendMenu trendId={trend.id} />
      </CardFooter>
    </Card>
  );
}
