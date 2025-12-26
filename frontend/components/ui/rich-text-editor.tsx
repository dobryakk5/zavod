'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { Bold, Heading1, Heading2, Italic, List, Redo, Undo } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { sanitizeRichText } from '@/lib/sanitize-html';

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function RichTextEditor({
  value,
  onChange,
  placeholder = 'Введите текст',
  disabled = false,
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const safeValue = sanitizeRichText(value || '');

  useEffect(() => {
    if (!editorRef.current) return;
    if (editorRef.current.innerHTML !== safeValue) {
      editorRef.current.innerHTML = safeValue;
    }
  }, [safeValue]);

  useEffect(() => {
    if (value && safeValue !== value) {
      onChange(safeValue);
    }
  }, [onChange, safeValue, value]);

  const emitChange = () => {
    const html = editorRef.current?.innerHTML ?? '';
    const sanitized = sanitizeRichText(html);
    onChange(sanitized);
  };

  const applyCommand = (command: string, valueArg?: string) => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    document.execCommand(command, false, valueArg);
    emitChange();
  };

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center gap-1 border-b border-gray-200 bg-gray-50 px-2 py-2">
        <ToolbarButton
          label="Отменить"
          icon={<Undo className="h-4 w-4" />}
          onClick={() => applyCommand('undo')}
          disabled={disabled}
        />
        <ToolbarButton
          label="Повторить"
          icon={<Redo className="h-4 w-4" />}
          onClick={() => applyCommand('redo')}
          disabled={disabled}
        />
        <div className="mx-1 h-4 w-px bg-gray-200" />
        <ToolbarButton
          label="Жирный"
          icon={<Bold className="h-4 w-4" />}
          onClick={() => applyCommand('bold')}
          disabled={disabled}
        />
        <ToolbarButton
          label="Курсив"
          icon={<Italic className="h-4 w-4" />}
          onClick={() => applyCommand('italic')}
          disabled={disabled}
        />
        <ToolbarButton
          label="Заголовок 1"
          icon={<Heading1 className="h-4 w-4" />}
          onClick={() => applyCommand('formatBlock', '<h1>')}
          disabled={disabled}
        />
        <ToolbarButton
          label="Заголовок 2"
          icon={<Heading2 className="h-4 w-4" />}
          onClick={() => applyCommand('formatBlock', '<h2>')}
          disabled={disabled}
        />
        <ToolbarButton
          label="Список"
          icon={<List className="h-4 w-4" />}
          onClick={() => applyCommand('insertUnorderedList')}
          disabled={disabled}
        />
      </div>

      <div className="relative">
        {!safeValue && (
          <div className="pointer-events-none absolute inset-3 text-sm text-gray-400">
            {placeholder}
          </div>
        )}
        <div
          ref={editorRef}
          className={cn(
            'min-h-[240px] w-full whitespace-pre-wrap px-3 pb-4 pt-3 text-gray-900 focus:outline-none',
            'prose prose-sm max-w-none'
          )}
          contentEditable={!disabled}
          suppressContentEditableWarning
          onInput={emitChange}
          onBlur={emitChange}
        />
      </div>
    </div>
  );
}

interface ToolbarButtonProps {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

function ToolbarButton({ icon, label, onClick, disabled }: ToolbarButtonProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-8 w-9 p-0 text-gray-700"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
    >
      {icon}
    </Button>
  );
}
