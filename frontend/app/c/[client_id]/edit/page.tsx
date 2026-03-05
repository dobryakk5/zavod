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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import type { ClientProduct, ClientSettings } from '@/lib/types';

// ─── Local block types ────────────────────────────────────────────────────────

type ImageBlockConfig = ClientPageImageBlockConfig;
type VideoBlockConfig = ClientPageVideoBlockConfig;

type LocalBlockData = {
  image: ImageBlockConfig;
  video: VideoBlockConfig;
};

const DEFAULT_IMAGE_CONFIG: ImageBlockConfig = {
  url: '', alt: '', caption: '', fit: 'cover', max_height: 420,
};

const DEFAULT_VIDEO_CONFIG: VideoBlockConfig = {
  url: '', caption: '',
};

type ExtendedBlockKey = ClientPageBlockKey;

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
  blockKey, label, isSelected, isFirst, isLast,
  onSelect, onRemove, onMoveUp, onMoveDown, children,
}: {
  blockKey: ExtendedBlockKey; label: string; isSelected: boolean;
  isFirst: boolean; isLast: boolean;
  onSelect: () => void; onRemove: () => void;
  onMoveUp: () => void; onMoveDown: () => void;
  children: React.ReactNode;
}) {
  const [hov, setHov] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: blockKey });

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
          {blockKey !== 'hero' && (
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
  blockKey, blockLabel, config, localData, content,
  activeProducts, selectedProduct, selectedProductPriceLabel,
  templateFields, editorRef,
  onUpdateHero, onUpdateConfig, onUpdateImage, onUpdateVideo,
  onUpdateContent, onInsertTemplateField, onCopyToken, onClose,
}: {
  blockKey: ExtendedBlockKey; blockLabel: string;
  config: ClientPageTemplateConfig; localData: LocalBlockData;
  content: Record<string, unknown>;
  activeProducts: ClientProduct[]; selectedProduct: ClientProduct | null;
  selectedProductPriceLabel: string;
  templateFields: typeof TEMPLATE_FIELDS;
  editorRef: React.MutableRefObject<Editor | null>;
  onUpdateHero: (p: Partial<ClientPageHeroConfig>) => void;
  onUpdateConfig: (p: Partial<ClientPageTemplateConfig>) => void;
  onUpdateImage: (p: Partial<ImageBlockConfig>) => void;
  onUpdateVideo: (p: Partial<VideoBlockConfig>) => void;
  onUpdateContent: (v: Record<string, unknown>) => void;
  onInsertTemplateField: (t: string) => void;
  onCopyToken: (t: string) => void;
  onClose: () => void;
}) {
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
        {blockKey === 'image' && (
          <>
            <Field label="URL картинки">
              <input className="input-base w-full" placeholder="https://example.com/photo.jpg"
                value={localData.image.url}
                onChange={(e) => onUpdateImage({ url: e.target.value })} />
            </Field>

            {localData.image.url && (
              <div className="overflow-hidden rounded-xl border bg-slate-50">
                <Image
                  src={localData.image.url}
                  alt={localData.image.alt || 'preview'}
                  width={1600}
                  height={900}
                  unoptimized
                  loader={({ src }) => src}
                  className="w-full"
                  style={{ maxHeight: Math.min(localData.image.max_height, 360), objectFit: localData.image.fit }}
                />
              </div>
            )}

            <Field label="Alt-текст (для SEO)">
              <input className="input-base w-full" placeholder="Описание картинки"
                value={localData.image.alt}
                onChange={(e) => onUpdateImage({ alt: e.target.value })} />
            </Field>

            <Field label="Подпись под картинкой">
              <input className="input-base w-full" placeholder="Необязательно"
                value={localData.image.caption}
                onChange={(e) => onUpdateImage({ caption: e.target.value })} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Отображение">
                <select className="input-base w-full" value={localData.image.fit}
                  onChange={(e) => onUpdateImage({ fit: e.target.value as 'cover' | 'contain' })}>
                  <option value="cover">Обрезать (cover)</option>
                  <option value="contain">Вписать (contain)</option>
                </select>
              </Field>
              <Field label={`Макс. высота: ${localData.image.max_height}px`}>
                <input type="range" min={120} max={900} step={20}
                  value={localData.image.max_height}
                  onChange={(e) => onUpdateImage({ max_height: Number(e.target.value) })}
                  className="w-full accent-blue-500 mt-2" />
              </Field>
            </div>
          </>
        )}

        {/* ── VIDEO ── */}
        {blockKey === 'video' && (
          <>
            <Field label="Ссылка на видео">
              <input className="input-base w-full"
                placeholder="YouTube, Vimeo или прямая .mp4 ссылка"
                value={localData.video.url}
                onChange={(e) => onUpdateVideo({ url: e.target.value })} />
            </Field>

            {localData.video.url && (() => {
              const r = resolveVideoEmbed(localData.video.url);
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
                value={localData.video.caption}
                onChange={(e) => onUpdateVideo({ caption: e.target.value })} />
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
        {blockKey === 'custom_content' && (
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
                initialContent={content}
                onChange={onUpdateContent}
                onEditorReady={(editor) => { editorRef.current = editor; }}
                autoSave={false} showToolbar
                placeholder="Напишите описание, оффер, FAQ..."
              />
            </div>
          </>
        )}

        {/* ── READ-ONLY ── */}
        {['header', 'booking', 'purchases', 'planned_meetings', 'referrals'].includes(blockKey) && (
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
  blockKey, config, localData, displayName, niche,
  selectedProduct, selectedProductPriceLabel, customContentHtml, previewValues,
}: {
  blockKey: ExtendedBlockKey; config: ClientPageTemplateConfig; localData: LocalBlockData;
  displayName: string; niche: string; selectedProduct: ClientProduct | null;
  selectedProductPriceLabel: string; customContentHtml: string;
  previewValues: Record<string, string>;
}): React.ReactNode {

  if (blockKey === 'image') {
    const img = localData.image;
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
    const vid = localData.video;
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

  if (blockKey === 'custom_content') return (
    <div className="px-8 py-8">
      {customContentHtml ? (
        <div className="tiptap prose prose-slate max-w-none"
          dangerouslySetInnerHTML={{ __html: customContentHtml }} />
      ) : (
        <div className="rounded-xl border border-dashed py-8 text-center text-sm text-muted-foreground">
          Откройте настройки блока, чтобы добавить контент
        </div>
      )}
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
  const { client_id: rawClientId } = useParams<{ client_id: string }>();
  const router = useRouter();
  const editorRef = useRef<Editor | null>(null);
  const pageClientId = Number(rawClientId);

  const [loading, setLoading]             = useState(true);
  const [saving, setSaving]               = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [saveMessage, setSaveMessage]     = useState<string | null>(null);
  const [clientName, setClientName]       = useState('');
  const [settings, setSettings]           = useState<ClientSettings | null>(null);
  const [products, setProducts]           = useState<ClientProduct[]>([]);
  const [config, setConfig]               = useState<ClientPageTemplateConfig>(createDefaultClientPageTemplateConfig);
  const [content, setContent]             = useState<Record<string, unknown>>({ ...EMPTY_TIPTAP_DOC });
  const [publicPageUrl, setPublicPageUrl] = useState('');
  const [localData, setLocalData]         = useState<LocalBlockData>({
    image: { ...DEFAULT_IMAGE_CONFIG },
    video: { ...DEFAULT_VIDEO_CONFIG },
  });
  const [extBlockOrder, setExtBlockOrder] = useState<ExtendedBlockKey[]>([]);
  const [selectedBlockKey, setSelectedBlockKey] = useState<ExtendedBlockKey | null>(null);
  const [showBlockPicker, setShowBlockPicker]   = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const activeProducts           = useMemo(() => products.filter(isProductActive), [products]);
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

  const inactiveBlocks = useMemo(() => {
    const active = new Set(extBlockOrder);
    return CLIENT_PAGE_BLOCK_LIBRARY.filter(
      (b) => !active.has(b.key as ExtendedBlockKey),
    ) as CombinedBlockMeta[];
  }, [extBlockOrder]);

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

  const customContentHtml = useMemo(() => {
    try {
      const replaced = replaceTemplateTokensInTiptapNode(content, previewValues) as Record<string, unknown>;
      return generateHTML(replaced, createKbExtensions());
    } catch { return ''; }
  }, [content, previewValues]);

  const selectedBlockMeta = selectedBlockKey ? allBlockMeta.get(selectedBlockKey) : null;

  // Sync canvas order with enabled blocks in config
  useEffect(() => {
    setExtBlockOrder(config.block_order.filter((k) => config.blocks[k]) as ExtendedBlockKey[]);
  }, [config.block_order, config.blocks]);

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

      const rawConfig = normalizeClientPageTemplateConfig(settingsData?.client_page_config);
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
      setContent(normalizeTiptapContent(settingsData?.client_page_content));
      setLocalData({
        image: { ...DEFAULT_IMAGE_CONFIG, ...(rawConfig.extra_blocks?.image || {}) },
        video: { ...DEFAULT_VIDEO_CONFIG, ...(rawConfig.extra_blocks?.video || {}) },
      });

      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      setPublicPageUrl(origin ? `${origin}/c/${activeId}` : `/c/${activeId}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { router.push('/login'); return; }
      setError('Не удалось загрузить редактор страницы клиента.');
    } finally { setLoading(false); }
  }, [pageClientId, router]);

  useEffect(() => { void loadEditorData(); }, [loadEditorData]);

  // ── Actions ───────────────────────────────────────────────

  const saveTemplate = async () => {
    setSaving(true); setSaveMessage(null);
    try {
      const configForSave: ClientPageTemplateConfig = {
        ...config,
        extra_blocks: {
          ...config.extra_blocks,
          image: { ...localData.image },
          video: { ...localData.video },
        },
      };
      const updated = await clientApi.updateSettings({
        client_page_config: configForSave as unknown as Record<string, unknown>,
        client_page_content: content,
      } as Partial<ClientSettings>);
      setSettings(updated);
      const normalized = normalizeClientPageTemplateConfig(updated?.client_page_config ?? configForSave);
      setConfig(normalized);
      setLocalData({
        image: { ...DEFAULT_IMAGE_CONFIG, ...(normalized.extra_blocks?.image || {}) },
        video: { ...DEFAULT_VIDEO_CONFIG, ...(normalized.extra_blocks?.video || {}) },
      });
      setContent(normalizeTiptapContent(updated?.client_page_content ?? content));
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
    setConfig((prev) => prev.blocks[key] ? prev : {
      ...prev,
      blocks: { ...prev.blocks, [key]: true },
      block_order: [...prev.block_order, key],
    });
    setSaveMessage(null);
    setSelectedBlockKey(key);
  };

  const removeBlock = (key: ExtendedBlockKey) => {
    if (key === 'hero') return;
    setConfig((prev) => ({
      ...prev,
      blocks: { ...prev.blocks, [key]: false },
      block_order: prev.block_order.filter((k) => k !== key),
    }));
    if (selectedBlockKey === key) setSelectedBlockKey(null);
    setSaveMessage(null);
  };

  const moveBlock = (key: ExtendedBlockKey, dir: -1 | 1) => {
    setConfig((prev) => {
      const activeOrder = prev.block_order.filter((k) => prev.blocks[k]) as ExtendedBlockKey[];
      const index = activeOrder.indexOf(key);
      const target = index + dir;
      if (index < 0 || target < 0 || target >= activeOrder.length) {
        return prev;
      }
      const movedActive = arrayMove(activeOrder, index, target);
      const hidden = prev.block_order.filter((k) => !prev.blocks[k]);
      return { ...prev, block_order: [...movedActive, ...hidden] };
    });
    setSaveMessage(null);
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setConfig((prev) => {
      const activeOrder = prev.block_order.filter((k) => prev.blocks[k]) as ExtendedBlockKey[];
      const oi = activeOrder.indexOf(String(active.id) as ExtendedBlockKey);
      const ni = activeOrder.indexOf(String(over.id) as ExtendedBlockKey);
      if (oi < 0 || ni < 0) {
        return prev;
      }
      const movedActive = arrayMove(activeOrder, oi, ni);
      const hidden = prev.block_order.filter((k) => !prev.blocks[k]);
      return { ...prev, block_order: [...movedActive, ...hidden] };
    });
    setSaveMessage(null);
  };

  const updateHero   = (p: Partial<ClientPageHeroConfig>) => { setConfig((c) => ({ ...c, hero: { ...c.hero, ...p } })); setSaveMessage(null); };
  const updateConfig = (p: Partial<ClientPageTemplateConfig>) => { setConfig((c) => ({ ...c, ...p })); setSaveMessage(null); };
  const updateImage  = (p: Partial<ImageBlockConfig>) => {
    setLocalData((d) => ({ ...d, image: { ...d.image, ...p } }));
    setConfig((c) => ({
      ...c,
      extra_blocks: {
        ...c.extra_blocks,
        image: { ...c.extra_blocks.image, ...p },
      },
    }));
    setSaveMessage(null);
  };
  const updateVideo  = (p: Partial<VideoBlockConfig>) => {
    setLocalData((d) => ({ ...d, video: { ...d.video, ...p } }));
    setConfig((c) => ({
      ...c,
      extra_blocks: {
        ...c.extra_blocks,
        video: { ...c.extra_blocks.video, ...p },
      },
    }));
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
          <span className="text-sm font-semibold truncate">{displayName}</span>
          <span className="hidden text-xs text-muted-foreground sm:block">/c/{pageClientId}</span>
        </div>
        <div className="flex-1" />
        {saveMessage && <span className="hidden text-xs text-emerald-600 sm:block">{saveMessage}</span>}
        <Button type="button" variant="ghost" size="sm"
          onClick={() => void copyTextToClipboard(publicPageUrl).then(() => setSaveMessage('Ссылка скопирована.'))}>
          <Copy className="mr-1.5 h-3.5 w-3.5" /> Ссылка
        </Button>
        <Button type="button" variant="outline" size="sm" asChild>
          <Link href={`/c/${pageClientId}`} target="_blank" rel="noopener noreferrer">
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
              {extBlockOrder.length === 0 ? (
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
                  <SortableContext items={extBlockOrder} strategy={verticalListSortingStrategy}>
                    <div>
                      <AddBlockDivider onClick={() => setShowBlockPicker(true)} />
                      {extBlockOrder.map((blockKey, index) => (
                        <div key={blockKey}>
                          <SortableCanvasBlock
                            blockKey={blockKey}
                            label={allBlockMeta.get(blockKey)?.label ?? blockKey}
                            isSelected={selectedBlockKey === blockKey}
                            isFirst={index === 0}
                            isLast={index === extBlockOrder.length - 1}
                            onSelect={() => setSelectedBlockKey(selectedBlockKey === blockKey ? null : blockKey)}
                            onRemove={() => removeBlock(blockKey)}
                            onMoveUp={() => moveBlock(blockKey, -1)}
                            onMoveDown={() => moveBlock(blockKey, 1)}
                          >
                            {renderBlockContent({
                              blockKey, config, localData, displayName, niche,
                              selectedProduct, selectedProductPriceLabel,
                              customContentHtml, previewValues,
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
        {selectedBlockKey && selectedBlockMeta && (
          <aside className="w-80 shrink-0 overflow-hidden border-l bg-white">
            <SettingsPanel
              blockKey={selectedBlockKey}
              blockLabel={selectedBlockMeta.label}
              config={config}
              localData={localData}
              content={content}
              activeProducts={activeProducts}
              selectedProduct={selectedProduct}
              selectedProductPriceLabel={selectedProductPriceLabel}
              templateFields={TEMPLATE_FIELDS}
              editorRef={editorRef}
              onUpdateHero={updateHero}
              onUpdateConfig={updateConfig}
              onUpdateImage={updateImage}
              onUpdateVideo={updateVideo}
              onUpdateContent={(v) => { setContent(v); setSaveMessage(null); }}
              onInsertTemplateField={insertTemplateField}
              onCopyToken={(t) => void copyTextToClipboard(t)}
              onClose={() => setSelectedBlockKey(null)}
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
