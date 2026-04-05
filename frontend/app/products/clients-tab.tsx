'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
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
type DealStage = Exclude<Contact['deal_stage'], undefined | ''>;
type DealLossReasonCode = Exclude<Contact['deal_loss_reason_code'], undefined | ''>;

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

const DEAL_STAGE_ORDER: DealStage[] = ['new_lead', 'interest', 'call', 'payment_expected', 'paid', 'lost'];

const DEAL_STAGE_LABELS: Record<DealStage, string> = {
  new_lead: 'Новый лид',
  interest: 'Интерес',
  call: 'Созвон',
  payment_expected: 'Оплата ожидается',
  paid: 'Оплачено',
  lost: 'Потеряно',
};

const DEAL_STAGE_BADGE_VARIANTS: Record<DealStage, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  new_lead: 'outline',
  interest: 'secondary',
  call: 'default',
  payment_expected: 'secondary',
  paid: 'default',
  lost: 'destructive',
};

const DEAL_LOSS_REASON_OPTIONS: Array<{ value: DealLossReasonCode; label: string }> = [
  { value: 'price', label: 'Дорого' },
  { value: 'timing', label: 'Не вовремя' },
  { value: 'no_response', label: 'Не отвечает' },
  { value: 'not_fit', label: 'Не подходит' },
  { value: 'competitor', label: 'Ушёл к конкуренту' },
  { value: 'priority_changed', label: 'Изменился приоритет' },
  { value: 'other', label: 'Другое' },
];

const DEAL_LOSS_REASON_LABELS: Record<DealLossReasonCode, string> = DEAL_LOSS_REASON_OPTIONS.reduce(
  (acc, item) => {
    acc[item.value] = item.label;
    return acc;
  },
  {} as Record<DealLossReasonCode, string>
);

const LOSS_COMMENT_TEMPLATES: Record<DealLossReasonCode, string[]> = {
  price: ['Дорого на текущий момент', 'Сравнивает с более дешёвым вариантом', 'Нужен более простой пакет'],
  timing: ['Вернётся позже', 'Сейчас не в приоритете', 'Перенёс решение на следующий месяц'],
  no_response: ['Перестал отвечать после созвона', 'Нет ответа после отправки предложения', 'Не выходит на связь'],
  not_fit: ['Запрос вне нашей специализации', 'Формат работы не подошёл', 'Нужна другая услуга'],
  competitor: ['Выбрали другого подрядчика', 'Остались у текущего специалиста', 'Ушли в другой сервис'],
  priority_changed: ['Сменился приоритет в бизнесе', 'Заморозили проект', 'Отложили направление'],
  other: ['Решили не продолжать', 'Пока без комментариев', 'Нужно уточнение позже'],
};

const GENERIC_LOSS_COMMENT_TEMPLATES = ['Вернуться через 2 недели', 'Сделать follow-up позже', 'Уточнить причину подробнее'];

function normalizeExplicitDealStage(raw: unknown): DealStage | null {
  const value = String(raw ?? '').trim().toLowerCase();
  if (DEAL_STAGE_ORDER.includes(value as DealStage)) {
    return value as DealStage;
  }
  return null;
}

function normalizeDealStage(client: MapClient): DealStage {
  return normalizeExplicitDealStage(client.deal_stage) ?? 'new_lead';
}

function normalizeDealSource(client: MapClient): string {
  const raw = String(client.source ?? '').trim();
  return raw || 'Без источника';
}

