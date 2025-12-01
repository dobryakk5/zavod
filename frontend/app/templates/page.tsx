'use client';

import { useState, useEffect } from 'react';
import { templatesApi } from '@/lib/api/templates';
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
import { Plus, Edit } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useRole } from '@/lib/hooks';
import type { ContentTemplate } from '@/lib/types';

export default function TemplatesPage() {
  const router = useRouter();
  const { canEdit } = useRole();
  const [templates, setTemplates] = useState<ContentTemplate[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const data = await templatesApi.list();
      setTemplates(data);
    } catch (error) {
      toast.error('Не удалось загрузить шаблоны');
    } finally {
      setLoading(false);
    }
  };

  const getToneName = (tone: string) => {
    switch (tone) {
      case 'professional':
        return 'Профессиональный';
      case 'casual':
        return 'Неформальный';
      case 'humorous':
        return 'Юмористический';
      case 'educational':
        return 'Образовательный';
      default:
        return tone;
    }
  };

  const getLengthName = (length: string) => {
    switch (length) {
      case 'short':
        return 'Короткий';
      case 'medium':
        return 'Средний';
      case 'long':
        return 'Длинный';
      default:
        return length;
    }
  };

  return (
    <div className="container mx-auto py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Шаблоны контента</h1>
          <p className="text-gray-500 mt-2">
            Управляйте шаблонами для генерации контента с помощью AI
          </p>
        </div>
        {canEdit && (
          <Button onClick={() => router.push('/templates/new')}>
            <Plus className="h-4 w-4 mr-2" />
            Создать шаблон
          </Button>
        )}
      </div>

      {loading && <div className="text-center py-8">Загрузка...</div>}

      {!loading && templates.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          Нет созданных шаблонов
        </div>
      )}

      {!loading && templates.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Тип</TableHead>
              <TableHead>Тон</TableHead>
              <TableHead>Длина</TableHead>
              <TableHead>Язык</TableHead>
              <TableHead>Промпт</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {templates.map((template) => (
              <TableRow key={template.id}>
                <TableCell>
                  <Badge variant="secondary">
                    {template.type === 'post' ? 'Пост' : 'Эпизод'}
                  </Badge>
                </TableCell>
                <TableCell>{getToneName(template.tone)}</TableCell>
                <TableCell>{getLengthName(template.length)}</TableCell>
                <TableCell>
                  <Badge variant="outline">{template.language}</Badge>
                </TableCell>
                <TableCell className="max-w-xs truncate font-mono text-xs">
                  {template.prompt_template}
                </TableCell>
                <TableCell className="text-right">
                  {canEdit && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => router.push(`/templates/${template.id}`)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
