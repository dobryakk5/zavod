'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ContentTemplate } from '@/lib/types';

const templateFormSchema = z.object({
  type: z.enum(['post', 'story_episode']),
  tone: z.enum(['professional', 'casual', 'humorous', 'educational']),
  length: z.enum(['short', 'medium', 'long']),
  language: z.string().min(2).max(10),
  prompt_template: z.string().min(1, 'Шаблон промпта обязателен'),
  additional_instructions: z.string().optional(),
});

type TemplateFormValues = z.infer<typeof templateFormSchema>;

interface TemplateFormProps {
  template?: ContentTemplate;
  onSubmit: (data: TemplateFormValues) => Promise<void>;
  loading?: boolean;
}

export function TemplateForm({ template, onSubmit, loading = false }: TemplateFormProps) {
  const isEditing = !!template;

  const form = useForm<TemplateFormValues>({
    resolver: zodResolver(templateFormSchema),
    defaultValues: {
      type: template?.type || 'post',
      tone: template?.tone || 'professional',
      length: template?.length || 'medium',
      language: template?.language || 'ru',
      prompt_template: template?.prompt_template || '',
      additional_instructions: template?.additional_instructions || '',
    },
  });

  const handleSubmit = async (data: TemplateFormValues) => {
    try {
      await onSubmit(data);
    } catch (error) {
      // Error handling is done in the parent component
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* Basic fields - readonly if editing */}
        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Тип контента</FormLabel>
                {isEditing ? (
                  <div className="mt-2">
                    <Badge variant="secondary" className="text-base py-1 px-3">
                      {field.value === 'post' ? 'Пост' : 'Эпизод истории'}
                    </Badge>
                  </div>
                ) : (
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите тип" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="post">Пост</SelectItem>
                      <SelectItem value="story_episode">Эпизод истории</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="tone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Тон</FormLabel>
                {isEditing ? (
                  <div className="mt-2">
                    <Badge variant="secondary" className="text-base py-1 px-3">
                      {field.value === 'professional' && 'Профессиональный'}
                      {field.value === 'casual' && 'Неформальный'}
                      {field.value === 'humorous' && 'Юмористический'}
                      {field.value === 'educational' && 'Образовательный'}
                    </Badge>
                  </div>
                ) : (
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите тон" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="professional">Профессиональный</SelectItem>
                      <SelectItem value="casual">Неформальный</SelectItem>
                      <SelectItem value="humorous">Юмористический</SelectItem>
                      <SelectItem value="educational">Образовательный</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="length"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Длина</FormLabel>
                {isEditing ? (
                  <div className="mt-2">
                    <Badge variant="secondary" className="text-base py-1 px-3">
                      {field.value === 'short' && 'Короткий'}
                      {field.value === 'medium' && 'Средний'}
                      {field.value === 'long' && 'Длинный'}
                    </Badge>
                  </div>
                ) : (
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите длину" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="short">Короткий</SelectItem>
                      <SelectItem value="medium">Средний</SelectItem>
                      <SelectItem value="long">Длинный</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="language"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Язык</FormLabel>
                {isEditing ? (
                  <div className="mt-2">
                    <Badge variant="secondary" className="text-base py-1 px-3">
                      {field.value}
                    </Badge>
                  </div>
                ) : (
                  <FormControl>
                    <Input placeholder="ru" {...field} />
                  </FormControl>
                )}
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Advanced fields - always editable */}
        <FormField
          control={form.control}
          name="prompt_template"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Шаблон промпта</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Введите шаблон промпта для генерации контента"
                  className="min-h-[150px] font-mono text-sm"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Используйте переменные: {'{topic}'}, {'{keywords}'}, {'{trend}'}
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="additional_instructions"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Дополнительные инструкции (опционально)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Дополнительные указания для генерации"
                  className="min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex gap-3">
          <Button type="submit" disabled={loading}>
            {loading ? 'Сохранение...' : template ? 'Обновить' : 'Создать'}
          </Button>
          <Button type="button" variant="outline" onClick={() => form.reset()}>
            Сбросить
          </Button>
        </div>
      </form>
    </Form>
  );
}
