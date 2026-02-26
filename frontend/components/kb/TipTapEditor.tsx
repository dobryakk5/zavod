'use client';

import { BubbleMenu, useEditor, EditorContent, type Editor } from '@tiptap/react';
import { Bold, ChevronDown, FilePlus, ImagePlus, Italic, Link2, List, ListOrdered, ListTodo, Quote, Table as TableIcon, Underline as UnderlineIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { kbDocumentsApi, kbLinkPreviewApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentDetail, KbLinkPreview } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

interface TipTapEditorProps {
  documentId?: number;
  initialContent?: Record<string, unknown> | null;
  onChange?: (content: Record<string, unknown>) => void;
  placeholder?: string;
  editable?: boolean;
  autoSave?: boolean;
  autoSaveInterval?: number;
  onSave?: (content: Record<string, unknown>) => Promise<void>;
  showToolbar?: boolean;
  onPageCreated?: (document: KbDocumentDetail) => void;
  onEditorReady?: (editor: Editor | null) => void;
}

const normalizeUrl = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
};

const toolbarButtonClass = (isActive = false) =>
  `p-2 rounded transition-colors ${isActive ? 'bg-gray-200 text-gray-900' : 'hover:bg-gray-200 text-gray-700'}`;

export default function TipTapEditor({
  documentId,
  initialContent,
  onChange,
  placeholder = 'Начните писать...',
  editable = true,
  autoSave = true,
  autoSaveInterval = 3000,
  onSave,
  showToolbar = true,
  onPageCreated,
  onEditorReady,
}: TipTapEditorProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [currentBlockLabel, setCurrentBlockLabel] = useState<'Text' | 'H1' | 'H2' | 'H3'>('Text');
  const [isCreatingPage, setIsCreatingPage] = useState(false);
  const [createPageError, setCreatePageError] = useState<string | null>(null);

  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const [linkText, setLinkText] = useState('');
  const [linkPreview, setLinkPreview] = useState<KbLinkPreview | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const editor = useEditor({
    extensions: createKbExtensions({ includePlaceholder: true, placeholder }),
    shouldRerenderOnTransaction: true,
    content: initialContent ?? undefined,
    editable,
    onUpdate: ({ editor: currentEditor }) => {
      const json = currentEditor.getJSON();
      onChange?.(json);
    },
    editorProps: {
      attributes: {
        class: 'tiptap not-prose focus:outline-none max-w-none min-h-[500px] p-8',
      },
    },
  });

  useEffect(() => {
    onEditorReady?.(editor ?? null);
    return () => {
      onEditorReady?.(null);
    };
  }, [editor, onEditorReady]);

  useEffect(() => {
    if (!autoSave || !editor || !documentId) return;

    let timeoutId: ReturnType<typeof setTimeout>;

    const handleAutoSave = async () => {
      const content = editor.getJSON();
      try {
        setIsSaving(true);
        setSaveError(null);
        if (onSave) {
          await onSave(content);
        } else {
          await kbDocumentsApi.update(documentId, { content });
        }
        setLastSaved(new Date());
      } catch (error: any) {
        console.error('Auto-save error:', error);
        setSaveError(error?.message || 'Ошибка сохранения');
      } finally {
        setIsSaving(false);
      }
    };

    const debouncedSave = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(handleAutoSave, autoSaveInterval);
    };

    editor.on('update', debouncedSave);

    return () => {
      clearTimeout(timeoutId);
      editor.off('update', debouncedSave);
    };
  }, [editor, autoSave, documentId, autoSaveInterval, onSave]);

  useEffect(() => {
    if (!editor) return;
    if (initialContent && JSON.stringify(editor.getJSON()) !== JSON.stringify(initialContent)) {
      editor.commands.setContent(initialContent);
    }
  }, [initialContent, editor]);

  useEffect(() => {
    if (!isLinkModalOpen) return;

    const normalized = normalizeUrl(linkUrl);
    if (!normalized) {
      setLinkPreview(null);
      setPreviewError(null);
      setIsPreviewLoading(false);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(async () => {
      setIsPreviewLoading(true);
      setPreviewError(null);
      try {
        const preview = await kbLinkPreviewApi.preview(normalized);
        if (!cancelled) {
          setLinkPreview(preview);
        }
      } catch (error: any) {
        if (!cancelled) {
          setLinkPreview(null);
          setPreviewError(error?.message || 'Не удалось загрузить превью');
        }
      } finally {
        if (!cancelled) {
          setIsPreviewLoading(false);
        }
      }
    }, 500);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isLinkModalOpen, linkUrl]);

  const openLinkModal = useCallback(() => {
    if (!editor) return;

    const previousUrl = String(editor.getAttributes('link').href || '');
    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, ' ').trim();

    setLinkUrl(previousUrl);
    setLinkText(selectedText && selectedText !== previousUrl ? selectedText : '');
    setPreviewError(null);
    setLinkPreview(null);
    setIsLinkModalOpen(true);
  }, [editor]);

  const closeLinkModal = useCallback(() => {
    setIsLinkModalOpen(false);
    setIsPreviewLoading(false);
    setPreviewError(null);
  }, []);

  const insertLink = useCallback(() => {
    if (!editor) return;

    const normalized = normalizeUrl(linkUrl);
    if (!normalized) {
      setPreviewError('Введите URL');
      return;
    }

    const text = linkText.trim() || normalized;

    editor
      .chain()
      .focus()
      .insertContent({
        type: 'text',
        text,
        marks: [
          {
            type: 'link',
            attrs: { href: normalized },
          },
        ],
      })
      .run();

    setLinkUrl('');
    setLinkText('');
    setLinkPreview(null);
    setPreviewError(null);
    setIsLinkModalOpen(false);
  }, [editor, linkText, linkUrl]);

  const addImage = useCallback(() => {
    if (!editor) return;
    const url = window.prompt('URL изображения:');
    const normalized = normalizeUrl(url || '');
    if (normalized) {
      editor.chain().focus().setImage({ src: normalized }).run();
    }
  }, [editor]);

  const createPageFromSelection = useCallback(async () => {
    if (!editor || !documentId) return;

    const { from, to, empty } = editor.state.selection;
    if (empty) {
      setCreatePageError('Выделите текст для новой страницы');
      return;
    }

    const selectedText = editor.state.doc.textBetween(from, to, ' ').trim();
    if (!selectedText) {
      setCreatePageError('Выделите текст для новой страницы');
      return;
    }

    const title = selectedText.slice(0, 120);
    setIsCreatingPage(true);
    setCreatePageError(null);

    try {
      const created = await kbDocumentsApi.create({
        title,
        content: { type: 'doc', content: [] },
        parent_document: documentId,
      });

      editor
        .chain()
        .focus()
        .insertContent({
          type: 'pageLink',
          attrs: {
            id: created.id,
            title: created.title,
            icon: created.icon || '📄',
          },
        })
        .run();

      onPageCreated?.(created);
    } catch (error: any) {
      console.error('Error creating page from selection:', error);
      setCreatePageError(error?.message || 'Не удалось создать страницу');
    } finally {
      setIsCreatingPage(false);
    }
  }, [editor, documentId, onPageCreated]);

  const insertDefaultTable = useCallback(() => {
    if (!editor) return;
    editor
      .chain()
      .focus()
      .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
      .run();
  }, [editor]);

  const insertStarDivider = useCallback(() => {
    if (!editor) return;
    editor
      .chain()
      .focus()
      .insertContent([
        {
          type: 'paragraph',
          attrs: { textAlign: 'center' },
          content: [{ type: 'text', text: '* * *' }],
        },
        {
          type: 'paragraph',
        },
      ])
      .run();
  }, [editor]);

  const canInsertTable = useMemo(() => {
    if (!editor) return false;
    return editor.can().chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    const syncBlockLabel = () => {
      setCreatePageError(null);
      if (editor.isActive('heading', { level: 1 })) {
        setCurrentBlockLabel('H1');
        return;
      }
      if (editor.isActive('heading', { level: 2 })) {
        setCurrentBlockLabel('H2');
        return;
      }
      if (editor.isActive('heading', { level: 3 })) {
        setCurrentBlockLabel('H3');
        return;
      }
      setCurrentBlockLabel('Text');
    };

    syncBlockLabel();
    editor.on('selectionUpdate', syncBlockLabel);
    editor.on('update', syncBlockLabel);

    return () => {
      editor.off('selectionUpdate', syncBlockLabel);
      editor.off('update', syncBlockLabel);
    };
  }, [editor]);

  if (!editor) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2" />
          <p className="text-gray-600 text-sm">Загрузка редактора...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {showToolbar && (
          <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2 flex-wrap">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className={`px-3 py-2 rounded transition-colors inline-flex items-center gap-1 ${currentBlockLabel !== 'Text' ? 'bg-gray-200 text-gray-900' : 'bg-white text-gray-700 hover:bg-gray-200'}`}
                    title="Формат блока"
                  >
                    <span className="text-sm font-medium">{currentBlockLabel}</span>
                    <ChevronDown className="w-4 h-4" strokeWidth={1.5} />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="!bg-white !text-gray-900 !border-gray-200">
                  <DropdownMenuItem
                    onSelect={() => editor.chain().focus().clearNodes().setParagraph().run()}
                    className={`!text-gray-900 data-[highlighted]:!bg-gray-100 data-[highlighted]:!text-gray-900 ${
                      editor.isActive('paragraph') ? '!bg-gray-100' : ''
                    }`}
                  >
                    Text
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => editor.chain().focus().clearNodes().setHeading({ level: 1 }).run()}
                    className={`!text-gray-900 data-[highlighted]:!bg-gray-100 data-[highlighted]:!text-gray-900 ${
                      editor.isActive('heading', { level: 1 }) ? '!bg-gray-100' : ''
                    }`}
                  >
                    H1
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => editor.chain().focus().clearNodes().setHeading({ level: 2 }).run()}
                    className={`!text-gray-900 data-[highlighted]:!bg-gray-100 data-[highlighted]:!text-gray-900 ${
                      editor.isActive('heading', { level: 2 }) ? '!bg-gray-100' : ''
                    }`}
                  >
                    H2
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() => editor.chain().focus().clearNodes().setHeading({ level: 3 }).run()}
                    className={`!text-gray-900 data-[highlighted]:!bg-gray-100 data-[highlighted]:!text-gray-900 ${
                      editor.isActive('heading', { level: 3 }) ? '!bg-gray-100' : ''
                    }`}
                  >
                    H3
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <div className="h-6 w-px bg-gray-300 mx-1" />

              <button
                type="button"
                onClick={() => editor.chain().focus().toggleBold().run()}
                className={toolbarButtonClass(editor.isActive('bold'))}
                title="Жирный"
              >
                <Bold className="w-6 h-6" strokeWidth={2} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleItalic().run()}
                className={toolbarButtonClass(editor.isActive('italic'))}
                title="Курсив"
              >
                <Italic className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleUnderline().run()}
                className={toolbarButtonClass(editor.isActive('underline'))}
                title="Подчеркнутый"
              >
                <UnderlineIcon className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleBlockquote().run()}
                className={toolbarButtonClass(editor.isActive('blockquote'))}
                title="Callout"
              >
                <Quote className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={insertStarDivider}
                className={toolbarButtonClass()}
                title="Разделитель ***"
              >
                <span className="text-base leading-none tracking-wide">*</span>
                <span className="text-base leading-none tracking-wide">*</span>
                <span className="text-base leading-none tracking-wide">*</span>
              </button>

              <div className="h-6 w-px bg-gray-300 mx-1" />

              <button
                type="button"
                onClick={() => editor.chain().focus().toggleBulletList().run()}
                className={toolbarButtonClass(editor.isActive('bulletList'))}
                title="Маркированный список"
              >
                <List className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleOrderedList().run()}
                className={toolbarButtonClass(editor.isActive('orderedList'))}
                title="Нумерованный список"
              >
                <ListOrdered className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleTaskList().run()}
                className={toolbarButtonClass(editor.isActive('taskList'))}
                title="Список задач"
              >
                <ListTodo className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={insertDefaultTable}
                disabled={!canInsertTable}
                className={toolbarButtonClass(editor.isActive('table'))}
                title="Вставить таблицу 3x3"
              >
                <TableIcon className="w-6 h-6" strokeWidth={1.5} />
              </button>

              <div className="h-6 w-px bg-gray-300 mx-1" />

              <button
                type="button"
                onClick={openLinkModal}
                className={toolbarButtonClass(editor.isActive('link'))}
                title="Вставить ссылку"
              >
                <Link2 className="w-6 h-6" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={addImage}
                className={toolbarButtonClass()}
                title="Вставить изображение"
              >
                <ImagePlus className="w-6 h-6" strokeWidth={1.5} />
              </button>
            </div>

            <div className="flex items-center gap-3 text-xs text-gray-500">
              {isSaving && <span>Сохранение...</span>}
              {!isSaving && lastSaved && (
                <span>
                  Сохранено {lastSaved.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
              {saveError && <span className="text-red-500">{saveError}</span>}
            </div>
          </div>
        )}

        {editable && (
          <BubbleMenu
            editor={editor}
            tippyOptions={{ duration: 150 }}
            shouldShow={({ editor: menuEditor }) => menuEditor.isEditable && !menuEditor.state.selection.empty}
          >
            <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1 shadow-lg">
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleBold().run()}
                className={toolbarButtonClass(editor.isActive('bold'))}
                title="Жирный"
              >
                <Bold className="w-4 h-4" strokeWidth={2} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleItalic().run()}
                className={toolbarButtonClass(editor.isActive('italic'))}
                title="Курсив"
              >
                <Italic className="w-4 h-4" strokeWidth={1.5} />
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().toggleUnderline().run()}
                className={toolbarButtonClass(editor.isActive('underline'))}
                title="Подчеркнутый"
              >
                <UnderlineIcon className="w-4 h-4" strokeWidth={1.5} />
              </button>

              <div className="h-5 w-px bg-gray-200 mx-1" />

              <button
                type="button"
                onClick={createPageFromSelection}
                disabled={isCreatingPage || !documentId}
                className="inline-flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50"
                title={documentId ? 'Создать вложенную страницу' : 'Сохраните документ, чтобы создать вложенную страницу'}
              >
                <FilePlus className="h-4 w-4" />
                Создать страницу
              </button>
            </div>
          </BubbleMenu>
        )}

        {createPageError && (
          <div className="mt-2 text-xs text-red-600">{createPageError}</div>
        )}

        <EditorContent editor={editor} />
      </div>

      <Dialog open={isLinkModalOpen} onOpenChange={(open) => (open ? setIsLinkModalOpen(true) : closeLinkModal())}>
        <DialogContent className="sm:max-w-xl bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200 [&>button]:text-gray-900 dark:[&>button]:text-gray-900 dark:[&>button]:data-[state=open]:bg-gray-100 dark:[&>button]:data-[state=open]:text-gray-600">
          <DialogHeader>
            <DialogTitle>Вставить ссылку</DialogTitle>
            <DialogDescription>
              Введите URL и текст ссылки. Превью загружается автоматически.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Input
              value={linkUrl}
              onChange={(event) => setLinkUrl(event.target.value)}
              placeholder="https://example.com"
            />
            <Input
              value={linkText}
              onChange={(event) => setLinkText(event.target.value)}
              placeholder="Текст ссылки (опционально)"
            />

            {isPreviewLoading && (
              <div className="text-sm text-gray-500">Загрузка превью...</div>
            )}

            {previewError && (
              <div className="text-sm text-red-500">{previewError}</div>
            )}

            {linkPreview?.title && (
              <div className="rounded-md border border-gray-200 p-3 flex items-start gap-3 bg-gray-50">
                {linkPreview.favicon ? (
                  <Image
                    src={linkPreview.favicon}
                    alt="favicon"
                    width={20}
                    height={20}
                    unoptimized
                    className="w-5 h-5 mt-0.5 rounded-sm object-contain"
                  />
                ) : (
                  <div className="w-5 h-5 mt-0.5 rounded-sm bg-gray-300" />
                )}
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-gray-900 truncate">{linkPreview.title}</p>
                  {linkPreview.description && (
                    <p className="text-xs text-gray-600 line-clamp-2">{linkPreview.description}</p>
                  )}
                  <p className="text-xs text-blue-600 truncate">{linkPreview.url}</p>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeLinkModal}>
              Отмена
            </Button>
            <Button type="button" onClick={insertLink}>
              Вставить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
