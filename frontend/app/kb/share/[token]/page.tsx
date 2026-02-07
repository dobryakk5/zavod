'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import TipTapEditor from '@/components/kb/TipTapEditor';
import { kbSharesApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentShare } from '@/lib/types';

export default function SharedDocumentPage() {
  const params = useParams();
  const token = params.token as string;

  const [share, setShare] = useState<KbDocumentShare | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadShare = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await kbSharesApi.byToken(token);
        setShare(data);
      } catch (err: any) {
        console.error('Error loading shared document:', err);
        setError('Ссылка недоступна или истекла');
      } finally {
        setIsLoading(false);
      }
    };

    void loadShare();
  }, [token]);

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

  if (error || !share?.document_detail) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">{error || 'Документ не найден'}</p>
      </div>
    );
  }

  const document = share.document_detail;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-2xl">{document.icon || '📄'}</div>
            <h1 className="text-xl font-semibold">{document.title}</h1>
          </div>
          <div className="text-sm text-gray-500">Публичный доступ</div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6">
        <TipTapEditor
          initialContent={document.content}
          editable={false}
          autoSave={false}
          showToolbar={false}
        />
      </div>
    </div>
  );
}
