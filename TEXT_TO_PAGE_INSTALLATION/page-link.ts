// components/Editor/extensions/page-link.ts
// Кастомное расширение Tiptap для ссылок на вложенные страницы

import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import PageLinkComponent from './PageLinkComponent';

export interface PageLinkOptions {
  HTMLAttributes: Record<string, any>;
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    pageLink: {
      /**
       * Set a page link
       */
      setPageLink: (attributes: { pageId: number; pageTitle: string; pageIcon?: string }) => ReturnType;
    };
  }
}

export const PageLink = Node.create<PageLinkOptions>({
  name: 'pageLink',

  group: 'inline',

  inline: true,

  atom: true,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      pageId: {
        default: null,
        parseHTML: element => element.getAttribute('data-page-id'),
        renderHTML: attributes => {
          if (!attributes.pageId) {
            return {};
          }
          return {
            'data-page-id': attributes.pageId,
          };
        },
      },
      pageTitle: {
        default: '',
        parseHTML: element => element.getAttribute('data-page-title'),
        renderHTML: attributes => {
          if (!attributes.pageTitle) {
            return {};
          }
          return {
            'data-page-title': attributes.pageTitle,
          };
        },
      },
      pageIcon: {
        default: '📄',
        parseHTML: element => element.getAttribute('data-page-icon'),
        renderHTML: attributes => {
          return {
            'data-page-icon': attributes.pageIcon || '📄',
          };
        },
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-type="page-link"]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(
        this.options.HTMLAttributes,
        HTMLAttributes,
        { 'data-type': 'page-link' }
      ),
      0,
    ];
  },

  addNodeView() {
    return ReactNodeViewRenderer(PageLinkComponent);
  },

  addCommands() {
    return {
      setPageLink:
        attributes =>
        ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: attributes,
          });
        },
    };
  },
});
