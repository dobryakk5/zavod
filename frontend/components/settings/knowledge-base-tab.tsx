'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentList } from '@/lib/types';
import { Button } from '@/components/ui/button';

// ─── Tree builder ─────────────────────────────────────────────────────────────

interface TreeNode extends KbDocumentList {
  children: TreeNode[];
}

function buildTree(docs: KbDocumentList[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  const roots: TreeNode[] = [];

  for (const doc of docs) {
    map.set(doc.id, { ...doc, children: [] });
  }

  for (const node of map.values()) {
    const parentId = (node as any).parent_document as number | null | undefined;
    if (parentId && map.has(parentId)) {
      map.get(parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

// ─── Tree node component ──────────────────────────────────────────────────────

interface TreeNodeRowProps {
  node: TreeNode;
  depth: number;
  onCreateChild: (parentId: number) => void;
  onArchive: (doc: KbDocumentList) => void;
  onOpen: (id: number) => void;
}

function TreeNodeRow({ node, depth, onCreateChild, onArchive, onOpen }: TreeNodeRowProps) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = node.children.length > 0;

  return (
    <>
      <div
        className="grid items-center gap-3 px-4 py-3 hover:bg-gray-50"
        style={{
          paddingLeft: `${16 + depth * 20}px`,
          gridTemplateColumns: '1fr max-content max-content',
        }}
      >
        {/* Col 1: expand toggle + icon + title */}
        <div className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            className="flex h-5 w-5 shrink-0 items-center justify-center text-gray-400 hover:text-gray-700 transition-transform"
            style={{
              visibility: hasChildren ? 'visible' : 'hidden',
              transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)',
            }}
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Свернуть' : 'Развернуть'}
          >
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M9 5l7 7-7 7" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <div className="text-lg leading-none">{node.icon || '📄'}</div>

          <div className="flex min-w-0 items-center gap-1.5">
            <button
              className="truncate text-left font-medium text-gray-900 hover:underline"
              onClick={() => onOpen(node.id)}
            >
              {node.title}
            </button>

            <button
              type="button"
              onClick={() => onCreateChild(node.id)}
              className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded border border-gray-200 text-gray-400 opacity-0 hover:bg-gray-100 hover:text-gray-700 transition-opacity [.grid:hover_&]:opacity-100"
              title="Создать вложенную страницу"
              aria-label={`Создать вложенную страницу для ${node.title}`}
            >
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 5v14m7-7H5" />
              </svg>
            </button>
          </div>
        </div>

        {/* Col 2: date */}
        <div className="whitespace-nowrap text-sm text-gray-400">
          {new Date(node.updated_at).toLocaleDateString('ru-RU')}
        </div>

        {/* Col 3: actions */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpen(node.id)}>
            Открыть
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onArchive(node)}
            className={node.is_archived ? 'text-green-600' : 'text-red-600'}
          >
            {node.is_archived ? 'Восстановить' : 'Архивировать'}
          </Button>
        </div>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div className="relative">
          <div
            className="absolute top-0 bottom-0 w-px bg-gray-200"
            style={{ left: `${16 + depth * 20 + 10}px` }}
          />
          {node.children.map((child) => (
            <TreeNodeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              onCreateChild={onCreateChild}
              onArchive={onArchive}
              onOpen={onOpen}
            />
          ))}
        </div>
      )}
    </>
  );
}

// ─── Main tab ─────────────────────────────────────────────────────────────────

export function KnowledgeBaseTab() {
  const router = useRouter();
  const [documents, setDocuments] = useState<KbDocumentList[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const loadDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await kbDocumentsApi.list({ archived: showArchived });
      setDocuments(data);
    } catch (err: any) {
      console.error('Failed to load kb documents', err);
      setError(err?.message || 'Не удалось загрузить документы');
    } finally {
      setIsLoading(false);
    }
  }, [showArchived]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const handleCreate = async () => {
    try {
      const created = await kbDocumentsApi.create({
        title: 'Новый документ',
        content: { type: 'doc', content: [] },
      });
      router.push(`/kb/${created.id}`);
    } catch (err) {
      console.error('Failed to create document', err);
      alert('Ошибка создания документа');
    }
  };

  const handleCreateChild = async (parentId: number) => {
    try {
      const created = await kbDocumentsApi.create({
        title: 'Новая страница',
        content: { type: 'doc', content: [] },
        parent_document: parentId,
      });
      router.push(`/kb/${created.id}`);
    } catch (err) {
      console.error('Failed to create child document', err);
      alert('Ошибка создания вложенной страницы');
    }
  };

  const handleArchive = async (doc: KbDocumentList) => {
    try {
      if (doc.is_archived) {
        await kbDocumentsApi.restore(doc.id);
      } else {
        await kbDocumentsApi.archive(doc.id);
      }
      await loadDocuments();
    } catch (err) {
      console.error('Failed to update archive state', err);
    }
  };

  const tree = useMemo(() => buildTree(documents), [documents]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">База знаний</h2>
          <p className="text-sm text-muted-foreground">Документы проекта, заметки и инструкции.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
            />
            Архив
          </label>
          <Button onClick={handleCreate}>Новый документ</Button>
        </div>
      </div>

      {isLoading && <div className="text-sm text-muted-foreground">Загрузка документов...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {!isLoading && !error && (
        <div className="rounded-lg border bg-white">
          {/* Table header */}
          <div
            className="grid border-b px-4 py-2 text-xs font-medium uppercase tracking-wide text-gray-400"
            style={{ gridTemplateColumns: '1fr max-content max-content' }}
          >
            <span>Название</span>
            <span>Обновлён</span>
            <span className="sr-only">Действия</span>
          </div>

          <div className="divide-y">
            {tree.length > 0 ? (
              tree.map((node) => (
                <TreeNodeRow
                  key={node.id}
                  node={node}
                  depth={0}
                  onCreateChild={handleCreateChild}
                  onArchive={handleArchive}
                  onOpen={(id) => router.push(`/kb/${id}`)}
                />
              ))
            ) : (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Пока нет документов
              </div>
            )}
          </div>

          <div className="border-t px-4 py-2 text-xs text-gray-400">
            Всего: {documents.length}
          </div>
        </div>
      )}
    </div>
  );
}
