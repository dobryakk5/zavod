'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useParams, useRouter } from 'next/navigation';
import type { Editor } from '@tiptap/react';
import { generateHTML } from '@tiptap/html';
import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  GripVertical,
  ImageIcon,
  Pencil,
  Play,
  Plus,
  Save,
  Settings,
  Trash2,
  X,
} from 'lucide-react';
import TipTapEditor from '@/components/kb/TipTapEditor';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api';
import { clientApi } from '@/lib/api/client';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';
import {
  CLIENT_PAGE_BLOCK_LIBRARY,
  createDefaultClientPageTemplateConfig,
  normalizeClientPageTemplateConfig,
  resolveClientPageVideoSource,
  type ClientPageBlockKey,
  type ClientPageHeroConfig,
  type ClientPageImageBlockConfig,
  type ClientPageTemplateConfig,
  type ClientPageVideoBlockConfig,
} from '@/lib/client-page-template';
import {
  buildSitePagePublicPath,
  findClientSitePageById,
  normalizeClientSitePagesConfig,
  validateSingleSitePageSlug,
  type ClientSitePage,
} from '@/lib/client-site-pages';
import type { ClientProduct, ClientSettings } from '@/lib/types';

// ─── Local block types ────────────────────────────────────────────────────────

type ImageBlockConfig = ClientPageImageBlockConfig;
type VideoBlockConfig = ClientPageVideoBlockConfig;
type TextBlockContent = Record<string, unknown>;

type LocalBlockData = {
  images: ImageBlockConfig[];
  videos: VideoBlockConfig[];
  textBlocks: TextBlockContent[];
};

const DEFAULT_IMAGE_CONFIG: ImageBlockConfig = {
  url: '', alt: '', caption: '', fit: 'cover', max_height: 420,
};

const DEFAULT_VIDEO_CONFIG: VideoBlockConfig = {
  url: '', caption: '',
};

type ExtendedBlockKey = ClientPageBlockKey;
type CanvasBlockId = string;
type CanvasBlockInstance = {
  id: CanvasBlockId;
  key: ExtendedBlockKey;
  repeatIndex: number | null;
};

const REPEATABLE_BLOCK_KEYS = new Set<ExtendedBlockKey>(['image', 'video', 'custom_content']);

const isRepeatableBlockKey = (key: ExtendedBlockKey): boolean => REPEATABLE_BLOCK_KEYS.has(key);

const makeCanvasBlockId = (key: ExtendedBlockKey, repeatIndex: number | null): CanvasBlockId => {
  if (repeatIndex === null || !isRepeatableBlockKey(key)) {
    return key;
  }
  return `${key}:${repeatIndex}`;
};

const parseCanvasBlockId = (id: CanvasBlockId): CanvasBlockInstance => {
  const [rawKey, rawIndex] = id.split(':');
  if (rawKey === 'image' || rawKey === 'video' || rawKey === 'custom_content') {
    const parsedIndex = Number(rawIndex);
    return {
      id,
      key: rawKey,
      repeatIndex: Number.isFinite(parsedIndex) && parsedIndex >= 0 ? parsedIndex : 0,
    };
  }
  return { id, key: rawKey as ExtendedBlockKey, repeatIndex: null };
};

const cloneTiptapDoc = (value: Record<string, unknown>): Record<string, unknown> => {
  try {
    return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
  } catch {
    return normalizeTiptapContent(value);
  }
};

// ─── Video URL resolver ───────────────────────────────────────────────────────

function resolveVideoEmbed(url: string): { type: 'iframe' | 'video' | 'unknown'; src: string } {
  const resolved = resolveClientPageVideoSource(url);
  if (resolved.type === 'youtube' || resolved.type === 'vimeo') {
    return { type: 'iframe', src: resolved.embed_url };
  }
  if (resolved.type === 'direct') {
    return { type: 'video', src: resolved.embed_url };
  }
  return { type: 'unknown', src: url };
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TEMPLATE_FIELDS: Array<{ token: string; label: string }> = [
  { token: '{{brand_name}}',     label: 'Название бренда' },
  { token: '{{niche}}',          label: 'Ниша' },
  { token: '{{product_name}}',   label: 'Название продукта' },
  { token: '{{product_price}}',  label: 'Цена продукта' },
  { token: '{{product_service}}',label: 'Продукт/услуга (из настроек)' },
];

const EMPTY_TIPTAP_DOC: Record<string, unknown> = {
  type: 'doc', content: [{ type: 'paragraph', content: [] }],
};

// ─── Pure helpers ─────────────────────────────────────────────────────────────

const normalizeTiptapContent = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...EMPTY_TIPTAP_DOC };
  return value as Record<string, unknown>;
};

const replaceTemplateTokens = (input: string, values: Record<string, string>) =>
  input.replace(/\{\{([a-zA-Z0-9_]+)\}\}/g, (_, key: string) => values[key] ?? `{{${key}}}`);

const replaceTemplateTokensInTiptapNode = (node: unknown, values: Record<string, string>): unknown => {
  if (typeof node === 'string') return replaceTemplateTokens(node, values);
  if (Array.isArray(node)) return node.map((item) => replaceTemplateTokensInTiptapNode(item, values));
  if (!node || typeof node !== 'object') return node;
  const src = node as Record<string, unknown>;
  const next: Record<string, unknown> = {};
  Object.entries(src).forEach(([k, v]) => {
    next[k] = k === 'text' && typeof v === 'string'
      ? replaceTemplateTokens(v, values)
      : replaceTemplateTokensInTiptapNode(v, values);
  });
  return next;
};

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value); return;
  }
  const el = Object.assign(document.createElement('textarea'), {
    value, style: 'position:fixed;top:-9999px',
  });
  document.body.appendChild(el);
  el.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(el);
  if (!ok) throw new Error('Copy failed');
};

const isProductActive = (p: ClientProduct) => !p?.status || p.status === 'active';

const resolveProductPrice = (product: ClientProduct): number | null => {
  const pkg = Array.isArray(product?.packages)
    ? product.packages.find((i) => typeof i?.price === 'number' && Number.isFinite(i.price))
    : undefined;
  return typeof pkg?.price === 'number' ? pkg.price : null;
};

// ─── Block picker modal ───────────────────────────────────────────────────────

type CombinedBlockMeta = { key: ExtendedBlockKey; label: string; description: string };

