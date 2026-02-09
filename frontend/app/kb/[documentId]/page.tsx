'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import TipTapEditor from '@/components/kb/TipTapEditor';
import ShareButton from '@/components/kb/ShareButton';
import ExportButton from '@/components/kb/ExportButton';
import CommentsPanel from '@/components/kb/CommentsPanel';
import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentDetail } from '@/lib/types';

export default function DocumentPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = Number(params.documentId as string);

  const [document, setDocument] = useState<KbDocumentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showComments, setShowComments] = useState(false);

  useEffect(() => {
    void loadDocument();
  }, [documentId]);

  const loadDocument = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await kbDocumentsApi.get(documentId);
      setDocument(data);
    } catch (err: any) {
      console.error('Error loading document:', err);
      setError(err?.message || 'Ошибка загрузки документа');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTitleChange = async (newTitle: string) => {
    if (!document) return;

    try {
      await kbDocumentsApi.update(documentId, { title: newTitle });
      setDocument({ ...document, title: newTitle });
    } catch (err) {
      console.error('Error updating title:', err);
    }
  };

  const handleIconChange = async () => {
    if (!document) return;

    const newIcon = window.prompt('Введите emoji иконку:', document.icon || '📄');
    if (newIcon === null) return;

    try {
      await kbDocumentsApi.update(documentId, { icon: newIcon });
      setDocument({ ...document, icon: newIcon });
    } catch (err) {
      console.error('Error updating icon:', err);
    }
  };

  const handleArchive = async () => {
    if (!confirm('Архивировать этот документ?')) return;

    try {
      await kbDocumentsApi.archive(documentId);
      router.push('/settings?tab=kb');
    } catch (err) {
      console.error('Error archiving document:', err);
      alert('Ошибка архивирования');
    }
  };

  const handleDuplicate = async () => {
    try {
      const created = await kbDocumentsApi.duplicate(documentId, {
        title: `${document?.title ?? ''} (копия)`,
        include_children: false,
      });
      router.push(`/kb/${created.id}`);
    } catch (err) {
      console.error('Error duplicating document:', err);
      alert('Ошибка дублирования');
    }
  };

  const handlePageCreated = (newPage: KbDocumentDetail) => {
    setDocument((prev) => {
      if (!prev) return prev;
      const existing = prev.child_documents ?? [];
      if (existing.some((child) => child.id === newPage.id)) {
        return prev;
      }
      return {
        ...prev,
        child_documents: [newPage, ...existing],
      };
    });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Загрузка документа...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={loadDocument}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Попробовать снова
          </button>
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Документ не найден</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/settings?tab=kb')}
              className="p-2 hover:bg-gray-100 rounded-lg"
              title="Назад к базе знаний"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            <div className="flex items-center gap-2">
              <button
                onClick={handleIconChange}
                className="text-2xl hover:bg-gray-100 p-1 rounded"
                title="Изменить иконку"
              >
                {document.icon || '📄'}
              </button>

              <input
                type="text"
                value={document.title}
                onChange={(e) => setDocument({ ...document, title: e.target.value })}
                onBlur={(e) => handleTitleChange(e.target.value)}
                className="text-xl font-semibold bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2 py-1"
                placeholder="Название документа"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowComments(!showComments)}
              className={`p-2 rounded-lg ${showComments ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-100'}`}
              title="Комментарии"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
                />
              </svg>
            </button>

            <ExportButton documentId={documentId} documentTitle={document.title} />
            <ShareButton documentId={documentId} />

            <div className="relative group">
              <button className="p-2 hover:bg-gray-100 rounded-lg">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
                  />
                </svg>
              </button>

              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-2 hidden group-hover:block">
                <button
                  onClick={handleDuplicate}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Дублировать
                </button>

                <button
                  onClick={handleArchive}
                  className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-2 text-red-600"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Архивировать
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto flex gap-4 p-6">
        <div className={`flex-1 ${showComments ? 'w-2/3' : 'w-full'}`}>
          <TipTapEditor
            documentId={documentId}
            initialContent={document.content}
            autoSave
            autoSaveInterval={3000}
            onPageCreated={handlePageCreated}
          />
        </div>

        {showComments && (
          <div className="w-80 flex-shrink-0">
            <CommentsPanel documentId={documentId} />
          </div>
        )}
      </div>

      <div className="max-w-6xl mx-auto px-6 pb-10">
        <div className="rounded-lg border bg-white">
          <div className="border-b px-4 py-3 text-sm text-gray-500">Вложенные страницы</div>
          <div className="divide-y">
            {(document.child_documents ?? []).map((child) => (
              <button
                key={child.id}
                onClick={() => router.push(`/kb/${child.id}`)}
                className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3"
              >
                <div className="text-lg">{child.icon || '📄'}</div>
                <div>
                  <div className="font-medium text-gray-900">{child.title}</div>
                  <div className="text-xs text-gray-500">
                    Обновлен: {new Date(child.updated_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>
              </button>
            ))}
            {(document.child_documents ?? []).length === 0 && (
              <div className="px-4 py-6 text-sm text-gray-500">
                Пока нет вложенных страниц. Выделите текст в документе и нажмите «Создать страницу».
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
