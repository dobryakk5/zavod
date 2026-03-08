'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useParams } from 'next/navigation';
import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  type DragEndEvent,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { AlertCircle, ArrowLeft, ChevronDown, FileText, GripVertical, Image as ImageIcon, Plus, Trash2, Video } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EventDescriptionEditor } from '@/components/products/event-description-editor';
import { clientProductsApi } from '@/lib/api/clientProducts';
import {
  buildCourseLessonEmbedUrl,
  createCourseLessonImageBlock,
  createCourseLessonTiptapBlock,
  createCourseLessonVideoBlock,
  createDefaultCourseLessonContent,
  extractPrimaryCourseVideoFields,
  mergeTopLevelVideoFields,
  normalizeCourseLessonContent,
  normalizeTiptapDoc,
  parseCourseVideoUrl,
  updateCourseLessonTiptapBlock,
  type CourseLessonBlock,
  type CourseLessonContent,
} from '@/lib/courseLessonContent';
import type { ProductCourse, ProductCourseLesson, ProductCourseLessonUnlockCondition } from '@/lib/types';

type RouteParams = { id: string; module_id: string };

type LessonDraft = {
  title: string;
  is_preview: boolean;
  content: CourseLessonContent;
};

type AddBlockType = 'video' | 'tiptap' | 'image';
type UnlockCondition = ProductCourseLessonUnlockCondition;

const DEFAULT_UNLOCK_CONDITION: UnlockCondition = 'after_student_complete';

const normalizeUnlockCondition = (value: unknown): UnlockCondition => {
  if (value === 'after_student_complete' || value === 'after_curator_complete' || value === 'after_timer') {
    return value;
  }
  return DEFAULT_UNLOCK_CONDITION;
};

const buildLessonDraft = (lesson: ProductCourseLesson): LessonDraft => {
  const mergedContent = mergeTopLevelVideoFields(
    normalizeCourseLessonContent(lesson.content),
    lesson,
  );

  return {
    title: lesson.title,
    is_preview: Boolean(lesson.is_preview),
    content: mergedContent,
  };
};

