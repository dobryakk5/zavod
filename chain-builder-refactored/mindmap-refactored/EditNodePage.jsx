'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Save, ExternalLink } from 'lucide-react';

// Shared components
import { 
  Alert, 
  LoadingSpinner, 
  SaveButton,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter
} from '@/shared/components';

// Shared hooks
import { 
  useAutoSave, 
  useIsMobile, 
  useTemporaryMessage,
  useDragAndDrop 
} from '@/shared/hooks';

// MindMap specific components
import { NodeForm } from './components/NodeForm';
import { PropertiesList } from './components/PropertiesList';

// MindMap utilities
import {
  toDrafts,
  extractProductId,
  isWebsiteNode as checkIsWebsiteNode,
  getWebsiteTitle,
  getWebsiteUrl,
  preparePropertiesForSave,
  validateProperties
} from './utils';

// API
import { mindMapsApi } from '@/lib/api/mindmaps';

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

export default function EditNodePage() {
  const { mapId, nodeId } = useParams();
  const router = useRouter();
  const isMobile = useIsMobile();

  // State
  const [mapData, setMapData] = useState(null);
  const [form, setForm] = useState({ title: '', typeLabel: '', meta: {} });
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  
  // Temporary messages
  const [successMessage, showSuccess] = useTemporaryMessage(3000);

  // Drag & Drop
  const {
    draggedItem: draggedProp,
    handleDragStart,
    handleDragEnd,
    handleDrop,
  } = useDragAndDrop(properties, setProperties);

  // Derived data
  const node = useMemo(
    () => mapData?.nodes.find((n) => String(n.id) === String(nodeId)),
    [mapData?.nodes, nodeId]
  );

  const productId = useMemo(
    () => node?.meta ? extractProductId(node.meta) : null,
    [node?.meta]
  );

  const isWebsiteNode = useMemo(
    () => node?.meta ? checkIsWebsiteNode(node.meta) : false,
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

      const meta = (currentNode.meta ?? {});
      const websiteTitle = getWebsiteTitle(meta, currentNode.text);
      const websiteUrl = getWebsiteUrl(meta);

      setForm({
        title: checkIsWebsiteNode(meta) ? websiteTitle : currentNode.text,
        typeLabel: checkIsWebsiteNode(meta) 
          ? websiteUrl 
          : (meta.metric_type || ''),
        meta
      });

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
    async (next) => {
      if (!mapId || !nodeId) return;
      if (!next.title.trim()) return;
      
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

  useAutoSave(
    { title: form.title, typeLabel: form.typeLabel }, 
    saveNodeNow, 
    500
  );

  // ─── Property management ────────────────────────────────────────────────
  const updateProperty = (key, patch) => {
    setProperties((prev) => 
      prev.map((p) => (p.key === key ? { ...p, ...patch } : p))
    );
  };

  const deleteProperty = (key) => {
    setProperties((prev) => 
      prev.map((p) => (p.key === key ? { ...p, deleted: true } : p))
    );
  };

  const addProperty = () => {
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

    // Validate
    const validation = validateProperties(properties);
    if (!validation.valid) {
      setError(validation.error);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const { toCreate, toUpdate, toDelete } = preparePropertiesForSave(
        properties, 
        nodeId
      );

      // Delete properties
      if (toDelete.length > 0) {
        await mindMapsApi.deleteProperties(toDelete);
      }

      // Update existing properties
      if (toUpdate.length > 0) {
        await mindMapsApi.updateProperties(toUpdate);
      }

      // Create new properties
      if (toCreate.length > 0) {
        await mindMapsApi.createProperties(toCreate);
      }

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
  if (loading) {
    return <LoadingSpinner text="Загрузка узла..." />;
  }

  const content = (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3">
        <Link 
          href={`/map/${mapId}`}
          className="inline-flex items-center gap-2 text-slate-700 hover:bg-slate-100 px-3 py-1.5 rounded-lg text-sm"
        >
          <ArrowLeft className="h-4 w-4" />
          Назад к карте
        </Link>

        {saving && (
          <span className="text-sm text-slate-500 animate-pulse">
            💾 Сохранение...
          </span>
        )}
      </div>

      {/* Alerts */}
      {error && <Alert variant="error">{error}</Alert>}
      {successMessage && <Alert variant="success">{successMessage}</Alert>}

      {/* Main card */}
      {node && (
        <Card>
          <CardHeader>
            <CardTitle>Редактирование узла</CardTitle>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Node form */}
            <NodeForm
              form={form}
              onChange={setForm}
              isWebsiteNode={isWebsiteNode}
            />

            {/* Properties */}
            <PropertiesList
              properties={properties}
              onUpdate={updateProperty}
              onDelete={deleteProperty}
              onAdd={addProperty}
              draggedProp={draggedProp}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDrop={handleDrop}
            />
          </CardContent>

          <CardFooter className="flex items-center justify-between">
            {productId ? (
              <Link 
                href={`/product/${productId}`}
                className="inline-flex items-center gap-2 text-slate-700 hover:bg-white px-3 py-1.5 rounded-lg text-sm"
              >
                Открыть продукт
                <ExternalLink className="h-3 w-3" />
              </Link>
            ) : (
              <span />
            )}
            
            <SaveButton
              onClick={saveAll}
              saving={saving}
              disabled={loading}
            >
              <Save className="h-4 w-4" />
              {saving ? 'Сохранение...' : 'Сохранить все'}
            </SaveButton>
          </CardFooter>
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="max-w-4xl w-full bg-white text-black max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="text-xl font-semibold text-slate-900">Редактирование узла</h2>
          <p className="text-sm text-slate-600 mt-1">
            Название, тип и свойства. Изменения сохраняются автоматически.
          </p>
        </div>
        <div className="p-6">
          {content}
        </div>
      </div>
    </div>
  );
}
