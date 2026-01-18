'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { tgstatApi, type TgstatCategory, type TgstatChannel, type TgstatTag } from '@/lib/api/tgstat';
import { Loader2, Plus } from 'lucide-react';

type TabValue = 'categories' | 'tags' | 'channels' | 'favorites';

export default function TgstatPageClient() {
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
  const [savingFavoriteId, setSavingFavoriteId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const numberFormatter = useMemo(() => new Intl.NumberFormat('ru-RU'), []);
  const favoriteIdSet = useMemo(() => new Set(favorites.map((channel) => channel.id)), [favorites]);

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

  const loadTags = useCallback(async (categorySlug: string) => {
    setIsTagsLoading(true);
    setErrorMessage(null);
    try {
      const data = await tgstatApi.listTags(categorySlug);
      setTags(data);
    } catch (error) {
      setErrorMessage('Не удалось загрузить подкатегории.');
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
    (category: TgstatCategory) => {
      setSelectedCategory(category);
      setSelectedTag(null);
      setTags([]);
      setChannels([]);
      setActiveTab('tags');
      void loadTags(category.slug);
    },
    [loadTags],
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

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold">Категории Telegram каналов</h1>
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
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Всего категорий: {categories.length}</span>
            <Button variant="outline" size="sm" onClick={loadCategories} disabled={isCategoriesLoading}>
              Обновить
            </Button>
          </div>
          {isCategoriesLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем категории
            </div>
          ) : categories.length === 0 ? (
            <p className="text-sm text-gray-500">Нет данных по категориям.</p>
          ) : (
            <div className="rounded-lg border bg-white shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-50">
                    <TableHead>Категория</TableHead>
                    <TableHead className="hidden md:table-cell">Slug</TableHead>
                    <TableHead className="hidden md:table-cell">Ссылка</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {categories.map((category) => {
                    const isSelected = selectedCategory?.slug === category.slug;
                    return (
                      <TableRow
                        key={category.slug}
                        className={`cursor-pointer ${isSelected ? 'bg-blue-50' : ''}`}
                        onClick={() => handleCategorySelect(category)}
                      >
                        <TableCell className="font-medium text-gray-900">{category.title}</TableCell>
                        <TableCell className="hidden md:table-cell text-xs text-gray-500">{category.slug}</TableCell>
                        <TableCell className="hidden md:table-cell text-xs text-blue-600">
                          {category.url}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
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
                onClick={() => loadTags(selectedCategory.slug)}
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
                    <TableHead className="hidden md:table-cell">Ссылка</TableHead>
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
                        <TableCell className="hidden md:table-cell text-xs text-blue-600">{tag.url}</TableCell>
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
                    <TableHead className="hidden md:table-cell">Ссылка</TableHead>
                    <TableHead className="w-16 text-right">В избранное</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {channels.map((channel) => {
                    const label = channel.title || channel.username || channel.url || 'Без названия';
                    const username = channel.username ? `@${channel.username.replace(/^@/, '')}` : null;
                    const isFavorite = favoriteIdSet.has(channel.id);
                    const isSaving = savingFavoriteId === channel.id;
                    return (
                      <TableRow key={channel.id}>
                        <TableCell className="space-y-1">
                          <div className="font-medium text-gray-900">{label}</div>
                          {username ? <div className="text-xs text-gray-500">{username}</div> : null}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-gray-600">
                          {channel.subscribers === null || channel.subscribers === undefined
                            ? '—'
                            : numberFormatter.format(channel.subscribers)}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-xs text-blue-600">
                          {channel.url ? (
                            <a href={channel.url} target="_blank" rel="noreferrer">
                              {channel.url}
                            </a>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleAddFavorite(channel)}
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
                    <TableHead className="hidden md:table-cell">Ссылка</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {favorites.map((channel) => {
                    const label = channel.title || channel.username || channel.url || 'Без названия';
                    const username = channel.username ? `@${channel.username.replace(/^@/, '')}` : null;
                    return (
                      <TableRow key={channel.id}>
                        <TableCell className="space-y-1">
                          <div className="font-medium text-gray-900">{label}</div>
                          {username ? <div className="text-xs text-gray-500">{username}</div> : null}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-gray-600">
                          {channel.subscribers === null || channel.subscribers === undefined
                            ? '—'
                            : numberFormatter.format(channel.subscribers)}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-xs text-blue-600">
                          {channel.url ? (
                            <a href={channel.url} target="_blank" rel="noreferrer">
                              {channel.url}
                            </a>
                          ) : (
                            '—'
                          )}
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
