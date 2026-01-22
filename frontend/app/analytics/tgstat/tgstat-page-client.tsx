'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ApiError } from '@/lib/api';
import { analyticsApi } from '@/lib/api/analytics';
import {
  tgstatApi,
  type TgstatCategory,
  type TgstatChannel,
  type TgstatRecommendationCategory,
  type TgstatTag,
} from '@/lib/api/tgstat';
import { toast } from 'sonner';
import { ChevronDown, Loader2, Plus } from 'lucide-react';

type TabValue = 'categories' | 'tags' | 'channels' | 'favorites';

const CATEGORY_GROUPS: Array<{ key: string; label: string; slugs: string[] }> = [
  {
    key: 'business',
    label: '💰 Бизнес',
    slugs: [
      'news',
      'economics',
      'business',
      'marketing',
      'design',
      'law',
      'telegram',
      'instagram',
      'sales',
      'politics',
    ],
  },
  {
    key: 'growth',
    label: '🚀 Работа',
    slugs: ['blogs', 'tech', 'apps', 'books', 'language', 'career', 'courses', 'education'],
  },
  {
    key: 'family',
    label: '🏠 Семья',
    slugs: ['babies', 'nature', 'construction', 'food', 'handmade', 'religion'],
  },
  {
    key: 'health',
    label: '❤️ Здоровье',
    slugs: ['health', 'medicine', 'psychology', 'sport', 'beauty'],
  },
  {
    key: 'rest',
    label: '🌴 Отдых',
    slugs: ['entertainment', 'travels', 'video', 'music', 'games', 'pics', 'edutainment', 'art', 'quotes', 'transport'],
  },
  {
    key: 'caution',
    label: '🕶 Осторожно',
    slugs: ['crypto', 'darknet', 'gambling', 'shock', 'erotica', 'adult', 'esoterics', 'other'],
  },
];

