'use client';

import { useState, useEffect } from 'react';
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
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import type { ContentTemplate } from '@/lib/types';
import { postTypesApi, postTonesApi, type PostType, type PostTone } from '@/lib/api/postTypes';

const templateFormSchema = z.object({
  name: z.string().min(1, 'Название обязательно'),
  type: z.string().min(1, 'Тип обязателен'),
  tone: z.string().min(1, 'Тон обязателен'),
  length: z.enum(['short', 'medium', 'long']),
  language: z.string().min(2).max(10),
  seo_prompt_template: z.string().min(1, 'SEO-промпт обязателен'),
  trend_prompt_template: z.string().min(1, 'Trend-промпт обязателен'),
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

  // Load types and tones from API
  const [availableTypes, setAvailableTypes] = useState<PostType[]>([]);
  const [availableTones, setAvailableTones] = useState<PostTone[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);

  // UI state for adding new type/tone
  const [showTypeInput, setShowTypeInput] = useState(false);
  const [showToneInput, setShowToneInput] = useState(false);
  const [newTypeValue, setNewTypeValue] = useState('');
  const [newToneValue, setNewToneValue] = useState('');

  const form = useForm<TemplateFormValues>({
    resolver: zodResolver(templateFormSchema),
    defaultValues: {
      name: template?.name || '',
      type: template?.type || '',
      tone: template?.tone || '',
      length: template?.length || 'medium',
      language: template?.language || 'ru',
      seo_prompt_template: template?.seo_prompt_template || '',
      trend_prompt_template: template?.trend_prompt_template || '',
      additional_instructions: template?.additional_instructions || '',
    },
  });

  // Load types and tones from API
  useEffect(() => {
    const loadOptions = async () => {
      try {
        const [types, tones] = await Promise.all([
          postTypesApi.list(),
          postTonesApi.list(),
        ]);
        setAvailableTypes(types);
        setAvailableTones(tones);

        // Set default values if not editing
        if (!template) {
          if (types.length > 0) {
            form.setValue('type', types[0].value);
          }
          if (tones.length > 0) {
            form.setValue('tone', tones[0].value);
          }
        }
      } catch (error) {
        toast.error('Не удалось загрузить типы и тоны');
      } finally {
        setLoadingOptions(false);
      }
    };
    loadOptions();
  }, [template, form]);

  const handleSubmit = async (data: TemplateFormValues) => {
    try {
      await onSubmit(data);
    } catch (error) {
      // Error handling is done in the parent component
    }
  };

  const getTypeLabel = (value: string) => {
    const found = availableTypes.find(t => t.value === value);
    return found ? found.label : value;
  };

  const getToneLabel = (value: string) => {
    const found = availableTones.find(t => t.value === value);
    return found ? found.label : value;
  };

  const handleAddCustomType = async () => {
    if (!newTypeValue.trim()) return;

    try {
      const created = await postTypesApi.create({
        value: newTypeValue.trim().toLowerCase().replace(/\s+/g, '_'),
        label: newTypeValue.trim(),
      });

      setAvailableTypes([...availableTypes, created]);
      form.setValue('type', created.value);
      setNewTypeValue('');
      setShowTypeInput(false);
      toast.success('Новый тип добавлен');
    } catch (error) {
      toast.error('Ошибка при создании типа');
    }
  };

  const handleAddCustomTone = async () => {
    if (!newToneValue.trim()) return;

    try {
      const created = await postTonesApi.create({
        value: newToneValue.trim().toLowerCase().replace(/\s+/g, '_'),
        label: newToneValue.trim(),
      });

      setAvailableTones([...availableTones, created]);
      form.setValue('tone', created.value);
      setNewToneValue('');
      setShowToneInput(false);
      toast.success('Новый тон добавлен');
    } catch (error) {
      toast.error('Ошибка при создании тона');
    }
  };

  if (loadingOptions) {
    return <div className="py-8 text-center">Загрузка...</div>;
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* Template name */}
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Название шаблона</FormLabel>
              <FormControl>
                <Input placeholder="Например: Instagram продающий пост" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Basic fields - editable for type and tone */}
        <div className="grid grid-cols-2 gap-4">
          {/* Type field */}
          <FormField
            control={form.control}
            name="type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Тип контента</FormLabel>
                <div className="flex gap-2">
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите тип">
                          {field.value ? getTypeLabel(field.value) : 'Выберите тип'}
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {availableTypes.map((type) => (
                        <SelectItem key={type.id} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setShowTypeInput(!showTypeInput)}
                    title="Добавить свой тип"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {showTypeInput && (
                  <div className="flex gap-2 mt-2">
                    <Input
                      placeholder="Введите свой тип (русскими буквами)"
                      value={newTypeValue}
                      onChange={(e) => setNewTypeValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddCustomType();
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={handleAddCustomType}
                    >
                      Добавить
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setShowTypeInput(false);
                        setNewTypeValue('');
                      }}
                    >
                      Отмена
                    </Button>
                  </div>
                )}

                <FormDescription>
                  Структура контента (продающий, экспертный и т.д.)
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Tone field */}
          <FormField
            control={form.control}
            name="tone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Тон</FormLabel>
                <div className="flex gap-2">
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите тон">
                          {field.value ? getToneLabel(field.value) : 'Выберите тон'}
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {availableTones.map((tone) => (
                        <SelectItem key={tone.id} value={tone.value}>
                          {tone.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setShowToneInput(!showToneInput)}
                    title="Добавить свой тон"
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                {showToneInput && (
                  <div className="flex gap-2 mt-2">
                    <Input
                      placeholder="Введите свой тон (русскими буквами)"
                      value={newToneValue}
                      onChange={(e) => setNewToneValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddCustomTone();
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={handleAddCustomTone}
                    >
                      Добавить
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setShowToneInput(false);
                        setNewToneValue('');
                      }}
                    >
                      Отмена
                    </Button>
                  </div>
                )}

                <FormDescription>
                  Стиль общения в контенте
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Length field */}
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
                      <SelectItem value="short">Короткий (до 280 символов)</SelectItem>
                      <SelectItem value="medium">Средний (280-500 символов)</SelectItem>
                      <SelectItem value="long">Длинный (500-1000 символов)</SelectItem>
                    </SelectContent>
                  </Select>
                )}
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Language field */}
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

        {/* Prompt templates */}
        <div className="grid gap-6 xl:grid-cols-2">
          <FormField
            control={form.control}
            name="seo_prompt_template"
            render={({ field }) => (
              <FormItem>
                <FormLabel>SEO-промпт</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder="Промпт для генерации по SEO-ключам"
                    className="min-h-[180px] font-mono text-sm"
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Доступные переменные: {'{seo_keywords}'}, {'{topic_name}'}, {'{tone}'}, {'{length}'}, {'{language}'}, {'{type}'}, {'{avatar}'}, {'{pains}'}, {'{desires}'}, {'{objections}'}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="trend_prompt_template"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Trend-промпт</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder="Промпт для генерации по трендам"
                    className="min-h-[180px] font-mono text-sm"
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Доступные переменные: {'{trend_title}'}, {'{trend_description}'}, {'{trend_url}'}, {'{topic_name}'}, {'{tone}'}, {'{length}'}, {'{language}'}, {'{type}'}, {'{avatar}'}, {'{pains}'}, {'{desires}'}, {'{objections}'}
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

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
