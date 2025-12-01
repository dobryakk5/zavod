'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { clientApi } from '@/lib/api/client';
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
import { toast } from 'sonner';
import type { ClientSettings } from '@/lib/types';

const settingsFormSchema = z.object({
  timezone: z.string().optional(),
  avatar: z.string().optional(),
  logo: z.string().optional(),
  website: z.string().url('Неверный URL').optional().or(z.literal('')),
  description: z.string().optional(),
  default_language: z.string().optional(),
});

type SettingsFormValues = z.infer<typeof settingsFormSchema>;

export function ClientSettingsForm() {
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [loading, setLoading] = useState(false);

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
    defaultValues: {
      timezone: '',
      avatar: '',
      logo: '',
      website: '',
      description: '',
      default_language: 'ru',
    },
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await clientApi.getSettings();
      setSettings(data);
      form.reset({
        timezone: data.timezone || '',
        avatar: data.avatar || '',
        logo: data.logo || '',
        website: data.website || '',
        description: data.description || '',
        default_language: data.default_language || 'ru',
      });
    } catch (error) {
      toast.error('Не удалось загрузить настройки');
    }
  };

  const handleSubmit = async (data: SettingsFormValues) => {
    setLoading(true);
    try {
      await clientApi.updateSettings(data);
      toast.success('Настройки успешно обновлены');
      await loadSettings();
    } catch (error) {
      toast.error('Ошибка при сохранении настроек');
    } finally {
      setLoading(false);
    }
  };

  if (!settings) {
    return <div className="text-center py-8">Загрузка...</div>;
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* Note: NO 'name' or 'id' field - they are read-only */}

        <FormField
          control={form.control}
          name="timezone"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Часовой пояс</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите часовой пояс" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="UTC">UTC</SelectItem>
                  <SelectItem value="Europe/Moscow">Europe/Moscow</SelectItem>
                  <SelectItem value="Europe/London">Europe/London</SelectItem>
                  <SelectItem value="America/New_York">America/New_York</SelectItem>
                  <SelectItem value="Asia/Tokyo">Asia/Tokyo</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>
                Используется для планирования публикаций
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="default_language"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Язык по умолчанию</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите язык" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="ru">Русский</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Español</SelectItem>
                  <SelectItem value="fr">Français</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>
                Язык для генерации контента по умолчанию
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="avatar"
          render={({ field }) => (
            <FormItem>
              <FormLabel>URL аватара</FormLabel>
              <FormControl>
                <Input placeholder="https://example.com/avatar.jpg" {...field} />
              </FormControl>
              <FormDescription>
                URL изображения для аватара
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="logo"
          render={({ field }) => (
            <FormItem>
              <FormLabel>URL логотипа</FormLabel>
              <FormControl>
                <Input placeholder="https://example.com/logo.png" {...field} />
              </FormControl>
              <FormDescription>
                URL изображения для логотипа
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="website"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Веб-сайт</FormLabel>
              <FormControl>
                <Input placeholder="https://example.com" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Описание</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Краткое описание компании или проекта"
                  className="min-h-[100px]"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={loading}>
          {loading ? 'Сохранение...' : 'Сохранить изменения'}
        </Button>
      </form>
    </Form>
  );
}
