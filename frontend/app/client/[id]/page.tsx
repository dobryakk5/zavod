'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ApiError, apiFetch } from '@/lib/api';
import { mapClientsApi, type MapClient } from '@/lib/api/mapClients';
import { mapTagsApi, type MapTag, type TagType } from '@/lib/api/mapTags';

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

export default function ClientPage() {
  const params = useParams<{ id: string }>();
  const clientId = Number(params?.id);
  const [client, setClient] = useState<MapClient | null>(null);
  const [clientName, setClientName] = useState('');
  const [tags, setTags] = useState<MapTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [pendingTags, setPendingTags] = useState<Record<number, boolean>>({});

  const tagsByType = useMemo(() => {
    return TAG_TYPES.reduce<Record<TagType, MapTag[]>>((acc, type) => {
      acc[type] = tags.filter((tag) => tag.type === type);
      return acc;
    }, { goal: [], pain: [], experience: [] });
  }, [tags]);

  const loadClient = useCallback(async () => {
    if (!clientId || Number.isNaN(clientId)) {
      setError('Некорректный идентификатор клиента.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [clientData, tagsData] = await Promise.all([
        mapClientsApi.detail(clientId),
        mapTagsApi.list()
      ]);
      const normalized = normalizeClient(clientData);
      setClient(normalized);
      setClientName(normalized.name ?? '');
      setTags(tagsData);
    } catch (err: unknown) {
      console.error('Failed to load client', err);
      if (err instanceof ApiError && err.status === 404) {
        setError('Клиент не найден.');
      } else {
        setError('Не удалось загрузить клиента. Проверьте API /clients/ и /tags/.');
      }
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void loadClient();
  }, [loadClient]);

  const handleSaveName = async () => {
    if (!client) return;
    const trimmed = clientName.trim();
    if (!trimmed) {
      setNameError('Название не может быть пустым.');
      return;
    }

    setSavingName(true);
    setNameError(null);
    try {
      const updated = await mapClientsApi.update(client.id, { name: trimmed });
      setClient((prev) => (prev ? { ...prev, ...updated } : updated));
      setClientName(updated.name ?? trimmed);
    } catch (err) {
      console.error('Failed to save client name', err);
      setNameError('Не удалось сохранить. Попробуйте ещё раз.');
    } finally {
      setSavingName(false);
    }
  };

  const toggleTag = async (tag: MapTag) => {
    if (!client) return;
    const selected = client.tags?.[tag.type] ?? [];
    const exists = selected.includes(tag.id);
    const previous = client;

    setClient({
      ...client,
      tags: {
        ...client.tags,
        [tag.type]: exists ? selected.filter((id) => id !== tag.id) : [...selected, tag.id]
      }
    });
    setPendingTags((prev) => ({ ...prev, [tag.id]: true }));

    try {
      await apiFetch('/client-tags/', {
        method: 'POST',
        body: { clientId: client.id, tagId: tag.id }
      });
    } catch (err) {
      console.error('Failed to update client tag', err);
      setClient(previous);
      setError('Не удалось обновить теги клиента.');
    } finally {
      setPendingTags((prev) => {
        const next = { ...prev };
        delete next[tag.id];
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Загружаем клиента…
      </div>
    );
  }

  if (!client) {
    return (
      <div className="space-y-4">
        <Button asChild variant="outline" size="sm">
          <Link href="/clients">
            <ArrowLeft className="mr-2 h-4 w-4" />
            К списку клиентов
          </Link>
        </Button>
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <Button asChild variant="outline" size="sm" className="w-fit">
          <Link href="/clients">
            <ArrowLeft className="mr-2 h-4 w-4" />
            К списку клиентов
          </Link>
        </Button>
        <div>
          <p className="text-sm font-medium text-muted-foreground uppercase">Клиент</p>
          <h1 className="text-3xl font-bold">{client.name}</h1>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Данные клиента</CardTitle>
          <CardDescription>Обновите имя и сохраните изменения.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="w-full max-w-md space-y-2">
            <label className="text-sm font-medium" htmlFor="client-name">
              Имя клиента
            </label>
            <Input
              id="client-name"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="Название клиента"
              aria-invalid={nameError ? true : undefined}
            />
            {nameError ? <div className="text-xs text-destructive">{nameError}</div> : null}
          </div>
          <Button onClick={handleSaveName} disabled={savingName || clientName.trim().length === 0}>
            {savingName ? 'Сохраняем…' : 'Сохранить'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Теги клиента</CardTitle>
          <CardDescription>Отмечайте цели, боли и опыт клиента.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-3">
            {TAG_TYPES.map((type) => (
              <TagColumn
                key={type}
                title={TAG_LABELS[type]}
                type={type}
                client={client}
                tags={tagsByType[type]}
                onToggle={toggleTag}
                pending={pendingTags}
              />
            ))}
          </div>
        </CardContent>
      </Card>
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
  onToggle: (tag: MapTag) => void;
  pending: Record<number, boolean>;
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
            return (
              <button
                key={tag.id}
                type="button"
                disabled={pending[tag.id]}
                onClick={() => onToggle(tag)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  checked
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                } ${pending[tag.id] ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
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