export default function TgstatPageClient() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabValue>('categories');
  const [categories, setCategories] = useState<TgstatCategory[]>([]);
  const [tags, setTags] = useState<TgstatTag[]>([]);
  const [channels, setChannels] = useState<TgstatChannel[]>([]);
  const [favorites, setFavorites] = useState<TgstatChannel[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<TgstatCategory | null>(null);
  const [selectedTag, setSelectedTag] = useState<TgstatTag | null>(null);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(false);
  const [isTagsLoading, setIsTagsLoading] = useState(false);
  const [isChannelsLoading, setIsChannelsLoading] = useState(false);
  const [isFavoritesLoading, setIsFavoritesLoading] = useState(false);
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<TgstatRecommendationCategory[]>([]);
  const [hasRequestedRecommendations, setHasRequestedRecommendations] = useState(false);
  const [recommendationsMeta, setRecommendationsMeta] = useState<{ niche: string; product: string } | null>(null);
  const [savingFavoriteId, setSavingFavoriteId] = useState<number | null>(null);
  const [runningAnalysisId, setRunningAnalysisId] = useState<number | null>(null);
  const [removingFavoriteId, setRemovingFavoriteId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set());

  const numberFormatter = useMemo(() => new Intl.NumberFormat('ru-RU'), []);
  const favoriteIdSet = useMemo(() => new Set(favorites.map((channel) => channel.id)), [favorites]);
  const categoriesBySlug = useMemo(() => {
    const map = new Map<string, TgstatCategory>();
    categories.forEach((category) => {
      map.set(category.slug, category);
    });
    return map;
  }, [categories]);
  const groupedCategories = useMemo(
    () =>
      CATEGORY_GROUPS.map((group) => ({
        ...group,
        categories: group.slugs
          .map((slug) => categoriesBySlug.get(slug))
          .filter((category): category is TgstatCategory => Boolean(category)),
      })),
    [categoriesBySlug],
  );

  const loadCategories = useCallback(async () => {
    setIsCategoriesLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listCategories();
      setCategories(data);
    } catch (error) {
      setErrorMessage('Не удалось загрузить категории.');
    } finally {
      setIsCategoriesLoading(false);
    }
  }, []);

  const loadTags = useCallback(async (categoryId: number) => {
    setIsTagsLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listTags(categoryId);
      setTags(data);
      return data;
    } catch (error) {
      setErrorMessage('Не удалось загрузить подкатегории.');
      return [];
    } finally {
      setIsTagsLoading(false);
    }
  }, []);

  const loadChannels = useCallback(async (tagSlug: string) => {
    setIsChannelsLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listChannels(tagSlug);
      setChannels(data);
    } catch (error) {
      setErrorMessage('Не удалось загрузить каналы.');
    } finally {
      setIsChannelsLoading(false);
    }
  }, []);

  const loadChannelsByCategory = useCallback(async (categoryId: number) => {
    setIsChannelsLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listChannelsByCategory(categoryId);
      setChannels(data);
    } catch (error) {
      setErrorMessage('Не удалось загрузить каналы.');
    } finally {
      setIsChannelsLoading(false);
    }
  }, []);

  const loadFavorites = useCallback(async () => {
    setIsFavoritesLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listFavorites();
      setFavorites(data);
    } catch (error) {
      setErrorMessage('Не удалось загрузить избранные каналы.');
    } finally {
      setIsFavoritesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
    void loadFavorites();
  }, [loadCategories, loadFavorites]);

  const handleCategorySelect = useCallback(
    async (category: TgstatCategory) => {
      setSelectedCategory(category);
      setSelectedTag(null);
      setTags([]);
      setChannels([]);
      const data = await loadTags(category.id);
      if (data.length === 0) {
        setActiveTab('channels');
        void loadChannelsByCategory(category.id);
      } else {
        setActiveTab('tags');
      }
    },
    [loadChannelsByCategory, loadTags],
  );

  const handleTagSelect = useCallback(
    (tag: TgstatTag) => {
      setSelectedTag(tag);
      setChannels([]);
      setActiveTab('channels');
      void loadChannels(tag.slug);
    },
    [loadChannels],
  );

  const handleAddFavorite = useCallback(
    async (channel: TgstatChannel) => {
      if (favoriteIdSet.has(channel.id)) {
        return;
      }
      setSavingFavoriteId(channel.id);
      setErrorMessage(null);
      try {
        await tgstatApi.addFavorite(channel.id);
        setFavorites((prev) => (prev.some((item) => item.id === channel.id) ? prev : [...prev, channel]));
      } catch (error) {
        setErrorMessage('Не удалось добавить канал в избранное.');
      } finally {
        setSavingFavoriteId(null);
      }
    },
    [favoriteIdSet],
  );

  const handleRemoveFavorite = useCallback(async (channel: TgstatChannel) => {
    setRemovingFavoriteId(channel.id);
    setErrorMessage(null);
    try {
      await tgstatApi.removeFavorite(channel.id);
      setFavorites((prev) => prev.filter((item) => item.id !== channel.id));
    } catch (error) {
      setErrorMessage('Не удалось убрать канал из избранного.');
    } finally {
      setRemovingFavoriteId(null);
    }
  }, []);

  const handleAnalyzeFavorite = useCallback(async (channel: TgstatChannel) => {
    const normalizedUsername = channel.username ? channel.username.replace(/^@/, '') : '';
    const channelUrl = normalizedUsername ? `https://t.me/${normalizedUsername}` : channel.url;
    if (!channelUrl) {
      setErrorMessage('Не удалось определить ссылку на канал.');
      return;
    }

    setRunningAnalysisId(channel.id);
    setErrorMessage(null);
    try {
      const response = await analyticsApi.analyzeChannel({
        channel_url: channelUrl,
        channel_type: 'telegram',
      });
      if (response.success) {
        toast.success('Анализ запущен');
        router.push('/analytics');
      } else {
        toast.error(response.error || 'Не удалось запустить анализ');
      }
    } catch (error) {
      toast.error('Не удалось запустить анализ');
    } finally {
      setRunningAnalysisId(null);
    }
  }, [router]);

  const handleGroupToggle = useCallback((key: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const handleFindRecommendations = useCallback(async () => {
    setIsRecommendationsLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.getRecommendations();
      if (!data.success) {
        setErrorMessage(data.error || 'Не удалось получить рекомендации.');
        return;
      }
      setRecommendations(data.recommendations || []);
      setRecommendationsMeta({
        niche: data.niche || '',
        product: data.product_service || '',
      });
      setHasRequestedRecommendations(true);
    } catch (error) {
      if (error instanceof ApiError) {
        try {
          const payload = error.body ? JSON.parse(error.body) : null;
          if (payload?.missing_fields) {
            setErrorMessage('Заполните нишу и продукт в настройках проекта.');
            return;
          }
          if (payload?.error) {
            setErrorMessage(String(payload.error));
            return;
          }
        } catch {}
      }
      setErrorMessage('Не удалось получить рекомендации.');
    } finally {
      setIsRecommendationsLoading(false);
    }
  }, []);

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold">Telegram каналы</h1>
        <p className="text-sm text-muted-foreground">
          Выберите категорию, затем подкатегорию, чтобы увидеть список каналов.
        </p>
      </div>

      {errorMessage ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : null}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as TabValue)} className="space-y-4">
        <TabsList>
          <TabsTrigger value="categories">Категории</TabsTrigger>
          <TabsTrigger value="tags">Подкатегории</TabsTrigger>
          <TabsTrigger value="channels">Каналы</TabsTrigger>
          <TabsTrigger value="favorites">Избранное</TabsTrigger>
        </TabsList>

        <TabsContent value="categories" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
            <span>Всего категорий: {categories.length}</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={loadCategories} disabled={isCategoriesLoading}>
                Обновить
              </Button>
              <Button
                size="sm"
                className="gap-2"
                onClick={handleFindRecommendations}
                disabled={isRecommendationsLoading}
              >
                {isRecommendationsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Найди мои
              </Button>
            </div>
          </div>
          {isRecommendationsLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Ищем подходящие подкатегории
            </div>
          ) : hasRequestedRecommendations && recommendations.length === 0 ? (
            <p className="text-sm text-gray-500">Не нашли подходящих подкатегорий для ниши.</p>
          ) : recommendations.length > 0 ? (
            <div className="rounded-lg border bg-white shadow-sm">
              <div className="border-b px-4 py-3">
                <div className="text-sm font-semibold text-gray-900">Рекомендации по подкатегориям</div>
                {recommendationsMeta ? (
                  <div className="text-xs text-muted-foreground">
                    Ниша: {recommendationsMeta.niche || '—'} · Продукт: {recommendationsMeta.product || '—'}
                  </div>
                ) : null}
              </div>
              <div className="space-y-4 px-4 py-3">
                {recommendations.map((recommendation) => (
                  <div key={recommendation.category_slug} className="space-y-2">
                    <div className="text-sm font-medium text-gray-900">{recommendation.category_title}</div>
                    <div className="flex flex-wrap gap-2">
                      {recommendation.tags.map((tag) => (
                        <Badge
                          key={`${recommendation.category_slug}-${tag.slug}`}
                          variant="secondary"
                          className="text-xs"
                          title={tag.reason || undefined}
                        >
                          {tag.title}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {isCategoriesLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем категории
            </div>
          ) : categories.length === 0 ? (
            <p className="text-sm text-gray-500">Нет данных по категориям.</p>
          ) : (
            <div className="space-y-3">
              {groupedCategories.map((group) => {
                const isExpanded = expandedGroups.has(group.key);
                return (
                  <div key={group.key} className="rounded-lg border bg-white shadow-sm">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-gray-900"
                      onClick={() => handleGroupToggle(group.key)}
                      aria-expanded={isExpanded}
                    >
                      <span>{group.label}</span>
                      <ChevronDown
                        className={`h-4 w-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      />
                    </button>
                    {isExpanded ? (
                      <div className="border-t">
                        {group.categories.map((category) => {
                          const isSelected = selectedCategory?.slug === category.slug;
                          const label = category.title || category.slug;
                          return (
                            <button
                              key={category.slug}
                              type="button"
                              className={`flex w-full items-center px-4 py-2 text-left text-sm ${
                                isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'
                              }`}
                              onClick={() => handleCategorySelect(category)}
                            >
                              <span className="font-medium text-gray-900">{label}</span>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="tags" className="space-y-4">
          {selectedCategory ? (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Категория: <span className="font-medium text-gray-900">{selectedCategory.title}</span>
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void loadTags(selectedCategory.id);
                }}
                disabled={isTagsLoading}
              >
                Обновить
              </Button>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Сначала выберите категорию.</p>
          )}

          {isTagsLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем подкатегории
            </div>
          ) : selectedCategory && tags.length === 0 ? (
            <p className="text-sm text-gray-500">В выбранной категории пока нет подкатегорий.</p>
          ) : tags.length > 0 ? (
            <div className="rounded-lg border bg-white shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Подкатегория</TableHead>
                    <TableHead className="hidden md:table-cell">Slug</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tags.map((tag) => {
                    const isSelected = selectedTag?.slug === tag.slug;
                    return (
                      <TableRow
                        key={tag.slug}
                        className={`cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                        onClick={() => handleTagSelect(tag)}
                      >
                        <TableCell className="font-medium text-gray-900">{tag.title}</TableCell>
                        <TableCell className="hidden md:table-cell text-xs text-gray-500">{tag.slug}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="channels" className="space-y-4">
          {selectedTag ? (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Подкатегория: <span className="font-medium text-gray-900">{selectedTag.title}</span>
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadChannels(selectedTag.slug)}
                disabled={isChannelsLoading}
              >
                Обновить
              </Button>
            </div>
          ) : selectedCategory ? (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Категория: <span className="font-medium text-gray-900">{selectedCategory.title}</span>
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadChannelsByCategory(selectedCategory.id)}
                disabled={isChannelsLoading}
              >
                Обновить
              </Button>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Сначала выберите подкатегорию.</p>
          )}

          {isChannelsLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем каналы
            </div>
          ) : selectedTag && channels.length === 0 ? (
            <p className="text-sm text-gray-500">В выбранной подкатегории пока нет каналов.</p>
          ) : channels.length > 0 ? (
            <div className="rounded-lg border bg-white shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Канал</TableHead>
                    <TableHead className="hidden md:table-cell">Подписчики</TableHead>
                    <TableHead className="w-16 text-right">В избранное</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {channels.map((channel) => {
                    const label = channel.title || channel.username || channel.url || 'Без названия';
                    const username = channel.username ? `@${channel.username.replace(/^@/, '')}` : null;
                    const normalizedUsername = channel.username ? channel.username.replace(/^@/, '') : '';
                    const isFavorite = favoriteIdSet.has(channel.id);
                    const isSaving = savingFavoriteId === channel.id;
                    return (
                      <TableRow
                        key={channel.id}
                        className={normalizedUsername ? 'cursor-pointer' : ''}
                        onClick={() => {
                          if (normalizedUsername) {
                            window.open(`https://t.me/${normalizedUsername}`, '_blank', 'noopener,noreferrer');
                          }
                        }}
                      >
                        <TableCell className="space-y-1">
                          <div className="font-medium text-gray-900">{label}</div>
                          {username ? <div className="text-xs text-gray-500">{username}</div> : null}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-gray-600">
                          {channel.subscribers === null || channel.subscribers === undefined
                            ? '—'
                            : numberFormatter.format(channel.subscribers)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleAddFavorite(channel);
                            }}
                            disabled={isFavorite || isSaving}
                            aria-label={isFavorite ? 'Канал уже в избранном' : 'Добавить в избранное'}
                          >
                            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="favorites" className="space-y-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Всего избранных: {favorites.length}</span>
            <Button variant="outline" size="sm" onClick={loadFavorites} disabled={isFavoritesLoading}>
              Обновить
            </Button>
          </div>
          {isFavoritesLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем избранные каналы
            </div>
          ) : favorites.length === 0 ? (
            <p className="text-sm text-gray-500">Пока нет избранных каналов.</p>
          ) : (
            <div className="rounded-lg border bg-white shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Канал</TableHead>
                    <TableHead className="hidden md:table-cell">Подписчики</TableHead>
                    <TableHead className="w-28 text-right">Действие</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {favorites.map((channel) => {
                    const label = channel.title || channel.username || channel.url || 'Без названия';
                    const username = channel.username ? `@${channel.username.replace(/^@/, '')}` : null;
                    const normalizedUsername = channel.username ? channel.username.replace(/^@/, '') : '';
                    const isAnalyzing = runningAnalysisId === channel.id;
                    const isRemoving = removingFavoriteId === channel.id;
                    return (
                      <TableRow
                        key={channel.id}
                        className={normalizedUsername ? 'cursor-pointer' : ''}
                        onClick={() => {
                          if (normalizedUsername) {
                            window.open(`https://t.me/${normalizedUsername}`, '_blank', 'noopener,noreferrer');
                          }
                        }}
                      >
                        <TableCell className="space-y-1">
                          <div className="font-medium text-gray-900">{label}</div>
                          {username ? <div className="text-xs text-gray-500">{username}</div> : null}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-gray-600">
                          {channel.subscribers === null || channel.subscribers === undefined
                            ? '—'
                            : numberFormatter.format(channel.subscribers)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="inline-flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="icon"
                              title="Анализ канала"
                              aria-label="Анализ канала"
                              disabled={isAnalyzing}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleAnalyzeFavorite(channel);
                              }}
                            >
                              {isAnalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : 'А'}
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              title="Убрать из избранного"
                              aria-label="Убрать из избранного"
                              disabled={isRemoving}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleRemoveFavorite(channel);
                              }}
                            >
                              {isRemoving ? <Loader2 className="h-4 w-4 animate-spin" /> : '-'}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
