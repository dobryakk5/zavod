'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { templatesApi } from '@/lib/api/templates';
import { TemplateForm } from '@/components/templates/template-form';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';

export default function NewTemplatePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (data: any) => {
    setLoading(true);
    try {
      await templatesApi.create(data);
      toast.success('Шаблон успешно создан');
      router.push('/templates');
    } catch (error) {
      toast.error('Ошибка при создании шаблона');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container max-w-4xl mx-auto py-8">
      <div className="mb-6">
        <Link href="/templates">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к шаблонам
          </Button>
        </Link>
      </div>

      <div className="mb-8">
        <h1 className="text-3xl font-bold">Создать шаблон</h1>
        <p className="text-gray-500 mt-2">
          Создайте новый шаблон для генерации контента. Вы можете использовать предустановленные типы и тоны или создать свои.
        </p>
      </div>

      <TemplateForm onSubmit={handleSubmit} loading={loading} />
    </div>
  );
}