function SortableBlockShell({
  id,
  title,
  icon,
  canRemove,
  onRemove,
  children,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  canRemove: boolean;
  onRemove: () => void;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  const style: CSSProperties = {
    transform: isDragging ? undefined : CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.45 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="space-y-2 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="inline-flex items-center gap-2 text-sm font-medium">
          {icon}
          {title}
        </div>

        <div className="inline-flex items-center gap-2">
          <Button type="button" size="icon" variant="outline" className="h-8 w-8" {...attributes} {...listeners}>
            <GripVertical className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="destructive"
            className="h-8 w-8"
            onClick={onRemove}
            disabled={!canRemove}
            title={canRemove ? 'Удалить блок' : 'Нельзя удалить последний блок'}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {children}
    </div>
  );
}

function SortableLessonShell({
  id,
  title,
  actions,
  expanded,
  onExpandedChange,
  children,
}: {
  id: string;
  title: string;
  actions: React.ReactNode;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.85 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="space-y-3 rounded-lg border p-3">
      <div className="flex items-center gap-2">
        <div className="inline-flex min-w-0 items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onExpandedChange(!expanded)}
            aria-label={expanded ? 'Свернуть урок' : 'Развернуть урок'}
            title={expanded ? 'Свернуть' : 'Развернуть'}
          >
            <ChevronDown className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </Button>
          <div className="truncate text-sm font-medium">{title}</div>
        </div>
        <div className="ml-auto inline-flex items-center gap-2">
          {actions}
          <Button type="button" size="icon" variant="outline" className="h-8 w-8" {...attributes} {...listeners}>
            <GripVertical className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {expanded ? children : null}
    </div>
  );
}

export default function ProductCourseModulePage() {
  const { id, module_id: rawModuleId } = useParams<RouteParams>();
  const productId = Number(id);
  const moduleId = Number(rawModuleId);

  const [loading, setLoading] = useState(true);
  const [moduleSaving, setModuleSaving] = useState(false);
  const [savingLessonId, setSavingLessonId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [course, setCourse] = useState<ProductCourse | null>(null);
  const [lessonDrafts, setLessonDrafts] = useState<Record<number, LessonDraft>>({});
  const [expandedLessonIds, setExpandedLessonIds] = useState<Record<number, boolean>>({});
  const [activeBlockDrag, setActiveBlockDrag] = useState<{ lessonId: number; blockId: string } | null>(null);
  const [moduleTitle, setModuleTitle] = useState('');
  const [moduleCover, setModuleCover] = useState('');
  const [moduleOpenLessonsImmediately, setModuleOpenLessonsImmediately] = useState(false);
  const [moduleUnlockCondition, setModuleUnlockCondition] = useState<UnlockCondition>(DEFAULT_UNLOCK_CONDITION);
  const [moduleDelayDays, setModuleDelayDays] = useState('0');
  const [moduleDelayHours, setModuleDelayHours] = useState('0');
  const [moduleDelayMinutes, setModuleDelayMinutes] = useState('0');

  const lessonSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const blockSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const selectedModule = useMemo(
    () => course?.modules.find((item) => item.id === moduleId) || null,
    [course, moduleId],
  );

  const loadCourse = async () => {
    if (!Number.isFinite(productId) || productId <= 0 || !Number.isFinite(moduleId) || moduleId <= 0) {
      setError('Некорректный URL модуля.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await clientProductsApi.getCourse(productId);
      const loaded = payload.course;
      if (!loaded) {
        setCourse(null);
        setError('Курс не найден.');
      } else {
        setCourse(loaded);
      }
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить курс.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCourse();
  }, [productId, moduleId]);

  useEffect(() => {
    if (!selectedModule) {
      setLessonDrafts({});
      setExpandedLessonIds({});
      setModuleTitle('');
      setModuleCover('');
      setModuleOpenLessonsImmediately(false);
      setModuleUnlockCondition(DEFAULT_UNLOCK_CONDITION);
      setModuleDelayDays('0');
      setModuleDelayHours('0');
      setModuleDelayMinutes('0');
      return;
    }

    setModuleTitle((selectedModule.title || '').trim());
    setModuleCover((selectedModule.cover_url || '').trim());
    setModuleOpenLessonsImmediately(Boolean(selectedModule.open_lessons_immediately));
    setModuleUnlockCondition(normalizeUnlockCondition(selectedModule.lesson_unlock_condition));
    setModuleDelayDays(String(Math.max(0, Number(selectedModule.unlock_delay_days || 0))));
    setModuleDelayHours(String(Math.max(0, Number(selectedModule.unlock_delay_hours || 0))));
    setModuleDelayMinutes(String(Math.max(0, Number(selectedModule.unlock_delay_minutes || 0))));

    const nextDrafts: Record<number, LessonDraft> = {};
    for (const lesson of selectedModule.lessons) {
      nextDrafts[lesson.id] = buildLessonDraft(lesson);
    }
    setLessonDrafts(nextDrafts);
    setExpandedLessonIds((prev) => {
      const next: Record<number, boolean> = {};
      for (const [index, lesson] of selectedModule.lessons.entries()) {
        if (Object.prototype.hasOwnProperty.call(prev, lesson.id)) {
          next[lesson.id] = Boolean(prev[lesson.id]);
        } else {
          next[lesson.id] = index === 0;
        }
      }
      return next;
    });
  }, [selectedModule]);

  const parseNonNegativeInt = (raw: string): number => {
    const parsed = Number.parseInt((raw || '').trim(), 10);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return parsed;
  };

  const saveModule = async () => {
    if (!selectedModule) return;

    setModuleSaving(true);
    setError(null);
    try {
      await clientProductsApi.updateCourseModule(productId, selectedModule.id, {
        title: moduleTitle.trim() || selectedModule.title,
        cover_url: moduleCover.trim() || null,
        open_lessons_immediately: moduleOpenLessonsImmediately,
        lesson_unlock_condition: moduleUnlockCondition,
        unlock_delay_days: parseNonNegativeInt(moduleDelayDays),
        unlock_delay_hours: parseNonNegativeInt(moduleDelayHours),
        unlock_delay_minutes: parseNonNegativeInt(moduleDelayMinutes),
      });
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось сохранить модуль.');
    } finally {
      setModuleSaving(false);
    }
  };

  const addLesson = async () => {
    if (!selectedModule) return;
    try {
      await clientProductsApi.createCourseLesson(productId, selectedModule.id, {
        title: `Урок ${selectedModule.lessons.length + 1}`,
        content: createDefaultCourseLessonContent(),
      });
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось создать урок.');
    }
  };

  const removeLesson = async (lessonId: number) => {
    if (!confirm('Удалить урок?')) return;
    try {
      await clientProductsApi.deleteCourseLesson(productId, lessonId);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось удалить урок.');
    }
  };

  const reorderLesson = async (lessonId: number, direction: -1 | 1) => {
    if (!selectedModule) return;

    const ids = selectedModule.lessons.map((lesson) => lesson.id);
    const idx = ids.findIndex((item) => item === lessonId);
    const target = idx + direction;
    if (idx < 0 || target < 0 || target >= ids.length) return;

    const next = [...ids];
    [next[idx], next[target]] = [next[target], next[idx]];

    try {
      await clientProductsApi.reorderCourseLessons(productId, selectedModule.id, next);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось изменить порядок уроков.');
    }
  };

  const onLessonDragEnd = async (event: DragEndEvent) => {
    if (!selectedModule) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const ids = selectedModule.lessons.map((lesson) => lesson.id);
    const oldIndex = ids.indexOf(Number(active.id));
    const newIndex = ids.indexOf(Number(over.id));
    if (oldIndex < 0 || newIndex < 0) return;

    const orderedIds = arrayMove(ids, oldIndex, newIndex);

    try {
      await clientProductsApi.reorderCourseLessons(productId, selectedModule.id, orderedIds);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось изменить порядок уроков.');
    }
  };

  const updateLessonDraft = (lessonId: number, patch: Partial<LessonDraft>) => {
    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current) return prev;
      return {
        ...prev,
        [lessonId]: {
          ...current,
          ...patch,
        },
      };
    });
  };

  const addLessonBlock = (lessonId: number, blockType: AddBlockType) => {
    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current) return prev;

      let newBlock: CourseLessonBlock;
      if (blockType === 'video') {
        newBlock = createCourseLessonVideoBlock();
      } else if (blockType === 'image') {
        newBlock = createCourseLessonImageBlock();
      } else {
        newBlock = createCourseLessonTiptapBlock();
      }

      return {
        ...prev,
        [lessonId]: {
          ...current,
          content: {
            blocks: [...current.content.blocks, newBlock],
          },
        },
      };
    });
  };

  const removeLessonBlock = (lessonId: number, blockId: string) => {
    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current || current.content.blocks.length <= 1) return prev;
      return {
        ...prev,
        [lessonId]: {
          ...current,
          content: {
            blocks: current.content.blocks.filter((block) => block.id !== blockId),
          },
        },
      };
    });
  };

  const updateLessonBlock = (
    lessonId: number,
    blockId: string,
    updater: (block: CourseLessonBlock) => CourseLessonBlock,
  ) => {
    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current) return prev;
      return {
        ...prev,
        [lessonId]: {
          ...current,
          content: {
            blocks: current.content.blocks.map((block) => {
              if (block.id !== blockId) return block;
              return updater(block);
            }),
          },
        },
      };
    });
  };

  const onLessonBlockDragEnd = (lessonId: number, event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current) return prev;

      const ids = current.content.blocks.map((block) => block.id);
      const oldIndex = ids.indexOf(String(active.id));
      const newIndex = ids.indexOf(String(over.id));
      if (oldIndex < 0 || newIndex < 0) return prev;

      return {
        ...prev,
        [lessonId]: {
          ...current,
          content: {
            blocks: arrayMove(current.content.blocks, oldIndex, newIndex),
          },
        },
      };
    });
  };

  const updateLessonTiptapBlockById = (lessonId: number, blockId: string, nextDoc: Record<string, unknown>) => {
    setLessonDrafts((prev) => {
      const current = prev[lessonId];
      if (!current) return prev;
      return {
        ...prev,
        [lessonId]: {
          ...current,
          content: updateCourseLessonTiptapBlock(current.content, blockId, nextDoc),
        },
      };
    });
  };

  const saveLesson = async (lesson: ProductCourseLesson) => {
    const draft = lessonDrafts[lesson.id] || buildLessonDraft(lesson);

    let hasInvalidVideo = false;
    const normalizedBlocks: CourseLessonBlock[] = draft.content.blocks.map((block) => {
      if (block.type === 'video') {
        const rawVideoUrl = block.video_url.trim();
        if (!rawVideoUrl) {
          return {
            ...block,
            video_url: '',
            youtube_video_id: null,
            rutube_video_id: null,
            vk_owner_id: null,
            vk_video_id: null,
            vk_hash: null,
          };
        }

        const parsedVideo = parseCourseVideoUrl(rawVideoUrl);
        if (!parsedVideo) {
          hasInvalidVideo = true;
          return block;
        }

        return {
          ...block,
          youtube_video_id: parsedVideo.youtube_video_id,
          rutube_video_id: parsedVideo.rutube_video_id,
          vk_owner_id: parsedVideo.vk_owner_id,
          vk_video_id: parsedVideo.vk_video_id,
          vk_hash: parsedVideo.vk_hash,
          video_url: rawVideoUrl,
        };
      }

      if (block.type === 'tiptap') {
        return {
          ...block,
          content: normalizeTiptapDoc(block.content),
        };
      }

      return {
        ...block,
        image_url: block.image_url.trim(),
        caption: block.caption.trim(),
      };
    });

    if (hasInvalidVideo) {
      setError('В одном из блоков видео указана неподдерживаемая ссылка. Используйте YouTube / Rutube / VK.');
      return;
    }

    const nextContent: CourseLessonContent = { blocks: normalizedBlocks };
    const primaryVideo = extractPrimaryCourseVideoFields(nextContent);

    setSavingLessonId(lesson.id);
    setError(null);
    try {
      await clientProductsApi.updateCourseLesson(productId, lesson.id, {
        title: draft.title.trim() || lesson.title,
        is_preview: draft.is_preview,
        content: nextContent,
        youtube_video_id: primaryVideo.youtube_video_id,
        rutube_video_id: primaryVideo.rutube_video_id,
        vk_owner_id: primaryVideo.vk_owner_id,
        vk_video_id: primaryVideo.vk_video_id,
        vk_hash: primaryVideo.vk_hash,
      });
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось сохранить урок.');
    } finally {
      setSavingLessonId(null);
    }
  };

  const resetLessonDraft = (lesson: ProductCourseLesson) => {
    setLessonDrafts((prev) => ({
      ...prev,
      [lesson.id]: buildLessonDraft(lesson),
    }));
  };

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Загрузка модуля...</div>;
  }

  if (!selectedModule) {
    return (
      <div className="mx-auto max-w-5xl space-y-3 p-6">
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {error || 'Модуль не найден.'}
        </div>
        <Link href={`/product/${productId}/course`}>
          <Button type="button" variant="outline" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            К списку модулей
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={`/product/${productId}/course`}>
          <Button type="button" variant="outline" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            К списку модулей
          </Button>
        </Link>
      </div>

      <div className="space-y-3 rounded-xl border p-4">
        <div className="text-lg font-semibold">Модуль</div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Название модуля</div>
            <Input value={moduleTitle} onChange={(event) => setModuleTitle(event.target.value)} />
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Обложка (URL)</div>
            <Input value={moduleCover} onChange={(event) => setModuleCover(event.target.value)} />
          </div>
        </div>

        <div className="space-y-3 rounded-lg border border-dashed p-3">
          <label className="inline-flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={moduleOpenLessonsImmediately}
              onChange={(event) => setModuleOpenLessonsImmediately(event.target.checked)}
            />
            Открывать уроки сразу все
          </label>

          {!moduleOpenLessonsImmediately ? (
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Условие открытия следующего урока</div>
                <select
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                  value={moduleUnlockCondition}
                  onChange={(event) => setModuleUnlockCondition(normalizeUnlockCondition(event.target.value))}
                >
                  <option value="after_student_complete">После отметки завершения урока</option>
                  <option value="after_curator_complete">После отметки куратора о завершении урока</option>
                  <option value="after_timer">По таймеру после завершения предыдущего урока</option>
                </select>
              </div>

              {moduleUnlockCondition === 'after_timer' ? (
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground">Задержка между уроками</div>
                  <div className="grid gap-2 md:grid-cols-3">
                    <Input
                      type="number"
                      min={0}
                      value={moduleDelayDays}
                      onChange={(event) => setModuleDelayDays(event.target.value)}
                      placeholder="Дней"
                    />
                    <Input
                      type="number"
                      min={0}
                      value={moduleDelayHours}
                      onChange={(event) => setModuleDelayHours(event.target.value)}
                      placeholder="Часов"
                    />
                    <Input
                      type="number"
                      min={0}
                      value={moduleDelayMinutes}
                      onChange={(event) => setModuleDelayMinutes(event.target.value)}
                      placeholder="Минут"
                    />
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <Button type="button" onClick={() => void saveModule()} disabled={moduleSaving}>
            {moduleSaving ? 'Сохраняем...' : 'Сохранить модуль'}
          </Button>
        </div>
      </div>

      {error ? <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="space-y-3 rounded-xl border p-4">
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">Уроки</div>
          <Button type="button" size="sm" variant="outline" onClick={() => void addLesson()}>
            <Plus className="mr-1 h-3 w-3" />
            Добавить урок
          </Button>
        </div>

        {selectedModule.lessons.length === 0 ? (
          <div className="rounded-lg border p-3 text-sm text-muted-foreground">Уроков пока нет.</div>
        ) : (
          <DndContext sensors={lessonSensors} collisionDetection={closestCenter} onDragEnd={(event) => void onLessonDragEnd(event)}>
            <SortableContext
              items={selectedModule.lessons.map((lesson) => String(lesson.id))}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {selectedModule.lessons.map((lesson, lessonIndex) => {
                  const draft = lessonDrafts[lesson.id] || buildLessonDraft(lesson);
                  const isExpanded = Boolean(expandedLessonIds[lesson.id]);

                  return (
                    <SortableLessonShell
                      key={lesson.id}
                      id={String(lesson.id)}
                      title={draft.title.trim() || `Урок #${lessonIndex + 1}`}
                      expanded={isExpanded}
                      onExpandedChange={(nextExpanded) => {
                        setExpandedLessonIds((prev) => ({
                          ...prev,
                          [lesson.id]: nextExpanded,
                        }));
                      }}
                      actions={(
                        <>
                          <Button type="button" size="sm" variant="outline" onClick={() => void reorderLesson(lesson.id, -1)}>↑</Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => void reorderLesson(lesson.id, 1)}>↓</Button>
                          <Button type="button" size="sm" variant="destructive" onClick={() => void removeLesson(lesson.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    >
                      <Input
                        value={draft.title}
                        onChange={(event) => updateLessonDraft(lesson.id, { title: event.target.value })}
                        placeholder="Название урока"
                      />

                      <label className="inline-flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={draft.is_preview}
                          onChange={(event) => updateLessonDraft(lesson.id, { is_preview: event.target.checked })}
                        />
                        Урок без оплаты
                      </label>

                      <div className="space-y-2 rounded-lg border border-dashed p-3">
                        <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
                          <span>Блоки урока</span>
                          <Button type="button" size="sm" variant="outline" onClick={() => addLessonBlock(lesson.id, 'video')}>
                            <Plus className="mr-1 h-3 w-3" />
                            Видео
                          </Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => addLessonBlock(lesson.id, 'tiptap')}>
                            <Plus className="mr-1 h-3 w-3" />
                            Текст
                          </Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => addLessonBlock(lesson.id, 'image')}>
                            <Plus className="mr-1 h-3 w-3" />
                            Картинка
                          </Button>
                        </div>

                        <DndContext
                          sensors={blockSensors}
                          collisionDetection={closestCenter}
                          onDragStart={(event) => {
                            if (typeof event.active.id !== 'string') return;
                            setActiveBlockDrag({ lessonId: lesson.id, blockId: event.active.id });
                          }}
                          onDragCancel={() => setActiveBlockDrag(null)}
                          onDragEnd={(event) => {
                            onLessonBlockDragEnd(lesson.id, event);
                            setActiveBlockDrag(null);
                          }}
                        >
                          <SortableContext
                            items={draft.content.blocks.map((block) => block.id)}
                            strategy={verticalListSortingStrategy}
                          >
                            <div className="space-y-2">
                              {draft.content.blocks.map((block, blockIndex) => {
                                const canRemoveBlock = draft.content.blocks.length > 1;

                                if (block.type === 'video') {
                                  const parsed = block.video_url.trim() ? parseCourseVideoUrl(block.video_url) : null;
                                  const parseError = block.video_url.trim() && !parsed;
                                  const embedUrl = buildCourseLessonEmbedUrl(parsed || block);

                                  return (
                                    <SortableBlockShell
                                      key={block.id}
                                      id={block.id}
                                      title={`Видео блок #${blockIndex + 1}`}
                                      icon={<Video className="h-4 w-4" />}
                                      canRemove={canRemoveBlock}
                                      onRemove={() => removeLessonBlock(lesson.id, block.id)}
                                    >
                                      <Input
                                        value={block.video_url}
                                        onChange={(event) => {
                                          const value = event.target.value;
                                          updateLessonBlock(lesson.id, block.id, (current) => {
                                            if (current.type !== 'video') return current;
                                            return { ...current, video_url: value };
                                          });
                                        }}
                                        placeholder="Вставьте ссылку на YouTube / Rutube / VK"
                                      />

                                      {parseError ? (
                                        <div className="inline-flex items-center gap-1 text-xs text-red-600">
                                          <AlertCircle className="h-3.5 w-3.5" />
                                          Не удалось распознать ссылку.
                                        </div>
                                      ) : null}

                                      {!parseError && parsed ? (
                                        <div className="rounded-md border bg-muted/30 p-2 text-xs text-muted-foreground">
                                          {parsed.youtube_video_id ? <div>YouTube ID: {parsed.youtube_video_id}</div> : null}
                                          {parsed.rutube_video_id ? <div>Rutube ID: {parsed.rutube_video_id}</div> : null}
                                          {parsed.vk_owner_id ? <div>VK owner: {parsed.vk_owner_id}</div> : null}
                                          {parsed.vk_video_id ? <div>VK video: {parsed.vk_video_id}</div> : null}
                                          {parsed.provider === 'vk' && !parsed.vk_hash ? (
                                            <div className="mt-1 text-amber-600">Для VK embed может потребоваться hash в ссылке.</div>
                                          ) : null}
                                        </div>
                                      ) : null}

                                      {embedUrl ? (
                                        <div className="overflow-hidden rounded-md border">
                                          <div className="aspect-video w-full">
                                            <iframe
                                              src={embedUrl}
                                              title={draft.title || 'Видео урока'}
                                              className="h-full w-full"
                                              allow="autoplay; encrypted-media; picture-in-picture"
                                              allowFullScreen
                                            />
                                          </div>
                                        </div>
                                      ) : null}
                                    </SortableBlockShell>
                                  );
                                }

                                if (block.type === 'tiptap') {
                                  return (
                                    <SortableBlockShell
                                      key={block.id}
                                      id={block.id}
                                      title={`Текстовый блок #${blockIndex + 1}`}
                                      icon={<FileText className="h-4 w-4" />}
                                      canRemove={canRemoveBlock}
                                      onRemove={() => removeLessonBlock(lesson.id, block.id)}
                                    >
                                      <EventDescriptionEditor
                                        value={block.content}
                                        onChange={(nextDoc) => updateLessonTiptapBlockById(lesson.id, block.id, nextDoc)}
                                        placeholder="Контент урока..."
                                      />
                                    </SortableBlockShell>
                                  );
                                }

                                return (
                                  <SortableBlockShell
                                    key={block.id}
                                    id={block.id}
                                    title={`Блок изображения #${blockIndex + 1}`}
                                    icon={<ImageIcon className="h-4 w-4" />}
                                    canRemove={canRemoveBlock}
                                    onRemove={() => removeLessonBlock(lesson.id, block.id)}
                                  >
                                    <div className="grid gap-2 md:grid-cols-2">
                                      <Input
                                        value={block.image_url}
                                        onChange={(event) => {
                                          const value = event.target.value;
                                          updateLessonBlock(lesson.id, block.id, (current) => {
                                            if (current.type !== 'image') return current;
                                            return { ...current, image_url: value };
                                          });
                                        }}
                                        placeholder="URL изображения"
                                      />
                                      <Input
                                        value={block.caption}
                                        onChange={(event) => {
                                          const value = event.target.value;
                                          updateLessonBlock(lesson.id, block.id, (current) => {
                                            if (current.type !== 'image') return current;
                                            return { ...current, caption: value };
                                          });
                                        }}
                                        placeholder="Подпись (необязательно)"
                                      />
                                    </div>

                                    {block.image_url.trim() ? (
                                      <div className="space-y-2 rounded-md border p-2">
                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                        <img
                                          src={block.image_url}
                                          alt={block.caption || 'Изображение блока'}
                                          className="max-h-72 w-full rounded-md object-contain"
                                        />
                                        {block.caption ? <div className="text-xs text-muted-foreground">{block.caption}</div> : null}
                                      </div>
                                    ) : null}
                                  </SortableBlockShell>
                                );
                              })}
                            </div>
                          </SortableContext>
                          <DragOverlay>
                            {activeBlockDrag?.lessonId === lesson.id ? (
                              <div className="h-1.5 w-64 rounded-full bg-primary/80 shadow" />
                            ) : null}
                          </DragOverlay>
                        </DndContext>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void saveLesson(lesson)}
                          disabled={savingLessonId === lesson.id}
                        >
                          {savingLessonId === lesson.id ? 'Сохраняем...' : 'Сохранить урок'}
                        </Button>
                        <Button type="button" size="sm" variant="outline" onClick={() => resetLessonDraft(lesson)}>
                          Сбросить изменения
                        </Button>
                      </div>
                    </SortableLessonShell>
                  );
                })}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  );
}
