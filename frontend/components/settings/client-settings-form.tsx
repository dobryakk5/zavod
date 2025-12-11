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
import { CustomTextarea } from '@/components/ui/custom-textarea';
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
  pains: z.string().optional(),
  desires: z.string().optional(),
  objections: z.string().optional(),
  ai_analysis_channel_url: z.string().optional(),
  ai_analysis_channel_type: z.string().optional(),
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
      pains: '',
      desires: '',
      objections: '',
      ai_analysis_channel_url: '',
      ai_analysis_channel_type: '',
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
        pains: data.pains || '',
        desires: data.desires || '',
        objections: data.objections || '',
        ai_analysis_channel_url: data.ai_analysis_channel_url || '',
        ai_analysis_channel_type: data.ai_analysis_channel_type || '',
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
          name="avatar"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Портрет ЦА</FormLabel>
              <FormControl>
                <CustomTextarea
                  placeholder="Описание целевой аудитории (например: 'Мама двоих детей, работает удалённо, хочет больше времени для себя')"
                  className="min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Кто ваша целевая аудитория
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="pains"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Боли</FormLabel>
              <FormControl>
                <CustomTextarea
                  placeholder="Проблемы и боли целевой аудитории (например: 'нет времени на себя, стресс, лишний вес, низкая самооценка')"
                  className="min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Проблемы и боли вашей аудитории
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="desires"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Желания</FormLabel>
              <FormControl>
                <CustomTextarea
                  placeholder="Желания и цели аудитории (например: 'похудеть к лету, научиться танцевать, найти хобби, познакомиться с новыми людьми')"
                  className="min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Желания и цели вашей аудитории
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="objections"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Возражения</FormLabel>
              <FormControl>
                <CustomTextarea
                  placeholder="Страхи и возражения аудитории (например: 'дорого, нет времени, боюсь выглядеть глупо, не получится')"
                  className="min-h-[80px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Страхи и возражения вашей аудитории
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />


        <FormField
          control={form.control}
          name="ai_analysis_channel_url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>AI Анализ канала</FormLabel>
              <FormControl>
                <Input placeholder="https://t.me/example_channel" {...field} />
              </FormControl>
              <FormDescription>
                URL канала для AI анализа
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="ai_analysis_channel_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Тип канала</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Выберите тип канала" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="instagram">Instagram</SelectItem>
                  <SelectItem value="youtube">YouTube</SelectItem>
                  <SelectItem value="vkontakte">VKontakte</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>
                Тип канала для AI анализа
              </FormDescription>
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
