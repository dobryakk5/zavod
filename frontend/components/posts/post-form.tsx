'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
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
import type { PostDetail } from '@/lib/types';

const postFormSchema = z.object({
  title: z.string().min(1, 'Заголовок обязателен').max(200, 'Максимум 200 символов'),
  text: z.string().min(1, 'Текст обязателен'),
  status: z.enum(['draft', 'ready', 'approved', 'scheduled', 'published']),
  topic: z.number().optional(),
  image_prompt: z.string().optional(),
});

type PostFormValues = z.infer<typeof postFormSchema>;

interface PostFormProps {
  post?: PostDetail;
  onSubmit: (data: PostFormValues) => Promise<void>;
  loading?: boolean;
}

export function PostForm({ post, onSubmit, loading = false }: PostFormProps) {
  const form = useForm<PostFormValues>({
    resolver: zodResolver(postFormSchema),
    defaultValues: {
      title: post?.title || '',
      text: post?.text || '',
      status: post?.status || 'draft',
      topic: post?.topic || undefined,
      image_prompt: post?.image_prompt || '',
    },
  });

  const handleSubmit = async (data: PostFormValues) => {
    try {
      await onSubmit(data);
    } catch (error) {
      // Error handling is done in the parent component
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Заголовок</FormLabel>
              <FormControl>
                <Input placeholder="Введите заголовок поста" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="text"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Текст</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Введите текст поста"
                  className="min-h-[200px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="image_prompt"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Промпт для изображения (опционально)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Опишите, какое изображение нужно сгенерировать"
                  className="min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Используется для генерации изображений AI
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="status"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Статус</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите статус" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="draft">Черновик</SelectItem>
                  <SelectItem value="ready">Готов</SelectItem>
                  <SelectItem value="approved">Одобрен</SelectItem>
                  <SelectItem value="scheduled">Запланирован</SelectItem>
                  <SelectItem value="published">Опубликован</SelectItem>
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex gap-3">
          <Button type="submit" disabled={loading}>
            {loading ? 'Сохранение...' : post ? 'Обновить' : 'Создать'}
          </Button>
          <Button type="button" variant="outline" onClick={() => form.reset()}>
            Сбросить
          </Button>
        </div>
      </form>
    </Form>
  );
}
