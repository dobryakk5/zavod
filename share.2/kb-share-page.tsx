'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { KnowledgeBaseTab } from '@/components/knowledge-base-tab';
import type { KbDocumentList } from '@/lib/types';

// API для публичного доступа к документам
const publicKbApi = {
  // Получить документ и все его вложенные страницы по share-токену
  getByShareToken: async (shareToken: string): Promise<KbDocumentList[]> => {
    const res = await fetch(`/api/kb/share/${shareToken}`);
    if (!res.ok) throw new Error('Документ не найден или доступ запрещён');
    return res.json();
  },

  // Получить share-ссылку для вложенной страницы
  getShareUrl: async (documentId: number): Promise<string> => {
    const res = await fetch(`/api/kb/${documentId}/share-url`);
    if (!res.ok) throw new Error('Не удалось получить ссылку');
    const data = await res.json();
    return data.shareUrl; // например: https://fibonatty.ru/kb/share/abc123...
  },
};

export default function KbSharePage() {
  const params = useParams();
  const shareToken = params?.shareToken as string;

  const [documents, setDocuments] = useState<KbDocumentList[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!shareToken) return;

    const loadSharedDocument = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const docs = await publicKbApi.getByShareToken(shareToken);
        setDocuments(docs);
      } catch (err: any) {
        console.error('Failed to load shared document', err);
        setError(err?.message || 'Не удалось загрузить документ');
      } finally {
        setIsLoading(false);
      }
    };

    void loadSharedDocument();
  }, [shareToken]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-lg">Загрузка документа...</div>
        </div>
      </div>
    );
  }

  if (error || documents.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-lg font-semibold text-red-600">
            {error || 'Документ не найден'}
          </div>
          <p className="text-sm text-gray-600">
            Проверьте правильность ссылки или обратитесь к автору документа
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-6xl px-4 py-8">
      <KnowledgeBaseTab
        shareMode={true}
        getShareUrl={publicKbApi.getShareUrl}
      />
    </div>
  );
}
