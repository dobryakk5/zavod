'use client';

import { NodeViewWrapper } from '@tiptap/react';
import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { kbSharesApi } from '@/lib/api/knowledgeBase';

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
  const params = useParams();
  const { id, title, icon } = node.attrs;
  const label = title?.trim() || 'Страница';
  const [isResolvingShare, setIsResolvingShare] = useState(false);

  const tokenParam = params?.token;
  const shareToken =
    typeof tokenParam === 'string'
      ? tokenParam
      : Array.isArray(tokenParam)
        ? tokenParam[0]
        : null;

  const handleClick = async () => {
    if (!id) return;

    // Public shared mode: resolve a public share URL for the linked page.
    if (shareToken) {
      try {
        setIsResolvingShare(true);
        const resolved = await kbSharesApi.resolveDocumentByToken(shareToken, id);
        if (resolved.share_url) {
          window.location.assign(resolved.share_url);
          return;
        }
      } catch (error) {
        console.error('Failed to resolve shared page link:', error);
      } finally {
        setIsResolvingShare(false);
      }

      // In public mode we do not fall back to a private URL.
      return;
    }

    router.push(`/kb/${id}`);
  };

  return (
    <NodeViewWrapper as="span" className="inline-block align-baseline" data-page-link="true">
      <button
        type="button"
        contentEditable={false}
        onClick={handleClick}
        disabled={isResolvingShare}
        className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-sm font-medium text-blue-700 hover:bg-blue-100 hover:text-blue-800"
        title={id ? `Открыть: ${label}` : label}
      >
        <span aria-hidden="true">{icon || '📄'}</span>
        <span className="truncate max-w-[240px]">{label}</span>
      </button>
    </NodeViewWrapper>
  );
}
