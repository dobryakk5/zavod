import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import PageLinkComponent from './PageLinkComponent';

type PageLinkAttrs = {
  id?: number | null;
  title?: string | null;
  icon?: string | null;
};

const getAttrNumber = (value: string | null) => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
};

const PageLink = Node.create({
  name: 'pageLink',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,

  addAttributes() {
    return {
      id: {
        default: null,
        parseHTML: (element: HTMLElement) => getAttrNumber(element.getAttribute('data-page-id')),
      },
      title: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('data-page-title'),
      },
      icon: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('data-page-icon'),
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'a[data-page-id]',
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    const attrs = node.attrs as PageLinkAttrs;
    const id = attrs.id ?? '';
    const title = attrs.title?.trim() || 'Страница';
    const icon = attrs.icon || '📄';
    const href = id ? `/kb/${id}` : '#';

    return [
      'a',
      mergeAttributes(HTMLAttributes, {
        href,
        'data-page-id': id,
        'data-page-title': title,
        'data-page-icon': icon,
        class: 'kb-page-link',
      }),
      `${icon} ${title}`,
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(PageLinkComponent);
  },
});

export default PageLink;
