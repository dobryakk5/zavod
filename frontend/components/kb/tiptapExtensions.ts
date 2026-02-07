import type { AnyExtension } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Placeholder from '@tiptap/extension-placeholder';
import Typography from '@tiptap/extension-typography';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Image from '@tiptap/extension-image';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import Highlight from '@tiptap/extension-highlight';
import Blockquote from '@tiptap/extension-blockquote';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { common, createLowlight } from 'lowlight';

type CreateKbExtensionsOptions = {
  placeholder?: string;
  includePlaceholder?: boolean;
};

const lowlight = createLowlight(common);

export const createKbExtensions = ({
  placeholder = 'Начните писать...',
  includePlaceholder = false,
}: CreateKbExtensionsOptions = {}): AnyExtension[] => {
  const extensions: AnyExtension[] = [
    StarterKit.configure({
      heading: {
        levels: [1, 2, 3, 4],
      },
      codeBlock: false,
      blockquote: false,
      bulletList: true,
      orderedList: true,
    }),
    Link.configure({
      openOnClick: false,
      autolink: false,
      linkOnPaste: false,
      HTMLAttributes: {
        class: 'text-blue-600 underline hover:text-blue-800 cursor-pointer',
      },
    }),
    Image.configure({
      HTMLAttributes: {
        class: 'max-w-full h-auto rounded-lg',
      },
    }),
    Table.configure({
      resizable: true,
      HTMLAttributes: {
        class: 'border-collapse table-auto w-full my-4',
      },
    }),
    TableRow,
    TableHeader.configure({
      HTMLAttributes: {
        class: 'border border-gray-300 bg-gray-100 px-4 py-2 font-semibold text-left',
      },
    }),
    TableCell.configure({
      HTMLAttributes: {
        class: 'border border-gray-300 px-4 py-2',
      },
    }),
    Typography,
    Underline,
    TextAlign.configure({
      types: ['heading', 'paragraph'],
    }),
    TaskList.configure({
      HTMLAttributes: {
        class: 'not-prose',
      },
    }),
    TaskItem.configure({
      nested: true,
      HTMLAttributes: {
        class: 'flex items-start gap-2',
      },
    }),
    Highlight.configure({
      multicolor: true,
    }),
    Blockquote,
    CodeBlockLowlight.configure({
      lowlight,
      HTMLAttributes: {
        class: 'bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto',
      },
    }),
  ];

  if (includePlaceholder) {
    extensions.push(
      Placeholder.configure({
        placeholder,
      })
    );
  }

  return extensions;
};
