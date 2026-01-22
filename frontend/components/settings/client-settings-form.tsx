'use client';

import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import * as z from 'zod';
import { clientApi } from '@/lib/api/client';
import { seoApi } from '@/lib/api/seo';
import { useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
import { toast } from 'sonner';
import type { ClientSettings } from '@/lib/types';

const settingsFormSchema = z.object({
  brand_name: z.string().optional(),
  niche: z.string().min(1, 'Ниша обязательна'),
  product_service: z.string().min(1, 'Продукт/услуга обязательна'),
  avatar: z.string().min(1, 'Портрет ЦА обязателен'),
  pains: z.string().optional(),
  desires: z.string().optional(),
  objections: z.string().optional(),
  expert_books: z.string().optional(),
});

type SettingsFormValues = z.infer<typeof settingsFormSchema>;

export function ClientSettingsForm() {
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [generatingSEO, setGeneratingSEO] = useState(false);
  const [generatingBooks, setGeneratingBooks] = useState(false);
  const [generatingSemantics, setGeneratingSemantics] = useState(false);
  const { canEdit } = useRole();

  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsFormSchema),
    defaultValues: {
      brand_name: '',
      niche: '',
      product_service: '',
      avatar: '',
      pains: '',
      desires: '',
      objections: '',
      expert_books: '',
    },
  });

  const loadSettings = useCallback(async () => {
    try {
      const data = await clientApi.getSettings();
      setSettings(data);
      form.reset({
        brand_name: data.brand_name || '',
        niche: data.niche || '',
        product_service: data.product_service || '',
        avatar: data.avatar || '',
        pains: data.pains || '',
        desires: data.desires || '',
        objections: data.objections || '',
        expert_books: data.expert_books || '',
      });
    } catch (error) {
      toast.error('Не удалось загрузить настройки');
    }
  }, [form]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

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

  const handleGenerateBookSemantics = async () => {
    if (!canEdit || generatingSemantics) {
      return;
    }
    const { expert_books } = form.getValues();
    if (!expert_books?.trim()) {
      toast.error('Добавьте книги экспертов, чтобы собрать семантику');
      return;
    }
    setGeneratingSemantics(true);
    try {
      const response = await clientApi.generateBookSemantics({ expert_books });
      if (response.success) {
        const details = [];
        if (response.groups_count) {
          details.push(`${response.groups_count} групп`);
        }
        if (response.keywords_count) {
          details.push(`${response.keywords_count} ключей`);
        }
        const suffix = details.length ? ` (${details.join(', ')})` : '';
        toast.success(`Семантика сохранена${suffix}`);
      } else {
        toast.error(response.error || 'Не удалось собрать семантику');
      }
    } catch (error) {
      toast.error('Не удалось собрать семантику');
    } finally {
      setGeneratingSemantics(false);
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
          name="niche"
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center justify-between gap-2">
                <FormLabel>
                  Ниша <span className="text-red-500">*</span>
                </FormLabel>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button
                      type="button"
                      variant="link"
                      className="h-auto p-0 text-xs text-blue-600 hover:text-blue-700"
                    >
                      Как заполнить нишу и продукт
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto bg-white text-gray-900 dark:bg-white dark:text-gray-900">
                    <DialogHeader>
                      <DialogTitle>Как заполнить нишу и продукт</DialogTitle>
                      <DialogDescription>
                        Примеры заполнения для товаров и услуг.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                      {`🟦 ТОВАРКА (e-commerce)
✅ ВЕРНО

1️⃣
Ниша: Продажа бытовой техники
Продукт: Холодильники и морозильные камеры

🔍 Почему верно:
ниша = рынок и тип товаров
продукт = конкретная товарная группа

2️⃣
Ниша: Товары для ремонта и строительства
Продукт: Ламинат и напольные покрытия

🔍 Почему верно:
Wordstat даст «ламинат купить», «ламинат цена», «ламинат для квартиры»

3️⃣
Ниша: Товары для красоты и ухода
Продукт: Профессиональная косметика для волос

🔍 Почему верно:
ниша шире, продукт коммерчески понятен

❌ НЕВЕРНО

1️⃣
Ниша: Интернет-магазин
Продукт: Товары

❌ Почему плохо:
это форма бизнеса, а не ниша
ИИ и Wordstat пойдут «куда угодно»

2️⃣
Ниша: Электроника
Продукт: Смартфоны Samsung Galaxy S23 256GB

❌ Почему плохо:
продукт слишком узкий, это уже хвост
нельзя масштабировать семантику

3️⃣
Ниша: Бизнес
Продукт: Продажа оборудования

❌ Почему плохо:
слишком абстрактно
Wordstat взорвётся мусором

🟩 УСЛУГИ

✅ ВЕРНО

1️⃣
Ниша: Юридические услуги
Услуга: Регистрация и сопровождение ООО

🔍 Почему верно:
чёткий интент, понятный SERP

2️⃣
Ниша: Ремонт и обслуживание недвижимости
Услуга: Ремонт квартир под ключ

🔍 Почему верно:
идеальный коммерческий кластер

3️⃣
Ниша: Digital-маркетинг
Услуга: SEO-продвижение сайтов

🔍 Почему верно:
масштабируемая семантика
понятная коммерция

❌ НЕВЕРНО

1️⃣
Ниша: Маркетинг
Услуга: Помощь бизнесу

❌ Почему плохо:
нет ни рынка, ни интента

2️⃣
Ниша: IT
Услуга: Разработка сайтов и приложений

❌ Почему плохо:
смешаны разные услуги
SERP будет разный

3️⃣
Ниша: Консалтинг
Услуга: Бизнес-консультации

❌ Почему плохо:
слишком широко
Wordstat даст кашу

🧠 Короткая шпаргалка
✔ Ниша отвечает на вопрос:

«В какой области мы работаем?»

✔ Продукт / услуга отвечает на вопрос:

«За что конкретно платят деньги?»`}
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
              <FormControl>
                <Input placeholder='Например: "пиццерия"' {...field} />
              </FormControl>
              <FormDescription>
                Например &quot;пиццерия&quot; или &quot;школа психологии&quot;
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="product_service"
          render={({ field }) => (
            <FormItem>
              <FormLabel>
                Продукт/услуга <span className="text-red-500">*</span>
              </FormLabel>
              <FormControl>
                <Input placeholder='Например: "доставка пиццы" или "онлайн-курс по йоге"' {...field} />
              </FormControl>
              <FormDescription>
                Коротко опишите, что именно вы предлагаете клиентам.
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
              <FormLabel>
                Портрет ЦА <span className="text-red-500">*</span>
              </FormLabel>
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
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleGenerateBookSemantics}
                  disabled={!canEdit || generatingSemantics}
                >
                  {generatingSemantics ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Семантика...
                    </>
                  ) : (
                    'Собрать семантику по книгам'
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
