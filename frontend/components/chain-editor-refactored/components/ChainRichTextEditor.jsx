import { useEditor, EditorContent } from '@tiptap/react';
import { getMarkRange } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Underline from '@tiptap/extension-underline';
import { Bold, Italic, Link2, Underline as UnderlineIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

const toolbarButtonClass = (isActive = false) =>
  `p-1.5 rounded transition-colors ${isActive ? 'bg-slate-200 text-slate-900' : 'hover:bg-slate-100 text-slate-700'}`;

const normalizeUrl = (value) => {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
};

const toEditorContent = (value = '') => {
  const raw = String(value || '').replace(/\r\n/g, '\n');
  if (!raw.trim()) return '';
  const hasHtmlTags = /<\/?[a-z][^>]*>/i.test(raw);
  if (hasHtmlTags) {
    return raw.replace(/\n/g, '<br>');
  }
  const escaped = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped.replace(/\n/g, '<br>');
};

export function ChainRichTextEditor({ value = '', onChange, placeholder = 'Введите текст...' }) {
  const [isLinkDialogOpen, setIsLinkDialogOpen] = useState(false);
  const [linkText, setLinkText] = useState('');
  const [linkUrl, setLinkUrl] = useState('');
  const [linkRange, setLinkRange] = useState(null);
  const editorContent = useMemo(() => toEditorContent(value), [value]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        bulletList: false,
        orderedList: false,
        blockquote: false,
        codeBlock: false,
        horizontalRule: false,
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 underline',
        },
      }),
      Underline,
    ],
    content: editorContent || '',
    onUpdate: ({ editor: currentEditor }) => {
      onChange?.(currentEditor.getHTML());
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none p-3 min-h-[100px] focus:outline-none',
      },
    },
  });

  useEffect(() => {
    if (!editor) return;
    if (editorContent !== editor.getHTML()) {
      editor.commands.setContent(editorContent || '');
    }
  }, [editor, editorContent]);

  const openLinkDialog = useCallback(() => {
    if (!editor) return;
    const { state } = editor;
    const { from, to, empty, $from } = state.selection;
    const linkMarkType = state.schema.marks.link;
    let selectedText = state.doc.textBetween(from, to, ' ').trim();
    let href = String(editor.getAttributes('link').href || '');
    let currentLinkRange = null;

    if (linkMarkType && empty) {
      const range = getMarkRange($from, linkMarkType);
      if (range) {
        currentLinkRange = range;
        selectedText = state.doc.textBetween(range.from, range.to, ' ').trim();
        const linkMark = $from.marks().find((mark) => mark.type === linkMarkType);
        href = String(linkMark?.attrs?.href || href || '');
      }
    }

    const initialText = selectedText || href;
    const initialUrl = href || selectedText;
    setLinkText(initialText);
    setLinkUrl(initialUrl);
    setLinkRange(currentLinkRange);
    setIsLinkDialogOpen(true);
  }, [editor]);

  const insertLink = useCallback(() => {
    if (!editor) return;
    const normalized = normalizeUrl(linkUrl);
    const textValue = linkText.trim() || normalized;
    if (normalized) {
      const chain = editor.chain().focus();
      if (linkRange?.from && linkRange?.to) {
        chain.setTextSelection({ from: linkRange.from, to: linkRange.to });
      }
      chain
        .insertContent({
          type: 'text',
          text: textValue,
          marks: [{ type: 'link', attrs: { href: normalized } }],
        })
        .run();
    }
    setIsLinkDialogOpen(false);
    setLinkRange(null);
    setLinkText('');
    setLinkUrl('');
  }, [editor, linkRange, linkText, linkUrl]);

  const removeLink = useCallback(() => {
    if (!editor) return;
    editor.chain().focus().unsetLink().run();
  }, [editor]);

  if (!editor) return null;

  return (
    <>
      <div className="border border-slate-300 rounded-lg overflow-hidden">
        <div className="border-b border-slate-200 p-2 flex items-center gap-1 bg-slate-50">
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={toolbarButtonClass(editor.isActive('bold'))}
            title="Жирный (Ctrl+B)"
          >
            <Bold className="w-4 h-4" strokeWidth={2} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={toolbarButtonClass(editor.isActive('italic'))}
            title="Курсив (Ctrl+I)"
          >
            <Italic className="w-4 h-4" strokeWidth={1.5} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={toolbarButtonClass(editor.isActive('underline'))}
            title="Подчеркнутый (Ctrl+U)"
          >
            <UnderlineIcon className="w-4 h-4" strokeWidth={1.5} />
          </button>

          <div className="h-4 w-px bg-slate-300 mx-1" />

          <button
            type="button"
            onClick={openLinkDialog}
            className={toolbarButtonClass(editor.isActive('link'))}
            title="Добавить ссылку"
          >
            <Link2 className="w-4 h-4" strokeWidth={1.5} />
          </button>
          {editor.isActive('link') && (
            <button
              type="button"
              onClick={removeLink}
              className="text-xs px-2 py-1 rounded hover:bg-slate-100 text-slate-600"
              title="Удалить ссылку"
            >
              Удалить ссылку
            </button>
          )}
        </div>

        <EditorContent editor={editor} />
      </div>

      {isLinkDialogOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-4 w-[36rem] max-w-[90vw] shadow-xl">
            <h3 className="text-lg font-semibold mb-3">Добавить ссылку</h3>
            <label className="block text-sm font-medium text-slate-700 mb-1">Текст</label>
            <input
              type="text"
              value={linkText}
              onChange={(e) => setLinkText(e.target.value)}
              placeholder="Текст ссылки"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 mb-3"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') insertLink();
                if (e.key === 'Escape') {
                  setIsLinkDialogOpen(false);
                  setLinkRange(null);
                }
              }}
            />
            <label className="block text-sm font-medium text-slate-700 mb-1">Ссылка</label>
            <input
              type="text"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="Ссылка"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 mb-3"
              onKeyDown={(e) => {
                if (e.key === 'Enter') insertLink();
                if (e.key === 'Escape') {
                  setIsLinkDialogOpen(false);
                  setLinkRange(null);
                }
              }}
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setIsLinkDialogOpen(false);
                  setLinkRange(null);
                }}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 hover:bg-slate-50"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={insertLink}
                className="px-3 py-1.5 text-sm rounded-lg bg-slate-900 text-white hover:bg-slate-800"
              >
                Вставить
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
