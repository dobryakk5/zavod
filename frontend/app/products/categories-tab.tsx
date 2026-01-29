'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Trash2 } from 'lucide-react';
import { mapTagsApi, type MapTag, type TagType } from '@/lib/api/mapTags';

const TAG_TYPES: TagType[] = ['goal', 'pain', 'experience'];
const TAG_LABELS: Record<TagType, string> = {
  goal: 'Цель',
  pain: 'Боль',
  experience: 'Опыт'
};

export function CategoriesTab() {
  const [tags, setTags] = useState<MapTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [createTagType, setCreateTagType] = useState<TagType>('goal');
  const [createTagValue, setCreateTagValue] = useState('');
  const [creatingTag, setCreatingTag] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const tagsData = await mapTagsApi.list();
      setTags(tagsData);
    } catch (err) {
      console.error('Failed to load tags', err);
      setError('Не удалось загрузить теги');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleCreateTag = async () => {
    const value = createTagValue.trim();
    if (!value || creatingTag) return;
    setCreatingTag(true);
    setError(null);
    try {
      const created = await mapTagsApi.create({ type: createTagType, value });
      setTags(prev => [created, ...prev]);
      setCreateTagValue('');
    } catch (err) {
      console.error('Failed to create tag', err);
      setError('Не удалось создать тег');
    } finally {
      setCreatingTag(false);
    }
  };

  const handleDeleteTag = async (tag: MapTag) => {
    const prev = tags;
    setTags(prev => prev.filter(item => item.id !== tag.id));
    try {
      await mapTagsApi.delete(tag.id);
    } catch (err) {
      console.error('Failed to delete tag', err);
      setTags(prev); // Restore if deletion failed
    }
  };

  const tagsByType = TAG_TYPES.reduce((acc, type) => {
    acc[type] = tags.filter(tag => tag.type === type);
    return acc;
  }, {} as Record<TagType, MapTag[]>);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Управление тегами</h2>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-full max-w-[220px]">
            <Select value={createTagType} onValueChange={(value) => setCreateTagType(value as TagType)}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Тип тега" />
              </SelectTrigger>
              <SelectContent>
                {TAG_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {TAG_LABELS[type]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Input
            placeholder="Название тега"
            value={createTagValue}
            onChange={(e) => setCreateTagValue(e.target.value)}
            className="w-full max-w-sm"
          />
          <Button onClick={handleCreateTag} disabled={creatingTag || !createTagValue.trim()}>
            {creatingTag ? 'Создание…' : 'Добавить тег'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Введите тег и тип, затем нажмите «Добавить тег»</p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Загружаем теги...</p>
      ) : tags.length === 0 ? (
        <p className="text-sm text-muted-foreground">Теги пока не добавлены.</p>
      ) : (
        <div className="space-y-6">
          {TAG_TYPES.map(type => (
            <Card key={type}>
              <CardHeader>
                <CardTitle>{TAG_LABELS[type]}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl border bg-card/70 shadow-sm">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Тег</TableHead>
                        <TableHead className="w-[120px]">Действия</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tagsByType[type].map((tag) => (
                        <TableRow key={tag.id}>
                          <TableCell className="font-medium">{tag.value}</TableCell>
                          <TableCell>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-red-600 hover:text-red-700"
                              onClick={() => handleDeleteTag(tag)}
                              aria-label="Удалить тег"
                              title="Удалить тег"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}