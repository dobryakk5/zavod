'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { chainsApi, type ChainCatalogItem } from '@/lib/api/chains';

export default function ChatbotPageClient() {
  const [chatbotChains, setChatbotChains] = useState<ChainCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadChatbotChains = async () => {
      setLoading(true);
      setError(null);
      try {
        const items = await chainsApi.list();
        if (!isActive) return;
        setChatbotChains(items);
      } catch (loadError) {
        if (!isActive) return;
        console.error('Failed to load chatbot chains', loadError);
        setError('Не удалось загрузить список цепочек.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadChatbotChains();

    return () => {
      isActive = false;
    };
  }, []);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Загрузка цепочек...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (chatbotChains.length === 0) {
    return <p className="text-sm text-muted-foreground">Цепочки пока не найдены.</p>;
  }

  return (
    <div className="space-y-3 rounded-lg bg-white p-6">
      {chatbotChains.map((chain) => (
        <Link
          key={chain.id}
          href={`/clients/chatbot/${chain.id}`}
          className="block rounded-lg border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50"
        >
          <div className="font-medium text-slate-900">{chain.title}</div>
          <div className="mt-1 text-xs text-slate-500">
            ID: {chain.id} · Статус: {chain.status}
          </div>
        </Link>
      ))}
    </div>
  );
}