function BlockPickerModal({
  inactiveBlocks,
  onAdd,
  onClose,
}: { inactiveBlocks: CombinedBlockMeta[]; onAdd: (k: ExtendedBlockKey) => void; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="w-[480px] rounded-2xl bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <div className="text-sm font-semibold">Добавить блок</div>
            <div className="text-xs text-muted-foreground mt-0.5">Выберите тип блока</div>
          </div>
          <button type="button" onClick={onClose}
            className="rounded-lg p-1.5 hover:bg-slate-100 text-slate-400">
            <X className="h-4 w-4" />
          </button>
        </div>

        {inactiveBlocks.length === 0 ? (
          <div className="p-5 text-sm text-muted-foreground text-center">
            Все доступные блоки уже добавлены.
          </div>
        ) : (
          <div className="p-3 space-y-1.5 max-h-[60vh] overflow-auto">
            {inactiveBlocks.map((block) => (
              <button key={block.key} type="button"
                onClick={() => { onAdd(block.key); onClose(); }}
                className="flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left
                           hover:bg-slate-50 hover:border-slate-300 transition-colors">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                  {block.key === 'image' ? <ImageIcon className="h-4 w-4" />
                   : block.key === 'video' ? <Play className="h-4 w-4" />
                   : <Plus className="h-4 w-4" />}
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium">{block.label}</div>
                  <div className="text-xs text-muted-foreground truncate">{block.description}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Add block divider ────────────────────────────────────────────────────────

function AddBlockDivider({ onClick }: { onClick: () => void }) {
  const [hov, setHov] = useState(false);
  return (
    <div className="relative flex h-8 items-center justify-center cursor-pointer"
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)} onClick={onClick}>
      <div className={`absolute inset-x-0 h-0.5 transition-colors ${hov ? 'bg-blue-400' : 'bg-transparent'}`} />
      {hov && (
        <div className="relative z-10 flex items-center gap-1.5 rounded-full bg-blue-500
                        px-3 py-1 text-xs font-semibold text-white shadow-md">
          <Plus className="h-3 w-3" /> Добавить блок
        </div>
      )}
    </div>
  );
}

// ─── Sortable canvas block ────────────────────────────────────────────────────

function SortableCanvasBlock({
  blockId, blockKey, label, isSelected, isFirst, isLast, canRemove,
  onSelect, onRemove, onMoveUp, onMoveDown, children,
}: {
  blockId: CanvasBlockId;
  blockKey: ExtendedBlockKey;
  label: string;
  isSelected: boolean;
  isFirst: boolean; isLast: boolean;
  canRemove: boolean;
  onSelect: () => void; onRemove: () => void;
  onMoveUp: () => void; onMoveDown: () => void;
  children: React.ReactNode;
}) {
  const [hov, setHov] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: blockId });

  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`relative ${isDragging ? 'z-50 opacity-60 shadow-2xl' : ''}`}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}>

      <div className={`transition-all duration-150 ${
        isSelected ? 'outline outline-2 outline-blue-500'
        : hov ? 'outline outline-1 outline-blue-300' : ''}`}>
        {children}
      </div>

      {(hov || isSelected) && !isDragging && (
        <div className="absolute right-3 top-3 z-20 flex items-center gap-1">
          <span className="rounded-md bg-slate-800/80 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm">
            {label}
          </span>
          <button type="button" title="Настроить" onClick={onSelect}
            className={`flex h-7 w-7 items-center justify-center rounded-md shadow transition-colors ${
              isSelected ? 'bg-blue-500 text-white'
                : 'bg-white text-slate-600 hover:bg-slate-50 border border-slate-200'}`}>
            {isSelected ? <X className="h-3.5 w-3.5" /> : <Settings className="h-3.5 w-3.5" />}
          </button>
          <button type="button" title="Вверх" onClick={onMoveUp} disabled={isFirst}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200
                       bg-white text-slate-600 shadow hover:bg-slate-50 disabled:opacity-30">
            <ChevronUp className="h-3.5 w-3.5" />
          </button>
          <button type="button" title="Вниз" onClick={onMoveDown} disabled={isLast}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200
                       bg-white text-slate-600 shadow hover:bg-slate-50 disabled:opacity-30">
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          <button type="button" title="Перетащить"
            className="flex h-7 w-7 cursor-grab items-center justify-center rounded-md border
                       border-slate-200 bg-white text-slate-600 shadow active:cursor-grabbing"
            {...attributes} {...listeners}>
            <GripVertical className="h-3.5 w-3.5" />
          </button>
          {canRemove && (
            <button type="button" title="Удалить" onClick={onRemove}
              className="flex h-7 w-7 items-center justify-center rounded-md border border-red-200
                         bg-white text-red-500 shadow hover:bg-red-50">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Settings panel ───────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  );
}

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-slate-50">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="rounded accent-blue-500" />
      {label}
    </label>
  );
}

function SettingsPanel({
  blockId, blockKey, blockLabel, repeatIndex, config, localData,
  activeProducts, selectedProduct, selectedProductPriceLabel,
  templateFields, editorRef,
  onUpdateHero, onUpdateConfig, onUpdateImage, onUpdateVideo,
  onUpdateTextContent, onInsertTemplateField, onCopyToken, onClose,
}: {
  blockId: CanvasBlockId;
  blockKey: ExtendedBlockKey;
  blockLabel: string;
  repeatIndex: number | null;
  config: ClientPageTemplateConfig; localData: LocalBlockData;
  activeProducts: ClientProduct[]; selectedProduct: ClientProduct | null;
  selectedProductPriceLabel: string;
  templateFields: typeof TEMPLATE_FIELDS;
  editorRef: React.MutableRefObject<Editor | null>;
  onUpdateHero: (p: Partial<ClientPageHeroConfig>) => void;
  onUpdateConfig: (p: Partial<ClientPageTemplateConfig>) => void;
  onUpdateImage: (index: number, p: Partial<ImageBlockConfig>) => void;
  onUpdateVideo: (index: number, p: Partial<VideoBlockConfig>) => void;
  onUpdateTextContent: (index: number, v: Record<string, unknown>) => void;
  onInsertTemplateField: (t: string) => void;
  onCopyToken: (t: string) => void;
  onClose: () => void;
}) {
  const activeImage = repeatIndex === null
    ? null
    : (localData.images[repeatIndex] || { ...DEFAULT_IMAGE_CONFIG });
  const activeVideo = repeatIndex === null
    ? null
    : (localData.videos[repeatIndex] || { ...DEFAULT_VIDEO_CONFIG });
  const activeTextContent = repeatIndex === null
    ? null
    : normalizeTiptapContent(localData.textBlocks[repeatIndex]);

  return (
    <div className="flex h-full flex-col border-l bg-white">
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Pencil className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold">{blockLabel}</span>
        </div>
        <button type="button" onClick={onClose}
          className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── HERO ── */}
        {blockKey === 'hero' && (
          <>
            <Field label="Заголовок">
              <textarea className="input-base h-20 resize-none w-full" value={config.hero.title}
                onChange={(e) => onUpdateHero({ title: e.target.value })} />
            </Field>
            <Field label="Подзаголовок">
              <textarea className="input-base h-20 resize-none w-full" value={config.hero.subtitle}
                onChange={(e) => onUpdateHero({ subtitle: e.target.value })} />
            </Field>
            <div className="flex gap-2">
              <Checkbox label="Подзаголовок" checked={config.hero.show_subtitle}
                onChange={(v) => onUpdateHero({ show_subtitle: v })} />
              <Checkbox label="Кнопка" checked={config.hero.show_button}
                onChange={(v) => onUpdateHero({ show_button: v })} />
            </div>
            {config.hero.show_button && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Текст кнопки">
                  <input className="input-base w-full" value={config.hero.button_text}
                    onChange={(e) => onUpdateHero({ button_text: e.target.value })} />
                </Field>
                <Field label="Ссылка кнопки">
                  <input className="input-base w-full" value={config.hero.button_url}
                    onChange={(e) => onUpdateHero({ button_url: e.target.value })} />
                </Field>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Выравнивание">
                <select className="input-base w-full" value={config.hero.align}
                  onChange={(e) => onUpdateHero({ align: e.target.value as ClientPageHeroConfig['align'] })}>
                  <option value="left">Слева</option>
                  <option value="center">По центру</option>
                  <option value="right">Справа</option>
                </select>
              </Field>
              <Field label="Цвет текста">
                <div className="flex gap-2">
                  <input type="color" className="h-9 w-10 shrink-0 cursor-pointer rounded border p-0.5"
                    value={config.hero.text_color}
                    onChange={(e) => onUpdateHero({ text_color: e.target.value })} />
                  <input className="input-base flex-1 min-w-0" value={config.hero.text_color}
                    onChange={(e) => onUpdateHero({ text_color: e.target.value })} />
                </div>
              </Field>
            </div>
            <Field label="Фон (CSS цвет или gradient)">
              <input className="input-base w-full" value={config.hero.background}
                onChange={(e) => onUpdateHero({ background: e.target.value })} />
            </Field>
            <Field label="Изображение фона (URL)">
              <input className="input-base w-full" value={config.hero.image_url}
                onChange={(e) => onUpdateHero({ image_url: e.target.value })} />
            </Field>
            {config.hero.image_url && (
              <Field label={`Затемнение: ${config.hero.overlay_opacity}%`}>
                <input type="range" min={0} max={100} value={config.hero.overlay_opacity}
                  onChange={(e) => onUpdateHero({ overlay_opacity: Number(e.target.value) })}
                  className="w-full accent-blue-500" />
              </Field>
            )}
          </>
        )}

        {/* ── IMAGE ── */}
        {blockKey === 'image' && activeImage && repeatIndex !== null && (
          <>
            <Field label="URL картинки">
              <input className="input-base w-full" placeholder="https://example.com/photo.jpg"
                value={activeImage.url}
                onChange={(e) => onUpdateImage(repeatIndex, { url: e.target.value })} />
            </Field>

            {activeImage.url && (
              <div className="overflow-hidden rounded-xl border bg-slate-50">
                <Image
                  src={activeImage.url}
                  alt={activeImage.alt || 'preview'}
                  width={1600}
                  height={900}
                  unoptimized
                  loader={({ src }) => src}
                  className="w-full"
                  style={{ maxHeight: Math.min(activeImage.max_height, 360), objectFit: activeImage.fit }}
                />
              </div>
            )}

            <Field label="Alt-текст (для SEO)">
              <input className="input-base w-full" placeholder="Описание картинки"
                value={activeImage.alt}
                onChange={(e) => onUpdateImage(repeatIndex, { alt: e.target.value })} />
            </Field>

            <Field label="Подпись под картинкой">
              <input className="input-base w-full" placeholder="Необязательно"
                value={activeImage.caption}
                onChange={(e) => onUpdateImage(repeatIndex, { caption: e.target.value })} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Отображение">
                <select className="input-base w-full" value={activeImage.fit}
                  onChange={(e) => onUpdateImage(repeatIndex, { fit: e.target.value as 'cover' | 'contain' })}>
                  <option value="cover">Обрезать (cover)</option>
                  <option value="contain">Вписать (contain)</option>
                </select>
              </Field>
              <Field label={`Макс. высота: ${activeImage.max_height}px`}>
                <input type="range" min={120} max={900} step={20}
                  value={activeImage.max_height}
                  onChange={(e) => onUpdateImage(repeatIndex, { max_height: Number(e.target.value) })}
                  className="w-full accent-blue-500 mt-2" />
              </Field>
            </div>
          </>
        )}

        {/* ── VIDEO ── */}
        {blockKey === 'video' && activeVideo && repeatIndex !== null && (
          <>
            <Field label="Ссылка на видео">
              <input className="input-base w-full"
                placeholder="YouTube, Vimeo или прямая .mp4 ссылка"
                value={activeVideo.url}
                onChange={(e) => onUpdateVideo(repeatIndex, { url: e.target.value })} />
            </Field>

            {activeVideo.url && (() => {
              const r = resolveVideoEmbed(activeVideo.url);
              return (
                <div className="overflow-hidden rounded-xl border bg-black aspect-video">
                  {r.type === 'iframe' && (
                    <iframe src={r.src} className="h-full w-full"
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope"
                      allowFullScreen />
                  )}
                  {r.type === 'video' && <video src={r.src} controls className="h-full w-full" />}
                  {r.type === 'unknown' && (
                    <div className="flex h-full items-center justify-center text-xs text-slate-400 p-4 text-center">
                      Не удалось определить формат. Проверьте ссылку.
                    </div>
                  )}
                </div>
              );
            })()}

            <div className="rounded-lg border bg-slate-50 p-3 text-xs text-muted-foreground space-y-1">
              <div className="font-medium text-foreground mb-1">Поддерживаемые форматы:</div>
              <div>• YouTube: youtube.com/watch?v=… или youtu.be/…</div>
              <div>• Vimeo: vimeo.com/…</div>
              <div>• Прямая ссылка: файл .mp4, .webm, .ogg</div>
            </div>

            <Field label="Подпись под видео">
              <input className="input-base w-full" placeholder="Необязательно"
                value={activeVideo.caption}
                onChange={(e) => onUpdateVideo(repeatIndex, { caption: e.target.value })} />
            </Field>
          </>
        )}

        {/* ── PRODUCT ── */}
        {blockKey === 'product' && (
          <>
            <Field label="Продукт">
              <Select
                value={config.selected_product_id ? String(config.selected_product_id) : 'auto'}
                onValueChange={(v) =>
                  onUpdateConfig({ selected_product_id: v === 'auto' ? null : Number(v) })
                }
              >
                <SelectTrigger><SelectValue placeholder="Выберите продукт" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Авто (первый активный)</SelectItem>
                  {activeProducts.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.name || `Продукт #${p.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <div className="rounded-lg border bg-slate-50 p-3 text-xs space-y-1 text-muted-foreground">
              <div>Выбран: <span className="font-medium text-foreground">{selectedProduct?.name || '—'}</span></div>
              <div>Цена: <span className="font-medium text-foreground">{selectedProductPriceLabel}</span></div>
            </div>
          </>
        )}

        {/* ── CUSTOM CONTENT ── */}
        {blockKey === 'custom_content' && activeTextContent && repeatIndex !== null && (
          <>
            <div className="space-y-2">
              <div className="text-xs font-medium text-muted-foreground">Шаблонные поля</div>
              {templateFields.map((field) => (
                <div key={field.token} className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-xs font-medium">{field.label}</div>
                    <div className="truncate text-xs text-muted-foreground">{field.token}</div>
                  </div>
                  <div className="flex gap-1">
                    <Button type="button" variant="ghost" size="sm"
                      onClick={() => onInsertTemplateField(field.token)}>Вставить</Button>
                    <Button type="button" variant="ghost" size="sm"
                      onClick={() => void onCopyToken(field.token)}>Копия</Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-xl border overflow-hidden">
              <TipTapEditor
                key={`${blockId}-editor`}
                initialContent={activeTextContent}
                onChange={(value) => onUpdateTextContent(repeatIndex, value)}
                onEditorReady={(editor) => { editorRef.current = editor; }}
                autoSave={false} showToolbar
                placeholder="Напишите описание, оффер, FAQ..."
              />
            </div>
          </>
        )}

        {/* ── READ-ONLY ── */}
        {['header', 'events', 'booking', 'purchases', 'planned_meetings', 'referrals'].includes(blockKey) && (
          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground text-center">
            Этот блок не требует настроек — он автоматически отображает данные клиента.
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Block canvas renders ─────────────────────────────────────────────────────

function renderBlockContent({
  blockKey, repeatIndex, config, localData, displayName, niche,
  selectedProduct, selectedProductPriceLabel, previewValues,
}: {
  blockKey: ExtendedBlockKey;
  repeatIndex: number | null;
  config: ClientPageTemplateConfig;
  localData: LocalBlockData;
  displayName: string; niche: string; selectedProduct: ClientProduct | null;
  selectedProductPriceLabel: string;
  previewValues: Record<string, string>;
}): React.ReactNode {

  if (blockKey === 'image') {
    const img = repeatIndex === null
      ? null
      : (localData.images[repeatIndex] || { ...DEFAULT_IMAGE_CONFIG });
    if (!img) {
      return null;
    }
    if (!img.url) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-16 bg-slate-50 text-muted-foreground">
          <ImageIcon className="h-10 w-10 opacity-25" />
          <div className="text-sm">Вставьте ссылку на картинку в настройках блока</div>
        </div>
      );
    }
    return (
      <div className="w-full">
        <div className="w-full overflow-hidden bg-slate-100" style={{ maxHeight: img.max_height }}>
          <Image
            src={img.url}
            alt={img.alt || 'Изображение'}
            width={1600}
            height={900}
            unoptimized
            loader={({ src }) => src}
            className="w-full"
            style={{ objectFit: img.fit, maxHeight: img.max_height }}
          />
        </div>
        {img.caption && (
          <div className="px-8 py-2 text-center text-sm text-muted-foreground">{img.caption}</div>
        )}
      </div>
    );
  }

  if (blockKey === 'video') {
    const vid = repeatIndex === null
      ? null
      : (localData.videos[repeatIndex] || { ...DEFAULT_VIDEO_CONFIG });
    if (!vid) {
      return null;
    }
    if (!vid.url) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 py-16 bg-slate-50 text-muted-foreground">
          <Play className="h-10 w-10 opacity-25" />
          <div className="text-sm">Вставьте ссылку на видео в настройках блока</div>
        </div>
      );
    }
    const r = resolveVideoEmbed(vid.url);
    return (
      <div className="w-full px-8 py-8">
        <div className="overflow-hidden rounded-2xl bg-black aspect-video shadow-lg">
          {r.type === 'iframe' && (
            <iframe src={r.src} className="h-full w-full"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope"
              allowFullScreen />
          )}
          {r.type === 'video' && <video src={r.src} controls className="h-full w-full" />}
          {r.type === 'unknown' && (
            <div className="flex h-full items-center justify-center text-sm text-slate-400 p-6 text-center">
              Не удалось определить формат. Проверьте ссылку.
            </div>
          )}
        </div>
        {vid.caption && (
          <div className="mt-3 text-center text-sm text-muted-foreground">{vid.caption}</div>
        )}
      </div>
    );
  }

  if (blockKey === 'hero') {
    const t  = replaceTemplateTokens(config.hero.title, previewValues);
    const s  = replaceTemplateTokens(config.hero.subtitle, previewValues);
    const bt = replaceTemplateTokens(config.hero.button_text, previewValues);
    const al = config.hero.align === 'center' ? 'items-center text-center'
             : config.hero.align === 'right'  ? 'items-end text-right' : 'items-start text-left';
    return (
      <div className="relative min-h-[320px] px-8 py-16 flex items-center"
        style={{ background: config.hero.image_url ? undefined : config.hero.background }}>
        {config.hero.image_url && (
          <>
            <div className="absolute inset-0"
              style={{ backgroundImage: `url(${config.hero.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
            <div className="absolute inset-0"
              style={{ background: config.hero.background, opacity: config.hero.overlay_opacity / 100 }} />
          </>
        )}
        <div className={`relative z-10 flex w-full max-w-2xl flex-col gap-4 ${al}`}>
          <h2 className="whitespace-pre-line text-4xl font-bold leading-tight"
            style={{ color: config.hero.text_color }}>
            {t || 'Заголовок Hero'}
          </h2>
          {config.hero.show_subtitle && (
            <p className="whitespace-pre-line text-lg opacity-90"
              style={{ color: config.hero.text_color }}>{s || 'Подзаголовок'}</p>
          )}
          {config.hero.show_button && (
            <span className="inline-flex w-fit rounded-xl bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow">
              {bt || 'Кнопка'}
            </span>
          )}
        </div>
      </div>
    );
  }

  if (blockKey === 'header') return (
    <div className="border-b px-8 py-5">
      <div className="text-lg font-semibold">{displayName}</div>
      <div className="text-sm text-muted-foreground">{niche}</div>
    </div>
  );

  if (blockKey === 'product') return (
    <div className="px-8 py-10">
      <div className="rounded-2xl border p-6 max-w-md">
        <div className="flex items-baseline justify-between gap-3 mb-2">
          <div className="text-base font-semibold">
            {selectedProduct?.name?.trim() || 'Продукт не выбран'}
          </div>
          <div className="text-base font-bold whitespace-nowrap">{selectedProductPriceLabel}</div>
        </div>
        <div className="mb-4 text-sm text-muted-foreground">
          {(selectedProduct?.short_description || '').trim() || 'Описание продукта появится здесь.'}
        </div>
        <button type="button" className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-medium text-white">
          Купить
        </button>
      </div>
    </div>
  );

  if (blockKey === 'events') return (
    <div className="px-8 py-8">
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Здесь будет список опубликованных мероприятий с переходом в карточку мероприятия.
      </div>
    </div>
  );

  if (blockKey === 'custom_content') return (
    <div className="px-8 py-8">
      {(() => {
        if (repeatIndex === null) {
          return (
            <div className="rounded-xl border border-dashed py-8 text-center text-sm text-muted-foreground">
              Не удалось определить текстовый блок
            </div>
          );
        }
        const source = normalizeTiptapContent(localData.textBlocks[repeatIndex]);
        try {
          const replaced = replaceTemplateTokensInTiptapNode(source, previewValues) as Record<string, unknown>;
          const html = generateHTML(replaced, createKbExtensions());
          if (!html) {
            return (
              <div className="rounded-xl border border-dashed py-8 text-center text-sm text-muted-foreground">
                Откройте настройки блока, чтобы добавить контент
              </div>
            );
          }
          return (
            <div className="tiptap prose prose-slate max-w-none"
              dangerouslySetInnerHTML={{ __html: html }} />
          );
        } catch {
          return (
            <div className="rounded-xl border border-dashed py-8 text-center text-sm text-muted-foreground">
              Ошибка рендера контента
            </div>
          );
        }
      })()}
    </div>
  );

  if (blockKey === 'purchases') return (
    <div className="px-8 py-8">
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Здесь будет список покупок контакта после авторизации.
      </div>
    </div>
  );

  if (blockKey === 'booking') return (
    <div className="px-8 py-8" id="booking">
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Календарь слотов и запись на встречу.
      </div>
    </div>
  );

  if (blockKey === 'planned_meetings') return (
    <div className="px-8 py-8">
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Список запланированных встреч контакта.
      </div>
    </div>
  );

  return (
    <div className="px-8 py-8">
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Раздел рефералов: код приглашения и приглашённые пользователи.
      </div>
    </div>
  );
}

// ─── Main editor ──────────────────────────────────────────────────────────────

export default function ClientPageEditor() {
  const { client_id: rawClientId, page_id: rawPageId } = useParams<{ client_id: string; page_id: string }>();
  const router = useRouter();
  const editorRef = useRef<Editor | null>(null);
  const pageClientId = Number(rawClientId);
  const pageId = String(rawPageId || '').trim();

  const [loading, setLoading]             = useState(true);
  const [saving, setSaving]               = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [saveMessage, setSaveMessage]     = useState<string | null>(null);
  const [clientName, setClientName]       = useState('');
  const [settings, setSettings]           = useState<ClientSettings | null>(null);
  const [sitePages, setSitePages]         = useState<ClientSitePage[]>([]);
  const [pageTitle, setPageTitle]         = useState('');
  const [pageSlug, setPageSlug]           = useState('');
  const [pageMetaDescription, setPageMetaDescription] = useState('');
  const [pageOgImage, setPageOgImage]     = useState('');
  const [products, setProducts]           = useState<ClientProduct[]>([]);
  const [config, setConfig]               = useState<ClientPageTemplateConfig>(createDefaultClientPageTemplateConfig);
  const [publicPageUrl, setPublicPageUrl] = useState('');
  const [localData, setLocalData]         = useState<LocalBlockData>({
    images: [],
    videos: [],
    textBlocks: [],
  });
  const [selectedBlockId, setSelectedBlockId] = useState<CanvasBlockId | null>(null);
  const [showBlockPicker, setShowBlockPicker]   = useState(false);
  const lastSavedSnapshotRef = useRef('');
  const lastAttemptedSnapshotRef = useRef('');
  const autosaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const activeProducts           = useMemo(() => products.filter(isProductActive), [products]);
  const currentPageIndex         = useMemo(
    () => sitePages.findIndex((page) => page.id === pageId),
    [pageId, sitePages],
  );
  const isHomePage               = currentPageIndex === 0;
  const selectedProduct          = useMemo(() => {
    if (config.selected_product_id)
      return activeProducts.find((p) => p.id === config.selected_product_id) || null;
    return activeProducts[0] || null;
  }, [activeProducts, config.selected_product_id]);
  const selectedProductPriceLabel = useMemo(() => {
    if (!selectedProduct) return 'Не выбран';
    const price = resolveProductPrice(selectedProduct);
    return price === null ? 'Цена не указана'
      : new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 }).format(price);
  }, [selectedProduct]);

  const allBlockMeta = useMemo(
    () => new Map<ExtendedBlockKey, CombinedBlockMeta>(
      CLIENT_PAGE_BLOCK_LIBRARY.map((b) => [b.key as ExtendedBlockKey, b]),
    ),
    [],
  );

  const repeatableCountByKey = useMemo(() => ({
    image: localData.images.length,
    video: localData.videos.length,
    custom_content: localData.textBlocks.length,
  }), [localData.images.length, localData.videos.length, localData.textBlocks.length]);

  const displayName    = useMemo(
    () => settings?.brand_name?.trim() || clientName || `Клиент #${pageClientId}`,
    [clientName, pageClientId, settings?.brand_name],
  );
  const niche          = useMemo(() => settings?.niche?.trim() || 'Ниша не указана', [settings?.niche]);
  const previewValues  = useMemo<Record<string, string>>(() => ({
    brand_name:      displayName,
    niche,
    product_name:    (selectedProduct?.name || '').trim(),
    product_price:   selectedProductPriceLabel,
    product_service: (settings?.product_service || '').trim(),
  }), [displayName, niche, selectedProduct, selectedProductPriceLabel, settings?.product_service]);

  const canvasBlockOrder = useMemo<CanvasBlockId[]>(() => {
    const counters = { image: 0, video: 0, custom_content: 0 };
    const result: CanvasBlockId[] = [];

    config.block_order.forEach((key) => {
      if (!config.blocks[key]) {
        return;
      }
      if (key === 'image') {
        result.push(makeCanvasBlockId(key, counters.image));
        counters.image += 1;
        return;
      }
      if (key === 'video') {
        result.push(makeCanvasBlockId(key, counters.video));
        counters.video += 1;
        return;
      }
      if (key === 'custom_content') {
        result.push(makeCanvasBlockId(key, counters.custom_content));
        counters.custom_content += 1;
        return;
      }
      if (!result.includes(key)) {
        result.push(key);
      }
    });

    const requiredImageCount = Math.max(repeatableCountByKey.image, config.blocks.image ? 1 : 0);
    while (counters.image < requiredImageCount) {
      result.push(makeCanvasBlockId('image', counters.image));
      counters.image += 1;
    }
    const requiredVideoCount = Math.max(repeatableCountByKey.video, config.blocks.video ? 1 : 0);
    while (counters.video < requiredVideoCount) {
      result.push(makeCanvasBlockId('video', counters.video));
      counters.video += 1;
    }
    const requiredTextCount = Math.max(repeatableCountByKey.custom_content, config.blocks.custom_content ? 1 : 0);
    while (counters.custom_content < requiredTextCount) {
      result.push(makeCanvasBlockId('custom_content', counters.custom_content));
      counters.custom_content += 1;
    }

    if (!result.includes('hero')) {
      result.unshift('hero');
    }
    return result;
  }, [config.block_order, config.blocks, repeatableCountByKey]);

  const canvasBlockInstances = useMemo<CanvasBlockInstance[]>(
    () => canvasBlockOrder.map((id) => parseCanvasBlockId(id)),
    [canvasBlockOrder],
  );

  const inactiveBlocks = useMemo(() => {
    return CLIENT_PAGE_BLOCK_LIBRARY.filter((block) => {
      const key = block.key as ExtendedBlockKey;
      if (isRepeatableBlockKey(key)) {
        return true;
      }
      return !canvasBlockInstances.some((item) => item.key === key);
    }) as CombinedBlockMeta[];
  }, [canvasBlockInstances]);

  const selectedBlockInstance = useMemo<CanvasBlockInstance | null>(() => {
    if (!selectedBlockId) return null;
    return canvasBlockInstances.find((instance) => instance.id === selectedBlockId) || null;
  }, [canvasBlockInstances, selectedBlockId]);

  const selectedBlockMeta = selectedBlockInstance ? allBlockMeta.get(selectedBlockInstance.key) : null;
  const getEditorSnapshot = useCallback(() => JSON.stringify({
    pageTitle: pageTitle.trim(),
    pageSlug: isHomePage ? '' : pageSlug.trim().toLowerCase(),
    pageMetaDescription: pageMetaDescription.trim(),
    pageOgImage: pageOgImage.trim(),
    config,
    localData,
  }), [config, isHomePage, localData, pageMetaDescription, pageOgImage, pageSlug, pageTitle]);

  // ── Load ──────────────────────────────────────────────────

  const loadEditorData = useCallback(async () => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      setError('Некорректный client_id.'); setLoading(false); return;
    }
    setLoading(true); setError(null);
    try {
      const [info, settingsData, productsData] = await Promise.all([
        clientApi.info(), clientApi.getSettings(), clientProductsApi.list(),
      ]);
      const activeId = Number(info?.client?.id || 0);
      if (!Number.isFinite(activeId) || activeId <= 0) { setError('Не удалось определить текущего клиента.'); return; }
      if (activeId !== pageClientId) { setError(`Редактор /c/${pageClientId}/edit недоступен.`); return; }

      setClientName((info?.client?.name || '').trim());
      setSettings(settingsData);
      setProducts(productsData);

      const normalizedSitePages = normalizeClientSitePagesConfig(settingsData?.client_page_config).site_pages;
      const targetPage = findClientSitePageById(normalizedSitePages, pageId);
      const targetPageIndex = normalizedSitePages.findIndex((page) => page.id === pageId);
      if (!targetPage) {
        setError('Страница не найдена.');
        return;
      }

      setSitePages(normalizedSitePages);
      setPageTitle(targetPage.title);
      setPageSlug(targetPage.slug);
      setPageMetaDescription(targetPage.meta_description || '');
      setPageOgImage(targetPage.og_image || '');

      const rawConfig = normalizeClientPageTemplateConfig(targetPage.template_config);
      const brandName = (settingsData?.brand_name || info?.client?.name || '').trim();
      const nicheVal  = (settingsData?.niche || '').trim();

      const patchedConfig: ClientPageTemplateConfig = {
        ...rawConfig,
        blocks:      { ...rawConfig.blocks, hero: true },
        block_order: rawConfig.block_order.includes('hero')
          ? ['hero', ...rawConfig.block_order.filter((k) => k !== 'hero')]
          : ['hero', ...rawConfig.block_order],
        hero: {
          ...rawConfig.hero,
          title:    rawConfig.hero.title    || brandName || 'Заголовок',
          subtitle: rawConfig.hero.subtitle || nicheVal  || '',
        },
      };
      setConfig(patchedConfig);
      const imagesFromConfig = rawConfig.extra_blocks.images.length > 0
        ? rawConfig.extra_blocks.images.map((item) => ({ ...DEFAULT_IMAGE_CONFIG, ...item }))
        : ((rawConfig.extra_blocks.image.url.trim() || rawConfig.blocks.image)
          ? [{ ...DEFAULT_IMAGE_CONFIG, ...rawConfig.extra_blocks.image }]
          : []);
      const videosFromConfig = rawConfig.extra_blocks.videos.length > 0
        ? rawConfig.extra_blocks.videos.map((item) => ({ ...DEFAULT_VIDEO_CONFIG, ...item }))
        : ((rawConfig.extra_blocks.video.url.trim() || rawConfig.blocks.video)
          ? [{ ...DEFAULT_VIDEO_CONFIG, ...rawConfig.extra_blocks.video }]
          : []);
      const textBlocksFromConfig = rawConfig.extra_blocks.text_blocks.length > 0
        ? rawConfig.extra_blocks.text_blocks.map((item) => normalizeTiptapContent(item))
        : [];
      setLocalData({
        images: imagesFromConfig,
        videos: videosFromConfig,
        textBlocks: textBlocksFromConfig.map((item) => cloneTiptapDoc(item)),
      });
      setSelectedBlockId(null);

      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const relativePublicPath = buildSitePagePublicPath(activeId, targetPage.slug, false);
      setPublicPageUrl(origin ? `${origin}${relativePublicPath}` : relativePublicPath);
      lastSavedSnapshotRef.current = JSON.stringify({
        pageTitle: targetPage.title.trim(),
        pageSlug: targetPageIndex === 0 ? '' : targetPage.slug.trim().toLowerCase(),
        pageMetaDescription: (targetPage.meta_description || '').trim(),
        pageOgImage: (targetPage.og_image || '').trim(),
        config: patchedConfig,
        localData: {
          images: imagesFromConfig,
          videos: videosFromConfig,
          textBlocks: textBlocksFromConfig.map((item) => cloneTiptapDoc(item)),
        },
      });
      lastAttemptedSnapshotRef.current = lastSavedSnapshotRef.current;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { router.push('/login'); return; }
      setError('Не удалось загрузить редактор страницы клиента.');
    } finally { setLoading(false); }
  }, [pageClientId, pageId, router]);

  useEffect(() => { void loadEditorData(); }, [loadEditorData]);

  useEffect(() => {
    if (loading || saving || currentPageIndex < 0) {
      return;
    }

    const snapshot = getEditorSnapshot();
    if (
      !snapshot
      || snapshot === lastSavedSnapshotRef.current
      || snapshot === lastAttemptedSnapshotRef.current
    ) {
      return;
    }

    if (autosaveTimeoutRef.current) {
      clearTimeout(autosaveTimeoutRef.current);
    }

    autosaveTimeoutRef.current = setTimeout(() => {
      void saveTemplate();
    }, 900);

    return () => {
      if (autosaveTimeoutRef.current) {
        clearTimeout(autosaveTimeoutRef.current);
        autosaveTimeoutRef.current = null;
      }
    };
  }, [currentPageIndex, getEditorSnapshot, loading, saving]);

  // ── Actions ───────────────────────────────────────────────

  const reorderByIndices = <T,>(source: T[], indices: number[], fallback: () => T): T[] => {
    return indices.map((index) => source[index] ?? fallback());
  };

  const applyCanvasOrder = useCallback((nextOrder: CanvasBlockId[]) => {
    const parsed = nextOrder.map((id) => parseCanvasBlockId(id));
    const imageIndices: number[] = [];
    const videoIndices: number[] = [];
    const textIndices: number[] = [];
    const seenNonRepeatable = new Set<ExtendedBlockKey>();
    const nextBlockOrder: ExtendedBlockKey[] = [];

    parsed.forEach((item) => {
      if (item.key === 'image') {
        imageIndices.push(item.repeatIndex ?? 0);
        nextBlockOrder.push('image');
        return;
      }
      if (item.key === 'video') {
        videoIndices.push(item.repeatIndex ?? 0);
        nextBlockOrder.push('video');
        return;
      }
      if (item.key === 'custom_content') {
        textIndices.push(item.repeatIndex ?? 0);
        nextBlockOrder.push('custom_content');
        return;
      }
      if (!seenNonRepeatable.has(item.key)) {
        seenNonRepeatable.add(item.key);
        nextBlockOrder.push(item.key);
      }
    });

    if (!nextBlockOrder.includes('hero')) {
      nextBlockOrder.unshift('hero');
    } else {
      const heroIndex = nextBlockOrder.indexOf('hero');
      if (heroIndex > 0) {
        nextBlockOrder.splice(heroIndex, 1);
        nextBlockOrder.unshift('hero');
      }
    }

    setConfig((prev) => {
      const nextBlocks = { ...prev.blocks };
      nextBlocks.hero = true;
      nextBlocks.image = imageIndices.length > 0;
      nextBlocks.video = videoIndices.length > 0;
      nextBlocks.custom_content = textIndices.length > 0;
      nextBlocks.header = nextBlockOrder.includes('header');
      nextBlocks.product = nextBlockOrder.includes('product');
      nextBlocks.events = nextBlockOrder.includes('events');
      nextBlocks.purchases = nextBlockOrder.includes('purchases');
      nextBlocks.booking = nextBlockOrder.includes('booking');
      nextBlocks.planned_meetings = nextBlockOrder.includes('planned_meetings');
      nextBlocks.referrals = nextBlockOrder.includes('referrals');

      return {
        ...prev,
        blocks: nextBlocks,
        block_order: nextBlockOrder,
      };
    });

    setLocalData((prev) => ({
      ...prev,
      images: reorderByIndices(prev.images, imageIndices, () => ({ ...DEFAULT_IMAGE_CONFIG })),
      videos: reorderByIndices(prev.videos, videoIndices, () => ({ ...DEFAULT_VIDEO_CONFIG })),
      textBlocks: reorderByIndices(prev.textBlocks, textIndices, () => cloneTiptapDoc(EMPTY_TIPTAP_DOC)),
    }));
    setSelectedBlockId(null);
  }, []);

  const saveTemplate = async () => {
    if (autosaveTimeoutRef.current) {
      clearTimeout(autosaveTimeoutRef.current);
      autosaveTimeoutRef.current = null;
    }
    lastAttemptedSnapshotRef.current = getEditorSnapshot();
    setSaving(true); setSaveMessage(null);
    try {
      if (currentPageIndex < 0) {
        setError('Страница не найдена.');
        return;
      }

      const normalizedTitle = pageTitle.trim();
      if (!normalizedTitle) {
        setError('Укажите название страницы.');
        return;
      }

      const normalizedSlug = isHomePage ? '' : pageSlug.trim().toLowerCase();
      if (!isHomePage) {
        const slugError = validateSingleSitePageSlug(sitePages, pageId, normalizedSlug);
        if (slugError) {
          setError(slugError);
          return;
        }
      }

      const nextBlockOrder = canvasBlockInstances.map((item) => item.key);
      const requiredImageCount = canvasBlockInstances.filter((item) => item.key === 'image').length;
      const requiredVideoCount = canvasBlockInstances.filter((item) => item.key === 'video').length;
      const requiredTextCount = canvasBlockInstances.filter((item) => item.key === 'custom_content').length;
      const nextBlocks = { ...config.blocks };
      nextBlocks.hero = true;
      nextBlocks.image = requiredImageCount > 0;
      nextBlocks.video = requiredVideoCount > 0;
      nextBlocks.custom_content = requiredTextCount > 0;
      nextBlocks.header = nextBlockOrder.includes('header');
      nextBlocks.product = nextBlockOrder.includes('product');
      nextBlocks.events = nextBlockOrder.includes('events');
      nextBlocks.purchases = nextBlockOrder.includes('purchases');
      nextBlocks.booking = nextBlockOrder.includes('booking');
      nextBlocks.planned_meetings = nextBlockOrder.includes('planned_meetings');
      nextBlocks.referrals = nextBlockOrder.includes('referrals');

      const imagesForSave = Array.from({ length: requiredImageCount }, (_, index) => {
        return { ...DEFAULT_IMAGE_CONFIG, ...(localData.images[index] || {}) };
      });
      const videosForSave = Array.from({ length: requiredVideoCount }, (_, index) => {
        return { ...DEFAULT_VIDEO_CONFIG, ...(localData.videos[index] || {}) };
      });
      const textBlocksForSave = Array.from({ length: requiredTextCount }, (_, index) => {
        return normalizeTiptapContent(localData.textBlocks[index]);
      });

      const configForSave: ClientPageTemplateConfig = {
        ...config,
        blocks: nextBlocks,
        block_order: nextBlockOrder,
        extra_blocks: {
          ...config.extra_blocks,
          image: imagesForSave[0] || { ...DEFAULT_IMAGE_CONFIG },
          video: videosForSave[0] || { ...DEFAULT_VIDEO_CONFIG },
          images: imagesForSave,
          videos: videosForSave,
          text_blocks: textBlocksForSave,
        },
      };

      const nextSitePages = sitePages.map((page, index) => {
        if (page.id !== pageId) {
          return page;
        }
        return {
          ...page,
          title: normalizedTitle,
          slug: index === 0 ? '' : normalizedSlug,
          meta_description: pageMetaDescription.trim(),
          og_image: pageOgImage.trim(),
          template_config: configForSave,
        };
      });

      const updated = await clientApi.updateSettings({
        client_page_config: {
          site_pages: nextSitePages,
        } as unknown as Record<string, unknown>,
      } as Partial<ClientSettings>);
      setSettings(updated);
      const normalizedPages = normalizeClientSitePagesConfig(updated?.client_page_config ?? { site_pages: nextSitePages }).site_pages;
      const refreshedPage = findClientSitePageById(normalizedPages, pageId);
      if (!refreshedPage) {
        setError('Страница была удалена во время сохранения.');
        return;
      }
      setSitePages(normalizedPages);
      setPageTitle(refreshedPage.title);
      setPageSlug(refreshedPage.slug);
      setPageMetaDescription(refreshedPage.meta_description || '');
      setPageOgImage(refreshedPage.og_image || '');
      const normalized = normalizeClientPageTemplateConfig(refreshedPage.template_config);
      setConfig(normalized);
      const nextImages = normalized.extra_blocks.images.length > 0
        ? normalized.extra_blocks.images.map((item) => ({ ...DEFAULT_IMAGE_CONFIG, ...item }))
        : (normalized.blocks.image ? [{ ...DEFAULT_IMAGE_CONFIG, ...normalized.extra_blocks.image }] : []);
      const nextVideos = normalized.extra_blocks.videos.length > 0
        ? normalized.extra_blocks.videos.map((item) => ({ ...DEFAULT_VIDEO_CONFIG, ...item }))
        : (normalized.blocks.video ? [{ ...DEFAULT_VIDEO_CONFIG, ...normalized.extra_blocks.video }] : []);
      const nextTextBlocks = normalized.extra_blocks.text_blocks.length > 0
        ? normalized.extra_blocks.text_blocks.map((item) => normalizeTiptapContent(item))
        : [];
      setLocalData({
        images: nextImages,
        videos: nextVideos,
        textBlocks: nextTextBlocks.map((item) => cloneTiptapDoc(item)),
      });
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const relativePublicPath = buildSitePagePublicPath(pageClientId, refreshedPage.slug, false);
      setPublicPageUrl(origin ? `${origin}${relativePublicPath}` : relativePublicPath);
      lastSavedSnapshotRef.current = JSON.stringify({
        pageTitle: refreshedPage.title.trim(),
        pageSlug: refreshedPage.slug.trim().toLowerCase(),
        pageMetaDescription: (refreshedPage.meta_description || '').trim(),
        pageOgImage: (refreshedPage.og_image || '').trim(),
        config: normalized,
        localData: {
          images: nextImages,
          videos: nextVideos,
          textBlocks: nextTextBlocks.map((item) => cloneTiptapDoc(item)),
        },
      });
      lastAttemptedSnapshotRef.current = lastSavedSnapshotRef.current;
      setSaveMessage('Изменения сохранены.');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { router.push('/login'); return; }
      setError('Не удалось сохранить.');
    } finally { setSaving(false); }
  };

  const insertTemplateField = (token: string) => {
    editorRef.current?.chain().focus().insertContent(token).run();
    setSaveMessage(null);
  };

  const addBlock = (key: ExtendedBlockKey) => {
    if (key === 'image') {
      const nextIndex = localData.images.length;
      setLocalData((prev) => ({ ...prev, images: [...prev.images, { ...DEFAULT_IMAGE_CONFIG }] }));
      setConfig((prev) => ({
        ...prev,
        blocks: { ...prev.blocks, image: true },
        block_order: [...prev.block_order, 'image'],
      }));
      setSelectedBlockId(makeCanvasBlockId('image', nextIndex));
      setSaveMessage(null);
      return;
    }
    if (key === 'video') {
      const nextIndex = localData.videos.length;
      setLocalData((prev) => ({ ...prev, videos: [...prev.videos, { ...DEFAULT_VIDEO_CONFIG }] }));
      setConfig((prev) => ({
        ...prev,
        blocks: { ...prev.blocks, video: true },
        block_order: [...prev.block_order, 'video'],
      }));
      setSelectedBlockId(makeCanvasBlockId('video', nextIndex));
      setSaveMessage(null);
      return;
    }
    if (key === 'custom_content') {
      const nextIndex = localData.textBlocks.length;
      setLocalData((prev) => ({ ...prev, textBlocks: [...prev.textBlocks, cloneTiptapDoc(EMPTY_TIPTAP_DOC)] }));
      setConfig((prev) => ({
        ...prev,
        blocks: { ...prev.blocks, custom_content: true },
        block_order: [...prev.block_order, 'custom_content'],
      }));
      setSelectedBlockId(makeCanvasBlockId('custom_content', nextIndex));
      setSaveMessage(null);
      return;
    }

    setConfig((prev) => prev.blocks[key] ? prev : {
      ...prev,
      blocks: { ...prev.blocks, [key]: true },
      block_order: [...prev.block_order, key],
    });
    setSaveMessage(null);
    setSelectedBlockId(key);
  };

  const removeBlock = (blockId: CanvasBlockId) => {
    const parsed = parseCanvasBlockId(blockId);
    if (parsed.key === 'hero') return;
    const nextOrder = canvasBlockOrder.filter((id) => id !== blockId);
    applyCanvasOrder(nextOrder);
    if (selectedBlockId === blockId) {
      setSelectedBlockId(null);
    }
    setSaveMessage(null);
  };

  const moveBlock = (blockId: CanvasBlockId, dir: -1 | 1) => {
    const index = canvasBlockOrder.indexOf(blockId);
    const target = index + dir;
    if (index < 0 || target < 0 || target >= canvasBlockOrder.length) {
      return;
    }
    const moved = arrayMove(canvasBlockOrder, index, target);
    applyCanvasOrder(moved);
    setSaveMessage(null);
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oi = canvasBlockOrder.indexOf(String(active.id));
    const ni = canvasBlockOrder.indexOf(String(over.id));
    if (oi < 0 || ni < 0) return;
    const moved = arrayMove(canvasBlockOrder, oi, ni);
    applyCanvasOrder(moved);
    setSaveMessage(null);
  };

  const updateHero   = (p: Partial<ClientPageHeroConfig>) => { setConfig((c) => ({ ...c, hero: { ...c.hero, ...p } })); setSaveMessage(null); };
  const updateConfig = (p: Partial<ClientPageTemplateConfig>) => { setConfig((c) => ({ ...c, ...p })); setSaveMessage(null); };
  const updateImage = (index: number, patch: Partial<ImageBlockConfig>) => {
    setLocalData((prev) => {
      const nextImages = [...prev.images];
      while (nextImages.length <= index) {
        nextImages.push({ ...DEFAULT_IMAGE_CONFIG });
      }
      nextImages[index] = { ...DEFAULT_IMAGE_CONFIG, ...nextImages[index], ...patch };
      return { ...prev, images: nextImages };
    });
    setSaveMessage(null);
  };
  const updateVideo = (index: number, patch: Partial<VideoBlockConfig>) => {
    setLocalData((prev) => {
      const nextVideos = [...prev.videos];
      while (nextVideos.length <= index) {
        nextVideos.push({ ...DEFAULT_VIDEO_CONFIG });
      }
      nextVideos[index] = { ...DEFAULT_VIDEO_CONFIG, ...nextVideos[index], ...patch };
      return { ...prev, videos: nextVideos };
    });
    setSaveMessage(null);
  };
  const updateTextContent = (index: number, value: Record<string, unknown>) => {
    const normalized = normalizeTiptapContent(value);
    setLocalData((prev) => {
      const nextTextBlocks = [...prev.textBlocks];
      while (nextTextBlocks.length <= index) {
        nextTextBlocks.push(cloneTiptapDoc(EMPTY_TIPTAP_DOC));
      }
      nextTextBlocks[index] = cloneTiptapDoc(normalized);
      return { ...prev, textBlocks: nextTextBlocks };
    });
    setSaveMessage(null);
  };

  // ── Render ────────────────────────────────────────────────

  if (loading) return (
    <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
      Загрузка редактора...
    </div>
  );

  if (error) return (
    <div className="flex h-screen items-center justify-center p-6">
      <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 max-w-lg">{error}</div>
    </div>
  );

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-100">

      {/* Top bar */}
      <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-white px-4">
        <div className="flex items-center gap-2 min-w-0">
          <Link href={`/c/${pageClientId}/edit`} className="text-xs text-blue-600 hover:underline">
            Все страницы
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-sm font-semibold truncate">{pageTitle || 'Страница'}</span>
          <span className="hidden text-xs text-muted-foreground sm:block">{publicPageUrl || `/c/${pageClientId}`}</span>
        </div>
        <div className="flex-1" />
        {saveMessage && <span className="hidden text-xs text-emerald-600 sm:block">{saveMessage}</span>}
        <Button type="button" variant="ghost" size="sm"
          onClick={() => void copyTextToClipboard(publicPageUrl).then(() => setSaveMessage('Ссылка скопирована.'))}>
          <Copy className="mr-1.5 h-3.5 w-3.5" /> Ссылка
        </Button>
        <Button type="button" variant="outline" size="sm" asChild>
          <Link href={publicPageUrl || `/c/${pageClientId}`} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Открыть
          </Link>
        </Button>
        <Button type="button" size="sm" onClick={() => void saveTemplate()} disabled={saving}>
          <Save className="mr-1.5 h-3.5 w-3.5" />
          {saving ? 'Сохранение...' : 'Сохранить'}
        </Button>
      </header>

      {/* Body */}
      <div className="flex min-h-0 flex-1">

        {/* Canvas */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto my-6 w-full max-w-5xl px-4">
            <div className="mb-4 rounded-2xl border bg-white p-5 shadow-sm">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Название страницы
                  </label>
                  <Input
                    value={pageTitle}
                    onChange={(event) => {
                      setPageTitle(event.target.value);
                      setSaveMessage(null);
                      setError(null);
                    }}
                    placeholder="Например, О компании"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Slug
                  </label>
                  <Input
                    value={isHomePage ? '' : pageSlug}
                    onChange={(event) => {
                      setPageSlug(event.target.value.trim().toLowerCase());
                      setSaveMessage(null);
                      setError(null);
                    }}
                    disabled={isHomePage}
                    placeholder={isHomePage ? 'Главная страница всегда в корне' : 'about'}
                  />
                </div>
                <div className="space-y-2 lg:col-span-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Meta description
                  </label>
                  <Textarea
                    value={pageMetaDescription}
                    onChange={(event) => {
                      setPageMetaDescription(event.target.value);
                      setSaveMessage(null);
                      setError(null);
                    }}
                    placeholder="Краткое описание для поисковиков"
                    rows={3}
                  />
                </div>
                <div className="space-y-2 lg:col-span-2">
                  <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    OG image
                  </label>
                  <Input
                    value={pageOgImage}
                    onChange={(event) => {
                      setPageOgImage(event.target.value);
                      setSaveMessage(null);
                      setError(null);
                    }}
                    placeholder="https://example.com/og-image.jpg"
                  />
                </div>
              </div>
            </div>
            <div className="overflow-hidden rounded-2xl border bg-white shadow-lg">

              {/* Browser chrome */}
              <div className="flex items-center gap-2 border-b bg-slate-50 px-4 py-2.5">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-red-400" />
                  <div className="h-3 w-3 rounded-full bg-yellow-400" />
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                </div>
                <div className="flex-1 rounded-md border bg-white px-3 py-1 text-xs text-slate-400">
                  {publicPageUrl || `/c/${pageClientId}`}
                </div>
              </div>

              {/* Blocks */}
              {canvasBlockOrder.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4">
                  <div className="text-4xl">🧩</div>
                  <div className="text-center">
                    <div className="text-base font-semibold text-slate-700">Страница пустая</div>
                    <div className="mt-1 text-sm text-muted-foreground">Нажмите кнопку, чтобы добавить первый блок</div>
                  </div>
                  <Button type="button" onClick={() => setShowBlockPicker(true)}>
                    <Plus className="mr-2 h-4 w-4" /> Добавить блок
                  </Button>
                </div>
              ) : (
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  <SortableContext items={canvasBlockOrder} strategy={verticalListSortingStrategy}>
                    <div>
                      <AddBlockDivider onClick={() => setShowBlockPicker(true)} />
                      {canvasBlockInstances.map((instance, index) => (
                        <div key={instance.id}>
                          <SortableCanvasBlock
                            blockId={instance.id}
                            blockKey={instance.key}
                            label={`${allBlockMeta.get(instance.key)?.label ?? instance.key}${
                              instance.repeatIndex === null ? '' : ` #${instance.repeatIndex + 1}`
                            }`}
                            isSelected={selectedBlockId === instance.id}
                            isFirst={index === 0}
                            isLast={index === canvasBlockInstances.length - 1}
                            canRemove={instance.key !== 'hero'}
                            onSelect={() => setSelectedBlockId(selectedBlockId === instance.id ? null : instance.id)}
                            onRemove={() => removeBlock(instance.id)}
                            onMoveUp={() => moveBlock(instance.id, -1)}
                            onMoveDown={() => moveBlock(instance.id, 1)}
                          >
                            {renderBlockContent({
                              blockKey: instance.key,
                              repeatIndex: instance.repeatIndex,
                              config, localData, displayName, niche,
                              selectedProduct, selectedProductPriceLabel,
                              previewValues,
                            })}
                          </SortableCanvasBlock>
                          <AddBlockDivider onClick={() => setShowBlockPicker(true)} />
                        </div>
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>
              )}
            </div>
          </div>
        </main>

        {/* Settings panel */}
        {selectedBlockInstance && selectedBlockMeta && (
          <aside className="w-80 shrink-0 overflow-hidden border-l bg-white">
            <SettingsPanel
              blockId={selectedBlockInstance.id}
              blockKey={selectedBlockInstance.key}
              blockLabel={selectedBlockMeta.label}
              repeatIndex={selectedBlockInstance.repeatIndex}
              config={config}
              localData={localData}
              activeProducts={activeProducts}
              selectedProduct={selectedProduct}
              selectedProductPriceLabel={selectedProductPriceLabel}
              templateFields={TEMPLATE_FIELDS}
              editorRef={editorRef}
              onUpdateHero={updateHero}
              onUpdateConfig={updateConfig}
              onUpdateImage={updateImage}
              onUpdateVideo={updateVideo}
              onUpdateTextContent={updateTextContent}
              onInsertTemplateField={insertTemplateField}
              onCopyToken={(t) => void copyTextToClipboard(t)}
              onClose={() => setSelectedBlockId(null)}
            />
          </aside>
        )}
      </div>

      {/* Block picker */}
      {showBlockPicker && (
        <BlockPickerModal
          inactiveBlocks={inactiveBlocks}
          onAdd={addBlock}
          onClose={() => setShowBlockPicker(false)}
        />
      )}
    </div>
  );
}
