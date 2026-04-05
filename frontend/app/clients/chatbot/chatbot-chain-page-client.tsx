'use client';

import { useEffect, useMemo, useState } from 'react';
import ChainEditor from '@/components/chain-editor';
import { Badge } from '@/components/ui/badge';
import { chainsApi, type ChainGraph, type ChainNodeType } from '@/lib/api/chains';

const NODE_TYPE_LABELS: Record<ChainNodeType, string> = {
  start: 'Старт',
  text: 'Сообщение',
  photo: 'Фото',
  buttons: 'Кнопки',
  router: 'Условие',
  timer: 'Задержка',
  booking: 'Бронирование',
  ai_assistant: 'ИИ чат',
  product_list: 'Продукты',
};

export default function ChatbotChainPageClient({ chainId }: { chainId: number }) {
  const [graph, setGraph] = useState<ChainGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadGraph = async () => {
      setLoading(true);
      setError(null);
      try {
        const nextGraph = await chainsApi.forChain(chainId).getGraph();
        if (!isActive) return;
        setGraph(nextGraph);
      } catch (loadError) {
        if (!isActive) return;
        console.error('Failed to load chain graph', loadError);
        setError('Не удалось загрузить цепочку.');
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadGraph();

    return () => {
      isActive = false;
    };
  }, [chainId]);

  const nodeBreakdown = useMemo(() => {
    if (!graph) return [] as Array<{ type: ChainNodeType; label: string; count: number }>;

    const counts = new Map<ChainNodeType, number>();
    graph.nodes.forEach((node) => {
      counts.set(node.node_type, (counts.get(node.node_type) ?? 0) + 1);
    });

    return [...counts.entries()]
      .map(([type, count]) => ({
        type,
        count,
        label: NODE_TYPE_LABELS[type],
      }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
  }, [graph]);

  return (
    <>
      <div className="space-y-4 md:hidden" data-testid="chatbot-mobile-summary">
        <div className="rounded-2xl border bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">
            {graph?.chain.name || `Цепочка #${chainId}`}
          </div>
          <div className="mt-1 text-sm text-slate-600">
            {graph?.chain.description?.trim() || 'Для телефона показываем краткую сводку по цепочке без canvas-редактора.'}
          </div>
          {error ? <div className="mt-3 text-sm text-red-500">{error}</div> : null}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border bg-white p-4">
            <div className="text-xs text-slate-500">Статус</div>
            <div className="mt-2">
              <Badge variant="secondary">{graph?.chain.status || '—'}</Badge>
            </div>
          </div>
          <div className="rounded-2xl border bg-white p-4">
            <div className="text-xs text-slate-500">Блоков</div>
            <div className="mt-2 text-2xl font-semibold text-slate-900">{graph?.nodes.length ?? '—'}</div>
          </div>
          <div className="rounded-2xl border bg-white p-4">
            <div className="text-xs text-slate-500">Связей</div>
            <div className="mt-2 text-2xl font-semibold text-slate-900">{graph?.edges.length ?? '—'}</div>
          </div>
        </div>

        <div className="rounded-2xl border bg-white p-4">
          <div className="text-sm font-semibold text-slate-900">Структура цепочки</div>
          <div className="mt-3 space-y-2">
            {loading ? (
              <div className="text-sm text-slate-500">Загрузка структуры...</div>
            ) : nodeBreakdown.length === 0 ? (
              <div className="text-sm text-slate-500">В цепочке пока нет блоков.</div>
            ) : (
              nodeBreakdown.map((item) => (
                <div key={item.type} className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2">
                  <span className="text-sm text-slate-700">{item.label}</span>
                  <span className="text-sm font-semibold text-slate-900">{item.count}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-2xl border bg-slate-900 p-4 text-white">
          <div className="text-sm font-semibold">Полный редактор</div>
          <div className="mt-1 text-sm text-slate-200">
            Canvas-редактор оставлен для планшета и десктопа. На телефоне доступна только сводка.
          </div>
        </div>
      </div>

      <div className="hidden rounded-2xl bg-white p-4 md:block md:h-[75vh]">
        <ChainEditor className="h-full" chainId={chainId} />
      </div>
    </>
  );
}
