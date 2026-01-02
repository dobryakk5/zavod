'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { MindMap, type MindMapEdgeDatum, type MindMapNodeDatum } from '@/components/mind-map';
import type { MindNodeData } from '@/components/mind-map-node';
import { mindMapsApi } from '@/lib/api/mindmaps';
import type { MindEdge, MindMapDetail, MindNode } from '@/lib/types';

const formatDateTime = (iso?: string) =>
  iso ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso)) : '—';

const fallbackPosition = (index: number) => ({
  x: 140 + (index % 4) * 160,
  y: 140 + Math.floor(index / 4) * 140
});

const toGraphNodes = (nodes: MindNode[], onEdit?: (nodeId: string) => void): MindMapNodeDatum[] =>
  nodes.map((node, index) => ({
    id: String(node.id),
    x: node.position?.x ?? fallbackPosition(index).x,
    y: node.position?.y ?? fallbackPosition(index).y,
    data: {
      title: node.text,
      typeLabel: typeof node.meta?.metric_type === 'string' ? (node.meta.metric_type as string) : undefined,
      properties: node.properties,
      color: node.color ?? null,
      meta: node.meta ?? {},
      onEdit
    } satisfies MindNodeData
  }));

const toGraphEdges = (edges: MindEdge[]): MindMapEdgeDatum[] =>
  edges.map((edge) => ({
    id: String(edge.id ?? `${edge.from_node_id}-${edge.to_node_id}`),
    source: String(edge.from_node_id),
    target: String(edge.to_node_id),
    label: edge.label ?? undefined,
    meta: edge.meta ?? undefined,
    sourceSide:
      edge.meta?.source_side === 'top' || edge.meta?.source_side === 'right' || edge.meta?.source_side === 'bottom' || edge.meta?.source_side === 'left'
        ? edge.meta.source_side
        : undefined,
    targetSide:
      edge.meta?.target_side === 'top' || edge.meta?.target_side === 'right' || edge.meta?.target_side === 'bottom' || edge.meta?.target_side === 'left'
        ? edge.meta.target_side
        : undefined
  }));

export default function MindMapPage() {
  const { mapId } = useParams<{ mapId: string }>();
  const router = useRouter();
  const [data, setData] = useState<MindMapDetail | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const graphNodes = useMemo(() => toGraphNodes(data?.nodes ?? []), [data?.nodes]);
  const graphEdges = useMemo(() => toGraphEdges(data?.edges ?? []), [data?.edges]);
  const handleEditNode = useCallback((nodeId: string) => router.push(`/map/${mapId}/node/${nodeId}`), [router, mapId]);

  const loadData = useCallback(async () => {
    if (!mapId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await mindMapsApi.detail(mapId);
      setData(detail);
      setLastSavedAt(detail.updated_at ?? null);
    } catch (err) {
      console.error('Failed to load mind map', err);
      setError('Не удалось загрузить карту. Проверьте API /map/mind-maps/:id/.');
    } finally {
      setLoading(false);
    }
  }, [mapId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hasData = !!data && !loading && !error;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <Button asChild variant="ghost" size="sm" className="px-2">
            <Link href={data?.type === 'website' ? '/analytics' : '/products'} className="inline-flex items-center gap-2">
              <ArrowLeft className="h-4 w-4" />
              К списку
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading || !mapId}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        {hasData && data && (
          <div className="flex w-full flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div className="w-full space-y-2">
              <h1 className="text-2xl font-bold">{data.title}</h1>
              <div className="grid w-full gap-1 sm:grid-cols-[1fr_auto] sm:items-baseline">
                <p className="text-muted-foreground italic">{data.description}</p>
                <span className="justify-self-end whitespace-nowrap text-sm text-muted-foreground">
                  Обновлено: {formatDateTime(lastSavedAt ?? data.updated_at)}
                </span>
              </div>
            </div>
          </div>
        )}

        {loading && <div className="text-sm text-muted-foreground">Загрузка карты…</div>}
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        {!loading && !error && !data && <div className="text-sm text-muted-foreground">Карта не найдена.</div>}
      </div>

      <MindMap
        initialNodes={graphNodes}
        initialEdges={graphEdges}
        mapId={mapId}
        mode={data?.type === 'product' ? 'product' : 'generic'}
        onEditNode={handleEditNode}
        onOpenProduct={(productId) => router.push(`/product/${productId}`)}
        onSaved={() => setLastSavedAt(new Date().toISOString())}
      />
    </div>
  );
}
