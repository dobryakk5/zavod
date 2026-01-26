'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Hammer, Loader2, Save, Sparkles, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { semanticClustersApi } from '@/lib/api/semantic-clusters';
import { semanticGroupsApi } from '@/lib/api/semantic-groups';
import type { SemanticCluster, SemanticGroup, SemanticPhrase } from '@/lib/types';
import { useRole } from '@/lib/hooks';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const INTENT_OPTIONS = [
  { value: 'none', label: '—' },
  { value: 'info', label: 'Инфо' },
  { value: 'commercial', label: 'Коммерческий' },
  { value: 'navigational', label: 'Навигационный' },
  { value: 'brand', label: 'Бренд' },
];

const STATUS_OPTIONS = [
  { value: 'planned', label: 'Запланировано' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'published', label: 'Опубликовано' },
];

export default function SemanticClusterDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { canEdit } = useRole();
  const [cluster, setCluster] = useState<SemanticCluster | null>(null);
  const [group, setGroup] = useState<SemanticGroup | null>(null);
  const [phrases, setPhrases] = useState<SemanticPhrase[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [phrasesLoading, setPhrasesLoading] = useState(false);
  const [phrasesGenerating, setPhrasesGenerating] = useState(false);
  const [phrasesDeleting, setPhrasesDeleting] = useState(false);
  const [phrasesAdding, setPhrasesAdding] = useState(false);
  const [phraseRemoving, setPhraseRemoving] = useState<Record<number, boolean>>({});
  const [contextGenerating, setContextGenerating] = useState(false);
  const [phraseFilter, setPhraseFilter] = useState<'all' | 'key' | 'lsi' | 'wordstat' | 'association'>('all');
  const [phraseDraft, setPhraseDraft] = useState('');

  const resolvePhraseType = (phrase: SemanticPhrase) => {
    if (phrase.type === 'lsi') return 'lsi';
    if (phrase.type === 'wordstat') return 'wordstat';
    if (phrase.type === 'association') return 'association';
    return 'key';
  };

  const [nameDraft, setNameDraft] = useState('');
  const [descriptionDraft, setDescriptionDraft] = useState('');
  const [mainKeywordDraft, setMainKeywordDraft] = useState('');
  const [intentDraft, setIntentDraft] = useState('');
  const [userGoalDraft, setUserGoalDraft] = useState('');
  const [ctaDraft, setCtaDraft] = useState('');
  const [priorityDraft, setPriorityDraft] = useState('');
  const [pageTypeDraft, setPageTypeDraft] = useState('');
  const [urlDraft, setUrlDraft] = useState('');
  const [statusDraft, setStatusDraft] = useState('planned');

  const phraseCounts = useMemo(() => {
    const counts = { total: 0, key: 0, lsi: 0, wordstat: 0, association: 0 };
    for (const phrase of phrases) {
      counts.total += 1;
      const type = resolvePhraseType(phrase);
      if (type !== 'wordstat') {
        counts[type] += 1;
      }
    }
    counts.wordstat = phrases.filter(
      (phrase) => phrase.wordstat_id != null && resolvePhraseType(phrase) !== 'association'
    ).length;
    return counts;
  }, [phrases]);

  const normalizePhrase = (value: string) => (value || '').trim().replace(/\s+/g, ' ').toLowerCase();

  const extractPhrases = (value: string) => {
    const seen = new Set<string>();
    return value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter((item) => {
        if (!item) return false;
        const normalized = normalizePhrase(item);
        if (!normalized || seen.has(normalized)) return false;
        seen.add(normalized);
        return true;
      });
  };

  const filteredPhrases = useMemo(() => {
    if (phraseFilter === 'all') return phrases;
    if (phraseFilter === 'wordstat') {
      return phrases.filter(
        (phrase) => phrase.wordstat_id != null && resolvePhraseType(phrase) !== 'association'
      );
    }
    return phrases.filter((phrase) => resolvePhraseType(phrase) === phraseFilter);
  }, [phraseFilter, phrases]);

  const clusterId = useMemo(() => {
    const raw = params?.id;
    if (!raw) return null;
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }, [params?.id]);

  const hydrateDrafts = (data: SemanticCluster) => {
    setNameDraft(data.name || '');
    setDescriptionDraft(data.description || '');
    setMainKeywordDraft(data.main_keyword || '');
    setIntentDraft(data.intent || '');
    setUserGoalDraft(data.user_goal || '');
    setCtaDraft(data.cta || '');
    setPriorityDraft(data.priority != null ? String(data.priority) : '');
    setPageTypeDraft(data.page_type || '');
    setUrlDraft(data.url || '');
    setStatusDraft(data.status || 'planned');
  };

  const loadCluster = async () => {
    if (!clusterId) return;
    setLoading(true);
    try {
      const data = await semanticClustersApi.get(clusterId);
      setCluster(data);
      hydrateDrafts(data);
      if (data.semantic_group) {
        const groupData = await semanticGroupsApi.get(data.semantic_group);
        setGroup(groupData);
      } else {
        setGroup(null);
      }
      await loadPhrases(data.id);
    } catch (error) {
      console.error('Failed to load semantic cluster', error);
      toast.error('Не удалось загрузить кластер');
    } finally {
      setLoading(false);
    }
  };

  const loadPhrases = async (id: number) => {
    setPhrasesLoading(true);
    try {
      const data = await semanticClustersApi.listPhrases(id);
      setPhrases(data);
    } catch (error) {
      console.error('Failed to load semantic phrases', error);
      toast.error('Не удалось загрузить фразы кластера');
      setPhrases([]);
    } finally {
      setPhrasesLoading(false);
    }
  };

  useEffect(() => {
    loadCluster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusterId]);

  const handleSave = async () => {
    if (!canEdit || !cluster) return;
    const trimmedName = nameDraft.trim();
    if (!trimmedName) {
      toast.error('Введите название кластера');
      return;
    }
    const parsedPriority =
      priorityDraft.trim() === '' ? null : Number.parseInt(priorityDraft.trim(), 10);
    const priorityValue = Number.isNaN(parsedPriority as number) ? null : parsedPriority;

    const payload: Partial<SemanticCluster> = {
      name: trimmedName,
      description: descriptionDraft.trim(),
      main_keyword: mainKeywordDraft.trim(),
      intent: intentDraft || '',
      user_goal: userGoalDraft.trim(),
      cta: ctaDraft.trim(),
      priority: priorityValue as number | null,
      page_type: pageTypeDraft.trim(),
      url: urlDraft.trim(),
      status: statusDraft,
    };

    setSaving(true);
    try {
      const updated = await semanticClustersApi.update(cluster.id, payload);
      setCluster(updated);
      hydrateDrafts(updated);
      toast.success('Кластер сохранен');
    } catch (error) {
      console.error('Failed to save semantic cluster', error);
      toast.error('Не удалось сохранить кластер');
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePhrases = async () => {
    if (!canEdit || !cluster) return;
    if (phrasesGenerating) return;
    setPhrasesGenerating(true);
    try {
      const response = await semanticClustersApi.generatePhrases(cluster.id);
      if (response.phrases) {
        setPhrases(response.phrases);
      } else {
        await loadPhrases(cluster.id);
      }
      toast.success(response.message || 'Фразы созданы');
    } catch (error) {
      console.error('Failed to generate semantic phrases', error);
      toast.error('Не удалось создать фразы');
    } finally {
      setPhrasesGenerating(false);
    }
  };

  const handleGenerateContext = async () => {
    if (!canEdit || !cluster) return;
    if (contextGenerating) return;
    setContextGenerating(true);
    try {
      const response = await semanticClustersApi.generateContext(cluster.id);
      if (response.phrases) {
        setPhrases(response.phrases);
      } else {
        await loadPhrases(cluster.id);
      }
      toast.success(response.message || 'Контекст создан');
    } catch (error) {
      console.error('Failed to generate semantic context', error);
      toast.error('Не удалось создать контекст');
    } finally {
      setContextGenerating(false);
    }
  };

  const handleDeletePhrases = async () => {
    if (!canEdit || !cluster || phrasesDeleting) return;
    if (!window.confirm('Удалить все фразы кластера? Это действие нельзя отменить.')) {
      return;
    }
    setPhrasesDeleting(true);
    try {
      const response = await semanticClustersApi.deletePhrases(cluster.id);
      setPhrases([]);
      setPhraseFilter('all');
      toast.success(response.message || 'Фразы удалены');
    } catch (error) {
      console.error('Failed to delete semantic phrases', error);
      toast.error('Не удалось удалить фразы');
    } finally {
      setPhrasesDeleting(false);
    }
  };

  const handleAddPhrases = async () => {
    if (!canEdit || !cluster || phrasesAdding) return;
    const incoming = extractPhrases(phraseDraft);
    if (!incoming.length) {
      toast.error('Введите фразы для добавления');
      return;
    }

    const existingSet = new Set(
      phrases
        .map((item) =>
          normalizePhrase(item.normalized_phrase || item.raw_phrase || item.phrase || '')
        )
        .filter(Boolean)
    );
    const toAdd = incoming.filter((phrase) => !existingSet.has(normalizePhrase(phrase)));

    if (!toAdd.length) {
      toast.error('Новых фраз нет — все уже есть в кластере');
      return;
    }

    setPhrasesAdding(true);
    try {
      const response = await semanticClustersApi.addPhrases(cluster.id, { phrases: toAdd });
      if (response.phrases) {
        setPhrases(response.phrases);
      } else {
        await loadPhrases(cluster.id);
      }
      setPhraseDraft('');
      setPhraseFilter('key');
      toast.success(response.message || 'Фразы добавлены');
      if (response.wordstat_error) {
        toast.error(response.wordstat_error);
      }
    } catch (error) {
      console.error('Failed to add cluster phrases', error);
      toast.error('Не удалось добавить фразы');
    } finally {
      setPhrasesAdding(false);
    }
  };

  const handleRemovePhrase = async (phraseId: number) => {
    if (!canEdit || !cluster || phraseRemoving[phraseId]) return;
    if (!window.confirm('Удалить фразу из кластера?')) return;
    setPhraseRemoving((prev) => ({ ...prev, [phraseId]: true }));
    setPhrases((prev) => prev.filter((item) => item.id !== phraseId));
    try {
      await semanticClustersApi.removePhrase(cluster.id, phraseId);
      toast.success('Фраза удалена');
    } catch (error) {
      console.error('Failed to remove cluster phrase', error);
      toast.error('Не удалось удалить фразу');
      await loadPhrases(cluster.id);
    } finally {
      setPhraseRemoving((prev) => {
        const next = { ...prev };
        delete next[phraseId];
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Загружаем кластер...
      </div>
    );
  }

  if (!cluster) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Кластер не найден</CardTitle>
          <CardDescription>Проверьте ссылку или вернитесь назад.</CardDescription>
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
        {cluster.semantic_group ? (
          <button
            type="button"
            onClick={() => router.push(`/seo/group/${cluster.semantic_group}`)}
            className="transition hover:text-slate-900"
          >
            {group?.name || 'Смысловая группа'}
          </button>
        ) : (
          <span className="text-muted-foreground">{group?.name || 'Смысловая группа'}</span>
        )}
        <span>/</span>
        <span className="text-slate-900">{cluster.name || 'Кластер'}</span>
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="icon"
          onClick={() => {
            if (cluster.semantic_group) {
              router.push(`/seo/group/${cluster.semantic_group}`);
            } else {
              router.push('/seo?tab=groups');
            }
          }}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-slate-900">Кластер</h1>
          <p className="text-sm text-muted-foreground">
            {group ? `Группа: ${group.name}` : 'Редактирование кластера'}
          </p>
        </div>
        <Button onClick={handleSave} disabled={!canEdit || saving}>
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Сохранить
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Параметры кластера</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Название:</span>
            <Input
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              placeholder="Название"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Описание:</span>
            <Input
              value={descriptionDraft}
              onChange={(event) => setDescriptionDraft(event.target.value)}
              placeholder="Описание"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Основной ключ:</span>
            <Input
              value={mainKeywordDraft}
              onChange={(event) => setMainKeywordDraft(event.target.value)}
              placeholder="Основной ключ"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Цель пользователя:</span>
            <Input
              value={userGoalDraft}
              onChange={(event) => setUserGoalDraft(event.target.value)}
              placeholder="Цель пользователя"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Интент:</span>
            <Select
              value={intentDraft || 'none'}
              onValueChange={(value) => setIntentDraft(value === 'none' ? '' : value)}
              disabled={!canEdit || saving}
            >
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Интент" />
              </SelectTrigger>
              <SelectContent>
                {INTENT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Статус:</span>
            <Select
              value={statusDraft}
              onValueChange={(value) => setStatusDraft(value)}
              disabled={!canEdit || saving}
            >
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Статус" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">CTA:</span>
            <Input
              value={ctaDraft}
              onChange={(event) => setCtaDraft(event.target.value)}
              placeholder="CTA"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Приоритет:</span>
            <Input
              value={priorityDraft}
              onChange={(event) => setPriorityDraft(event.target.value)}
              placeholder="Приоритет (1-3)"
              type="number"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">Тип страницы:</span>
            <Input
              value={pageTypeDraft}
              onChange={(event) => setPageTypeDraft(event.target.value)}
              placeholder="Тип страницы"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="w-44 text-sm text-muted-foreground">URL:</span>
            <Input
              value={urlDraft}
              onChange={(event) => setUrlDraft(event.target.value)}
              placeholder="URL"
              disabled={!canEdit || saving}
              className="flex-1"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          variant="outline"
          onClick={handleGeneratePhrases}
          disabled={!canEdit || phrasesGenerating || contextGenerating}
        >
          {phrasesGenerating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Генерация...
            </>
          ) : (
            <>
              <Hammer className="mr-2 h-4 w-4" />
              Подобрать фразы
            </>
          )}
        </Button>
        <Button
          variant="outline"
          onClick={handleGenerateContext}
          disabled={!canEdit || contextGenerating || phrasesGenerating}
        >
          {contextGenerating ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Генерация...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              Подобрать контекст
            </>
          )}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Фразы кластера</CardTitle>
              <CardDescription>
                {phrases.length ? `${phrases.length} фраз` : 'Фразы еще не созданы'}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              className="border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
              onClick={handleDeletePhrases}
              disabled={!canEdit || phrasesDeleting || phrases.length === 0}
            >
              {phrasesDeleting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin text-red-600" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4 text-red-600" />
              )}
              Удалить все фразы
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {phrasesLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем фразы...
            </div>
          ) : (
            <div className="space-y-3">
              {canEdit && (
                <div className="space-y-2 rounded-md border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-slate-900">Добавить фразы</p>
                  <Textarea
                    placeholder="Каждая строка — отдельная фраза"
                    value={phraseDraft}
                    onChange={(event) => setPhraseDraft(event.target.value)}
                    className="min-h-[96px]"
                    disabled={phrasesAdding}
                  />
                  <div className="flex justify-end">
                    <Button type="button" onClick={handleAddPhrases} disabled={!canEdit || phrasesAdding}>
                      {phrasesAdding ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Добавляем...
                        </>
                      ) : (
                        'Добавить фразы'
                      )}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Фразы сразу проверяются в Wordstat.
                  </p>
                </div>
              )}
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge
                  variant={phraseFilter === 'all' ? 'secondary' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => setPhraseFilter('all')}
                >
                  Все: {phraseCounts.total}
                </Badge>
                <Badge
                  variant={phraseFilter === 'key' ? 'secondary' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => setPhraseFilter('key')}
                >
                  Ключи: {phraseCounts.key}
                </Badge>
                <Badge
                  variant={phraseFilter === 'lsi' ? 'secondary' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => setPhraseFilter('lsi')}
                >
                  Контекст: {phraseCounts.lsi}
                </Badge>
                <Badge
                  variant={phraseFilter === 'wordstat' ? 'secondary' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => setPhraseFilter('wordstat')}
                >
                  Wordstat: {phraseCounts.wordstat}
                </Badge>
                <Badge
                  variant={phraseFilter === 'association' ? 'secondary' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => setPhraseFilter('association')}
                >
                  Ассоциации: {phraseCounts.association}
                </Badge>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[28%]">Ключ</TableHead>
                    <TableHead className="w-[28%]">Норм фраза (по ключу)</TableHead>
                    <TableHead className="w-[28%]">Комментарий</TableHead>
                    <TableHead className="w-[10%] text-right">Частота</TableHead>
                    {canEdit && <TableHead className="w-[6%] text-right"></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPhrases.map((phrase) => (
                    <TableRow key={phrase.id}>
                      <TableCell className="font-medium text-slate-900">
                        {phrase.raw_phrase && phrase.raw_phrase.trim() ? phrase.raw_phrase.trim() : '—'}
                      </TableCell>
                      <TableCell className="text-slate-700">
                        {phrase.normalized_phrase?.trim() || phrase.phrase || '—'}
                      </TableCell>
                      <TableCell className="text-slate-600">
                        {phrase.comment?.trim() ? phrase.comment.trim() : '—'}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-slate-700">
                        {phrase.frequency != null ? phrase.frequency.toLocaleString('ru-RU') : '—'}
                      </TableCell>
                      {canEdit && (
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleRemovePhrase(phrase.id)}
                            disabled={phraseRemoving[phrase.id]}
                            className="text-red-600 hover:text-red-700"
                          >
                            {phraseRemoving[phrase.id] ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {phrases.length === 0 && !phrasesLoading && (
            <p className="mt-3 text-sm text-muted-foreground">Нет фраз в кластере.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
