'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  Copy,
  ExternalLink,
  GripVertical,
  Pencil,
  Plus,
  Save,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api';
import { clientApi } from '@/lib/api/client';
import {
  buildSitePagePublicPath,
  createDefaultClientSitePage,
  normalizeClientSitePagesConfig,
  slugifySitePageTitle,
  validateSitePages,
  validateSingleSitePageSlug,
  type ClientSitePage,
} from '@/lib/client-site-pages';
import type { ClientSettings } from '@/lib/types';

type NewPageFormState = {
  title: string;
  slug: string;
  meta_description: string;
  og_image: string;
};

const EMPTY_NEW_PAGE_FORM: NewPageFormState = {
  title: '',
  slug: '',
  meta_description: '',
  og_image: '',
};

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error('Copy failed');
  }
};

const buildAbsoluteUrl = (path: string): string => {
  if (typeof window === 'undefined') {
    return path;
  }
  return `${window.location.origin}${path}`;
};

const suggestSlug = (title: string, pages: ClientSitePage[], excludeId?: string): string => {
  const base = slugifySitePageTitle(title) || 'page';
  let candidate = base;
  let index = 2;

  while (validateSingleSitePageSlug(pages, excludeId || '__new__', candidate)) {
    candidate = `${base}-${index}`;
    index += 1;
  }

  return candidate;
};

