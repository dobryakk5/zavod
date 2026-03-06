'use client';

import { useEffect, useMemo } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import { Bold, Italic, Link2, List, ListOrdered, Underline as UnderlineIcon, Unlink } from 'lucide-react';

export const EMPTY_TIPTAP_DOC: Record<string, unknown> = {
  type: 'doc',
  content: [{ type: 'paragraph' }],
};

const docFromText = (text: string): Record<string, unknown> => ({
  type: 'doc',
  content: [
    {
      type: 'paragraph',
      content: [{ type: 'text', text }],
    },
  ],
});

export const normalizeTiptapDoc = (value: unknown): Record<string, unknown> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const candidate = value as { type?: unknown; content?: unknown };
    if (candidate.type === 'doc' && Array.isArray(candidate.content)) {
      return value as Record<string, unknown>;
    }
  }

  if (typeof value === 'string' && value.trim()) {
    return docFromText(value.trim());
  }

  return EMPTY_TIPTAP_DOC;
};

type EventDescriptionEditorProps = {
  value: Record<string, unknown> | null | undefined;
  onChange: (value: Record<string, unknown>) => void;
  editable?: boolean;
  placeholder?: string;
};

export function EventDescriptionEditor({
  value,
  onChange,
  editable = true,
  placeholder = 'Опишите программу мероприятия, формат и выгоды для участника...',
}: EventDescriptionEditorProps) {
  const normalizedValue = useMemo(() => normalizeTiptapDoc(value), [value]);
  const normalizedHash = useMemo(() => JSON.stringify(normalizedValue), [normalizedValue]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
      }),
      Underline,
      Link.configure({
        openOnClick: false,
        autolink: false,
        linkOnPaste: false,
        HTMLAttributes: {
          class: 'text-blue-600 underline hover:text-blue-800',
        },
      }),
      Placeholder.configure({ placeholder }),
    ],
    content: normalizedValue,
    editable,
    onUpdate: ({ editor: currentEditor }) => {
      onChange(currentEditor.getJSON() as Record<string, unknown>);
    },
    editorProps: {
      attributes: {
        class: 'tiptap prose prose-sm max-w-none min-h-[220px] p-3 focus:outline-none',
      },
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(editable);
  }, [editable, editor]);

  useEffect(() => {
    if (!editor) return;
    const currentHash = JSON.stringify(editor.getJSON());
    if (currentHash !== normalizedHash) {
      editor.commands.setContent(normalizedValue, false);
    }
  }, [editor, normalizedHash, normalizedValue]);

  const handleSetLink = () => {
    if (!editor || !editable) return;
    const previousUrl = String(editor.getAttributes('link').href || '');
    const raw = window.prompt('Введите URL ссылки', previousUrl);
    if (raw === null) return;
    const href = raw.trim();
    if (!href) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    const normalizedHref = /^https?:\/\//i.test(href) ? href : `https://${href}`;
    editor.chain().focus().setLink({ href: normalizedHref }).run();
  };

  if (!editor) {
    return (
      <div className="rounded-lg border border-input bg-background p-3 text-sm text-muted-foreground">
        Инициализация редактора...
      </div>
    );
  }

  const toolbarButtonClass = (active = false) =>
    `inline-flex h-8 w-8 items-center justify-center rounded-md border ${
      active ? 'border-primary/40 bg-primary/10 text-primary' : 'border-transparent text-muted-foreground hover:bg-muted'
    }`;

  return (
    <div className="rounded-lg border border-input bg-background">
      <div className="flex flex-wrap items-center gap-1 border-b px-2 py-1.5">
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('bold'))}
          onClick={() => editor.chain().focus().toggleBold().run()}
          disabled={!editable}
          aria-label="Жирный"
          title="Жирный"
        >
          <Bold className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('italic'))}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          disabled={!editable}
          aria-label="Курсив"
          title="Курсив"
        >
          <Italic className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('underline'))}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          disabled={!editable}
          aria-label="Подчёркивание"
          title="Подчёркивание"
        >
          <UnderlineIcon className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('bulletList'))}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          disabled={!editable}
          aria-label="Маркированный список"
          title="Маркированный список"
        >
          <List className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('orderedList'))}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          disabled={!editable}
          aria-label="Нумерованный список"
          title="Нумерованный список"
        >
          <ListOrdered className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(editor.isActive('link'))}
          onClick={handleSetLink}
          disabled={!editable}
          aria-label="Вставить ссылку"
          title="Вставить ссылку"
        >
          <Link2 className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={toolbarButtonClass(false)}
          onClick={() => editor.chain().focus().unsetLink().run()}
          disabled={!editable}
          aria-label="Удалить ссылку"
          title="Удалить ссылку"
        >
          <Unlink className="h-4 w-4" />
        </button>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
