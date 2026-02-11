'use client';

import TipTapEditor from '@/components/kb/TipTapEditor';
import type { KbDocumentDetail } from '@/lib/types';

interface SharedDocumentClientProps {
  document: KbDocumentDetail;
}

export default function SharedDocumentClient({ document }: SharedDocumentClientProps) {
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
