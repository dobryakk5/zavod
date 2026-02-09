'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentList } from '@/lib/types';
import { Button } from '@/components/ui/button';

export function KnowledgeBaseTab() {
  const router = useRouter();
  const [documents, setDocuments] = useState<KbDocumentList[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const loadDocuments = async () => {
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
  };

  useEffect(() => {
    void loadDocuments();
  }, [showArchived]);

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

  const documentsCount = useMemo(() => documents.length, [documents]);

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
          <div className="flex items-center justify-between border-b px-4 py-3 text-sm text-muted-foreground">
            <span>Всего: {documentsCount}</span>
          </div>
          <div className="divide-y">
            {documents.map((doc) => (
              <div key={doc.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="text-lg">{doc.icon || '📄'}</div>
                  <div>
                    <div className="flex items-center gap-2">
                      <button
                        className="text-left font-medium text-gray-900 hover:underline"
                        onClick={() => router.push(`/kb/${doc.id}`)}
                      >
                        {doc.title}
                      </button>
                      {doc.has_children && (
                        <span className="text-gray-400 text-sm" title="Есть вложенные страницы">
                          &gt;
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => handleCreateChild(doc.id)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded border border-gray-200 text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                        title="Создать вложенную страницу"
                        aria-label={`Создать вложенную страницу для ${doc.title}`}
                      >
                        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14m7-7H5" />
                        </svg>
                      </button>
                    </div>
                    <div className="text-xs text-gray-500">
                      Обновлен: {new Date(doc.updated_at).toLocaleDateString('ru-RU')}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => router.push(`/kb/${doc.id}`)}>
                    Открыть
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleArchive(doc)}
                    className={doc.is_archived ? 'text-green-600' : 'text-red-600'}
                  >
                    {doc.is_archived ? 'Восстановить' : 'Архивировать'}
                  </Button>
                </div>
              </div>
            ))}
            {documents.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Пока нет документов
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
