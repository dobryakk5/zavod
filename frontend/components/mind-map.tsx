'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import * as d3 from 'd3';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MindMapNode as MindMapNodeCard, type MindNodeData } from '@/components/mind-map-node';
import { NodeContextMenu, formatNodeClipboardText } from '@/components/mind-map-node-context-menu';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/utils';
import { mindMapsApi } from '@/lib/api/mindmaps';
import type { MindNode, MindNodeProperty } from '@/lib/types';

export type MindMapNodeDatum = {
  id: string;
  x: number;
  y: number;
  data: MindNodeData;
};

type PortSide = 'top' | 'right' | 'bottom' | 'left';
type EdgeLineStyle = 'solid' | 'dashed' | 'dotted';
type EdgeArrow = 'forward' | 'backward' | 'both' | 'none';
type EdgeMeta = {
  source_side?: PortSide;
  target_side?: PortSide;
  line_style?: EdgeLineStyle;
  stroke_width?: number;
  arrow?: EdgeArrow;
} & Record<string, unknown>;

export type MindMapEdgeDatum = {
  id: string;
  source: string;
  target: string;
  label?: string;
  sourceSide?: PortSide;
  targetSide?: PortSide;
  meta?: EdgeMeta;
};

type MindMapNodeWithSize = MindMapNodeDatum & { width: number; height: number };

type Point = { x: number; y: number };

const sideDir = (side: PortSide): Point => {
  switch (side) {
    case 'top':
      return { x: 0, y: -1 };
    case 'bottom':
      return { x: 0, y: 1 };
    case 'left':
      return { x: -1, y: 0 };
    case 'right':
      return { x: 1, y: 0 };
  }
};

const oppositeSide = (side: PortSide): PortSide => {
  switch (side) {
    case 'top':
      return 'bottom';
    case 'bottom':
      return 'top';
    case 'left':
      return 'right';
    case 'right':
      return 'left';
  }
};

const inferSideBetweenPoints = (from: Point, to: Point): PortSide => {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? 'right' : 'left';
  return dy >= 0 ? 'bottom' : 'top';
};

const bezierLink = (a: Point, aSide: PortSide, b: Point, bSide: PortSide) => {
  const MAX_OFFSET = 80;
  const distance = Math.hypot(b.x - a.x, b.y - a.y);
  const offset = Math.min(MAX_OFFSET, distance * 0.5);

  const da = sideDir(aSide);
  const db = sideDir(bSide);

  const c1 = { x: a.x + da.x * offset, y: a.y + da.y * offset };
  const c2 = { x: b.x + db.x * offset, y: b.y + db.y * offset };

  return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
};

type DraggingLink =
  | {
      mode: 'create';
      sourceId: string;
      side: PortSide;
      x: number;
      y: number;
    }
  | {
      mode: 'rewire';
      edgeId: string;
      movingEnd: 'source' | 'target';
      fixedNodeId: string;
      fixedSide: PortSide;
      x: number;
      y: number;
    }
  | null;

type MindMapProps = {
  initialNodes?: MindMapNodeDatum[];
  initialEdges?: MindMapEdgeDatum[];
  mapId?: string | number;
  onEditNode?: (nodeId: string) => void;
  onSaved?: () => void;
};

const NODE_WIDTH = 320;
// Header uses `py-3` (24px) + input `h-8` (32px) + inner `border-b` (1px)
const HEADER_HEIGHT_TITLE_ONLY = 57;
// Plus `space-y-2` gap (8px) + `text-xs` line (~16px)
const HEADER_HEIGHT_WITH_TYPE = 81;
const BADGES_HEIGHT = 44;
const PROPERTIES_PADDING_Y = 24;
const PROPERTIES_ROW_GAP = 12;
const PROPERTIES_ROW_HEIGHT_TITLE_ONLY = 24;
const PROPERTIES_ROW_HEIGHT = 40;
const PROPERTIES_ROW_HEIGHT_WITH_DELTA = 60;

const toDatum = (node: MindNode, onEditNode?: (nodeId: string) => void, fallback?: { x: number; y: number }): MindMapNodeDatum => ({
  id: String(node.id),
  x: node.position?.x ?? fallback?.x ?? 140,
  y: node.position?.y ?? fallback?.y ?? 140,
  data: {
    title: node.text || 'Новый узел',
    typeLabel: typeof node.meta?.metric_type === 'string' ? (node.meta.metric_type as string) : undefined,
    properties: node.properties,
    color: node.color ?? null,
    meta: node.meta ?? {},
    onEdit: onEditNode
  }
});

const defaultNodes: MindMapNodeDatum[] = [
  {
    id: 'default-root',
    x: 300,
    y: 200,
    data: { title: 'Root node', typeLabel: 'root', properties: [] }
  }
];

const defaultEdges: MindMapEdgeDatum[] = [];

const attachHandlers = (
  nodes: MindMapNodeDatum[],
  handlers: {
    onEditNode?: (nodeId: string) => void;
    onChangeNode?: (nodeId: string, patch: { title?: string }) => void;
  }
) =>
  nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      onEdit: node.data?.onEdit ?? handlers.onEditNode,
      onChange: node.data?.onChange ?? handlers.onChangeNode
    }
  }));

const calculateNodeHeight = (node: MindMapNodeDatum) => {
  const hasType = !!node.data.typeLabel?.trim();
  const hasBadges = !!node.data.color;
  const properties = [...(node.data.properties ?? [])]
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .filter((p) => (p.title ?? '').trim() || (p.value ?? '').trim() || (p.delta ?? '').trim());
  const rows: Array<typeof properties> = [];

  for (let i = 0; i < properties.length; i += 3) rows.push(properties.slice(i, i + 3));

  let height = (hasType ? HEADER_HEIGHT_WITH_TYPE : HEADER_HEIGHT_TITLE_ONLY) + (hasBadges ? BADGES_HEIGHT : 0);

  if (rows.length > 0) {
    height += PROPERTIES_PADDING_Y;
    if (rows.length > 1) height += (rows.length - 1) * PROPERTIES_ROW_GAP;
    height += rows.reduce((sum, row) => {
      const hasDelta = row.some((p) => !!p.delta?.trim());
      const hasValue = row.some((p) => !!p.value?.trim());
      const hasTitleOnly = row.some((p) => !!p.title?.trim() && !p.value?.trim() && !p.delta?.trim());
      if (hasDelta && hasValue) return sum + PROPERTIES_ROW_HEIGHT_WITH_DELTA;
      if (hasDelta || hasValue) return sum + PROPERTIES_ROW_HEIGHT;
      if (hasTitleOnly) return sum + PROPERTIES_ROW_HEIGHT_TITLE_ONLY;
      return sum + PROPERTIES_ROW_HEIGHT_TITLE_ONLY;
    }, 0);
  }

  return height;
};

