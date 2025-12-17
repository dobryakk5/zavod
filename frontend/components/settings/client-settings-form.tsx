'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import * as z from 'zod';
import { clientApi } from '@/lib/api/client';
import { seoApi } from '@/lib/api/seo';
import { useRole } from '@/lib/hooks';
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
import { CustomTextarea } from '@/components/ui/custom-textarea';
import { Input } from '@/components/ui/input';
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
  brand_name: z.string().optional(),
  timezone: z.string().optional(),
  avatar: z.string().optional(),
  pains: z.string().optional(),
  desires: z.string().optional(),
  objections: z.string().optional(),
  expert_books: z.string().optional(),
  telegram_source_channels: z.string().optional(),
  rss_source_feeds: z.string().optional(),
  youtube_source_channels: z.string().optional(),
  instagram_source_accounts: z.string().optional(),
  vkontakte_source_groups: z.string().optional(),
});

type SettingsFormValues = z.infer<typeof settingsFormSchema>;

export function ClientSettingsForm() {
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [generatingSEO, setGeneratingSEO] = useState(false);
  const [generatingBooks, setGeneratingBooks] = useState(false);
  const { canEdit } = useRole();

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
    defaultValues: {
      brand_name: '',
      timezone: '',
      avatar: '',
      pains: '',
      desires: '',
      objections: '',
      expert_books: '',
      telegram_source_channels: '',
      rss_source_feeds: '',
      youtube_source_channels: '',
      instagram_source_accounts: '',
      vkontakte_source_groups: '',
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
        brand_name: data.brand_name || '',
        timezone: data.timezone || '',
        avatar: data.avatar || '',
        pains: data.pains || '',
        desires: data.desires || '',
        objections: data.objections || '',
        expert_books: data.expert_books || '',
        telegram_source_channels: data.telegram_source_channels || '',
        rss_source_feeds: data.rss_source_feeds || '',
        youtube_source_channels: data.youtube_source_channels || '',
        instagram_source_accounts: data.instagram_source_accounts || '',
        vkontakte_source_groups: data.vkontakte_source_groups || '',
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

  const handleGenerateSEO = async () => {
    if (!canEdit || generatingSEO) {
      return;
    }
    setGeneratingSEO(true);
    try {
      const response = await seoApi.generate();
      toast.success(response.message || 'Генерация SEO запущена');
    } catch (error) {
      console.error('Failed to start SEO generation', error);
      toast.error('Не удалось запустить SEO-анализ');
    } finally {
      setGeneratingSEO(false);
    }
  };

  const handleGenerateBooks = async () => {
    if (!canEdit || generatingBooks) {
      return;
    }
    const { pains = '', desires = '', avatar = '' } = form.getValues();
    if (!pains.trim() && !desires.trim()) {
      toast.error('Заполните блоки «Боли» или «Желания», чтобы подобрать книги');
      return;
    }
    setGeneratingBooks(true);
    try {
      const response = await clientApi.generateExpertBooks({
        pains,
        desires,
        avatar,
      });
      if (response.success) {
        if (response.text) {
          form.setValue('expert_books', response.text, { shouldDirty: false });
          setSettings((prev) => (prev ? { ...prev, expert_books: response.text } : prev));
        }
        const successMessage = response.saved
          ? 'Подборка книг сохранена'
          : 'Подборка книг обновлена';
        toast.success(successMessage);
      } else {
        toast.error(response.error || 'Не удалось подобрать книги');
      }
    } catch (error) {
      toast.error('Не удалось подобрать книги');
    } finally {
      setGeneratingBooks(false);
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
          name="brand_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Название бренда</FormLabel>
              <FormControl>
                <Input placeholder="Например: Zavod Media" {...field} />
              </FormControl>
              <FormDescription>Используется для упоминания в постах</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

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
          name="expert_books"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Книги экспертов</FormLabel>
              <FormControl>
                <CustomTextarea
                  placeholder="По одной книге на строку, например: «Атомные привычки — Джеймс Клир: помогает выстроить новые ритуалы»"
                  className="min-h-[120px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Список книг, которые вы рекомендуете своей аудитории. Можно сгенерировать автоматически с учётом болей и желаний.
              </FormDescription>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleGenerateBooks}
                  disabled={!canEdit || generatingBooks}
                >
                  {generatingBooks ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Подбираем...
                    </>
                  ) : (
                    'Найти книги для ЦА'
                  )}
                </Button>
                {!canEdit && (
                  <p className="text-xs text-muted-foreground">
                    Кнопка доступна владельцу и редактору.
                  </p>
                )}
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="space-y-4 rounded-lg border border-slate-200 p-4">
          <div>
            <p className="text-base font-semibold">Источники контента</p>
            <p className="text-sm text-muted-foreground">
              Добавьте ссылки или идентификаторы через запятую (можно переносить на новую строку). Здесь
              хранится только список источников — токены не требуются.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <FormField
              control={form.control}
              name="telegram_source_channels"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Telegram каналы</FormLabel>
                  <FormControl>
                    <CustomTextarea
                      placeholder="@rian_ru, @tjournal"
                      className="min-h-[80px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Указывайте @username или ссылку, через запятую.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="rss_source_feeds"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>RSS / Atom фиды</FormLabel>
                  <FormControl>
                    <CustomTextarea
                      placeholder="https://lenta.ru/rss, https://example.com/feed.xml"
                      className="min-h-[80px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Полные URL фидов.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="youtube_source_channels"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>YouTube каналы</FormLabel>
                  <FormControl>
                    <CustomTextarea
                      placeholder="UC_x5XG1OV2P6uZZ5FSM9Ttw, @channel_handle"
                      className="min-h-[80px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>ID канала или @handle, через запятую.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="instagram_source_accounts"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Instagram аккаунты</FormLabel>
                  <FormControl>
                    <CustomTextarea
                      placeholder="username1, username2"
                      className="min-h-[80px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Список usernames.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="vkontakte_source_groups"
              render={({ field }) => (
                <FormItem className="md:col-span-2">
                  <FormLabel>VK сообщества</FormLabel>
                  <FormControl>
                    <CustomTextarea
                      placeholder="apiclub, https://vk.com/thecode"
                      className="min-h-[80px]"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>screen name или ссылка, через запятую.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </div>

        <Button type="submit" disabled={loading}>
          {loading ? 'Сохранение...' : 'Сохранить изменения'}
        </Button>

        <div className="space-y-3 rounded-lg border border-dashed border-slate-200 p-4">
          <div>
            <p className="text-base font-semibold">Генерация SEO групп</p>
            <p className="text-sm text-muted-foreground">
              Создаёт новый комплект SEO-групп (боли, желания, возражения и ключевые фразы) для текущего клиента.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={handleGenerateSEO}
            disabled={!canEdit || generatingSEO}
          >
            {generatingSEO ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Генерация...
              </>
            ) : (
              'Создать SEO-подборку'
            )}
          </Button>
          {!canEdit && (
            <p className="text-xs text-muted-foreground">
              Кнопка доступна владельцу и редактору.
            </p>
          )}
        </div>
      </form>
    </Form>
  );
}
