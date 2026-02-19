'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ApiError } from '@/lib/api';
import {
  crmContactTagsApi,
  crmContactsApi,
  crmTagsApi,
  type Contact,
  type Tag as MapTag,
  type TagType,
} from '@/lib/api/crm';
import { Trash2, X } from 'lucide-react';

type MapClient = Contact;

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

  const [createClientInput, setCreateClientInput] = useState('');
  const [createClientChips, setCreateClientChips] = useState<string[]>([]);
  const [createClientError, setCreateClientError] = useState('');
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
  const [nameFilter, setNameFilter] = useState('');
  const clientDraftsRef = useRef(clientDrafts);
  const tagDraftsRef = useRef(tagDrafts);

  const openClientWindow = useCallback((clientId: number) => {
    window.open(`/contact/${clientId}`, '_blank', 'noopener');
  }, []);

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
        crmContactsApi.list(),
        crmTagsApi.list()
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
        setError('Не удалось загрузить клиентов и теги. Проверьте API /crm/contacts/ и /crm/tags/.');
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
    const search = nameFilter.trim().toLowerCase();
    return clients.filter((client) => {
      if (search && !(client.name ?? '').toLowerCase().includes(search)) return false;
      return TAG_TYPES.every((type) => {
        const selected = filters[type] ?? [];
        if (selected.length === 0) return true;
        const clientTags = client.tags?.[type] ?? [];
        return selected.some((id) => clientTags.includes(id));
      });
    });
  }, [clients, filters, nameFilter]);

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
      const updated = await crmContactsApi.update(clientId, { name });
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
      const updated = await crmTagsApi.update(tagId, { type, value });
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
      if (exists) {
        await crmContactTagsApi.delete({ contact_id: clientId, tag_id: tag.id });
      } else {
        await crmContactTagsApi.create({ contact_id: clientId, tag_id: tag.id });
      }
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

  const normalizeClientName = (value: string) => value.trim().replace(/\s+/g, ' ');

  const addClientNames = (rawNames: string[]) => {
    const cleaned = rawNames
      .map((item) => normalizeClientName(item))
      .filter((item) => item.length > 0);
    if (cleaned.length === 0) return;
    setCreateClientChips((prev) => {
      const existing = new Set(prev.map((item) => item.toLowerCase()));
      const next = [...prev];
      cleaned.forEach((item) => {
        const key = item.toLowerCase();
        if (!existing.has(key)) {
          existing.add(key);
          next.push(item);
        }
      });
      return next;
    });
    setCreateClientError('');
  };

  const handleClientPaste = (event: React.ClipboardEvent<HTMLInputElement>) => {
    const text = event.clipboardData.getData('text');
    if (!text) return;
    event.preventDefault();
    addClientNames(text.split(/\r?\n|\t/));
    setCreateClientInput('');
  };

  const handleClientKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      addClientNames([createClientInput]);
      setCreateClientInput('');
      return;
    }
    if (event.key === 'Backspace' && createClientInput.length === 0 && createClientChips.length > 0) {
      event.preventDefault();
      setCreateClientChips((prev) => prev.slice(0, -1));
    }
  };

  const handleClientBlur = () => {
    if (createClientInput.trim().length === 0) return;
    addClientNames([createClientInput]);
    setCreateClientInput('');
  };

  const removeClientChip = (value: string) => {
    setCreateClientChips((prev) => prev.filter((item) => item !== value));
  };

  const handleCreateClient = async () => {
    const pendingInput = normalizeClientName(createClientInput);
    const names = [...createClientChips, ...(pendingInput ? [pendingInput] : [])];
    if (names.length === 0 || creatingClient) {
      setCreateClientError('Введите хотя бы одно имя.');
      return;
    }
    setCreatingClient(true);
    setError(null);
    try {
      const results = await Promise.allSettled(names.map((name) => crmContactsApi.create({ name })));
      const created = results
        .filter((result): result is PromiseFulfilledResult<MapClient> => result.status === 'fulfilled')
        .map((result) => normalizeClient(result.value));
      if (created.length > 0) {
        const next = [...created, ...clients];
        setClients(next);
        syncClientDrafts(next);
        setCreateClientInput('');
        setCreateClientChips([]);
        setCreateClientError('');
      }
      const failedCount = results.length - created.length;
      if (failedCount > 0) {
        toast.error(`Не удалось создать клиентов: ${failedCount}`);
      }
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
      await crmContactsApi.delete(client.id);
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
      const created = await crmTagsApi.create({ type: createTagType, value });
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
      await crmTagsApi.delete(tag.id);
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
      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      <div className="space-y-6">
        <div className="space-y-4">

          <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <div
                className={`flex min-h-10 w-full max-w-xl flex-wrap items-center gap-2 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 max-h-32 overflow-y-auto ${
                  createClientError ? 'border-red-500 focus-within:ring-red-500' : ''
                }`}
              >
                {createClientChips.map((chip) => (
                  <span
                    key={chip}
                    className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-foreground"
                  >
                    <span className="max-w-[12rem] truncate">{chip}</span>
                    <button
                      type="button"
                      onClick={() => removeClientChip(chip)}
                      className="rounded-full p-0.5 text-muted-foreground transition hover:text-foreground"
                      aria-label={`Удалить ${chip}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  value={createClientInput}
                  onChange={(e) => setCreateClientInput(e.target.value)}
                  onKeyDown={handleClientKeyDown}
                  onPaste={handleClientPaste}
                  onBlur={handleClientBlur}
                  placeholder={createClientChips.length === 0 ? 'Введите имя или вставьте столбец' : ''}
                  className="min-w-[180px] flex-1 border-0 bg-transparent p-0 text-sm outline-none placeholder:text-muted-foreground"
                />
              </div>
              <Button
                onClick={handleCreateClient}
                disabled={creatingClient || (createClientChips.length === 0 && createClientInput.trim().length === 0)}
              >
                {creatingClient ? 'Создание…' : 'Добавить клиента'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">Вставьте столбец из Excel — каждое имя станет тегом.</p>
            {createClientError ? (
              <p className="text-xs text-red-500">{createClientError}</p>
            ) : null}
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Загружаем клиентов...</p>
          ) : clients.length === 0 ? (
            <p className="text-sm text-muted-foreground">Клиенты пока не добавлены.</p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border bg-card/70 p-4 shadow-sm">
                <div className="grid gap-3 lg:grid-cols-[minmax(200px,260px)_repeat(3,minmax(200px,1fr))]">
                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-muted-foreground">Имя клиента</div>
                    <Input
                      value={nameFilter}
                      onChange={(e) => setNameFilter(e.target.value)}
                      placeholder="Поиск по имени"
                      className="h-8 text-xs"
                    />
                  </div>
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
                  <Card
                    key={client.id}
                    role="button"
                    tabIndex={0}
                    onClick={(event) => {
                      const target = event.target as HTMLElement | null;
                      if (target?.closest('input,textarea,button,a,select')) return;
                      openClientWindow(client.id);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openClientWindow(client.id);
                      }
                    }}
                    className="cursor-pointer transition hover:shadow-sm"
                  >
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

          <div className="space-y-3 pt-2">
            <p className="text-sm text-muted-foreground">
              Сводка по целям, болям и опыту клиентов. Данные синхронизируются с таблицами clients, tags и client_tags.
            </p>
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
          </div>
        </div>
      </div>
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
