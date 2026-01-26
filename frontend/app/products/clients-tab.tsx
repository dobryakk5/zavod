'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ApiError, apiFetch } from '@/lib/api';
import { mapClientsApi, type MapClient } from '@/lib/api/mapClients';
import { mapTagsApi, type MapTag, type TagType } from '@/lib/api/mapTags';
import { Trash2 } from 'lucide-react';

type ClientDraft = {
  name: string;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  revision: number;
};

type TagDraft = {
  type: TagType;
  value: string;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  revision: number;
};

const TAG_TYPES: TagType[] = ['goal', 'pain', 'experience'];
const TAG_LABELS: Record<TagType, string> = {
  goal: 'Цель',
  pain: 'Боль',
  experience: 'Опыт'
};

const emptyTags = () => ({
  goal: [] as number[],
  pain: [] as number[],
  experience: [] as number[]
});

const normalizeClient = (client: MapClient): MapClient => ({
  ...client,
  tags: {
    ...emptyTags(),
    ...(client.tags ?? {})
  }
});

export function ClientsTab() {
  const [clients, setClients] = useState<MapClient[]>([]);
  const [tags, setTags] = useState<MapTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});

  const [createClientName, setCreateClientName] = useState('');
  const [creatingClient, setCreatingClient] = useState(false);

  const [createTagType, setCreateTagType] = useState<TagType>('goal');
  const [createTagValue, setCreateTagValue] = useState('');
  const [creatingTag, setCreatingTag] = useState(false);

  const [clientDrafts, setClientDrafts] = useState<Record<number, ClientDraft>>({});
  const [tagDrafts, setTagDrafts] = useState<Record<number, TagDraft>>({});
  const [filters, setFilters] = useState<Record<TagType, number[]>>({
    goal: [],
    pain: [],
    experience: []
  });
  const clientDraftsRef = useRef(clientDrafts);
  const tagDraftsRef = useRef(tagDrafts);

  useEffect(() => {
    clientDraftsRef.current = clientDrafts;
  }, [clientDrafts]);

  useEffect(() => {
    tagDraftsRef.current = tagDrafts;
  }, [tagDrafts]);

  const syncClientDrafts = useCallback((items: MapClient[]) => {
    setClientDrafts((prev) => {
      const next: Record<number, ClientDraft> = { ...prev };
      for (const client of items) {
        const existing = next[client.id];
        const freshName = client.name ?? '';
        if (!existing) {
          next[client.id] = {
            name: freshName,
            dirty: false,
            saving: false,
            error: null,
            revision: 0
          };
          continue;
        }

        if (!existing.dirty && !existing.saving) {
          next[client.id] = {
            ...existing,
            name: freshName,
            error: null
          };
        }
      }
      return next;
    });
  }, []);

  const syncTagDrafts = useCallback((items: MapTag[]) => {
    setTagDrafts((prev) => {
      const next: Record<number, TagDraft> = { ...prev };
      for (const tag of items) {
        const existing = next[tag.id];
        const freshValue = tag.value ?? '';
        const freshType = tag.type;
        if (!existing) {
          next[tag.id] = {
            type: freshType,
            value: freshValue,
            dirty: false,
            saving: false,
            error: null,
            revision: 0
          };
          continue;
        }

        if (!existing.dirty && !existing.saving) {
          next[tag.id] = {
            ...existing,
            type: freshType,
            value: freshValue,
            error: null
          };
        }
      }
      return next;
    });
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [clientsData, tagsData] = await Promise.all([
        mapClientsApi.list(),
        mapTagsApi.list()
      ]);

      const normalizedClients = clientsData.map(normalizeClient);
      setClients(normalizedClients);
      setTags(tagsData);
      syncClientDrafts(normalizedClients);
      syncTagDrafts(tagsData);
    } catch (err) {
      console.error('Failed to load clients map data', err);
      if (err instanceof ApiError && err.status === 404) {
        setClients([]);
        setTags([]);
        syncClientDrafts([]);
        syncTagDrafts([]);
        setError(null);
      } else {
        setError('Не удалось загрузить клиентов и теги. Проверьте API /clients/ и /tags/.');
      }
    } finally {
      setLoading(false);
    }
  }, [syncClientDrafts, syncTagDrafts]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const tagsByType = useMemo(() => {
    return TAG_TYPES.reduce((acc, type) => {
      acc[type] = tags.filter((tag) => tag.type === type);
      return acc;
    }, {} as Record<TagType, MapTag[]>);
  }, [tags]);

  useEffect(() => {
    setFilters((prev) => {
      const next: Record<TagType, number[]> = { ...prev };
      let changed = false;
      TAG_TYPES.forEach((type) => {
        const selected = prev[type] ?? [];
        if (selected.length === 0) return;
        const validIds = new Set(tagsByType[type].map((tag) => tag.id));
        const filtered = selected.filter((id) => validIds.has(id));
        if (filtered.length !== selected.length) {
          next[type] = filtered;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [tagsByType]);

  const tagStats = useMemo(() => {
    const stats: Record<number, number> = {};
    clients.forEach((client) => {
      TAG_TYPES.forEach((type) => {
        (client.tags?.[type] ?? []).forEach((tagId) => {
          stats[tagId] = (stats[tagId] ?? 0) + 1;
        });
      });
    });
    return stats;
  }, [clients]);

  const totalClients = clients.length;
  const totalTags = tags.length;
  const totalAssignments = useMemo(() => {
    return clients.reduce((sum, client) => {
      return sum + TAG_TYPES.reduce((inner, type) => inner + (client.tags?.[type]?.length ?? 0), 0);
    }, 0);
  }, [clients]);

  const filteredClients = useMemo(() => {
    return clients.filter((client) =>
      TAG_TYPES.every((type) => {
        const selected = filters[type] ?? [];
        if (selected.length === 0) return true;
        const clientTags = client.tags?.[type] ?? [];
        return selected.some((id) => clientTags.includes(id));
      })
    );
  }, [clients, filters]);

  const saveClientDraft = useCallback(async (clientId: number, override?: Partial<ClientDraft>) => {
    const current = clientDraftsRef.current[clientId];
    if (!current) return;
    const draft = { ...current, ...override };
    if (!draft || (!draft.dirty && !override)) return;
    if (draft.saving) return;

    const savedRevision = draft.revision;
    const name = (draft.name ?? '').trim();

    if (!name) {
      setClientDrafts((prev) => {
        const existing = prev[clientId];
        if (!existing) return prev;
        return { ...prev, [clientId]: { ...existing, error: 'Название не может быть пустым.' } };
      });
      return;
    }

    setClientDrafts((prev) => {
      const existing = prev[clientId];
      if (!existing || existing.saving) return prev;
      return { ...prev, [clientId]: { ...existing, saving: true, error: null } };
    });

    try {
      const updated = await mapClientsApi.update(clientId, { name });
      setClients((prev) => prev.map((client) => (client.id === clientId ? { ...client, name: updated.name ?? name } : client)));
      setClientDrafts((prev) => {
        const existing = prev[clientId];
        if (!existing) return prev;
        const shouldClearDirty = existing.revision === savedRevision;
        return {
          ...prev,
          [clientId]: {
            ...existing,
            name: shouldClearDirty ? updated.name ?? name : existing.name,
            dirty: shouldClearDirty ? false : existing.dirty,
            saving: false,
            error: null
          }
        };
      });
    } catch (err) {
      console.error('Failed to autosave client', clientId, err);
      setClientDrafts((prev) => {
        const existing = prev[clientId];
        if (!existing) return prev;
        return { ...prev, [clientId]: { ...existing, saving: false, error: 'Не удалось сохранить. Повторим через 5 сек.' } };
      });
    }
  }, []);

  const saveTagDraft = useCallback(async (tagId: number, override?: Partial<TagDraft>) => {
    const current = tagDraftsRef.current[tagId];
    if (!current) return;
    const draft = { ...current, ...override };
    if (!draft || (!draft.dirty && !override)) return;
    if (draft.saving) return;

    const savedRevision = draft.revision;
    const value = (draft.value ?? '').trim();
    const type = draft.type;

    if (!value) {
      setTagDrafts((prev) => {
        const existing = prev[tagId];
        if (!existing) return prev;
        return { ...prev, [tagId]: { ...existing, error: 'Название не может быть пустым.' } };
      });
      return;
    }

    setTagDrafts((prev) => {
      const existing = prev[tagId];
      if (!existing || existing.saving) return prev;
      return { ...prev, [tagId]: { ...existing, saving: true, error: null } };
    });

    try {
      const updated = await mapTagsApi.update(tagId, { type, value });
      setTags((prev) => prev.map((tag) => (tag.id === tagId ? { ...tag, ...updated } : tag)));
      if (current && updated.type && updated.type !== current.type) {
        setClients((prev) =>
          prev.map((client) => {
            const hasTag = TAG_TYPES.some((tagType) => client.tags?.[tagType]?.includes(tagId));
            if (!hasTag) return client;
            const nextTags = { ...emptyTags(), ...(client.tags ?? {}) };
            TAG_TYPES.forEach((tagType) => {
              nextTags[tagType] = (nextTags[tagType] ?? []).filter((id) => id !== tagId);
            });
            nextTags[updated.type] = [...(nextTags[updated.type] ?? []), tagId];
            return { ...client, tags: nextTags };
          })
        );
      }

      setTagDrafts((prev) => {
        const existing = prev[tagId];
        if (!existing) return prev;
        const shouldClearDirty = existing.revision === savedRevision;
        return {
          ...prev,
          [tagId]: {
            ...existing,
            type: shouldClearDirty ? updated.type ?? type : existing.type,
            value: shouldClearDirty ? updated.value ?? value : existing.value,
            dirty: shouldClearDirty ? false : existing.dirty,
            saving: false,
            error: null
          }
        };
      });
    } catch (err) {
      console.error('Failed to autosave tag', tagId, err);
      setTagDrafts((prev) => {
        const existing = prev[tagId];
        if (!existing) return prev;
        return { ...prev, [tagId]: { ...existing, saving: false, error: 'Не удалось сохранить. Повторим через 5 сек.' } };
      });
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      const clientSnapshot = clientDraftsRef.current;
      for (const [id, draft] of Object.entries(clientSnapshot)) {
        const clientId = Number(id);
        if (Number.isNaN(clientId)) continue;
        if (!draft?.dirty || draft.saving) continue;
        void saveClientDraft(clientId);
      }

      const tagSnapshot = tagDraftsRef.current;
      for (const [id, draft] of Object.entries(tagSnapshot)) {
        const tagId = Number(id);
        if (Number.isNaN(tagId)) continue;
        if (!draft?.dirty || draft.saving) continue;
        void saveTagDraft(tagId);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [saveClientDraft, saveTagDraft]);

  const toggleTag = async (clientId: number, tag: MapTag) => {
    const client = clients.find((item) => item.id === clientId);
    if (!client) return;

    const selected = client.tags?.[tag.type] ?? [];
    const exists = selected.includes(tag.id);
    const pendingKey = `${clientId}:${tag.id}`;

    if (pending[pendingKey]) return;

    let snapshot: MapClient[] | null = null;
    setPending((prev) => ({ ...prev, [pendingKey]: true }));
    setClients((prev) => {
      snapshot = prev;
      return prev.map((item) => {
        if (item.id !== clientId) return item;
        const updatedTags = item.tags?.[tag.type] ?? [];
        return {
          ...item,
          tags: {
            ...item.tags,
            [tag.type]: exists
              ? updatedTags.filter((id) => id !== tag.id)
              : [...updatedTags, tag.id]
          }
        };
      });
    });

    try {
      await apiFetch('/client-tags/', {
        method: exists ? 'DELETE' : 'POST',
        body: { clientId, tagId: tag.id }
      });
    } catch (err) {
      console.error('Failed to update client tag', err);
      toast.error('Не удалось обновить тег клиента');
      if (snapshot) {
        setClients(snapshot);
      }
    } finally {
      setPending((prev) => {
        const next = { ...prev };
        delete next[pendingKey];
        return next;
      });
    }
  };

  const handleCreateClient = async () => {
    const name = createClientName.trim();
    if (!name || creatingClient) return;
    setCreatingClient(true);
    setError(null);
    try {
      const created = await mapClientsApi.create({ name });
      const normalized = normalizeClient(created);
      const next = [normalized, ...clients];
      setClients(next);
      syncClientDrafts(next);
      setCreateClientName('');
    } catch (err) {
      console.error('Failed to create client', err);
      setError('Не удалось создать клиента.');
    } finally {
      setCreatingClient(false);
    }
  };

  const handleDeleteClient = async (client: MapClient) => {
    const ok = window.confirm(`Удалить клиента «${client.name}»? Это действие нельзя отменить.`);
    if (!ok) return;
    setError(null);
    const prev = clients;
    setClients((items) => items.filter((item) => item.id !== client.id));
    setClientDrafts((prevDrafts) => {
      const next = { ...prevDrafts };
      delete next[client.id];
      return next;
    });
    try {
      await mapClientsApi.delete(client.id);
    } catch (err) {
      console.error('Failed to delete client', err);
      toast.error('Не удалось удалить клиента.');
      setClients(prev);
      syncClientDrafts(prev);
    }
  };

  const handleCreateTag = async () => {
    const value = createTagValue.trim();
    if (!value || creatingTag) return;
    setCreatingTag(true);
    setError(null);
    try {
      const created = await mapTagsApi.create({ type: createTagType, value });
      const next = [created, ...tags];
      setTags(next);
      syncTagDrafts(next);
      setCreateTagValue('');
    } catch (err) {
      console.error('Failed to create tag', err);
      toast.error('Не удалось создать тег.');
    } finally {
      setCreatingTag(false);
    }
  };

  const handleDeleteTag = async (tag: MapTag) => {
    const prev = tags;
    setTags((items) => items.filter((item) => item.id !== tag.id));
    setTagDrafts((prevDrafts) => {
      const next = { ...prevDrafts };
      delete next[tag.id];
      return next;
    });
    setClients((prevClients) =>
      prevClients.map((client) => {
        const nextTags = { ...emptyTags(), ...(client.tags ?? {}) };
        TAG_TYPES.forEach((tagType) => {
          nextTags[tagType] = (nextTags[tagType] ?? []).filter((id) => id !== tag.id);
        });
        return { ...client, tags: nextTags };
      })
    );
    try {
      await mapTagsApi.delete(tag.id);
    } catch (err) {
      console.error('Failed to delete tag', err);
      toast.error('Не удалось удалить тег.');
      setTags(prev);
      syncTagDrafts(prev);
    }
  };

  const clientRows = useMemo(() => {
    return clients.map((client) => {
      const draft = clientDrafts[client.id];
      return {
        client,
        name: draft?.name ?? client.name,
        saving: draft?.saving ?? false,
        error: draft?.error ?? null
      };
    });
  }, [clients, clientDrafts]);

  const tagRows = useMemo(() => {
    return tags.map((tag) => {
      const draft = tagDrafts[tag.id];
      return {
        tag,
        type: draft?.type ?? tag.type,
        value: draft?.value ?? tag.value,
        saving: draft?.saving ?? false,
        error: draft?.error ?? null
      };
    });
  }, [tags, tagDrafts]);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold">Клиенты</h2>
        <p className="text-sm text-muted-foreground">
          Сводка по целям, болям и опыту клиентов. Данные синхронизируются с таблицами clients, tags и client_tags.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Клиенты</CardTitle>
            <CardDescription>Всего в базе</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{totalClients}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Теги</CardTitle>
            <CardDescription>Всего категорий</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{totalTags}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Назначения</CardTitle>
            <CardDescription>Всего связок клиент - тег</CardDescription>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{totalAssignments}</CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList>
          <TabsTrigger value="clients">Список клиентов</TabsTrigger>
          <TabsTrigger value="categories">Категории</TabsTrigger>
        </TabsList>

        <TabsContent value="clients" className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Отметьте теги для каждого клиента. Изменения сохраняются сразу.
            </p>
            <Button variant="outline" size="sm" onClick={() => void loadData()} disabled={loading}>
              {loading ? 'Обновляем...' : 'Обновить'}
            </Button>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <Input
                placeholder="Новый клиент"
                value={createClientName}
                onChange={(e) => setCreateClientName(e.target.value)}
                className="w-full max-w-sm"
              />
              <Button onClick={handleCreateClient} disabled={creatingClient || !createClientName.trim()}>
                {creatingClient ? 'Создание…' : 'Добавить клиента'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Введите название и нажмите «Добавить клиента»</p>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Загружаем клиентов...</p>
          ) : clients.length === 0 ? (
            <p className="text-sm text-muted-foreground">Клиенты пока не добавлены.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border bg-card/70 p-4 shadow-sm">
                <div className="grid gap-3 lg:grid-cols-[minmax(200px,260px)_repeat(3,minmax(200px,1fr))]">
                  <div className="text-xs font-semibold uppercase text-muted-foreground">Фильтры по тегам</div>
                  {TAG_TYPES.map((type) => (
                    <div key={`filter-${type}`} className="space-y-2">
                      <div className="text-xs font-semibold text-muted-foreground">{TAG_LABELS[type]}</div>
                      {tagsByType[type].length === 0 ? (
                        <p className="text-sm text-muted-foreground">Нет тегов</p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => setFilters((prev) => ({ ...prev, [type]: [] }))}
                            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                              filters[type].length === 0
                                ? 'bg-primary text-primary-foreground shadow-sm'
                                : 'bg-muted text-muted-foreground hover:bg-muted/80'
                            }`}
                          >
                            Все
                          </button>
                          {tagsByType[type].map((tag) => {
                            const selected = filters[type].includes(tag.id);
                            return (
                              <button
                                key={tag.id}
                                type="button"
                                onClick={() =>
                                  setFilters((prev) => {
                                    const existing = prev[type] ?? [];
                                    const next = selected
                                      ? existing.filter((id) => id !== tag.id)
                                      : [...existing, tag.id];
                                    return { ...prev, [type]: next };
                                  })
                                }
                                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                                  selected
                                    ? 'bg-primary text-primary-foreground shadow-sm'
                                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                                }`}
                              >
                                {tag.value}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {filteredClients.length === 0 ? (
                <p className="text-sm text-muted-foreground">Клиенты по выбранным тегам не найдены.</p>
              ) : (
                filteredClients.map((client) => {
                const row = clientRows.find((item) => item.client.id === client.id);
                return (
                  <Card key={client.id}>
                    <CardContent className="p-4">
                      <div className="grid gap-4 lg:grid-cols-[minmax(200px,260px)_repeat(3,minmax(200px,1fr))]">
                        <div className="space-y-2">
                          <Input
                            value={row?.name ?? client.name}
                            onChange={(e) => {
                              const nextName = e.target.value;
                              setClientDrafts((prev) => {
                                const existing = prev[client.id] ?? {
                                  name: client.name ?? '',
                                  dirty: false,
                                  saving: false,
                                  error: null,
                                  revision: 0
                                };
                                return {
                                  ...prev,
                                  [client.id]: {
                                    ...existing,
                                    name: nextName,
                                    dirty: true,
                                    error: null,
                                    revision: existing.revision + 1
                                  }
                                };
                              });
                            }}
                            onBlur={() => void saveClientDraft(client.id)}
                            className="h-9"
                          />
                          {row?.error ? <div className="text-xs text-destructive">{row.error}</div> : null}
                          {row?.saving ? <div className="text-xs text-muted-foreground">Сохранение…</div> : null}
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => void handleDeleteClient(client)}
                            aria-label="Удалить клиента"
                            title="Удалить клиента"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                        {TAG_TYPES.map((type) => (
                          <TagColumn
                            key={`${client.id}-${type}`}
                            title={TAG_LABELS[type]}
                            type={type}
                            client={client}
                            tags={tagsByType[type]}
                            onToggle={toggleTag}
                            pending={pending}
                          />
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                );
              })
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="categories" className="space-y-4">
          <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-full max-w-[220px]">
                <Select value={createTagType} onValueChange={(value) => setCreateTagType(value as TagType)}>
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="Категория" />
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
            <p className="text-xs text-muted-foreground">Введите тег и категорию, затем нажмите «Добавить тег»</p>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Загружаем категории...</p>
          ) : tags.length === 0 ? (
            <p className="text-sm text-muted-foreground">Теги пока не добавлены.</p>
          ) : (
            <div className="rounded-xl border bg-card/70 shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Категория</TableHead>
                    <TableHead>Тег</TableHead>
                    <TableHead className="w-[120px]">Клиентов</TableHead>
                    <TableHead className="text-right">Действия</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tagRows.map(({ tag, type, value, saving, error: rowError }) => (
                    <TableRow key={tag.id}>
                      <TableCell className="w-[180px]">
                        <Select
                          value={type}
                          onValueChange={(nextType) => {
                            const existing = tagDraftsRef.current[tag.id] ?? {
                              type: tag.type,
                              value: tag.value ?? '',
                              dirty: false,
                              saving: false,
                              error: null,
                              revision: 0
                            };
                            const nextRevision = existing.revision + 1;
                            setTagDrafts((prev) => ({
                              ...prev,
                              [tag.id]: {
                                ...existing,
                                type: nextType as TagType,
                                dirty: true,
                                error: null,
                                revision: nextRevision
                              }
                            }));
                            void saveTagDraft(tag.id, {
                              type: nextType as TagType,
                              value,
                              revision: nextRevision,
                              dirty: true
                            });
                          }}
                        >
                          <SelectTrigger className="h-9">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {TAG_TYPES.map((tagType) => (
                              <SelectItem key={tagType} value={tagType}>
                                {TAG_LABELS[tagType]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Input
                          value={value}
                          onChange={(e) => {
                            const nextValue = e.target.value;
                            setTagDrafts((prev) => {
                              const existing = prev[tag.id] ?? {
                                type: tag.type,
                                value: tag.value ?? '',
                                dirty: false,
                                saving: false,
                                error: null,
                                revision: 0
                              };
                              return {
                                ...prev,
                                [tag.id]: {
                                  ...existing,
                                  value: nextValue,
                                  dirty: true,
                                  error: null,
                                  revision: existing.revision + 1
                                }
                              };
                            });
                          }}
                          onBlur={() => void saveTagDraft(tag.id)}
                          className="h-9"
                          aria-invalid={rowError ? true : undefined}
                        />
                        {rowError ? <div className="mt-1 text-xs text-destructive">{rowError}</div> : null}
                        {saving ? <div className="mt-1 text-xs text-muted-foreground">Сохранение…</div> : null}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {tagStats[tag.id] ?? 0}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => void handleDeleteTag(tag)}
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
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TagColumn({
  title,
  type,
  client,
  tags,
  onToggle,
  pending
}: {
  title: string;
  type: TagType;
  client: MapClient;
  tags: MapTag[];
  onToggle: (clientId: number, tag: MapTag) => void;
  pending: Record<string, boolean>;
}) {
  return (
    <div className="space-y-2">
      <div className="text-sm font-semibold text-muted-foreground">{title}</div>
      {tags.length === 0 ? (
        <p className="text-sm text-muted-foreground">Нет тегов</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => {
            const checked = client.tags?.[type]?.includes(tag.id) ?? false;
            const pendingKey = `${client.id}:${tag.id}`;
            return (
              <button
                key={tag.id}
                type="button"
                disabled={pending[pendingKey]}
                onClick={() => onToggle(client.id, tag)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  checked
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${pending[pendingKey] ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                {tag.value}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
