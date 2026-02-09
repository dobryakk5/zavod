// components/Editor/extensions/PageLinkComponent.tsx
// React компонент для рендеринга ссылок на страницы

'use client';

import { NodeViewWrapper } from '@tiptap/react';
import { useRouter } from 'next/navigation';
import { FileText } from 'lucide-react';

interface PageLinkComponentProps {
  node: {
    attrs: {
      pageId: number;
      pageTitle: string;
      pageIcon: string;
    };
  };
  updateAttributes: (attributes: Record<string, any>) => void;
  deleteNode: () => void;
}

export default function PageLinkComponent({
  node,
  updateAttributes,
  deleteNode,
}: PageLinkComponentProps) {
  const router = useRouter();
  const { pageId, pageTitle, pageIcon } = node.attrs;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (pageId) {
      router.push(`/kb/${pageId}`);
    }
  };

  return (
    <NodeViewWrapper
      as="span"
      className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded cursor-pointer transition-colors"
      onClick={handleClick}
    >
      <span className="text-sm">{pageIcon || '📄'}</span>
      <span className="text-sm font-medium text-blue-700">
        {pageTitle || 'Untitled'}
      </span>
      <FileText className="w-3 h-3 text-blue-500" />
    </NodeViewWrapper>
  );
}
