'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useParams } from 'next/navigation';
import {
  closestCenter,
  DndContext,
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
import { ArrowLeft, GripVertical, Plus, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CustomTextarea } from '@/components/ui/custom-textarea';
import { clientProductsApi } from '@/lib/api/clientProducts';
import type { ProductCourse } from '@/lib/types';

type RouteParams = { id: string };

function SortableModuleRow({
  id,
  children,
}: {
  id: string;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.8 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
      {children}
      <Button type="button" size="icon" variant="outline" className="h-8 w-8" {...attributes} {...listeners}>
        <GripVertical className="h-4 w-4" />
      </Button>
    </div>
  );
}

export default function ProductCourseOverviewPage() {
  const { id } = useParams<RouteParams>();
  const productId = Number(id);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [course, setCourse] = useState<ProductCourse | null>(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [coverUrl, setCoverUrl] = useState('');
  const [isPublished, setIsPublished] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadCourse = useCallback(async () => {
    if (!Number.isFinite(productId) || productId <= 0) {
      setError('Некорректный product id');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await clientProductsApi.getCourse(productId);
      const loaded = payload.course;
      setCourse(loaded);
      setTitle((loaded?.title || '').trim());
      setDescription((loaded?.description || '').trim());
      setCoverUrl((loaded?.cover_url || '').trim());
      setIsPublished(Boolean(loaded?.is_published));
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить курс продукта.');
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => {
    void loadCourse();
  }, [loadCourse]);

  const saveCourse = async () => {
    if (!Number.isFinite(productId) || productId <= 0) return;

    setSaving(true);
    setError(null);
    try {
      const payload = await clientProductsApi.upsertCourse(productId, {
        title: title.trim() || `Курс продукта #${productId}`,
        description: description.trim(),
        cover_url: coverUrl.trim() || null,
        is_published: isPublished,
      });
      const loaded = payload.course;
      setCourse(loaded);
      setTitle((loaded?.title || '').trim());
      setDescription((loaded?.description || '').trim());
      setCoverUrl((loaded?.cover_url || '').trim());
      setIsPublished(Boolean(loaded?.is_published));
    } catch (err) {
      console.error(err);
      setError('Не удалось сохранить курс.');
    } finally {
      setSaving(false);
    }
  };

  const addModule = async () => {
    try {
      await clientProductsApi.createCourseModule(productId, {
        title: `Модуль ${(course?.modules.length || 0) + 1}`,
      });
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось создать модуль.');
    }
  };

  const removeModule = async (moduleId: number) => {
    if (!confirm('Удалить модуль и все уроки внутри?')) return;
    try {
      await clientProductsApi.deleteCourseModule(productId, moduleId);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось удалить модуль.');
    }
  };

  const reorderModule = async (moduleId: number, direction: -1 | 1) => {
    if (!course) return;
    const ids = course.modules.map((module) => module.id);
    const idx = ids.findIndex((item) => item === moduleId);
    const target = idx + direction;
    if (idx < 0 || target < 0 || target >= ids.length) return;

    const orderedIds = [...ids];
    [orderedIds[idx], orderedIds[target]] = [orderedIds[target], orderedIds[idx]];

    try {
      await clientProductsApi.reorderCourseModules(productId, orderedIds);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось изменить порядок модулей.');
    }
  };

  const onModuleDragEnd = async (event: DragEndEvent) => {
    if (!course) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const ids = course.modules.map((module) => module.id);
    const oldIndex = ids.indexOf(Number(active.id));
    const newIndex = ids.indexOf(Number(over.id));
    if (oldIndex < 0 || newIndex < 0) return;

    const orderedIds = arrayMove(ids, oldIndex, newIndex);

    try {
      await clientProductsApi.reorderCourseModules(productId, orderedIds);
      await loadCourse();
    } catch (err) {
      console.error(err);
      setError('Не удалось изменить порядок модулей.');
    }
  };

  const publicCourseUrl = useMemo(() => {
    if (!course?.product_id) return null;
    return `/c/${course.owner_id}/products/${course.product_id}/course`;
  }, [course]);

  if (loading) {
    return <div className="p-6 text-sm text-muted-foreground">Загрузка курса...</div>;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href={`/product/${productId}`}>
          <Button type="button" variant="outline" size="sm">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Назад к продукту
          </Button>
        </Link>
        {publicCourseUrl ? (
          <Link href={publicCourseUrl} target="_blank">
            <Button type="button" variant="secondary" size="sm">
              Открыть публичный курс
            </Button>
          </Link>
        ) : null}
      </div>

      <div className="space-y-3 rounded-xl border p-4">
        <div className="text-lg font-semibold">Курс продукта</div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Название курса</div>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">Обложка (URL)</div>
            <Input value={coverUrl} onChange={(event) => setCoverUrl(event.target.value)} />
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Описание</div>
          <CustomTextarea value={description} onChange={(event) => setDescription(event.target.value)} rows={5} />
        </div>

        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isPublished} onChange={(event) => setIsPublished(event.target.checked)} />
          Курс опубликован
        </label>

        <div>
          <Button onClick={() => void saveCourse()} disabled={saving}>
            {saving ? 'Сохраняем...' : 'Сохранить курс'}
          </Button>
        </div>
      </div>

      {error ? <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="space-y-3 rounded-xl border p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-lg font-semibold">Модули</div>
          <Button type="button" variant="outline" onClick={() => void addModule()}>
            <Plus className="mr-2 h-4 w-4" />
            Добавить модуль
          </Button>
        </div>

        {!course || course.modules.length === 0 ? (
          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
            Модулей пока нет.
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(event) => void onModuleDragEnd(event)}>
            <SortableContext
              items={course.modules.map((module) => String(module.id))}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {course.modules.map((module, moduleIndex) => (
                  <SortableModuleRow key={module.id} id={String(module.id)}>
                    <Link href={`/product/${productId}/course/${module.id}`} className="min-w-0 flex-1">
                      <div className="font-medium hover:underline">{module.title || `Модуль ${moduleIndex + 1}`}</div>
                      <div className="text-xs text-muted-foreground">Уроков: {module.lessons.length}</div>
                    </Link>

                    <div className="inline-flex items-center gap-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => void reorderModule(module.id, -1)}>↑</Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => void reorderModule(module.id, 1)}>↓</Button>
                      <Link href={`/product/${productId}/course/${module.id}`}>
                        <Button type="button" size="sm" variant="secondary">Открыть</Button>
                      </Link>
                      <Button type="button" size="sm" variant="destructive" onClick={() => void removeModule(module.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </SortableModuleRow>
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  );
}
