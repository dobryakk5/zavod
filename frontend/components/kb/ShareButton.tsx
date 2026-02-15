'use client';

import { useCallback, useEffect, useState } from 'react';
import { kbSharesApi } from '@/lib/api/knowledgeBase';
import type { KbDocumentShare } from '@/lib/types';

interface ShareButtonProps {
  documentId: number;
}

export default function ShareButton({ documentId }: ShareButtonProps) {
  const [share, setShare] = useState<KbDocumentShare | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadExistingShare = useCallback(async () => {
    try {
      const shares = await kbSharesApi.list();
      const existingShare = shares.find((s) => s.document === documentId && s.is_active);
      if (existingShare) {
        setShare(existingShare);
      }
    } catch (error) {
      console.error('Error loading share:', error);
    }
  }, [documentId]);

  useEffect(() => {
    void loadExistingShare();
  }, [loadExistingShare]);

  const handleCreateShare = async () => {
    setIsLoading(true);
    try {
      const created = await kbSharesApi.create({
        document: documentId,
        permission: 'view',
      });
      setShare(created);
      setShowModal(true);
    } catch (error) {
      console.error('Error creating share:', error);
      alert('Ошибка создания ссылки');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeShare = async () => {
    if (!share || !confirm('Отключить публичный доступ?')) return;

    setIsLoading(true);
    try {
      await kbSharesApi.revoke(share.id);
      setShare(null);
      setShowModal(false);
    } catch (error) {
      console.error('Error revoking share:', error);
      alert('Ошибка отключения доступа');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyLink = async () => {
    if (!share) return;

    try {
      await navigator.clipboard.writeText(share.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Error copying to clipboard:', error);
    }
  };

  const handleOpenInNewTab = () => {
    if (!share) return;
    window.open(share.share_url, '_blank');
  };

  return (
    <>
      <button
        onClick={share ? () => setShowModal(true) : handleCreateShare}
        disabled={isLoading}
        className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
          share ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
        } disabled:opacity-50`}
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          />
        </svg>
        {share ? 'Общая ссылка' : 'Поделиться'}
      </button>

      {showModal && share && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-gray-900">Публичная ссылка</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="mb-6">
              <p className="text-gray-600 mb-4">Любой, у кого есть эта ссылка, сможет просмотреть этот документ.</p>

              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={share.share_url}
                  readOnly
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm"
                  onClick={(e) => e.currentTarget.select()}
                />
                <button
                  onClick={handleCopyLink}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors whitespace-nowrap"
                >
                  {copied ? (
                    <span className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Скопировано
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      Копировать
                    </span>
                  )}
                </button>
              </div>

              <div className="flex gap-2 mb-4">
                <button
                  onClick={handleOpenInNewTab}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700"
                >
                  Открыть в новой вкладке
                </button>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div className="flex gap-3">
                  <svg className="w-5 h-5 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="text-sm text-blue-800">
                    <p className="font-medium">Статистика</p>
                    <p>Просмотров: {share.visit_count}</p>
                    {share.expires_at && (
                      <p>Действует до: {new Date(share.expires_at).toLocaleDateString('ru-RU')}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t pt-4">
              <button
                onClick={handleRevokeShare}
                disabled={isLoading}
                className="w-full px-4 py-2 border border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                Отключить публичный доступ
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