export function MindMap({ initialNodes = defaultNodes, initialEdges = defaultEdges, mapId, onEditNode, onSaved }: MindMapProps) {
  const [nodes, setNodes] = useState<MindMapNodeDatum[]>(
    initialNodes.length ? attachHandlers(initialNodes, { onEditNode }) : attachHandlers(defaultNodes, { onEditNode })
  );
  const [edges, setEdges] = useState<MindMapEdgeDatum[]>(initialEdges);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [edgeMenu, setEdgeMenu] = useState<{ edgeId: string; x: number; y: number } | null>(null);
  const [edgeEditor, setEdgeEditor] = useState<{
    edgeId: string;
    x: number;
    y: number;
    label: string;
    style: EdgeLineStyle;
    strokeWidth: number;
    arrow: EdgeArrow;
  } | null>(null);
  const [nodeMenu, setNodeMenu] = useState<{ nodeId: string; x: number; y: number } | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [draggingLink, setDraggingLink] = useState<DraggingLink>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const innerRef = useRef<SVGGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const zoomTransform = useRef<d3.ZoomTransform>(d3.zoomIdentity);
  const dragOffset = useRef(new Map<string, { dx: number; dy: number }>());
  const draggingLinkRef = useRef<DraggingLink>(null);
  const tempToServerNodeIdRef = useRef(new Map<string, string>());
  const flushTimerRef = useRef<number | null>(null);
  const flushingRef = useRef(false);
  const dirtyRef = useRef(false);
  const flushChangesRef = useRef<(() => void) | null>(null);
  const pendingPositionsRef = useRef(new Map<string, { x: number; y: number }>());
  const pendingNodesRef = useRef(new Map<string, { title: string; x: number; y: number }>());
  const pendingNodeUpdatesRef = useRef(new Map<string, { text: string }>());
  const pendingEdgesRef = useRef(
    new Map<
      string,
      { id: string; source: string; target: string; sourceSide?: PortSide; targetSide?: PortSide; label?: string; meta?: EdgeMeta }
    >()
  );

  useEffect(() => {
    const nextNodes = initialNodes.length
      ? attachHandlers(initialNodes, { onEditNode })
      : attachHandlers(defaultNodes, { onEditNode });
    setNodes((prev) => {
      if (!prev.length) return nextNodes;
      const merged = [...prev];
      nextNodes.forEach((node) => {
        const idx = merged.findIndex((n) => n.id === node.id);
        if (idx >= 0) {
          merged[idx] = {
            ...merged[idx],
            ...node,
            data: {
              ...merged[idx].data,
              ...node.data,
              onEdit: node.data.onEdit ?? merged[idx].data.onEdit,
              onChange: node.data.onChange ?? merged[idx].data.onChange
            }
          };
        } else {
          merged.push(node);
        }
      });
      const hasServerData = nextNodes.length > 0;
      return merged.filter((node) => !(hasServerData && node.id === 'default-root'));
    });
  }, [initialNodes, onEditNode]);

  useEffect(() => {
    if (!onEditNode) return;
    setNodes((prev) => prev.map((node) => ({ ...node, data: { ...node.data, onEdit: node.data.onEdit ?? onEditNode } })));
  }, [onEditNode]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges]);

  const nodesWithSize = useMemo<MindMapNodeWithSize[]>(
    () => nodes.map((node) => ({ ...node, width: NODE_WIDTH, height: calculateNodeHeight(node) })),
    [nodes]
  );

  const nodesWithSizeRef = useRef(nodesWithSize);
  useEffect(() => {
    nodesWithSizeRef.current = nodesWithSize;
  }, [nodesWithSize]);

  const nodesRef = useRef(nodes);
  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  const nodeDraftsRef = useRef(new Map<string, { title: string }>());

  const edgesRef = useRef(edges);
  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  const selectedNodeIdRef = useRef<string | null>(null);
  useEffect(() => {
    selectedNodeIdRef.current = selectedNodeId;
  }, [selectedNodeId]);

  const nodeClipboardRef = useRef<{
    title: string;
    typeLabel?: string;
    color?: string | null;
    properties?: Array<{
      title?: string | null;
      value?: string | null;
      delta?: string | null;
      order_index?: number | null;
      meta?: Record<string, unknown> | null;
    }>;
  } | null>(null);

  const getPortPosition = (node: MindMapNodeWithSize, side: PortSide) => {
    switch (side) {
      case 'top':
        return { x: node.x + node.width / 2, y: node.y };
      case 'bottom':
        return { x: node.x + node.width / 2, y: node.y + node.height };
      case 'left':
        return { x: node.x, y: node.y + node.height / 2 };
      case 'right':
        return { x: node.x + node.width, y: node.y + node.height / 2 };
    }
  };

  const inferSideBetween = (from: MindMapNodeWithSize, to: MindMapNodeWithSize): PortSide => {
    const fromCx = from.x + from.width / 2;
    const fromCy = from.y + from.height / 2;
    const toCx = to.x + to.width / 2;
    const toCy = to.y + to.height / 2;
    const dx = toCx - fromCx;
    const dy = toCy - fromCy;
    if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? 'right' : 'left';
    return dy >= 0 ? 'bottom' : 'top';
  };

  const inferSideByPoint = (node: MindMapNodeWithSize, x: number, y: number): PortSide => {
    const cx = node.x + node.width / 2;
    const cy = node.y + node.height / 2;
    const dx = x - cx;
    const dy = y - cy;
    if (Math.abs(dx) > Math.abs(dy)) return dx >= 0 ? 'right' : 'left';
    return dy >= 0 ? 'bottom' : 'top';
  };

  const updateDraggingLink = useCallback((next: DraggingLink) => {
    draggingLinkRef.current = next;
    setDraggingLink(next);
  }, []);

  const scheduleFlush = useCallback(() => {
    dirtyRef.current = true;
    if (flushTimerRef.current) return;
    flushTimerRef.current = window.setTimeout(() => {
      flushTimerRef.current = null;
      flushChangesRef.current?.();
    }, 5000);
  }, []);

  const flushChanges = useCallback(async () => {
    if (flushingRef.current) return;
    if (!dirtyRef.current) return;

    const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
    if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

    flushingRef.current = true;
    dirtyRef.current = false;

    let didPersist = false;
    const positionsSnapshot = new Map(pendingPositionsRef.current);
    pendingPositionsRef.current.clear();
    const nodesSnapshot = new Map(pendingNodesRef.current);
    pendingNodesRef.current.clear();
    const nodeUpdatesSnapshot = new Map(pendingNodeUpdatesRef.current);
    pendingNodeUpdatesRef.current.clear();
    const edgesSnapshot = new Map(pendingEdgesRef.current);
    pendingEdgesRef.current.clear();

    const idMap = new Map<string, string>();

    try {
      for (const [tempId, pendingNode] of nodesSnapshot) {
        const latestPos = positionsSnapshot.get(tempId) ?? { x: pendingNode.x, y: pendingNode.y };
        positionsSnapshot.delete(tempId);

        const created = await mindMapsApi.createNode(Number(mapIdNumber), {
          map_id: Number(mapIdNumber),
          text: pendingNode.title || 'Новый узел',
          position: { x: latestPos.x, y: latestPos.y },
          meta: {}
        });
        didPersist = true;

        const serverId = String(created.id);
        idMap.set(tempId, serverId);
        nodeDraftsRef.current.set(serverId, { title: created.text ?? pendingNode.title ?? '' });
        nodeDraftsRef.current.delete(tempId);

        setNodes((prev) =>
          prev.map((n) => (n.id === tempId ? toDatum(created, onEditNode, latestPos) : n))
        );
      }

      for (const [rawNodeId, patch] of nodeUpdatesSnapshot) {
        const nodeId = idMap.get(rawNodeId) ?? tempToServerNodeIdRef.current.get(rawNodeId) ?? rawNodeId;

        if (nodesSnapshot.has(rawNodeId) || pendingNodesRef.current.has(rawNodeId) || nodesSnapshot.has(nodeId) || pendingNodesRef.current.has(nodeId)) {
          pendingNodeUpdatesRef.current.set(rawNodeId, patch);
          dirtyRef.current = true;
          continue;
        }

        try {
          const updated = await mindMapsApi.updateNode(Number(mapIdNumber), nodeId, { text: patch.text });
          didPersist = true;
          nodeDraftsRef.current.set(nodeId, { title: updated.text ?? patch.text });
          setNodes((prev) =>
            prev.map((n) =>
              n.id === rawNodeId
                ? {
                    ...n,
                    id: nodeId,
                    data: {
                      ...n.data,
                      title: updated.text ?? patch.text
                    }
                  }
                : n
            )
          );
        } catch (error) {
          console.error('Failed to persist node update', { nodeId, mapId }, error);
          pendingNodeUpdatesRef.current.set(rawNodeId, patch);
          dirtyRef.current = true;
        }
      }

      if (idMap.size) {
        setEdges((prev) =>
          prev.map((e) => ({
            ...e,
            source: idMap.get(e.source) ?? e.source,
            target: idMap.get(e.target) ?? e.target
          }))
        );
      }

      for (const [localId, edge] of edgesSnapshot) {
        const source = idMap.get(edge.source) ?? edge.source;
        const target = idMap.get(edge.target) ?? edge.target;
        if (!source || !target || source === target) continue;

        // If still references a not-yet-created temp node, keep it queued.
        if (nodesSnapshot.has(source) || nodesSnapshot.has(target) || pendingNodesRef.current.has(source) || pendingNodesRef.current.has(target)) {
          pendingEdgesRef.current.set(localId, edge);
          dirtyRef.current = true;
          continue;
        }

        try {
          const meta: EdgeMeta = {
            line_style: edge.meta?.line_style ?? 'solid',
            stroke_width: edge.meta?.stroke_width ?? 2,
            arrow: edge.meta?.arrow ?? 'forward',
            ...(edge.meta ?? {}),
            source_side: edge.sourceSide,
            target_side: edge.targetSide
          };
          const created = await mindMapsApi.createEdge(Number(mapIdNumber), {
            map_id: Number(mapIdNumber),
            from_node_id: source,
            to_node_id: target,
            label: edge.label ?? null,
            meta
          });
          didPersist = true;

          if (created?.id !== undefined && created?.id !== null) {
            setEdges((prev) => prev.map((e) => (e.id === localId ? { ...e, id: String(created.id) } : e)));
          }
        } catch (error) {
          console.error('Failed to persist edge', edge, error);
          pendingEdgesRef.current.set(localId, edge);
          dirtyRef.current = true;
        }
      }

      for (const [nodeIdRaw, pos] of positionsSnapshot) {
        const nodeId = idMap.get(nodeIdRaw) ?? tempToServerNodeIdRef.current.get(nodeIdRaw) ?? nodeIdRaw;
        try {
          await mindMapsApi.upsertPosition(nodeId, { x: pos.x, y: pos.y });
          didPersist = true;
        } catch (error) {
          const isNotFound = error instanceof ApiError && error.status === 404;
          if (!isNotFound) {
            console.error('Failed to persist node position', { nodeId, x: pos.x, y: pos.y, mapId }, error);
          }
          pendingPositionsRef.current.set(nodeIdRaw, pos);
          dirtyRef.current = true;
        }
      }
    } catch (error) {
      console.error('Failed to flush mind map changes', error);
      for (const [k, v] of positionsSnapshot) pendingPositionsRef.current.set(k, v);
      for (const [k, v] of nodesSnapshot) pendingNodesRef.current.set(k, v);
      for (const [k, v] of nodeUpdatesSnapshot) pendingNodeUpdatesRef.current.set(k, v);
      for (const [k, v] of edgesSnapshot) pendingEdgesRef.current.set(k, v);
      dirtyRef.current = true;
    } finally {
      flushingRef.current = false;
      if (didPersist) onSaved?.();
      if (dirtyRef.current) scheduleFlush();
    }
  }, [mapId, onEditNode, onSaved, scheduleFlush]);

  flushChangesRef.current = () => {
    void flushChanges();
  };

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) window.clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
      flushChangesRef.current = null;
    };
  }, []);

  const queuePosition = useCallback(
    (nodeId: string, x: number, y: number) => {
      pendingPositionsRef.current.set(nodeId, { x, y });
      scheduleFlush();
    },
    [scheduleFlush]
  );

  const queueNodeCreate = useCallback(
    (tempId: string, title: string, x: number, y: number) => {
      pendingNodesRef.current.set(tempId, { title, x, y });
      scheduleFlush();
    },
    [scheduleFlush]
  );

  const queueEdgeCreate = useCallback(
    (edge: { id: string; source: string; target: string; sourceSide?: PortSide; targetSide?: PortSide; label?: string; meta?: EdgeMeta }) => {
      pendingEdgesRef.current.set(edge.id, edge);
      scheduleFlush();
    },
    [scheduleFlush]
  );

  const queueNodeUpdate = useCallback(
    (nodeId: string, patch: { title?: string }) => {
      const base =
        nodeDraftsRef.current.get(nodeId) ??
        (() => {
          const current = nodesRef.current.find((n) => n.id === nodeId);
          if (!current) return null;
          const initial = { title: current.data.title ?? '' };
          nodeDraftsRef.current.set(nodeId, initial);
          return initial;
        })();
      if (!base) return;

      const nextTitle = patch.title ?? base.title;
      nodeDraftsRef.current.set(nodeId, { title: nextTitle });

      setNodes((prev) =>
        prev.map((n) =>
          n.id !== nodeId
            ? n
            : {
                ...n,
                data: {
                  ...n.data,
                  title: nextTitle
                }
              }
        )
      );

      if (pendingNodesRef.current.has(nodeId)) {
        const pending = pendingNodesRef.current.get(nodeId);
        if (pending) {
          pendingNodesRef.current.set(nodeId, { ...pending, title: nextTitle });
        }
        scheduleFlush();
        return;
      }

      pendingNodeUpdatesRef.current.set(nodeId, { text: nextTitle });
      scheduleFlush();
    },
    [scheduleFlush]
  );

  const dismissMenus = useCallback(() => {
    setEdgeMenu(null);
    setNodeMenu(null);
  }, []);

  const getViewportCenter = useCallback(() => {
    const rect = svgRef.current?.getBoundingClientRect();
    const center: [number, number] = rect ? [rect.width / 2, rect.height / 2] : [200, 200];
    const [x, y] = zoomTransform.current.invert(center);
    return { x, y };
  }, []);

  const deleteEdge = useCallback(
    async (edgeId: string) => {
      setEdges((prev) => prev.filter((e) => e.id !== edgeId));
      pendingEdgesRef.current.delete(edgeId);
      setEdgeEditor(null);
      setSelectedEdgeId((prev) => (prev === edgeId ? null : prev));
      dismissMenus();

      const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
      if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

      const numericId = Number(edgeId);
      if (Number.isNaN(numericId)) return;

      try {
        await mindMapsApi.deleteEdge(Number(mapIdNumber), numericId);
        onSaved?.();
      } catch (error) {
        console.error('Failed to delete edge', { edgeId, mapId }, error);
      }
    },
    [dismissMenus, mapId, onSaved]
  );

  const openEdgeEditor = useCallback((edgeId: string, x: number, y: number) => {
    const edge = edgesRef.current.find((e) => e.id === edgeId);
    const meta = edge?.meta;
    const rawWidth = typeof meta?.stroke_width === 'number' ? meta.stroke_width : 2;
    const strokeWidth = Number.isFinite(rawWidth) ? Math.max(1, Math.min(24, Math.round(rawWidth))) : 2;
    const style: EdgeLineStyle = meta?.line_style === 'dashed' || meta?.line_style === 'dotted' || meta?.line_style === 'solid' ? meta.line_style : 'solid';
    const arrow: EdgeArrow = meta?.arrow === 'backward' || meta?.arrow === 'both' || meta?.arrow === 'none' || meta?.arrow === 'forward' ? meta.arrow : 'forward';

    setEdgeEditor({
      edgeId,
      x,
      y,
      label: edge?.label ?? '',
      style,
      strokeWidth,
      arrow
    });
  }, []);

  const persistEdgeUpdate = useCallback(
    async (edgeId: string, patch: { label: string; style: EdgeLineStyle; strokeWidth: number; arrow: EdgeArrow }) => {
      const nextLabel = patch.label.trim();

      setEdges((prev) =>
        prev.map((e) =>
          e.id === edgeId
            ? {
                ...e,
                label: nextLabel ? nextLabel : undefined,
                meta: {
                  ...(e.meta ?? {}),
                  line_style: patch.style,
                  stroke_width: patch.strokeWidth,
                  arrow: patch.arrow,
                  source_side: e.sourceSide,
                  target_side: e.targetSide
                }
              }
            : e
        )
      );

      const pending = pendingEdgesRef.current.get(edgeId);
      if (pending) {
        pendingEdgesRef.current.set(edgeId, {
          ...pending,
          label: nextLabel ? nextLabel : undefined,
          meta: {
            ...(pending.meta ?? {}),
            line_style: patch.style,
            stroke_width: patch.strokeWidth,
            arrow: patch.arrow,
            source_side: pending.sourceSide,
            target_side: pending.targetSide
          }
        });
      }

      const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
      if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

      const numericId = Number(edgeId);
      if (Number.isNaN(numericId)) return;

      try {
        const edge = edgesRef.current.find((e) => e.id === edgeId);
        const meta: EdgeMeta = {
          ...(edge?.meta ?? {}),
          line_style: patch.style,
          stroke_width: patch.strokeWidth,
          arrow: patch.arrow,
          source_side: edge?.sourceSide,
          target_side: edge?.targetSide
        };
        await mindMapsApi.updateEdge(Number(mapIdNumber), numericId, { label: nextLabel || null, meta });
        onSaved?.();
      } catch (error) {
        console.error('Failed to update edge', { edgeId, mapId }, error);
      }
    },
    [mapId, onSaved]
  );

  const persistEdgeRewire = useCallback(
    async (edgeId: string, next: { source: string; target: string; sourceSide: PortSide; targetSide: PortSide }) => {
      const isNumericId = /^\d+$/.test(edgeId);
      if (!isNumericId) {
        const pending = pendingEdgesRef.current.get(edgeId);
        if (pending) {
          pendingEdgesRef.current.set(edgeId, {
            ...pending,
            source: next.source,
            target: next.target,
            sourceSide: next.sourceSide,
            targetSide: next.targetSide,
            meta: { ...(pending.meta ?? {}), source_side: next.sourceSide, target_side: next.targetSide }
          });
          scheduleFlush();
        }
        return;
      }

      const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
      if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

      const numericId = Number(edgeId);
      if (Number.isNaN(numericId)) return;

      try {
        const edge = edgesRef.current.find((e) => e.id === edgeId);
        const meta = edge?.meta ?? {};
        const lineStyle: EdgeLineStyle = meta.line_style === 'dashed' || meta.line_style === 'dotted' || meta.line_style === 'solid' ? meta.line_style : 'solid';
        const arrow: EdgeArrow =
          meta.arrow === 'backward' || meta.arrow === 'both' || meta.arrow === 'none' || meta.arrow === 'forward' ? meta.arrow : 'forward';
        const strokeWidth = typeof meta.stroke_width === 'number' && Number.isFinite(meta.stroke_width) ? meta.stroke_width : 2;

        const nextMeta: EdgeMeta = {
          line_style: lineStyle,
          stroke_width: strokeWidth,
          arrow,
          ...meta,
          source_side: next.sourceSide,
          target_side: next.targetSide
        };

        await mindMapsApi.updateEdge(Number(mapIdNumber), numericId, {
          from_node_id: next.source,
          to_node_id: next.target,
          meta: nextMeta
        });
        onSaved?.();
      } catch (error) {
        console.error('Failed to rewire edge', { edgeId, mapId, next }, error);
      }
    },
    [mapId, onSaved, scheduleFlush]
  );

  useEffect(() => {
    if (!edgeEditor) return;

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      const editor = document.querySelector('[data-edge-editor="true"]');
      if (editor && editor.contains(target)) return;
      setEdgeEditor(null);
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setEdgeEditor(null);
    };

    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [edgeEditor]);

  const openNodeMenu = useCallback(
    (nodeId: string, clientX: number, clientY: number) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setSelectedEdgeId(null);
      setEdgeMenu(null);
      setEdgeEditor(null);
      setSelectedNodeId(nodeId);
      setNodeMenu({ nodeId, x: clientX - rect.left, y: clientY - rect.top });
    },
    []
  );

  const copyNode = useCallback(async (nodeId: string) => {
    const node = nodesRef.current.find((n) => n.id === nodeId);
    if (!node) return;

    nodeClipboardRef.current = {
      title: node.data.title,
      typeLabel: node.data.typeLabel,
      color: node.data.color ?? null,
      properties: (node.data.properties ?? []).map((p) => ({
        title: p.title,
        value: p.value,
        delta: p.delta ?? null,
        order_index: p.order_index ?? null,
        meta: (p.meta as Record<string, unknown> | undefined) ?? null
      }))
    };

    const text = formatNodeClipboardText({
      title: node.data.title,
      typeLabel: node.data.typeLabel,
      color: node.data.color ?? null,
      properties: node.data.properties
    });

    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      console.warn('Clipboard API failed, falling back to execCommand', error);
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      textarea.style.top = '0';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
  }, []);

  const pasteNode = useCallback(async () => {
    const snapshot = nodeClipboardRef.current;
    if (!snapshot) return;

    const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
    if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

    const pos = getViewportCenter();
    const tempId = crypto.randomUUID();

    const optimistic: MindMapNodeDatum = {
      id: tempId,
      x: pos.x,
      y: pos.y,
      data: {
        title: snapshot.title || 'Новый узел',
        typeLabel: snapshot.typeLabel,
        properties: (snapshot.properties ?? []).map((p) => ({
          id: -Math.floor(Math.random() * 1_000_000),
          node_id: tempId,
          title: (p.title ?? '').toString(),
          value: (p.value ?? '').toString(),
          delta: p.delta ?? null,
          order_index: p.order_index ?? 0,
          meta: p.meta ?? undefined
        })),
        color: snapshot.color ?? null
      } satisfies MindNodeData
    };

    setNodes((prev) => [...prev, optimistic]);

    try {
      const created = await mindMapsApi.createNode(Number(mapIdNumber), {
        map_id: Number(mapIdNumber),
        text: snapshot.title || 'Новый узел',
        color: snapshot.color ?? null,
        meta: snapshot.typeLabel ? { metric_type: snapshot.typeLabel } : {}
      });

      const createdId = String(created.id);
      tempToServerNodeIdRef.current.set(tempId, createdId);
      setNodes((prev) => prev.map((n) => (n.id === tempId ? { ...n, id: createdId } : n)));
      setSelectedNodeId(createdId);

      const pendingTempPos = pendingPositionsRef.current.get(tempId);
      if (pendingTempPos) {
        pendingPositionsRef.current.set(createdId, pendingTempPos);
        pendingPositionsRef.current.delete(tempId);
      }

      try {
        await mindMapsApi.upsertPosition(createdId, pos);
      } catch (error) {
        console.error('Failed to persist pasted node position, will retry via flush', { createdId, mapId }, error);
        queuePosition(createdId, pos.x, pos.y);
      }

      const sourceProps = (snapshot.properties ?? [])
        .slice()
        .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
        .filter((p) => (p.title ?? '').trim() && (p.value ?? '').trim());

      if (!sourceProps.length) return;

      const createdProps = (await Promise.all(
        sourceProps.map((p) =>
          mindMapsApi.createProperty({
            node: createdId,
            title: (p.title ?? '').trim(),
            value: (p.value ?? '').trim(),
            delta: (p.delta ?? '').trim() || undefined,
            order_index: p.order_index ?? 0,
            meta: p.meta ?? undefined
          })
        )
      )) as unknown as MindNodeProperty[];

      setNodes((prev) =>
        prev.map((n) =>
          n.id === createdId
            ? {
                ...n,
                data: { ...n.data, properties: createdProps }
              }
            : n
        )
      );
    } catch (error) {
      console.error('Failed to paste node', { mapId }, error);
      setNodes((prev) => prev.filter((n) => n.id !== tempId));
    }
  }, [getViewportCenter, mapId, queuePosition]);

  useEffect(() => {
    const isEditableTarget = (target: EventTarget | null) => {
      const el = target as HTMLElement | null;
      if (!el) return false;
      if (el.isContentEditable) return true;
      return !!el.closest('input, textarea, select, [contenteditable="true"]');
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      if (isEditableTarget(e.target)) return;
      if (!e.ctrlKey && !e.metaKey) return;
      const selectionText = typeof window !== 'undefined' ? window.getSelection?.()?.toString() : '';

      if (e.code === 'KeyC') {
        const id = selectedNodeIdRef.current;
        if (!id) return;
        if (selectionText) return;
        e.preventDefault();
        void copyNode(id);
        return;
      }

      if (e.code === 'KeyV') {
        if (!nodeClipboardRef.current) return;
        e.preventDefault();
        void pasteNode();
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [copyNode, pasteNode]);

  const duplicateNode = useCallback(
    async (nodeId: string) => {
      const source = nodesRef.current.find((n) => n.id === nodeId);
      if (!source) return;

      const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
      if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

      const pos = { x: source.x + 40, y: source.y + 40 };
      const tempId = crypto.randomUUID();

      const optimistic: MindMapNodeDatum = {
        id: tempId,
        x: pos.x,
        y: pos.y,
        data: {
          title: source.data.title || 'Новый узел',
          typeLabel: source.data.typeLabel,
          properties: source.data.properties ?? [],
          color: source.data.color ?? null,
          meta: (source.data.meta ?? {}) as Record<string, unknown>,
          onEdit: onEditNode,
          onOpenMenu: openNodeMenu
        } satisfies MindNodeData
      };

      setNodes((prev) => [...prev, optimistic]);

      try {
        const created = await mindMapsApi.createNode(Number(mapIdNumber), {
          map_id: Number(mapIdNumber),
          text: source.data.title || 'Новый узел',
          color: source.data.color ?? null,
          meta: {
            ...((source.data.meta ?? {}) as Record<string, unknown>),
            metric_type: source.data.typeLabel || undefined
          }
        });

        const createdId = String(created.id);
        tempToServerNodeIdRef.current.set(tempId, createdId);
        const pendingTempPos = pendingPositionsRef.current.get(tempId);
        if (pendingTempPos) {
          pendingPositionsRef.current.set(createdId, pendingTempPos);
          pendingPositionsRef.current.delete(tempId);
        }

        try {
          await mindMapsApi.upsertPosition(createdId, pos);
        } catch (error) {
          console.error('Failed to persist duplicated node position, will retry via flush', { createdId, mapId }, error);
          queuePosition(createdId, pos.x, pos.y);
        }

        const sourceProps = (source.data.properties ?? [])
          .slice()
          .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
          .filter((p) => p.title?.trim() && p.value?.trim());

        const createdProps = (await Promise.all(
          sourceProps.map((p) =>
            mindMapsApi.createProperty({
              node: createdId,
              title: p.title,
              value: p.value,
              delta: p.delta ?? undefined,
              order_index: p.order_index ?? 0,
              meta: p.meta ?? undefined
            })
          )
        )) as unknown as MindNodeProperty[];

        setNodes((prev) =>
          prev.map((n) =>
            n.id === tempId
              ? {
                  ...n,
                  id: createdId,
                  data: {
                    ...n.data,
                    properties: createdProps
                  }
                }
              : n
          )
        );
      } catch (error) {
        console.error('Failed to duplicate node', { nodeId, mapId }, error);
        setNodes((prev) => prev.filter((n) => n.id !== tempId));
      }
    },
    [mapId, onEditNode, openNodeMenu, queuePosition]
  );

  const deleteNode = useCallback(
    async (nodeId: string) => {
      const wasPending = pendingNodesRef.current.has(nodeId);
      setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setNodes((prev) => prev.filter((n) => n.id !== nodeId));
      setSelectedNodeId((prev) => (prev === nodeId ? null : prev));

      pendingNodesRef.current.delete(nodeId);
      pendingPositionsRef.current.delete(nodeId);
      pendingNodeUpdatesRef.current.delete(nodeId);
      nodeDraftsRef.current.delete(nodeId);
      for (const [edgeId, edge] of pendingEdgesRef.current) {
        if (edge.source === nodeId || edge.target === nodeId) pendingEdgesRef.current.delete(edgeId);
      }

      setSelectedEdgeId(null);
      setEdgeEditor(null);
      dismissMenus();

      if (wasPending) return;

      const mapIdNumber = typeof mapId === 'string' ? Number(mapId) : mapId;
      if (mapIdNumber === undefined || Number.isNaN(mapIdNumber)) return;

      try {
        for (const [tempId, serverId] of tempToServerNodeIdRef.current) {
          if (tempId === nodeId || serverId === nodeId) tempToServerNodeIdRef.current.delete(tempId);
        }
        await mindMapsApi.deleteNode(Number(mapIdNumber), nodeId);
        onSaved?.();
      } catch (error) {
        console.error('Failed to delete node', { nodeId, mapId }, error);
      }
    },
    [dismissMenus, mapId, onSaved]
  );

  const edgesWithPositions = useMemo(() => {
    const nodeMap = new Map(nodesWithSize.map((node) => [node.id, node]));

    return edges
      .map((edge) => {
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (!source || !target) return null;

        const sourceSide = edge.sourceSide ?? inferSideBetween(source, target);
        const targetSide = edge.targetSide ?? inferSideBetween(target, source);
        const p1 = getPortPosition(source, sourceSide);
        const p2 = getPortPosition(target, targetSide);

        return {
          ...edge,
          sourceSide,
          targetSide,
          x1: p1.x,
          y1: p1.y,
          x2: p2.x,
          y2: p2.y
        };
      })
      .filter(Boolean) as Array<MindMapEdgeDatum & { sourceSide: PortSide; targetSide: PortSide; x1: number; y1: number; x2: number; y2: number }>;
  }, [edges, nodesWithSize]);

  useEffect(() => {
    if (!svgRef.current || !innerRef.current) return;

    const svg = d3.select(svgRef.current);
    const layer = d3.select(innerRef.current);

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .filter((event) => {
        return !event.ctrlKey && event.button !== 1;
      })
      .on('zoom', (event) => {
        zoomTransform.current = event.transform;
        layer.attr('transform', event.transform.toString());
      });

    svg.call(zoom as any);

    return () => {
      svg.on('.zoom', null);
    };
  }, []);

  useEffect(() => {
    if (!innerRef.current || !svgRef.current) return;

    const svgEl = svgRef.current;
    const dragBehavior = d3
      .drag<SVGGElement, MindMapNodeWithSize>()
      .on('start', function (event, d) {
        event.sourceEvent?.stopPropagation();
        const [sx, sy] = d3.pointer(event.sourceEvent ?? event, svgEl);
        const [x, y] = zoomTransform.current.invert([sx, sy]);
        dragOffset.current.set(d.id, { dx: x - d.x, dy: y - d.y });
        d3.select(this).style('cursor', 'grabbing');
      })
      .on('drag', function (event, d) {
        event.sourceEvent?.stopPropagation();
        const [sx, sy] = d3.pointer(event.sourceEvent ?? event, svgEl);
        const [x, y] = zoomTransform.current.invert([sx, sy]);
        const offset = dragOffset.current.get(d.id) ?? { dx: 0, dy: 0 };
        const nextX = x - offset.dx;
        const nextY = y - offset.dy;
        setNodes((prev) => prev.map((node) => (node.id === d.id ? { ...node, x: nextX, y: nextY } : node)));
      })
      .on('end', function (event, d) {
        event.sourceEvent?.stopPropagation();
        const [sx, sy] = d3.pointer(event.sourceEvent ?? event, svgEl);
        const [x, y] = zoomTransform.current.invert([sx, sy]);
        const offset = dragOffset.current.get(d.id) ?? { dx: 0, dy: 0 };
        const nextX = x - offset.dx;
        const nextY = y - offset.dy;
        dragOffset.current.delete(d.id);
        console.debug('Node position changed', d.id, { x: nextX, y: nextY, mapId });
        setNodes((prev) => prev.map((node) => (node.id === d.id ? { ...node, x: nextX, y: nextY } : node)));
        queuePosition(d.id, nextX, nextY);
        d3.select(this).style('cursor', 'grab');
      });

    const selection = d3
      .select(innerRef.current)
      .selectAll<SVGGElement, MindMapNodeWithSize>('g.node')
      .data(nodesWithSize, function (d, i) {
        return d?.id ?? this.getAttribute('data-node-id') ?? `unbound-${i}`;
      });
    selection.call(dragBehavior as any).style('cursor', 'grab');

    return () => {
      selection.on('.drag', null);
    };
  }, [nodesWithSize, mapId, queuePosition]);

  const isDraggingLink = draggingLink !== null;

  useEffect(() => {
    if (!isDraggingLink || !svgRef.current) return;

    const svgEl = svgRef.current;

    const move = (e: PointerEvent) => {
      const link = draggingLinkRef.current;
      if (!link) return;
      const [sx, sy] = d3.pointer(e, svgEl);
      const [x, y] = zoomTransform.current.invert([sx, sy]);
      updateDraggingLink({ ...link, x, y });
    };

    const up = (e: PointerEvent) => {
      const link = draggingLinkRef.current;
      if (!link) return;

      const [sx, sy] = d3.pointer(e, svgEl);
      const [x, y] = zoomTransform.current.invert([sx, sy]);

      const allNodes = nodesWithSizeRef.current;
      let targetNode: MindMapNodeWithSize | undefined;
      for (let i = allNodes.length - 1; i >= 0; i -= 1) {
        const node = allNodes[i];
        if (x >= node.x && x <= node.x + node.width && y >= node.y && y <= node.y + node.height) {
          targetNode = node;
          break;
        }
      }

      if (link.mode === 'create') {
        if (targetNode && targetNode.id !== link.sourceId) {
          const targetSide = inferSideByPoint(targetNode, x, y);
          const newEdge: MindMapEdgeDatum = {
            id: crypto.randomUUID(),
            source: link.sourceId,
            target: targetNode.id,
            sourceSide: link.side,
            targetSide
          };
          setEdges((prev) => [...prev, newEdge]);
          queueEdgeCreate(newEdge);
        }
      } else {
        if (targetNode && targetNode.id !== link.fixedNodeId) {
          const movedSide = inferSideByPoint(targetNode, x, y);
          const next =
            link.movingEnd === 'target'
              ? {
                  source: link.fixedNodeId,
                  target: targetNode.id,
                  sourceSide: link.fixedSide,
                  targetSide: movedSide
                }
              : {
                  source: targetNode.id,
                  target: link.fixedNodeId,
                  sourceSide: movedSide,
                  targetSide: link.fixedSide
                };

          setEdges((prev) =>
            prev.map((e) =>
              e.id === link.edgeId
                ? {
                    ...e,
                    source: next.source,
                    target: next.target,
                    sourceSide: next.sourceSide,
                    targetSide: next.targetSide,
                    meta: { ...(e.meta ?? {}), source_side: next.sourceSide, target_side: next.targetSide }
                  }
                : e
            )
          );
          void persistEdgeRewire(link.edgeId, next);
        }
      }

      updateDraggingLink(null);
    };

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
  }, [isDraggingLink, persistEdgeRewire, queueEdgeCreate, updateDraggingLink]);

  const addNode = () => {
    const pos = getViewportCenter();
    const tempId = crypto.randomUUID();
    const optimistic: MindMapNodeDatum = {
      id: tempId,
      x: pos.x,
      y: pos.y,
      data: { title: 'Новый узел', meta: {}, properties: [], onEdit: onEditNode, onChange: queueNodeUpdate }
    };

    setNodes((nds) => [...nds, optimistic]);
    queueNodeCreate(tempId, optimistic.data.title, pos.x, pos.y);
  };

  return (
    <div ref={containerRef} className="relative h-[70vh] min-h-[520px] w-full overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="absolute left-4 top-4 z-10 flex items-center gap-3 rounded-lg bg-background/80 px-3 py-2 text-sm shadow-sm backdrop-blur">
        <Button size="sm" onClick={addNode} className="shadow-sm">
          + Узел
        </Button>
      </div>

      <NodeContextMenu
        anchor={edgeMenu ? { x: edgeMenu.x, y: edgeMenu.y } : null}
        containerRef={containerRef}
        onClose={dismissMenus}
        items={
          edgeMenu
            ? [
                { action: 'edit', label: 'Редактировать', onSelect: () => openEdgeEditor(edgeMenu.edgeId, edgeMenu.x, edgeMenu.y) },
                { action: 'delete', label: 'Удалить', destructive: true, onSelect: () => void deleteEdge(edgeMenu.edgeId) }
              ]
            : []
        }
      />

      {edgeEditor && (
        typeof document !== 'undefined' &&
        createPortal((() => {
          const rect = containerRef.current?.getBoundingClientRect();
          const width = 280;
          const height = 260;
          const baseLeft = (rect?.left ?? 0) + edgeEditor.x + 8;
          const baseTop = (rect?.top ?? 0) + edgeEditor.y + 8;
          const left = Math.min(baseLeft, (rect?.right ?? baseLeft) - width - 8);
          const top = Math.min(baseTop, (rect?.bottom ?? baseTop) - height - 8);

          return (
            <div
              data-edge-editor="true"
              className="fixed z-50 w-[280px] rounded-lg border bg-white p-3 shadow-md"
              style={{ left: Math.max(8, left), top: Math.max(8, top) }}
              onPointerDown={(e) => e.stopPropagation()}
            >
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="text-xs font-medium text-slate-700">Надпись</div>
                  <Input
                    value={edgeEditor.label}
                    onChange={(e) => setEdgeEditor((prev) => (prev ? { ...prev, label: e.target.value } : prev))}
                    className="border-slate-300 bg-white text-black placeholder:text-slate-400"
                    placeholder="Текст на связи"
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-medium text-slate-700">Стиль</div>
                  <select
                    value={edgeEditor.style}
                    onChange={(e) =>
                      setEdgeEditor((prev) => (prev ? { ...prev, style: (e.target.value as EdgeLineStyle) || 'solid' } : prev))
                    }
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-mono text-sm text-black"
                  >
                    <option value="dotted">. . . . . . . .</option>
                    <option value="dashed">- - - - - - - -</option>
                    <option value="solid">──────────────</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-medium text-slate-700">Стрелка</div>
                  <select
                    value={edgeEditor.arrow}
                    onChange={(e) =>
                      setEdgeEditor((prev) => (prev ? { ...prev, arrow: (e.target.value as EdgeArrow) || 'forward' } : prev))
                    }
                    className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 font-mono text-sm text-black"
                  >
                    <option value="forward">&gt;</option>
                    <option value="backward">&lt;</option>
                    <option value="both">&lt;&gt;</option>
                    <option value="none">-</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-medium text-slate-700">Жирность (px)</div>
                  <Input
                    type="number"
                    min={1}
                    max={24}
                    value={edgeEditor.strokeWidth}
                    onChange={(e) =>
                      setEdgeEditor((prev) =>
                        prev ? { ...prev, strokeWidth: Math.max(1, Math.min(24, Number(e.target.value) || 1)) } : prev
                      )
                    }
                    className="border-slate-300 bg-white text-black placeholder:text-slate-400"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <Button
                    type="button"
                    variant="outline"
                    className="border-slate-300 bg-white text-black hover:bg-slate-100 hover:text-black"
                    onClick={() => setEdgeEditor(null)}
                  >
                    Отмена
                  </Button>
                  <Button
                    type="button"
                    className="bg-black text-white hover:bg-black/90"
                    onClick={() => {
                      void persistEdgeUpdate(edgeEditor.edgeId, {
                        label: edgeEditor.label,
                        style: edgeEditor.style,
                        strokeWidth: edgeEditor.strokeWidth,
                        arrow: edgeEditor.arrow
                      });
                      setEdgeEditor(null);
                    }}
                  >
                    Сохранить
                  </Button>
                </div>
              </div>
            </div>
          );
        })(), document.body)
      )}

      <NodeContextMenu
        anchor={nodeMenu ? { x: nodeMenu.x, y: nodeMenu.y } : null}
        containerRef={containerRef}
        onClose={dismissMenus}
        items={
          nodeMenu
            ? [
                { action: 'edit', label: 'Редактировать', onSelect: () => onEditNode?.(nodeMenu.nodeId) },
                { action: 'copy', label: 'Скопировать', onSelect: () => void copyNode(nodeMenu.nodeId) },
                { action: 'duplicate', label: 'Дублировать', onSelect: () => void duplicateNode(nodeMenu.nodeId) },
                { action: 'delete', label: 'Удалить', destructive: true, onSelect: () => void deleteNode(nodeMenu.nodeId) }
              ]
            : []
        }
      />

      <svg ref={svgRef} className="h-full w-full select-none">
        <defs>
          <marker id="arrow" markerWidth="12" markerHeight="12" refX="12" refY="6" orient="auto" markerUnits="userSpaceOnUse">
            <path d="M0,0 L12,6 L0,12 z" fill="#0f172a" />
          </marker>
          <marker
            id="arrow-selected"
            markerWidth="12"
            markerHeight="12"
            refX="12"
            refY="6"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M0,0 L12,6 L0,12 z" fill="#ef4444" />
          </marker>
          <marker id="arrow-start" markerWidth="12" markerHeight="12" refX="0" refY="6" orient="auto" markerUnits="userSpaceOnUse">
            <path d="M12,0 L0,6 L12,12 z" fill="#0f172a" />
          </marker>
          <marker id="arrow-start-selected" markerWidth="12" markerHeight="12" refX="0" refY="6" orient="auto" markerUnits="userSpaceOnUse">
            <path d="M12,0 L0,6 L12,12 z" fill="#ef4444" />
          </marker>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#e2e8f0" strokeWidth="1" />
          </pattern>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="url(#grid)"
          onPointerDown={() => {
            dismissMenus();
            setSelectedEdgeId(null);
            setEdgeEditor(null);
          }}
        />

        <g ref={innerRef}>
          {draggingLink && (() => {
            const startNodeId = draggingLink.mode === 'create' ? draggingLink.sourceId : draggingLink.fixedNodeId;
            const startSide = draggingLink.mode === 'create' ? draggingLink.side : draggingLink.fixedSide;
            const sourceNode = nodesWithSize.find((n) => n.id === startNodeId);
            if (!sourceNode) return null;
            const p = getPortPosition(sourceNode, startSide);
            const endSide = oppositeSide(inferSideBetweenPoints(p, { x: draggingLink.x, y: draggingLink.y }));
            return (
              <path
                d={bezierLink(p, startSide, { x: draggingLink.x, y: draggingLink.y }, endSide)}
                fill="none"
                stroke="#2563eb"
                strokeWidth={2}
                strokeDasharray="5 4"
                pointerEvents="none"
              />
            );
          })()}

          <g className="edges">
            {edgesWithPositions.map((edge) => {
              const meta = edge.meta;
              const isSelected = edge.id === selectedEdgeId;
              const lineStyle: EdgeLineStyle = meta?.line_style === 'dashed' || meta?.line_style === 'dotted' || meta?.line_style === 'solid' ? meta.line_style : 'solid';
              const arrow: EdgeArrow =
                meta?.arrow === 'backward' || meta?.arrow === 'both' || meta?.arrow === 'none' || meta?.arrow === 'forward' ? meta.arrow : 'forward';
              const rawWidth = typeof meta?.stroke_width === 'number' ? meta.stroke_width : 2;
              const strokeWidth = Number.isFinite(rawWidth) ? Math.max(1, Math.min(24, rawWidth)) : 2;
              const hitWidth = Math.max(14, strokeWidth + 10);
              const dasharray =
                lineStyle === 'dashed'
                  ? `${Math.max(6, Math.round(strokeWidth * 2))} ${Math.max(4, Math.round(strokeWidth * 1.5))}`
                  : lineStyle === 'dotted'
                    ? `${Math.max(1, Math.round(strokeWidth))} ${Math.max(4, Math.round(strokeWidth * 1.8))}`
                    : undefined;

              const markerEnd =
                arrow === 'forward' || arrow === 'both'
                  ? isSelected
                    ? 'url(#arrow-selected)'
                    : 'url(#arrow)'
                  : undefined;
              const markerStart =
                arrow === 'backward' || arrow === 'both'
                  ? isSelected
                    ? 'url(#arrow-start-selected)'
                    : 'url(#arrow-start)'
                  : undefined;

              return (
              <g key={edge.id} className="edge">
                <path
                  d={bezierLink(
                    { x: edge.x1, y: edge.y1 },
                    edge.sourceSide,
                    { x: edge.x2, y: edge.y2 },
                    edge.targetSide
                  )}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={hitWidth}
                  className="cursor-pointer"
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    const rect = containerRef.current?.getBoundingClientRect();
                    if (!rect) return;
                    setSelectedEdgeId(edge.id);
                    setEdgeMenu({ edgeId: edge.id, x: e.clientX - rect.left, y: e.clientY - rect.top });
                    setNodeMenu(null);
                    setEdgeEditor(null);
                  }}
                />
                <path
                  d={bezierLink(
                    { x: edge.x1, y: edge.y1 },
                    edge.sourceSide,
                    { x: edge.x2, y: edge.y2 },
                    edge.targetSide
                  )}
                  fill="none"
                  stroke={isSelected ? '#ef4444' : '#0f172a'}
                  strokeWidth={strokeWidth}
                  strokeDasharray={dasharray}
                  strokeLinecap="round"
                  markerEnd={markerEnd}
                  markerStart={markerStart}
                  opacity={0.75}
                  className={cn(isSelected ? 'drop-shadow-sm' : '', 'pointer-events-none')}
                />
                {edge.label && (
                  <text
                    x={(edge.x1 + edge.x2) / 2}
                    y={(edge.y1 + edge.y2) / 2 - 6}
                    textAnchor="middle"
                    className="fill-slate-600 text-xs"
                  >
                    {edge.label}
                  </text>
                )}
              </g>
              );
            })}
          </g>

          <g className="nodes">
            {nodesWithSize.map((node) => (
              <g
                key={node.id}
                className="node group cursor-grab"
                data-node-id={node.id}
                transform={`translate(${node.x}, ${node.y})`}
              >
                <foreignObject width={node.width} height={node.height}>
                  <MindMapNodeCard
                    id={node.id}
                    data={{ ...node.data, onChange: node.data.onChange ?? queueNodeUpdate }}
                    onOpenMenu={openNodeMenu}
                    onSelect={(nodeId) => setSelectedNodeId(nodeId)}
                  />
                </foreignObject>

                {(['top', 'right', 'bottom', 'left'] as PortSide[]).map((side) => {
                  const p = getPortPosition(node, side);
                  const candidates = edgesWithPositions.filter(
                    (edge) =>
                      (edge.source === node.id && edge.sourceSide === side) || (edge.target === node.id && edge.targetSide === side)
                  );
                  const selectedCandidate = candidates.find((edge) => edge.id === selectedEdgeId);
                  const edgeToRewire = (selectedCandidate ?? candidates[candidates.length - 1]) as
                    | (typeof candidates)[number]
                    | undefined;
                  const movingEnd: 'source' | 'target' | undefined =
                    edgeToRewire && edgeToRewire.source === node.id && edgeToRewire.sourceSide === side
                      ? 'source'
                      : edgeToRewire && edgeToRewire.target === node.id && edgeToRewire.targetSide === side
                        ? 'target'
                        : undefined;
                  const isConnectedPort = !!edgeToRewire && !!movingEnd;
                  return (
                    <circle
                      key={side}
                      cx={p.x - node.x}
                      cy={p.y - node.y}
                      r={6}
                      fill="#2563eb"
                      className={cn(
                        'port opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:opacity-100',
                        isConnectedPort ? 'cursor-grab' : 'cursor-crosshair'
                      )}
                      onPointerDown={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                        if (!svgRef.current) return;
                        const [sx, sy] = d3.pointer(e.nativeEvent, svgRef.current);
                        const [x, y] = zoomTransform.current.invert([sx, sy]);
                        if (isConnectedPort && edgeToRewire && movingEnd) {
                          const fixedNodeId = movingEnd === 'target' ? edgeToRewire.source : edgeToRewire.target;
                          const fixedSide = movingEnd === 'target' ? edgeToRewire.sourceSide : edgeToRewire.targetSide;

                          setSelectedEdgeId(edgeToRewire.id);
                          setEdgeMenu(null);
                          setNodeMenu(null);
                          setEdgeEditor(null);
                          updateDraggingLink({
                            mode: 'rewire',
                            edgeId: edgeToRewire.id,
                            movingEnd,
                            fixedNodeId,
                            fixedSide,
                            x,
                            y
                          });
                        } else {
                          setEdgeMenu(null);
                          setNodeMenu(null);
                          setEdgeEditor(null);
                          updateDraggingLink({ mode: 'create', sourceId: node.id, side, x, y });
                        }
                      }}
                    />
                  );
                })}
              </g>
            ))}
          </g>
        </g>
      </svg>
    </div>
  );
}

export default MindMap;
