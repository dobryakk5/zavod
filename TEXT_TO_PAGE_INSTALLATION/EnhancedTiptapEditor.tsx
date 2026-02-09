// components/Editor/EnhancedTiptapEditor.tsx
// Редактор с функцией создания вложенных страниц из выделенного текста (как в Craft)

'use client';

import { useEffect, useCallback, useState } from 'react';
import { useEditor, EditorContent, BubbleMenu } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import Typography from '@tiptap/extension-typography';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Highlight from '@tiptap/extension-highlight';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { lowlight } from 'lowlight';
import { File, Loader2 } from 'lucide-react';

import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import type { KbDocument } from '@/lib/types';
import { debounce } from '@/lib/utils';
import { Button } from '@/components/ui/button';

// Кастомное расширение для ссылок на страницы
import { PageLink } from './extensions/page-link';

interface EnhancedTiptapEditorProps {
  document: KbDocument;
  onUpdate?: (content: any) => void;
  editable?: boolean;
  onPageCreated?: (newDocument: KbDocument) => void;
}

export default function EnhancedTiptapEditor({ 
  document, 
  onUpdate,
  editable = true,
  onPageCreated
}: EnhancedTiptapEditorProps) {
  const [isCreatingPage, setIsCreatingPage] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      Placeholder.configure({
        placeholder: 'Начните писать или нажмите "/" для команд...',
      }),
      Typography,
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 underline cursor-pointer',
        },
      }),
      Image.configure({
        HTMLAttributes: {
          class: 'max-w-full rounded-lg',
        },
      }),
      Table.configure({
        resizable: true,
      }),
      TableRow,
      TableHeader,
      TableCell,
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
      Highlight.configure({
        multicolor: true,
      }),
      CodeBlockLowlight.configure({
        lowlight,
      }),
      // Кастомное расширение для ссылок на страницы
      PageLink,
    ],
    content: document.content,
    editable,
    onUpdate: ({ editor }) => {
      const json = editor.getJSON();
      handleAutoSave(json);
      onUpdate?.(json);
    },
  });

  // Автосохранение с debounce
  const handleAutoSave = useCallback(
    debounce(async (content: any) => {
      try {
        await kbDocumentsApi.update(document.id, { content });
        console.log('Document auto-saved');
      } catch (error) {
        console.error('Auto-save failed:', error);
      }
    }, 2000),
    [document.id]
  );

  // Обновляем контент если документ изменился
  useEffect(() => {
    if (editor && document.content) {
      editor.commands.setContent(document.content);
    }
  }, [editor, document.content]);

  // Функция создания страницы из выделенного текста
  const handleCreatePageFromSelection = async () => {
    if (!editor) return;

    const { from, to, empty } = editor.state.selection;
    
    if (empty) {
      alert('Выделите текст для создания страницы');
      return;
    }

    // Получаем выделенный текст
    const selectedText = editor.state.doc.textBetween(from, to, ' ');
    
    if (!selectedText.trim()) {
      alert('Выделенный текст пуст');
      return;
    }

    try {
      setIsCreatingPage(true);

      // Создаем новый документ
      const newDocument = await kbDocumentsApi.create({
        title: selectedText.trim(),
        content: { type: 'doc', content: [] },
        parent_document: document.id, // Устанавливаем текущий документ как родитель
      });

      // Заменяем выделенный текст на ссылку на новую страницу
      editor
        .chain()
        .focus()
        .deleteSelection()
        .insertContent({
          type: 'pageLink',
          attrs: {
            pageId: newDocument.id,
            pageTitle: newDocument.title,
            pageIcon: newDocument.icon || '📄',
          },
        })
        .run();

      // Сохраняем изменения
      const updatedContent = editor.getJSON();
      await kbDocumentsApi.update(document.id, { content: updatedContent });

      // Уведомляем родительский компонент
      onPageCreated?.(newDocument);

      console.log('Created page from selection:', newDocument);
    } catch (error) {
      console.error('Failed to create page from selection:', error);
      alert('Не удалось создать страницу');
    } finally {
      setIsCreatingPage(false);
    }
  };

  if (!editor) {
    return <div>Loading editor...</div>;
  }

  return (
    <div className="tiptap-editor">
      {/* Bubble Menu для выделенного текста */}
      {editable && (
        <BubbleMenu
          editor={editor}
          tippyOptions={{ duration: 100 }}
          className="bg-white border border-gray-200 rounded-lg shadow-lg p-1 flex items-center gap-1"
        >
          {/* Стандартные кнопки форматирования */}
          <button
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-2 rounded hover:bg-gray-100 ${
              editor.isActive('bold') ? 'bg-gray-100' : ''
            }`}
            title="Bold"
          >
            <strong>B</strong>
          </button>
          <button
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-2 rounded hover:bg-gray-100 ${
              editor.isActive('italic') ? 'bg-gray-100' : ''
            }`}
            title="Italic"
          >
            <em>I</em>
          </button>
          <button
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-2 rounded hover:bg-gray-100 ${
              editor.isActive('underline') ? 'bg-gray-100' : ''
            }`}
            title="Underline"
          >
            <u>U</u>
          </button>

          {/* Разделитель */}
          <div className="w-px h-6 bg-gray-200 mx-1" />

          {/* Кнопка создания страницы из выделенного текста */}
          <button
            onClick={handleCreatePageFromSelection}
            disabled={isCreatingPage}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded hover:bg-blue-50 text-blue-600 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            title="Создать страницу из выделенного текста"
          >
            {isCreatingPage ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <File className="w-4 h-4" />
            )}
            Создать страницу
          </button>
        </BubbleMenu>
      )}

      {/* Toolbar */}
      {editable && <EditorToolbar editor={editor} />}
      
      {/* Editor Content */}
      <EditorContent 
        editor={editor} 
        className="prose prose-lg max-w-none p-8 focus:outline-none"
      />
    </div>
  );
}

// ========== TOOLBAR COMPONENT ==========
interface EditorToolbarProps {
  editor: any;
}

function EditorToolbar({ editor }: EditorToolbarProps) {
  if (!editor) return null;

  const buttons = [
    {
      icon: 'B',
      label: 'Bold',
      action: () => editor.chain().focus().toggleBold().run(),
      isActive: editor.isActive('bold'),
    },
    {
      icon: 'I',
      label: 'Italic',
      action: () => editor.chain().focus().toggleItalic().run(),
      isActive: editor.isActive('italic'),
    },
    {
      icon: 'U',
      label: 'Underline',
      action: () => editor.chain().focus().toggleUnderline().run(),
      isActive: editor.isActive('underline'),
    },
    {
      icon: 'S',
      label: 'Strike',
      action: () => editor.chain().focus().toggleStrike().run(),
      isActive: editor.isActive('strike'),
    },
    {
      icon: 'H1',
      label: 'Heading 1',
      action: () => editor.chain().focus().toggleHeading({ level: 1 }).run(),
      isActive: editor.isActive('heading', { level: 1 }),
    },
    {
      icon: 'H2',
      label: 'Heading 2',
      action: () => editor.chain().focus().toggleHeading({ level: 2 }).run(),
      isActive: editor.isActive('heading', { level: 2 }),
    },
    {
      icon: 'H3',
      label: 'Heading 3',
      action: () => editor.chain().focus().toggleHeading({ level: 3 }).run(),
      isActive: editor.isActive('heading', { level: 3 }),
    },
    {
      icon: '•',
      label: 'Bullet List',
      action: () => editor.chain().focus().toggleBulletList().run(),
      isActive: editor.isActive('bulletList'),
    },
    {
      icon: '1.',
      label: 'Ordered List',
      action: () => editor.chain().focus().toggleOrderedList().run(),
      isActive: editor.isActive('orderedList'),
    },
    {
      icon: '☑',
      label: 'Task List',
      action: () => editor.chain().focus().toggleTaskList().run(),
      isActive: editor.isActive('taskList'),
    },
    {
      icon: '""',
      label: 'Blockquote',
      action: () => editor.chain().focus().toggleBlockquote().run(),
      isActive: editor.isActive('blockquote'),
    },
    {
      icon: '</>',
      label: 'Code Block',
      action: () => editor.chain().focus().toggleCodeBlock().run(),
      isActive: editor.isActive('codeBlock'),
    },
    {
      icon: '🔗',
      label: 'Link',
      action: () => {
        const url = window.prompt('Enter URL:');
        if (url) {
          editor.chain().focus().setLink({ href: url }).run();
        }
      },
      isActive: editor.isActive('link'),
    },
    {
      icon: '🖼',
      label: 'Image',
      action: () => {
        const url = window.prompt('Enter image URL:');
        if (url) {
          editor.chain().focus().setImage({ src: url }).run();
        }
      },
      isActive: false,
    },
  ];

  return (
    <div className="flex flex-wrap gap-1 p-2 border-b border-gray-200 bg-gray-50 sticky top-0 z-10">
      {buttons.map((button, index) => (
        <button
          key={index}
          onClick={button.action}
          className={`
            px-3 py-1.5 rounded text-sm font-medium transition-colors
            ${button.isActive 
              ? 'bg-blue-600 text-white' 
              : 'bg-white text-gray-700 hover:bg-gray-100'
            }
            border border-gray-300
          `}
          title={button.label}
        >
          {button.icon}
        </button>
      ))}
      
      <div className="flex-1" />
      
      {/* Additional actions */}
      <button
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        className="px-3 py-1.5 rounded text-sm bg-white border border-gray-300 disabled:opacity-50"
        title="Undo"
      >
        ↶
      </button>
      <button
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        className="px-3 py-1.5 rounded text-sm bg-white border border-gray-300 disabled:opacity-50"
        title="Redo"
      >
        ↷
      </button>
    </div>
  );
}