function SortablePageRow({
  page,
  pageClientId,
  index,
  isHome,
  onCopyUrl,
  onDelete,
}: {
  page: ClientSitePage;
  pageClientId: number;
  index: number;
  isHome: boolean;
  onCopyUrl: (path: string) => void;
  onDelete: (pageId: string) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: page.id });

  const publicPath = buildSitePagePublicPath(pageClientId, page.slug, false);
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`rounded-2xl border bg-white p-4 shadow-sm ${isDragging ? 'opacity-70' : ''}`}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <button
            type="button"
            className="mt-1 rounded-lg border p-2 text-slate-500 hover:bg-slate-50"
            {...attributes}
            {...listeners}
            aria-label={`Переместить страницу ${page.title}`}
          >
            <GripVertical className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold">{page.title}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {isHome ? 'Главная' : `#${index + 1}`}
              </span>
            </div>
            <div className="mt-1 text-xs text-muted-foreground">{publicPath}</div>
            {page.meta_description ? (
              <p className="mt-2 line-clamp-2 text-sm text-slate-600">{page.meta_description}</p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => onCopyUrl(publicPath)}
            aria-label={`Скопировать ссылку на страницу ${page.title}`}
          >
            <Copy className="h-4 w-4" />
          </Button>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link href={publicPath} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Открыть
            </Link>
          </Button>
          <Button type="button" variant="outline" size="sm" asChild>
            <Link href={`/c/${pageClientId}/edit/pages/${page.id}`}>
              <Pencil className="mr-1.5 h-3.5 w-3.5" /> Редактировать
            </Link>
          </Button>
          {!isHome ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-red-600 hover:text-red-700"
              onClick={() => onDelete(page.id)}
              aria-label={`Удалить страницу ${page.title}`}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function ClientSitePagesIndex() {
  const { client_id: rawClientId } = useParams<{ client_id: string }>();
  const router = useRouter();
  const pageClientId = Number(rawClientId);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [savedPages, setSavedPages] = useState<ClientSitePage[]>([]);
  const [draftPages, setDraftPages] = useState<ClientSitePage[]>([]);
  const [newPageOpen, setNewPageOpen] = useState(false);
  const [newPageForm, setNewPageForm] = useState<NewPageFormState>(EMPTY_NEW_PAGE_FORM);
  const [newPageError, setNewPageError] = useState<string | null>(null);
  const [homeChangeOpen, setHomeChangeOpen] = useState(false);
  const [formerHomeSlug, setFormerHomeSlug] = useState('');
  const [formerHomeError, setFormerHomeError] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const hasUnsavedChanges = useMemo(
    () => JSON.stringify(savedPages) !== JSON.stringify(draftPages),
    [draftPages, savedPages],
  );
  const savedHome = savedPages[0] || null;
  const draftHome = draftPages[0] || null;
  const homeChanged = Boolean(savedHome && draftHome && savedHome.id !== draftHome.id);

  const loadPages = useCallback(async () => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      setError('Некорректный client_id.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [info, settingsData] = await Promise.all([
        clientApi.info(),
        clientApi.getSettings(),
      ]);
      const activeId = Number(info?.client?.id || 0);
      if (!Number.isFinite(activeId) || activeId <= 0) {
        setError('Не удалось определить текущего клиента.');
        return;
      }
      if (activeId !== pageClientId) {
        setError(`Раздел /c/${pageClientId}/edit недоступен.`);
        return;
      }

      const normalizedPages = normalizeClientSitePagesConfig(settingsData?.client_page_config).site_pages;
      setClientName((info?.client?.name || '').trim());
      setSettings(settingsData);
      setSavedPages(normalizedPages);
      setDraftPages(normalizedPages);
      setSaveMessage(null);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) {
        router.push('/login');
        return;
      }
      setError('Не удалось загрузить страницы сайта.');
    } finally {
      setLoading(false);
    }
  }, [pageClientId, router]);

  useEffect(() => {
    void loadPages();
  }, [loadPages]);

  const updateNewPageField = (field: keyof NewPageFormState, value: string) => {
    setNewPageForm((prev) => ({ ...prev, [field]: value }));
    setNewPageError(null);
    setSaveMessage(null);
  };

  const handleOpenNewPage = () => {
    const isFirstPage = draftPages.length === 0;
    setNewPageForm({
      title: isFirstPage ? 'Главная' : '',
      slug: isFirstPage ? '' : '',
      meta_description: '',
      og_image: '',
    });
    setNewPageError(null);
    setNewPageOpen(true);
  };

  const handleCreatePage = async () => {
    const isFirstPage = draftPages.length === 0;
    const title = newPageForm.title.trim() || (isFirstPage ? 'Главная' : 'Новая страница');
    const slug = isFirstPage ? '' : (newPageForm.slug.trim().toLowerCase() || suggestSlug(title, draftPages));

    if (!isFirstPage) {
      const slugError = validateSingleSitePageSlug(draftPages, '__new__', slug);
      if (slugError) {
        setNewPageError(slugError);
        return;
      }
    }

    const nextPage = createDefaultClientSitePage({
      title,
      slug,
      meta_description: newPageForm.meta_description.trim(),
      og_image: newPageForm.og_image.trim(),
    });

    const nextPages = [...draftPages, nextPage].map((page, index) => ({
      ...page,
      slug: index === 0 ? '' : page.slug,
    }));
    const saved = await persistPages(nextPages);
    if (saved) {
      setNewPageOpen(false);
      setNewPageForm(EMPTY_NEW_PAGE_FORM);
      setNewPageError(null);
      setSaveMessage('Страница добавлена.');
    }
  };

  const handleDeletePage = (pageId: string) => {
    const nextPages = draftPages.filter((page, index) => !(index > 0 && page.id === pageId));
    setDraftPages(nextPages);
    setSaveMessage(null);
    setError(null);
  };

  const handleCopyUrl = async (path: string) => {
    try {
      await copyTextToClipboard(buildAbsoluteUrl(path));
      setSaveMessage('Ссылка скопирована.');
    } catch {
      setError('Не удалось скопировать ссылку.');
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }
    const oldIndex = draftPages.findIndex((page) => page.id === String(active.id));
    const newIndex = draftPages.findIndex((page) => page.id === String(over.id));
    if (oldIndex < 0 || newIndex < 0) {
      return;
    }
    setDraftPages(arrayMove(draftPages, oldIndex, newIndex));
    setSaveMessage(null);
    setError(null);
  };

  const persistPages = async (pagesToSave: ClientSitePage[]): Promise<boolean> => {
    const validationError = validateSitePages(pagesToSave);
    if (validationError) {
      setError(validationError);
      return false;
    }

    setSaving(true);
    setError(null);
    setSaveMessage(null);
    try {
      const updated = await clientApi.updateSettings({
        client_page_config: {
          site_pages: pagesToSave,
        } as unknown as Record<string, unknown>,
      } as Partial<ClientSettings>);
      const normalizedPages = normalizeClientSitePagesConfig(updated?.client_page_config).site_pages;
      setSettings(updated);
      setSavedPages(normalizedPages);
      setDraftPages(normalizedPages);
      setSaveMessage('Страницы сайта сохранены.');
      return true;
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 401) {
        router.push('/login');
        return false;
      }
      setError('Не удалось сохранить страницы сайта.');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!hasUnsavedChanges) {
      setSaveMessage('Изменений нет.');
      return;
    }

    if (homeChanged && savedHome) {
      const suggestedSlug = suggestSlug(savedHome.title, draftPages, savedHome.id);
      setFormerHomeSlug(suggestedSlug);
      setFormerHomeError(null);
      setHomeChangeOpen(true);
      return;
    }

    await persistPages(draftPages);
  };

  const confirmHomeChange = async () => {
    if (!savedHome) {
      setHomeChangeOpen(false);
      await persistPages(draftPages);
      return;
    }

    const normalizedSlug = formerHomeSlug.trim().toLowerCase();
    const slugError = validateSingleSitePageSlug(draftPages, savedHome.id, normalizedSlug);
    if (slugError) {
      setFormerHomeError(slugError);
      return;
    }

    const nextPages = draftPages.map((page, index) => {
      if (index === 0) {
        return { ...page, slug: '' };
      }
      if (page.id === savedHome.id) {
        return { ...page, slug: normalizedSlug };
      }
      return page;
    });

    const saved = await persistPages(nextPages);
    if (saved) {
      setFormerHomeError(null);
      setHomeChangeOpen(false);
    }
  };

  const cancelHomeChange = () => {
    setHomeChangeOpen(false);
    setFormerHomeError(null);
    setDraftPages(savedPages);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Загрузка страниц сайта...
      </div>
    );
  }

  if (error && !draftPages.length) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 rounded-2xl border bg-white p-5 shadow-sm lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Внешний сайт</div>
            <h1 className="mt-1 text-2xl font-semibold">Страницы сайта</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {clientName || 'Клиент'} · /c/{pageClientId}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {saveMessage ? <span className="text-sm text-emerald-600">{saveMessage}</span> : null}
            <Button type="button" variant="outline" onClick={handleOpenNewPage}>
              <Plus className="mr-2 h-4 w-4" /> Добавить страницу
            </Button>
            <Button type="button" onClick={() => void handleSave()} disabled={saving}>
              <Save className="mr-2 h-4 w-4" /> {saving ? 'Сохраняем...' : 'Сохранить'}
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {draftPages.length === 0 ? (
          <div className="rounded-2xl border bg-white p-8 text-center shadow-sm">
            <h2 className="text-lg font-semibold">Страниц пока нет</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Создайте первую страницу сайта. Она станет главной и будет открываться на /c/{pageClientId}/.
            </p>
            <div className="mt-6">
              <Button type="button" onClick={handleOpenNewPage}>
                <Plus className="mr-2 h-4 w-4" /> Создать главную страницу
              </Button>
            </div>
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={draftPages.map((page) => page.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-3">
                {draftPages.map((page, index) => {
                  return (
                    <div key={page.id}>
                      <SortablePageRow
                        page={page}
                        pageClientId={pageClientId}
                        index={index}
                        isHome={index === 0}
                        onCopyUrl={(path) => void handleCopyUrl(path)}
                        onDelete={handleDeletePage}
                      />
                    </div>
                  );
                })}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      <Dialog open={newPageOpen} onOpenChange={setNewPageOpen}>
        <DialogContent className="sm:max-w-xl bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200 [&>button]:text-gray-900 dark:[&>button]:text-gray-900 dark:[&>button]:data-[state=open]:bg-gray-100 dark:[&>button]:data-[state=open]:text-gray-600">
          <DialogHeader>
            <DialogTitle>{draftPages.length === 0 ? 'Создать главную страницу' : 'Добавить страницу'}</DialogTitle>
            <DialogDescription>
              Новая страница будет добавлена в список и сохранится вместе с остальными изменениями после нажатия кнопки «Сохранить».
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Название</label>
              <Input
                value={newPageForm.title}
                onChange={(event) => {
                  const title = event.target.value;
                  const nextSlug = draftPages.length === 0
                    ? ''
                    : (newPageForm.slug.trim() ? newPageForm.slug : suggestSlug(title, draftPages));
                  setNewPageForm((prev) => ({ ...prev, title, slug: nextSlug }));
                  setNewPageError(null);
                }}
                placeholder={draftPages.length === 0 ? 'Главная' : 'Например, О компании'}
              />
            </div>
            {draftPages.length > 0 ? (
              <div className="space-y-2">
                <label className="text-sm font-medium">Slug</label>
                <Input
                  value={newPageForm.slug}
                  onChange={(event) => updateNewPageField('slug', event.target.value.toLowerCase())}
                  placeholder="about"
                />
              </div>
            ) : null}
            <div className="space-y-2">
              <label className="text-sm font-medium">Meta description</label>
              <Textarea
                value={newPageForm.meta_description}
                onChange={(event) => updateNewPageField('meta_description', event.target.value)}
                rows={3}
                placeholder="Краткое описание страницы"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">OG image</label>
              <Input
                value={newPageForm.og_image}
                onChange={(event) => updateNewPageField('og_image', event.target.value)}
                placeholder="https://example.com/og-image.jpg"
              />
            </div>
            {newPageError ? <div className="text-sm text-red-600">{newPageError}</div> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setNewPageOpen(false)} disabled={saving}>
                Отмена
              </Button>
              <Button type="button" onClick={() => void handleCreatePage()} disabled={saving}>
                {saving ? 'Сохраняем...' : 'Добавить'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={homeChangeOpen} onOpenChange={(open) => {
        if (!open) {
          cancelHomeChange();
        }
      }}>
        <DialogContent className="sm:max-w-lg bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200 [&>button]:text-gray-900 dark:[&>button]:text-gray-900 dark:[&>button]:data-[state=open]:bg-gray-100 dark:[&>button]:data-[state=open]:text-gray-600">
          <DialogHeader>
            <DialogTitle>Смена главной страницы</DialogTitle>
            <DialogDescription>
              Новая первая страница станет главной. Для прежней главной нужно указать новый slug.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-xl border bg-slate-50 p-3 text-sm text-slate-700">
              <div>Новая главная: <span className="font-medium">{draftHome?.title || '—'}</span></div>
              <div className="mt-1">Бывшая главная: <span className="font-medium">{savedHome?.title || '—'}</span></div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Slug для бывшей главной</label>
              <Input
                value={formerHomeSlug}
                onChange={(event) => {
                  setFormerHomeSlug(event.target.value.toLowerCase());
                  setFormerHomeError(null);
                }}
                placeholder="home-old"
              />
            </div>
            {formerHomeError ? <div className="text-sm text-red-600">{formerHomeError}</div> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={cancelHomeChange}>
                Отмена
              </Button>
              <Button type="button" onClick={() => void confirmHomeChange()}>
                Подтвердить и сохранить
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
