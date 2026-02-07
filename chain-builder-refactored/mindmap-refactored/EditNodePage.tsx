'use client';

import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { mindMapsApi } from '@/lib/api/mindmaps';
import type { MindMapDetail } from '@/lib/types';

// Shared components and utilities
import { Alert } from './components/Alert';
import { NodeHeader } from './components/NodeHeader';
import { NodeFormFields } from './components/NodeFormFields';
import { PropertiesSection } from './components/PropertiesSection';
import { NodeFooter } from './components/NodeFooter';

// Shared hooks and utils
import { useIsMobile, useAutoSave, useDragAndDrop, useTemporaryMessage } from './hooks';
import { 
  toDrafts, 
  extractProductId, 
  isWebsiteNode as checkIsWebsiteNode,
  extractWebsiteTitle,
  extractWebsiteUrl,
  validateProperties,
  filterDeleted 
} from './utils';

import type { NodeFormState, PropertyDraft } from './types';

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT - Now much cleaner!
// ═══════════════════════════════════════════════════════════════════════════

export default function EditNodePage() {
  const { mapId, nodeId } = useParams<{ mapId: string; nodeId: string }>();
  const router = useRouter();
  const isMobile = useIsMobile();

  // State
  const [mapData, setMapData] = useState<MindMapDetail | null>(null);
  const [form, setForm] = useState<NodeFormState>({ title: '', typeLabel: '', meta: {} });
  const [properties, setProperties] = useState<PropertyDraft[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Shared hooks
  const [successMessage, showSuccess] = useTemporaryMessage(3000);
  const { draggedKey, handleDragStart, handleDragEnd, handleDrop } = useDragAndDrop<PropertyDraft>();

  // Derived data
  const node = useMemo(
    () => mapData?.nodes.find((n) => String(n.id) === String(nodeId)),
    [mapData?.nodes, nodeId]
  );

  const productId = useMemo(
    () => extractProductId((node?.meta as Record<string, unknown>) ?? null),
    [node?.meta]
  );

  const isWebsiteNode = useMemo(
    () => checkIsWebsiteNode((node?.meta as Record<string, unknown>) ?? null),
    [node?.meta]
  );

  // ─── Load data ──────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!mapId || !nodeId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const detail = await mindMapsApi.detail(mapId);
      setMapData(detail);
      
      const currentNode = detail.nodes.find((n) => String(n.id) === String(nodeId));
      if (!currentNode) {
        setError('Узел не найден в карте');
        return;
      }

      const meta = (currentNode.meta ?? {}) as Record<string, unknown>;
      const title = checkIsWebsiteNode(meta)
        ? extractWebsiteTitle(meta, currentNode.text)
        : currentNode.text;
      
      const typeLabel = checkIsWebsiteNode(meta)
        ? extractWebsiteUrl(meta)
        : (typeof meta.metric_type === 'string' && meta.metric_type) || '';

      setForm({ title, typeLabel, meta });
      setProperties(toDrafts(currentNode.properties ?? []));
    } catch (err) {
      console.error('Failed to load node', err);
      setError('Не удалось загрузить данные узла');
    } finally {
      setLoading(false);
    }
  }, [mapId, nodeId]);

  useEffect(() => {
    void load();
  }, [load]);

  // ─── Auto-save node (title & typeLabel) ─────────────────────────────────
  const saveNodeNow = useCallback(
    async (next: { title: string; typeLabel: string }) => {
      if (!mapId || !nodeId || !next.title.trim()) return;
      
      setSaving(true);
      setError(null);
      
      try {
        const meta = {
          ...(form.meta ?? {}),
          metric_type: next.typeLabel || undefined,
          ...(isWebsiteNode ? { page_title: next.title } : {}),
        };
        
        await mindMapsApi.updateNode(Number(mapId), nodeId, { 
          text: next.title, 
          meta 
        });
      } catch (err) {
        console.error('Failed to save node', err);
        setError('Не удалось сохранить изменения');
      } finally {
        setSaving(false);
      }
    },
    [form.meta, isWebsiteNode, mapId, nodeId]
  );

  useAutoSave({ title: form.title, typeLabel: form.typeLabel }, saveNodeNow, 500);

  // ─── Property management ────────────────────────────────────────────────
  const updateProperty = (key: string, patch: Partial<PropertyDraft>) => {
    setProperties((prev) => prev.map((p) => (p.key === key ? { ...p, ...patch } : p)));
  };

  const deleteProperty = (key: string) => {
    setProperties((prev) => prev.map((p) => (p.key === key ? { ...p, deleted: true } : p)));
  };

  const addPropertyRow = () => {
    setProperties((prev) => [
      ...prev,
      { 
        key: `new_${Date.now()}`, 
        title: '', 
        value: '', 
        delta: '', 
        order_index: prev.length 
      }
    ]);
  };

  // ─── Save all (explicit save button) ───────────────────────────────────
  const saveAll = async () => {
    if (!mapId || !nodeId || !node) return;

    const validationError = validateProperties(properties);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      // Delete removed properties
      const toDelete = properties.filter((p) => p.deleted && p.id);
      await Promise.all(
        toDelete.map((p) => mindMapsApi.deleteNodeProperty(Number(mapId), nodeId, p.id!))
      );

      // Update/create properties
      const toSave = filterDeleted(properties);
      await Promise.all(
        toSave.map((p, idx) => {
          const nextOrder = idx;
          const nextDelta = p.delta?.trim() || undefined;

          if (p.id) {
            return mindMapsApi.updateNodeProperty(Number(mapId), nodeId, p.id, {
              title: p.title,
              value: p.value,
              delta: nextDelta,
              order_index: nextOrder
            });
          } else if (p.title.trim()) {
            return mindMapsApi.createNodeProperty(Number(mapId), nodeId, {
              title: p.title,
              value: p.value,
              delta: nextDelta,
              order_index: nextOrder
            });
          }
        }).filter(Boolean)
      );

      showSuccess('✓ Изменения сохранены');
      await load();
    } catch (err) {
      console.error('Failed to save node', err);
      setError('Не удалось сохранить изменения');
    } finally {
      setSaving(false);
    }
  };

  // ─── Render ─────────────────────────────────────────────────────────────
  const content = (
    <div className="space-y-6">
      <NodeHeader mapId={mapId} saving={saving} />

      {/* Alerts */}
      {error && <Alert variant="error">{error}</Alert>}
      {successMessage && <Alert variant="success">{successMessage}</Alert>}
      {loading && <Alert variant="info">Загрузка...</Alert>}

      {/* Main card */}
      {node && (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader className="border-b border-slate-100">
            <CardTitle className="text-slate-900">Редактирование узла</CardTitle>
          </CardHeader>

          <CardContent className="space-y-6 pt-6">
            <NodeFormFields
              form={form}
              isWebsiteNode={isWebsiteNode}
              onChange={(patch) => setForm((p) => ({ ...p, ...patch }))}
            />

            <PropertiesSection
              properties={properties}
              draggedKey={draggedKey}
              onAdd={addPropertyRow}
              onUpdate={updateProperty}
              onDelete={deleteProperty}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDrop={(targetKey) => handleDrop(targetKey, properties, setProperties)}
            />
          </CardContent>

          <NodeFooter
            productId={productId}
            saving={saving}
            loading={loading}
            onSave={saveAll}
          />
        </Card>
      )}
    </div>
  );

  // ─── Mobile vs Desktop rendering ────────────────────────────────────────
  if (isMobile) {
    return (
      <div className="min-h-screen bg-slate-50 p-6">
        {content}
      </div>
    );
  }

  return (
    <Dialog open onOpenChange={(open) => !open && router.push(`/map/${mapId}`)}>
      <DialogContent className="max-w-4xl bg-white text-black max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-slate-900">Редактирование узла</DialogTitle>
          <DialogDescription className="text-slate-600">
            Название, тип и свойства. Изменения сохраняются автоматически.
          </DialogDescription>
        </DialogHeader>
        {content}
      </DialogContent>
    </Dialog>
  );
}
