'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, CheckCircle2, Hammer, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api';
import { semanticGroupsApi } from '@/lib/api/semantic-groups';
import { semanticClustersApi } from '@/lib/api/semantic-clusters';
import type { SemanticCluster, SemanticGroup } from '@/lib/types';
import { useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const INTENT_LABELS: Record<string, string> = {
  info: 'Инфо',
  commercial: 'Коммерческий',
  navigational: 'Навигационный',
  brand: 'Бренд',
};

const PRIORITY_LABELS: Record<number, string> = {
  3: 'Высокий',
  2: 'Средний',
  1: 'Низкий',
};

const GROUP_SCOPE_OPTIONS = [
  { value: 'narrow', label: 'Узкая' },
  { value: 'normal', label: 'Средняя' },
  { value: 'wide', label: 'Широкая' },
];

const GROUP_STATUS_OPTIONS = [
  { value: 'draft', label: 'Черновик' },
  { value: 'approved', label: 'Одобрено' },
  { value: 'archived', label: 'Архив' },
];

const GROUP_SOURCE_OPTIONS = [
  { value: 'ai', label: 'AI' },
  { value: 'manual', label: 'Ручной' },
];

export default function SemanticGroupDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { canEdit } = useRole();
  const [group, setGroup] = useState<SemanticGroup | null>(null);
  const [clusters, setClusters] = useState<SemanticCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [clustering, setClustering] = useState(false);
  const [phrasesGenerating, setPhrasesGenerating] = useState<Record<number, boolean>>({});
  const [projectDataDialogOpen, setProjectDataDialogOpen] = useState(false);

  const [nameDraft, setNameDraft] = useState('');
  const [descriptionDraft, setDescriptionDraft] = useState('');
  const [scopeDraft, setScopeDraft] = useState('normal');
  const [statusDraft, setStatusDraft] = useState('draft');
  const [expectedClustersDraft, setExpectedClustersDraft] = useState('');
  const [sourceDraft, setSourceDraft] = useState('manual');
  const [parentDraft, setParentDraft] = useState('');
  const [sourceBooksDraft, setSourceBooksDraft] = useState('');

  const groupId = useMemo(() => {
    const raw = params?.id;
    if (!raw) return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }, [params?.id]);

  const hydrateDrafts = (data: SemanticGroup) => {
    setNameDraft(data.name || '');
    setDescriptionDraft(data.description || '');
    setScopeDraft(data.scope || 'normal');
    setStatusDraft(data.status || 'draft');
    setExpectedClustersDraft(
      data.expected_clusters != null ? String(data.expected_clusters) : ''
    );
    setSourceDraft(data.source || 'manual');
    setParentDraft(data.parent != null ? String(data.parent) : '');
    const books = Array.isArray(data.source_books) ? data.source_books : [];
    setSourceBooksDraft(books.filter((item) => item && String(item).trim()).join('\n'));
  };

  const loadGroup = async () => {
    if (!groupId) return;
    setLoading(true);
    try {
      const [groupData, clusterData] = await Promise.all([
        semanticGroupsApi.get(groupId),
        semanticClustersApi.list(groupId),
      ]);
      setGroup(groupData);
      setClusters(clusterData);
      hydrateDrafts(groupData);
    } catch (error) {
      console.error('Failed to load semantic group', error);
      toast.error('Не удалось загрузить смысловую группу');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroup();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupId]);

  const hasClusters = clusters.length > 0;

  const handleSave = async () => {
    if (!canEdit || !group) return;
    const trimmedName = nameDraft.trim();
    if (!trimmedName) {
      toast.error('Введите название смысловой группы');
      return;
    }

    const parsedExpected =
      expectedClustersDraft.trim() === ''
        ? null
        : Number.parseInt(expectedClustersDraft.trim(), 10);
    const expectedValue = Number.isNaN(parsedExpected as number) ? null : parsedExpected;

    const parentValue =
      parentDraft.trim() === '' ? null : Number.parseInt(parentDraft.trim(), 10);
    const safeParent = Number.isNaN(parentValue as number) ? null : parentValue;

    const books = sourceBooksDraft
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);

    const payload: Partial<SemanticGroup> = {
      name: trimmedName,
      description: descriptionDraft.trim(),
      scope: scopeDraft,
      status: statusDraft,
      expected_clusters: expectedValue as number | null,
      source: sourceDraft,
      parent: safeParent as number | null,
      source_books: books,
    };

    setSaving(true);
    try {
      const updated = await semanticGroupsApi.update(group.id, payload);
      setGroup(updated);
      hydrateDrafts(updated);
      toast.success('Смысловая группа сохранена');
    } catch (error) {
      console.error('Failed to save semantic group', error);
      toast.error('Не удалось сохранить смысловую группу');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!canEdit || !group) return;
    if (!window.confirm('Удалить смысловую группу? Это действие нельзя отменить.')) return;
    setDeleting(true);
    try {
      await semanticGroupsApi.remove(group.id);
      toast.success('Смысловая группа удалена');
      router.push('/seo?tab=groups');
    } catch (error) {
      console.error('Failed to delete semantic group', error);
      toast.error('Не удалось удалить смысловую группу');
    } finally {
      setDeleting(false);
    }
  };

  const handleGenerateClusters = async () => {
    if (!canEdit || !group) return;
    if (clustering) return;
    setClustering(true);
    try {
      const response = await semanticGroupsApi.generateClusters(group.id);
      toast.success(response.message || 'Кластеры созданы');
      await loadGroup();
    } catch (error) {
      console.error('Failed to generate semantic clusters', error);
      if (error instanceof ApiError) {
        try {
          const payload = error.body ? JSON.parse(error.body) : null;
          if (payload?.missing_fields) {
            setProjectDataDialogOpen(true);
            return;
          }
          if (payload?.error) {
            toast.error(String(payload.error));
            return;
          }
        } catch {}
      }
      const message = error instanceof Error ? error.message : 'Не удалось создать кластеры';
      toast.error(message);
    } finally {
      setClustering(false);
    }
  };

  const handleGeneratePhrases = async (clusterId: number) => {
    if (!canEdit) return;
    if (phrasesGenerating[clusterId]) return;
    setPhrasesGenerating((prev) => ({ ...prev, [clusterId]: true }));
    try {
      const response = await semanticClustersApi.generatePhrases(clusterId);
      toast.success(response.message || 'Фразы созданы');
      await loadGroup();
    } catch (error) {
      console.error('Failed to generate semantic phrases', error);
      if (error instanceof ApiError) {
        try {
          const payload = error.body ? JSON.parse(error.body) : null;
          if (payload?.error) {
            toast.error(String(payload.error));
            return;
          }
        } catch {}
      }
      const message = error instanceof Error ? error.message : 'Не удалось создать фразы';
      toast.error(message);
    } finally {
      setPhrasesGenerating((prev) => ({ ...prev, [clusterId]: false }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Загружаем смысловую группу...
      </div>
    );
  }

  if (!group) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Группа не найдена</CardTitle>
          <CardDescription>Проверьте ссылку или вернитесь к списку смыслов.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => router.push('/seo?tab=groups')}>
            Вернуться к смыслам
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <button
          type="button"
          onClick={() => router.push('/seo?tab=groups')}
          className="transition hover:text-slate-900"
        >
          SEO
        </button>
        <span>/</span>
        <span className="text-slate-900">{group?.name || 'Смысловая группа'}</span>
      </div>

      <Dialog open={projectDataDialogOpen} onOpenChange={setProjectDataDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Введите данные проекта</DialogTitle>
            <DialogDescription>
              Для генерации кластеров заполните нишу, продукт и ЦА в настройках.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              onClick={() => {
                setProjectDataDialogOpen(false);
                router.push('/settings?tab=client');
              }}
            >
              Перейти к вводу
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="flex items-center gap-3">
        <Button variant="outline" size="icon" onClick={() => router.push('/seo?tab=groups')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-slate-900">Смысловая группа</h1>
          <p className="text-sm text-muted-foreground">Редактирование группы и управление кластерами.</p>
        </div>
        {hasClusters && (
          <div className="flex items-center gap-2 text-xs text-emerald-600">
            <CheckCircle2 className="h-4 w-4" />
            Кластеры созданы
          </div>
        )}
      </div>

      <Card>
        <CardHeader className="space-y-2">
          <CardTitle>Параметры группы</CardTitle>
          <CardDescription>Измените данные группы и сохраните.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleSave} disabled={!canEdit || saving || deleting}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Сохранение...
                </>
              ) : (
                'Сохранить'
              )}
            </Button>
            <Button variant="outline" onClick={handleDelete} disabled={!canEdit || saving || deleting}>
              <Trash2 className="mr-2 h-4 w-4" />
              Удалить
            </Button>
            <Button
              variant="outline"
              onClick={handleGenerateClusters}
              disabled={!canEdit || clustering || hasClusters}
            >
              {clustering ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Генерация...
                </>
              ) : hasClusters ? (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4 text-emerald-600" />
                  Кластеры созданы
                </>
              ) : (
                <>
                  <Hammer className="mr-2 h-4 w-4" />
                  Создать кластеры
                </>
              )}
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Input
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              placeholder="Название группы"
              disabled={!canEdit || saving || deleting}
            />
            <Input
              value={expectedClustersDraft}
              onChange={(event) => setExpectedClustersDraft(event.target.value)}
              placeholder="Ожидаемые кластеры"
              type="number"
              disabled={!canEdit || saving || deleting}
            />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Select
              value={scopeDraft || 'normal'}
              onValueChange={(value) => setScopeDraft(value)}
              disabled={!canEdit || saving || deleting}
            >
              <SelectTrigger>
                <SelectValue placeholder="Ширина" />
              </SelectTrigger>
              <SelectContent>
                {GROUP_SCOPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusDraft || 'draft'}
              onValueChange={(value) => setStatusDraft(value)}
              disabled={!canEdit || saving || deleting}
            >
              <SelectTrigger>
                <SelectValue placeholder="Статус" />
              </SelectTrigger>
              <SelectContent>
                {GROUP_STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={sourceDraft || 'manual'}
              onValueChange={(value) => setSourceDraft(value)}
              disabled={!canEdit || saving || deleting}
            >
              <SelectTrigger>
                <SelectValue placeholder="Источник" />
              </SelectTrigger>
              <SelectContent>
                {GROUP_SOURCE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <Input
              value={parentDraft}
              onChange={(event) => setParentDraft(event.target.value)}
              placeholder="Parent ID (если есть)"
              type="number"
              disabled={!canEdit || saving || deleting}
            />
            <Textarea
              value={sourceBooksDraft}
              onChange={(event) => setSourceBooksDraft(event.target.value)}
              placeholder="Книги-источники (каждая с новой строки)"
              className="min-h-[90px]"
              disabled={!canEdit || saving || deleting}
            />
          </div>

          <Textarea
            value={descriptionDraft}
            onChange={(event) => setDescriptionDraft(event.target.value)}
            placeholder="Описание: что входит и что не входит"
            className="min-h-[140px]"
            disabled={!canEdit || saving || deleting}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Кластеры</CardTitle>
          <CardDescription>Список кластеров для этой смысловой группы.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!clusters.length ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Кластеры не созданы.</p>
              <Button onClick={handleGenerateClusters} disabled={!canEdit || clustering}>
                {clustering ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Генерация...
                  </>
                ) : (
                  'Создать'
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {clusters.map((cluster) => {
                const hasPhrases = (cluster.phrases_count ?? 0) > 0;
                const generating = Boolean(phrasesGenerating[cluster.id]);
                return (
                <div
                  key={cluster.id}
                  className="cursor-pointer rounded-md border p-3 transition hover:border-slate-300"
                  role="button"
                  tabIndex={0}
                  onClick={() => router.push(`/seo/cluster/${cluster.id}`)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      router.push(`/seo/cluster/${cluster.id}`);
                    }
                  }}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{cluster.name}</p>
                    {cluster.intent && (
                      <Badge variant="outline" className="text-xs">
                        {INTENT_LABELS[cluster.intent] ?? cluster.intent}
                      </Badge>
                    )}
                    {cluster.priority != null && (
                      <Badge variant="outline" className="text-xs">
                        {PRIORITY_LABELS[cluster.priority] ?? `P${cluster.priority}`}
                      </Badge>
                    )}
                    {cluster.phrases_count != null && (
                      <Badge variant="outline" className="text-xs">
                        Фраз: {cluster.phrases_count}
                      </Badge>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="ml-auto"
                      disabled={!canEdit || generating || hasPhrases}
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleGeneratePhrases(cluster.id);
                      }}
                      onPointerDown={(event) => event.stopPropagation()}
                      aria-label="Создать фразы"
                    >
                      {generating ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : hasPhrases ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      ) : (
                        <Hammer className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  {(cluster.description || cluster.user_goal) && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {(cluster.description || '').trim() || cluster.user_goal}
                    </p>
                  )}
                  {cluster.main_keyword && (
                    <p className="mt-2 text-xs text-slate-600">
                      Основной ключ: <span className="font-medium text-slate-700">{cluster.main_keyword}</span>
                    </p>
                  )}
                </div>
              )})}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
