'use client';

import { NodeViewWrapper } from '@tiptap/react';
import { useRouter } from 'next/navigation';

type PageLinkAttrs = {
  id?: number | null;
  title?: string | null;
  icon?: string | null;
};

type PageLinkComponentProps = {
  node: {
    attrs: PageLinkAttrs;
  };
};

export default function PageLinkComponent({ node }: PageLinkComponentProps) {
  const router = useRouter();
  const { id, title, icon } = node.attrs;
  const label = title?.trim() || 'Страница';

  const handleClick = () => {
    if (!id) return;
    router.push(`/kb/${id}`);
  };

  return (
    <NodeViewWrapper as="span" className="inline-block align-baseline" data-page-link="true">
      <button
        type="button"
        contentEditable={false}
        onClick={handleClick}
        className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-sm font-medium text-blue-700 hover:bg-blue-100 hover:text-blue-800"
        title={id ? `Открыть: ${label}` : label}
      >
        <span aria-hidden="true">{icon || '📄'}</span>
        <span className="truncate max-w-[240px]">{label}</span>
      </button>
    </NodeViewWrapper>
  );
}
