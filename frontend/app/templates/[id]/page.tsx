'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { templatesApi } from '@/lib/api/templates';
import { TemplateForm } from '@/components/templates/template-form';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';
import { useRole } from '@/lib/hooks';
import type { ContentTemplate } from '@/lib/types';

interface TemplatePageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function TemplatePage({ params }: TemplatePageProps) {
  const router = useRouter();
  const { canEdit } = useRole();
  const [template, setTemplate] = useState<ContentTemplate | null>(null);
  const [loading, setLoading] = useState(false);
  const [templateId, setTemplateId] = useState<number | null>(null);

  useEffect(() => {
    params.then((p) => setTemplateId(parseInt(p.id)));
  }, [params]);

  useEffect(() => {
    if (templateId !== null) {
      loadTemplate();
    }
  }, [templateId]);

  const loadTemplate = async () => {
    if (templateId === null) return;
    try {
      const data = await templatesApi.get(templateId);
      setTemplate(data);
    } catch (error) {
      toast.error('Не удалось загрузить шаблон');
    }
  };

  const handleSubmit = async (data: any) => {
    if (templateId === null) return;
    setLoading(true);
    try {
      await templatesApi.update(templateId, data);
      toast.success('Шаблон успешно обновлен');
      await loadTemplate();
    } catch (error) {
      toast.error('Ошибка при обновлении шаблона');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (templateId === null) return;
    if (!confirm('Вы уверены, что хотите удалить этот шаблон?')) {
      return;
    }

    try {
      await templatesApi.delete(templateId);
      toast.success('Шаблон успешно удален');
      router.push('/templates');
    } catch (error) {
      toast.error('Ошибка при удалении шаблона');
    }
  };

  if (!template) {
    return <div className="container max-w-4xl mx-auto py-8">Загрузка...</div>;
  }

  return (
    <div className="container max-w-4xl mx-auto py-8">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/templates">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к шаблонам
          </Button>
        </Link>

        {canEdit && (
          <Button variant="destructive" size="sm" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Удалить
          </Button>
        )}
      </div>

      <div className="mb-8">
        <h1 className="text-3xl font-bold">Редактировать шаблон</h1>
        <p className="text-gray-500 mt-2">
          Редактирование шаблона контента. Тип и тон можно изменять, длина и язык остаются неизменными после создания.
        </p>
      </div>

      <TemplateForm template={template} onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