function resolveDealManagerLabel(client: MapClient): string {
  const dynamic = client as MapClient & {
    manager_name?: string | null;
    responsible_name?: string | null;
    assignee_name?: string | null;
  };
  const raw = dynamic.manager_name ?? dynamic.responsible_name ?? dynamic.assignee_name ?? '';
  return String(raw || '').trim() || 'Не назначен';
}

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
  const [workspaceMode] = useState<'clients' | 'deals'>('clients');
  const [nameFilter, setNameFilter] = useState('');
  const [dealNameFilter, setDealNameFilter] = useState('');
  const [dealSourceFilter, setDealSourceFilter] = useState<string>('all');
  const [clientsView, setClientsView] = useState<'list' | 'kanban'>('list');
  const [draggingClientId, setDraggingClientId] = useState<number | null>(null);
  const [kanbanDropStage, setKanbanDropStage] = useState<DealStage | null>(null);
  const [movingDealClientId, setMovingDealClientId] = useState<number | null>(null);
  const [lossDialogOpen, setLossDialogOpen] = useState(false);
  const [pendingLostClientId, setPendingLostClientId] = useState<number | null>(null);
  const [pendingLostFromStage, setPendingLostFromStage] = useState<DealStage | null>(null);
  const [lossReasonCode, setLossReasonCode] = useState<string>('none');
  const [lossReasonText, setLossReasonText] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
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
        crmTagsApi.list(),
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

  const dealSourceOptions = useMemo(() => {
    const values = new Set<string>();
    clients.forEach((client) => values.add(normalizeDealSource(client)));
    return [...values].sort((a, b) => a.localeCompare(b));
  }, [clients]);

  const dealFilteredClients = useMemo(() => {
    const search = dealNameFilter.trim().toLowerCase();
    return clients.filter((client) => {
      if (search && !(client.name ?? '').toLowerCase().includes(search)) return false;
      if (dealSourceFilter !== 'all' && normalizeDealSource(client) !== dealSourceFilter) return false;
      return true;
    });
  }, [clients, dealNameFilter, dealSourceFilter]);

  const kanbanColumns = useMemo(() => {
    const columns = DEAL_STAGE_ORDER.reduce<Record<DealStage, MapClient[]>>((acc, stage) => {
      acc[stage] = [];
      return acc;
    }, {} as Record<DealStage, MapClient[]>);
    dealFilteredClients.forEach((client) => {
      columns[normalizeDealStage(client)].push(client);
    });
    DEAL_STAGE_ORDER.forEach((stage) => {
      columns[stage].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    });
    return columns;
  }, [dealFilteredClients]);

  const dealReportBySource = useMemo(() => {
    type Row = {
      key: string;
      label: string;
      total: number;
      paid: number;
      lost: number;
      stages: Record<DealStage, number>;
      lossReasons: Record<string, number>;
    };
    const map = new Map<string, Row>();
    for (const client of dealFilteredClients) {
      const key = normalizeDealSource(client);
      const stage = normalizeDealStage(client);
      const row = map.get(key) ?? {
        key,
        label: key,
        total: 0,
        paid: 0,
        lost: 0,
        stages: DEAL_STAGE_ORDER.reduce((acc, item) => ({ ...acc, [item]: 0 }), {} as Record<DealStage, number>),
        lossReasons: {},
      };
      row.total += 1;
      row.stages[stage] += 1;
      if (stage === 'paid') row.paid += 1;
      if (stage === 'lost') {
        row.lost += 1;
        const reasonCode = String(client.deal_loss_reason_code || 'other').trim() || 'other';
        row.lossReasons[reasonCode] = (row.lossReasons[reasonCode] ?? 0) + 1;
      }
      map.set(key, row);
    }
    return [...map.values()]
      .map((row) => {
        const topLoss = Object.entries(row.lossReasons).sort((a, b) => b[1] - a[1])[0];
        const lossReasonsSummary = Object.entries(row.lossReasons)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([code, count]) => `${DEAL_LOSS_REASON_LABELS[code as DealLossReasonCode] ?? code}: ${count}`)
          .join(' · ');
        return {
          ...row,
          paidConversionPct: row.total > 0 ? Math.round((row.paid / row.total) * 100) : 0,
          topLossLabel: topLoss
            ? `${DEAL_LOSS_REASON_LABELS[topLoss[0] as DealLossReasonCode] ?? topLoss[0]} (${topLoss[1]})`
            : '—',
          lossReasonsSummary: lossReasonsSummary || '—',
        };
      })
      .sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
  }, [dealFilteredClients]);

  const dealReportByManager = useMemo(() => {
    type Row = {
      key: string;
      label: string;
      total: number;
      paid: number;
      lost: number;
      stages: Record<DealStage, number>;
      lossReasons: Record<string, number>;
    };
    const map = new Map<string, Row>();
    for (const client of dealFilteredClients) {
      const key = resolveDealManagerLabel(client);
      const stage = normalizeDealStage(client);
      const row = map.get(key) ?? {
        key,
        label: key,
        total: 0,
        paid: 0,
        lost: 0,
        stages: DEAL_STAGE_ORDER.reduce((acc, item) => ({ ...acc, [item]: 0 }), {} as Record<DealStage, number>),
        lossReasons: {},
      };
      row.total += 1;
      row.stages[stage] += 1;
      if (stage === 'paid') row.paid += 1;
      if (stage === 'lost') {
        row.lost += 1;
        const reasonCode = String(client.deal_loss_reason_code || 'other').trim() || 'other';
        row.lossReasons[reasonCode] = (row.lossReasons[reasonCode] ?? 0) + 1;
      }
      map.set(key, row);
    }
    return [...map.values()]
      .map((row) => {
        const topLoss = Object.entries(row.lossReasons).sort((a, b) => b[1] - a[1])[0];
        const lossReasonsSummary = Object.entries(row.lossReasons)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([code, count]) => `${DEAL_LOSS_REASON_LABELS[code as DealLossReasonCode] ?? code}: ${count}`)
          .join(' · ');
        return {
          ...row,
          paidConversionPct: row.total > 0 ? Math.round((row.paid / row.total) * 100) : 0,
          topLossLabel: topLoss
            ? `${DEAL_LOSS_REASON_LABELS[topLoss[0] as DealLossReasonCode] ?? topLoss[0]} (${topLoss[1]})`
            : '—',
          lossReasonsSummary: lossReasonsSummary || '—',
        };
      })
      .sort((a, b) => b.total - a.total || a.label.localeCompare(b.label));
  }, [dealFilteredClients]);

  const resetLossDialog = useCallback(() => {
    setLossDialogOpen(false);
    setPendingLostClientId(null);
    setPendingLostFromStage(null);
    setLossReasonCode('none');
    setLossReasonText('');
  }, []);

  const applyDealMove = useCallback(
    async (
      client: MapClient,
      targetStage: DealStage,
      extra?: Partial<Pick<MapClient, 'deal_loss_reason_code' | 'deal_loss_reason_text'>>
    ) => {
      const sourceStage = normalizeDealStage(client);
      if (sourceStage === targetStage && !extra) return;

      const optimisticPatch: Partial<MapClient> = {
        deal_stage: targetStage,
        deal_loss_reason_code: targetStage === 'lost' ? (extra?.deal_loss_reason_code ?? client.deal_loss_reason_code ?? '') : '',
        deal_loss_reason_text: targetStage === 'lost' ? (extra?.deal_loss_reason_text ?? client.deal_loss_reason_text ?? '') : '',
      };

      let snapshot: MapClient[] | null = null;
      setMovingDealClientId(client.id);
      setClients((prev) => {
        snapshot = prev;
        return prev.map((item) => (item.id === client.id ? normalizeClient({ ...item, ...optimisticPatch }) : item));
      });

      try {
        const updated = await crmContactsApi.update(client.id, {
          deal_stage: targetStage,
          deal_loss_reason_code: (optimisticPatch.deal_loss_reason_code || '') as Contact['deal_loss_reason_code'],
          deal_loss_reason_text: optimisticPatch.deal_loss_reason_text || '',
        });
        setClients((prev) =>
          prev.map((item) => (item.id === client.id ? normalizeClient({ ...item, ...updated }) : item))
        );
      } catch (err) {
        console.error('Failed to move deal stage', err);
        toast.error('Не удалось изменить стадию сделки');
        if (snapshot) {
          setClients(snapshot);
        }
      } finally {
        setMovingDealClientId(null);
      }
    },
    []
  );

  const requestMoveToStage = useCallback(
    async (client: MapClient, targetStage: DealStage) => {
      if (targetStage === 'lost') {
        setPendingLostClientId(client.id);
        setPendingLostFromStage(normalizeDealStage(client));
        setLossReasonCode(client.deal_loss_reason_code ? String(client.deal_loss_reason_code) : 'none');
        setLossReasonText(client.deal_loss_reason_text ?? '');
        setLossDialogOpen(true);
        return;
      }
      await applyDealMove(client, targetStage);
    },
    [applyDealMove]
  );

  const confirmLostMove = useCallback(async () => {
    if (!pendingLostClientId) return;
    const client = clients.find((item) => item.id === pendingLostClientId);
    if (!client) {
      resetLossDialog();
      return;
    }
    const reasonCode = lossReasonCode === 'none' ? '' : lossReasonCode;
    const comment = lossReasonText.trim();
    if (!reasonCode) {
      toast.error('Выберите причину потери');
      return;
    }
    await applyDealMove(client, 'lost', {
      deal_loss_reason_code: reasonCode as Contact['deal_loss_reason_code'],
      deal_loss_reason_text: comment,
    });
    resetLossDialog();
  }, [applyDealMove, clients, lossReasonCode, lossReasonText, pendingLostClientId, resetLossDialog]);

  const lossCommentTemplates = useMemo(() => {
    const code = lossReasonCode === 'none' ? null : (lossReasonCode as DealLossReasonCode);
    const fromReason = code ? LOSS_COMMENT_TEMPLATES[code] ?? [] : [];
    return [...fromReason, ...GENERIC_LOSS_COMMENT_TEMPLATES];
  }, [lossReasonCode]);

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

  const tagLookupById = useMemo(() => {
    return new Map<number, MapTag>(tags.map((tag) => [tag.id, tag]));
  }, [tags]);

  const getClientTagSummary = useCallback((client: MapClient) => {
    return TAG_TYPES.flatMap((type) =>
      (client.tags?.[type] ?? [])
        .map((tagId) => {
          const tag = tagLookupById.get(tagId);
          if (!tag) return null;
          return {
            key: `${type}-${tag.id}`,
            type,
            label: TAG_LABELS[type],
            value: tag.value,
          };
        })
        .filter((item): item is { key: string; type: TagType; label: string; value: string } => Boolean(item))
    );
  }, [tagLookupById]);

  const clientsFiltersContent = (
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
  );

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
              {workspaceMode === 'clients' && (
                <div className="flex items-center justify-between gap-3 rounded-xl border bg-card/70 p-3 shadow-sm md:hidden">
                  <div>
                    <div className="text-sm font-medium text-slate-900">Клиенты</div>
                    <div className="text-xs text-muted-foreground">Найдено: {filteredClients.length}</div>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={() => setFiltersOpen(true)}>
                    Фильтры
                  </Button>
                </div>
              )}

              {workspaceMode === 'clients' && (
                <div className="hidden rounded-xl border bg-card/70 p-4 shadow-sm md:block">
                  {clientsFiltersContent}
                </div>
              )}

              {workspaceMode === 'deals' && (
                <>
                  <div className="rounded-xl border bg-card/70 p-4 shadow-sm">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-muted-foreground">Поиск по клиенту</div>
                        <Input
                          value={dealNameFilter}
                          onChange={(e) => setDealNameFilter(e.target.value)}
                          placeholder="Имя клиента"
                          className="h-8 text-xs"
                        />
                      </div>
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-muted-foreground">Источник</div>
                        <Select value={dealSourceFilter} onValueChange={setDealSourceFilter}>
                          <SelectTrigger className="h-8 text-xs">
                            <SelectValue placeholder="Все источники" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">Все источники</SelectItem>
                            {dealSourceOptions.map((source) => (
                              <SelectItem key={source} value={source}>
                                {source}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="rounded-lg border bg-background p-3">
                        <div className="text-xs text-muted-foreground">Сделок в фильтре</div>
                        <div className="mt-1 text-xl font-semibold">{dealFilteredClients.length}</div>
                      </div>
                      <div className="rounded-lg border bg-background p-3">
                        <div className="text-xs text-muted-foreground">Оплачено</div>
                        <div className="mt-1 text-xl font-semibold">
                          {dealFilteredClients.filter((client) => normalizeDealStage(client) === 'paid').length}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-2">
                    <DealBreakdownCard
                      title="Конверсия и потери по источнику"
                      subtitle="Источник берётся из поля `source` контакта"
                      rows={dealReportBySource}
                    />
                    <DealBreakdownCard
                      title="Конверсия и потери по менеджеру"
                      subtitle="Если поле ответственного не хранится, всё попадает в «Не назначен»"
                      rows={dealReportByManager}
                    />
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card/70 p-3 shadow-sm">
                    <div>
                      <div className="text-sm font-medium">Режим отображения сделок</div>
                      <div className="text-xs text-muted-foreground">
                        `Kanban` использует стадию сделки и позволяет переносить клиентов между этапами воронки
                      </div>
                    </div>
                    <div className="inline-flex rounded-lg border bg-background p-1">
                      <Button
                        type="button"
                        variant={clientsView === 'list' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setClientsView('list')}
                      >
                        Список
                      </Button>
                      <Button
                        type="button"
                        variant={clientsView === 'kanban' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setClientsView('kanban')}
                      >
                        Kanban
                      </Button>
                    </div>
                  </div>
                </>
              )}

              {(workspaceMode === 'clients' ? filteredClients.length === 0 : dealFilteredClients.length === 0) ? (
                <p className="text-sm text-muted-foreground">
                  {workspaceMode === 'clients'
                    ? 'Клиенты по выбранным тегам не найдены.'
                    : 'Сделки по выбранным фильтрам не найдены.'}
                </p>
              ) : workspaceMode === 'clients' ? (
                <>
                  <div className="space-y-3 md:hidden" data-testid="clients-mobile-list">
                    {filteredClients.map((client) => {
                      const tagSummary = getClientTagSummary(client);
                      return (
                        <Card key={client.id}>
                          <CardContent className="space-y-4 p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-base font-semibold text-slate-900">{client.name}</div>
                                <div className="mt-1 text-xs text-slate-500">ID клиента: {client.id}</div>
                              </div>
                              <Button type="button" variant="outline" size="sm" onClick={() => openClientWindow(client.id)}>
                                Открыть
                              </Button>
                            </div>

                            <div className="grid grid-cols-3 gap-2 text-center">
                              {TAG_TYPES.map((type) => (
                                <div key={`${client.id}-${type}`} className="rounded-xl border bg-slate-50 px-3 py-2">
                                  <div className="text-[11px] uppercase tracking-wide text-slate-500">{TAG_LABELS[type]}</div>
                                  <div className="mt-1 text-lg font-semibold text-slate-900">
                                    {client.tags?.[type]?.length ?? 0}
                                  </div>
                                </div>
                              ))}
                            </div>

                            <div className="space-y-2">
                              <div className="text-xs font-semibold text-slate-500">Теги</div>
                              {tagSummary.length === 0 ? (
                                <div className="text-sm text-slate-500">Теги пока не назначены.</div>
                              ) : (
                                <div className="flex flex-wrap gap-2">
                                  {tagSummary.slice(0, 8).map((tag) => (
                                    <Badge key={tag.key} variant="outline" className="max-w-full">
                                      <span className="truncate">{tag.value}</span>
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="flex items-center justify-between gap-3">
                              <Button type="button" variant="ghost" className="px-0 text-red-600 hover:text-red-700" onClick={() => void handleDeleteClient(client)}>
                                Удалить
                              </Button>
                              <Button type="button" variant="outline" onClick={() => openClientWindow(client.id)}>
                                В карточку клиента
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>

                  <div className="hidden space-y-4 md:block">
                    {filteredClients.map((client) => {
                      const row = clientRows.find((item) => item.client.id === client.id);
                      const dealStage = normalizeDealStage(client);
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
                            {workspaceMode === 'clients' ? (
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
                          ) : (
                            <div className="grid gap-3 md:grid-cols-[minmax(220px,1.5fr)_repeat(3,minmax(0,1fr))]">
                              <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                  <div className="font-medium">{client.name}</div>
                                  <Badge variant={DEAL_STAGE_BADGE_VARIANTS[dealStage]}>
                                    {DEAL_STAGE_LABELS[dealStage]}
                                  </Badge>
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  #{client.id} · {normalizeDealSource(client)}
                                </div>
                                {client.deal_loss_reason_code && dealStage === 'lost' && (
                                  <div className="text-xs text-amber-700">
                                    {DEAL_LOSS_REASON_LABELS[client.deal_loss_reason_code as DealLossReasonCode] ?? client.deal_loss_reason_code}
                                    {client.deal_loss_reason_text ? ` · ${client.deal_loss_reason_text}` : ''}
                                  </div>
                                )}
                              </div>
                              <div className="rounded-md border px-3 py-2">
                                <div className="text-xs text-muted-foreground">Сумма сделки</div>
                                <div className="mt-1 font-semibold">
                                  {(client.deal_amount ?? '') !== '' && client.deal_amount !== null ? `${client.deal_amount} ₽` : '—'}
                                </div>
                              </div>
                              <div className="rounded-md border px-3 py-2">
                                <div className="text-xs text-muted-foreground">Быстрый переход</div>
                                <div className="mt-1 text-sm">Откройте карточку контакта для суммы/причины/деталей</div>
                              </div>
                              <div className="flex items-center justify-end">
                                <Button type="button" variant="outline" onClick={() => openClientWindow(client.id)}>
                                  Открыть сделку
                                </Button>
                              </div>
                            </div>
                            )}
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </>
              ) : workspaceMode === 'deals' && clientsView === 'kanban' ? (
                <div className="grid gap-4 xl:grid-cols-6">
                  {DEAL_STAGE_ORDER.map((stage) => (
                    <div
                      key={stage}
                      className={cn(
                        'rounded-xl border bg-card/70 p-3 shadow-sm transition-colors',
                        kanbanDropStage === stage && draggingClientId !== null && 'border-primary bg-primary/5'
                      )}
                      onDragOver={(event) => {
                        event.preventDefault();
                        setKanbanDropStage(stage);
                      }}
                      onDragLeave={(event) => {
                        const related = event.relatedTarget as Node | null;
                        if (related && event.currentTarget.contains(related)) return;
                        setKanbanDropStage((prev) => (prev === stage ? null : prev));
                      }}
                      onDrop={(event) => {
                        event.preventDefault();
                        const raw = event.dataTransfer.getData('text/plain');
                        const parsed = Number(raw);
                        const clientId = Number.isFinite(parsed) && parsed > 0 ? parsed : draggingClientId;
                        const client = clientId ? clients.find((item) => item.id === clientId) : null;
                        setKanbanDropStage(null);
                        setDraggingClientId(null);
                        if (!client) return;
                        void requestMoveToStage(client, stage);
                      }}
                    >
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold">{DEAL_STAGE_LABELS[stage]}</div>
                        <Badge variant={DEAL_STAGE_BADGE_VARIANTS[stage]}>{kanbanColumns[stage].length}</Badge>
                      </div>
                      <div className="space-y-2 min-h-[120px]">
                        {kanbanColumns[stage].length === 0 ? (
                          <div className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
                            Перетащите сюда клиента
                          </div>
                        ) : (
                          kanbanColumns[stage].map((client) => {
                            const isDragging = draggingClientId === client.id;
                            const isSaving = movingDealClientId === client.id;
                            const currentStage = normalizeDealStage(client);
                            return (
                              <button
                                key={client.id}
                                type="button"
                                draggable={!isSaving}
                                onDragStart={(event) => {
                                  setDraggingClientId(client.id);
                                  event.dataTransfer.effectAllowed = 'move';
                                  event.dataTransfer.setData('text/plain', String(client.id));
                                }}
                                onDragEnd={() => {
                                  setDraggingClientId(null);
                                  setKanbanDropStage(null);
                                }}
                                onClick={() => openClientWindow(client.id)}
                                className={cn(
                                  'w-full rounded-lg border bg-background p-3 text-left shadow-sm transition hover:border-primary',
                                  isDragging && 'opacity-50',
                                  isSaving && 'opacity-70 cursor-wait'
                                )}
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div className="min-w-0">
                                    <div className="truncate text-sm font-medium">{client.name}</div>
                                    <div className="mt-1 text-xs text-muted-foreground">
                                      #{client.id}
                                      {client.source ? ` · ${client.source}` : ''}
                                    </div>
                                  </div>
                                  <Badge variant={DEAL_STAGE_BADGE_VARIANTS[currentStage]} className="shrink-0">
                                    {DEAL_STAGE_LABELS[currentStage]}
                                  </Badge>
                                </div>
                                {(client.deal_amount ?? '') !== '' && client.deal_amount !== null && (
                                  <div className="mt-2 text-xs text-muted-foreground">
                                    План сделки: <span className="font-medium text-foreground">{client.deal_amount} ₽</span>
                                  </div>
                                )}
                                {currentStage === 'lost' && (client.deal_loss_reason_code || client.deal_loss_reason_text) && (
                                  <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-900">
                                    {client.deal_loss_reason_code
                                      ? DEAL_LOSS_REASON_LABELS[
                                          client.deal_loss_reason_code as DealLossReasonCode
                                        ] ?? client.deal_loss_reason_code
                                      : 'Причина не выбрана'}
                                    {client.deal_loss_reason_text ? ` · ${client.deal_loss_reason_text}` : ''}
                                  </div>
                                )}
                                {isSaving && (
                                  <div className="mt-2 text-xs text-muted-foreground">Сохраняем стадию…</div>
                                )}
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                (dealFilteredClients).map((client) => {
                  const row = clientRows.find((item) => item.client.id === client.id);
                  const dealStage = normalizeDealStage(client);
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
                        <div className="grid gap-3 md:grid-cols-[minmax(220px,1.5fr)_repeat(3,minmax(0,1fr))]">
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <div className="font-medium">{client.name}</div>
                              <Badge variant={DEAL_STAGE_BADGE_VARIANTS[dealStage]}>
                                {DEAL_STAGE_LABELS[dealStage]}
                              </Badge>
                            </div>
                            <div className="text-xs text-muted-foreground">
                              #{client.id} · {normalizeDealSource(client)}
                            </div>
                            {client.deal_loss_reason_code && dealStage === 'lost' && (
                              <div className="text-xs text-amber-700">
                                {DEAL_LOSS_REASON_LABELS[client.deal_loss_reason_code as DealLossReasonCode] ?? client.deal_loss_reason_code}
                                {client.deal_loss_reason_text ? ` · ${client.deal_loss_reason_text}` : ''}
                              </div>
                            )}
                          </div>
                          <div className="rounded-md border px-3 py-2">
                            <div className="text-xs text-muted-foreground">Сумма сделки</div>
                            <div className="mt-1 font-semibold">
                              {(client.deal_amount ?? '') !== '' && client.deal_amount !== null ? `${client.deal_amount} ₽` : '—'}
                            </div>
                          </div>
                          <div className="rounded-md border px-3 py-2">
                            <div className="text-xs text-muted-foreground">Быстрый переход</div>
                            <div className="mt-1 text-sm">Откройте карточку контакта для суммы/причины/деталей</div>
                          </div>
                          <div className="flex items-center justify-end">
                            <Button type="button" variant="outline" onClick={() => openClientWindow(client.id)}>
                              Открыть сделку
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          )}

          {workspaceMode === 'clients' && (
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
          )}
        </div>
      </div>

      <Dialog
        open={lossDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            resetLossDialog();
          } else {
            setLossDialogOpen(true);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Причина потери сделки</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Клиент будет перемещён в этап <span className="font-medium text-foreground">Потеряно</span>
              {pendingLostFromStage ? ` из этапа «${DEAL_STAGE_LABELS[pendingLostFromStage]}»` : ''}.
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Причина (обязательно)</label>
              <Select value={lossReasonCode} onValueChange={setLossReasonCode}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите причину" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Не выбрано</SelectItem>
                  {DEAL_LOSS_REASON_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Комментарий (необязательно)</label>
              <Textarea
                value={lossReasonText}
                onChange={(event) => setLossReasonText(event.target.value)}
                rows={3}
                placeholder="Например: отложили покупку до следующего месяца"
              />
              <div className="flex flex-wrap gap-2">
                {lossCommentTemplates.map((template) => (
                  <button
                    key={template}
                    type="button"
                    className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
                    onClick={() => setLossReasonText(template)}
                  >
                    {template}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={resetLossDialog}>
              Отмена
            </Button>
            <Button type="button" onClick={() => void confirmLostMove()} disabled={movingDealClientId !== null}>
              {movingDealClientId !== null ? 'Сохраняем…' : 'Переместить в Потеряно'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-3xl border-t bg-white px-4 py-6">
          <div className="mb-4 text-base font-semibold text-slate-900">Фильтры клиентов</div>
          {clientsFiltersContent}
        </SheetContent>
      </Sheet>
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

function DealBreakdownCard({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: Array<{
    key: string;
    label: string;
    total: number;
    paid: number;
    lost: number;
    stages: Record<DealStage, number>;
    paidConversionPct: number;
    topLossLabel: string;
    lossReasonsSummary: string;
  }>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <div className="text-sm text-muted-foreground">Нет данных по текущему фильтру.</div>
        ) : (
          <div className="space-y-2">
            {rows.slice(0, 8).map((row) => (
              <div key={row.key} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium">{row.label}</div>
                  <div className="text-xs text-muted-foreground">
                    Лидов: <span className="font-medium text-foreground">{row.total}</span>
                  </div>
                </div>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  <div className="rounded-md bg-muted/40 px-2 py-1.5 text-xs">
                    Оплачено: <span className="font-medium text-foreground">{row.paid}</span>
                  </div>
                  <div className="rounded-md bg-muted/40 px-2 py-1.5 text-xs">
                    Потеряно: <span className="font-medium text-foreground">{row.lost}</span>
                  </div>
                  <div className="rounded-md bg-muted/40 px-2 py-1.5 text-xs">
                    Конверсия в оплату: <span className="font-medium text-foreground">{row.paidConversionPct}%</span>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {DEAL_STAGE_ORDER.map((stage) => (
                    <span key={`${row.key}-${stage}`} className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
                      {DEAL_STAGE_LABELS[stage]}: <span className="font-medium text-foreground">{row.stages[stage] ?? 0}</span>
                    </span>
                  ))}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  Топ причина потери: <span className="font-medium text-foreground">{row.topLossLabel}</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  Причины потерь: <span className="font-medium text-foreground">{row.lossReasonsSummary}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
