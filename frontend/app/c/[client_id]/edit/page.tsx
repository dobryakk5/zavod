'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import type { Editor } from '@tiptap/react';
import { Copy, ExternalLink, Save } from 'lucide-react';
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
import type { ClientProduct, ClientSettings } from '@/lib/types';

type ClientPageBlockKey =
  | 'header'
  | 'product'
  | 'purchases'
  | 'custom_content'
  | 'booking'
  | 'planned_meetings'
  | 'referrals';

type ClientPageBlocksConfig = Record<ClientPageBlockKey, boolean>;

type ClientPageTemplateConfig = {
  blocks: ClientPageBlocksConfig;
  selected_product_id: number | null;
};

const DEFAULT_BLOCKS: ClientPageBlocksConfig = {
  header: true,
  product: true,
  purchases: true,
  custom_content: true,
  booking: true,
  planned_meetings: true,
  referrals: true,
};

const DEFAULT_TEMPLATE_CONFIG: ClientPageTemplateConfig = {
  blocks: DEFAULT_BLOCKS,
  selected_product_id: null,
};

const BLOCK_LABELS: Array<{ key: ClientPageBlockKey; label: string; description: string }> = [
  { key: 'header', label: 'Шапка', description: 'Имя клиента и ниша' },
  { key: 'product', label: 'Продукт', description: 'Выбранный продукт и цена' },
  { key: 'purchases', label: 'Список покупок', description: 'Купленные цифровые продукты контакта' },
  { key: 'custom_content', label: 'Текстовый блок', description: 'Rich-text блок из Tiptap' },
  { key: 'booking', label: 'Запись', description: 'Календарь и свободные слоты' },
  { key: 'planned_meetings', label: 'Запланированные встречи', description: 'Список встреч контакта' },
  { key: 'referrals', label: 'Рефералы', description: 'Код приглашения и приглашения' },
];

const TEMPLATE_FIELDS: Array<{ token: string; label: string }> = [
  { token: '{{brand_name}}', label: 'Название бренда' },
  { token: '{{niche}}', label: 'Ниша' },
  { token: '{{product_name}}', label: 'Название продукта' },
  { token: '{{product_price}}', label: 'Цена продукта' },
  { token: '{{product_service}}', label: 'Продукт/услуга (из настроек)' },
];

const EMPTY_TIPTAP_DOC: Record<string, unknown> = {
  type: 'doc',
  content: [
    {
      type: 'paragraph',
      content: [],
    },
  ],
};

const normalizeTemplateConfig = (value: unknown): ClientPageTemplateConfig => {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_TEMPLATE_CONFIG, blocks: { ...DEFAULT_BLOCKS } };
  }

  const raw = value as Record<string, unknown>;
  const rawBlocks = (raw.blocks && typeof raw.blocks === 'object' ? raw.blocks : {}) as Record<string, unknown>;
  const blocks = { ...DEFAULT_BLOCKS };
  (Object.keys(DEFAULT_BLOCKS) as ClientPageBlockKey[]).forEach((key) => {
    if (typeof rawBlocks[key] === 'boolean') {
      blocks[key] = rawBlocks[key] as boolean;
    }
  });

  const rawSelectedProductId = raw.selected_product_id;
  const selectedProductId = typeof rawSelectedProductId === 'number' && Number.isFinite(rawSelectedProductId)
    ? rawSelectedProductId
    : null;

  return {
    blocks,
    selected_product_id: selectedProductId,
  };
};

const normalizeTiptapContent = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ...EMPTY_TIPTAP_DOC };
  }
  return value as Record<string, unknown>;
};

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textArea = document.createElement('textarea');
  textArea.value = value;
  textArea.style.position = 'fixed';
  textArea.style.top = '-9999px';
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textArea);
  if (!copied) {
    throw new Error('Copy failed');
  }
};

const isProductActive = (product: ClientProduct): boolean => {
  if (!product?.status) return true;
  return product.status === 'active';
};

const resolveProductPrice = (product: ClientProduct): number | null => {
  const packageWithPrice = Array.isArray(product?.packages)
    ? product.packages.find((item) => typeof item?.price === 'number' && Number.isFinite(item.price))
    : undefined;
  return typeof packageWithPrice?.price === 'number' && Number.isFinite(packageWithPrice.price)
    ? packageWithPrice.price
    : null;
};

export default function ClientPageEditor() {
  const { client_id: rawClientId } = useParams<{ client_id: string }>();
  const router = useRouter();
  const editorRef = useRef<Editor | null>(null);

  const pageClientId = Number(rawClientId);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [config, setConfig] = useState<ClientPageTemplateConfig>({ ...DEFAULT_TEMPLATE_CONFIG, blocks: { ...DEFAULT_BLOCKS } });
  const [content, setContent] = useState<Record<string, unknown>>({ ...EMPTY_TIPTAP_DOC });
  const [publicPageUrl, setPublicPageUrl] = useState('');

  const activeProducts = useMemo(() => products.filter((item) => isProductActive(item)), [products]);
  const selectedProduct = useMemo(() => {
    if (config.selected_product_id) {
      return activeProducts.find((item) => item.id === config.selected_product_id) || null;
    }
    return activeProducts[0] || null;
  }, [activeProducts, config.selected_product_id]);

  const selectedProductPriceLabel = useMemo(() => {
    if (!selectedProduct) return 'Не выбран';
    const price = resolveProductPrice(selectedProduct);
    if (price === null) return 'Цена не указана';
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 2,
    }).format(price);
  }, [selectedProduct]);

  const loadEditorData = useCallback(async () => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      setError('Некорректный client_id.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [info, settingsData, productsData] = await Promise.all([
        clientApi.info(),
        clientApi.getSettings(),
        clientProductsApi.list(),
      ]);

      const activeId = Number(info?.client?.id || 0);
      if (!Number.isFinite(activeId) || activeId <= 0) {
        setError('Не удалось определить текущего клиента.');
        return;
      }
      if (activeId !== pageClientId) {
        setError(`Редактор /c/${pageClientId}/edit недоступен для этого аккаунта. Ваш клиент: /c/${activeId}/edit.`);
        return;
      }

      setClientName((info?.client?.name || '').trim());
      setSettings(settingsData);
      setProducts(productsData);
      setConfig(normalizeTemplateConfig(settingsData?.client_page_config));
      setContent(normalizeTiptapContent(settingsData?.client_page_content));
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      setPublicPageUrl(origin ? `${origin}/c/${activeId}` : `/c/${activeId}`);
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) {
        router.push('/login');
        return;
      }
      setError('Не удалось загрузить редактор страницы клиента.');
    } finally {
      setLoading(false);
    }
  }, [pageClientId, router]);

  useEffect(() => {
    void loadEditorData();
  }, [loadEditorData]);

  const updateBlock = (key: ClientPageBlockKey, checked: boolean) => {
    setConfig((prev) => ({
      ...prev,
      blocks: {
        ...prev.blocks,
        [key]: checked,
      },
    }));
    setSaveMessage(null);
  };

  const saveTemplate = async () => {
    setSaving(true);
    setSaveMessage(null);
    try {
      const payload: Partial<ClientSettings> = {
        client_page_config: config as unknown as Record<string, unknown>,
        client_page_content: content,
      };
      const updated = await clientApi.updateSettings(payload);
      setSettings(updated);
      setConfig(normalizeTemplateConfig(updated?.client_page_config ?? config));
      setContent(normalizeTiptapContent(updated?.client_page_content ?? content));
      setSaveMessage('Изменения сохранены.');
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 401) {
        router.push('/login');
        return;
      }
      setError('Не удалось сохранить настройки страницы.');
    } finally {
      setSaving(false);
    }
  };

  const insertTemplateField = (token: string) => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.chain().focus().insertContent(token).run();
    setSaveMessage(null);
  };

  const handleCopyPublicUrl = async () => {
    if (!publicPageUrl) return;
    try {
      await copyTextToClipboard(publicPageUrl);
      setSaveMessage('Ссылка на страницу скопирована.');
    } catch {
      setError('Не удалось скопировать ссылку.');
    }
  };

  if (loading) {
    return <div className="mx-auto max-w-6xl p-6 text-sm text-muted-foreground">Загрузка редактора...</div>;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-5">
        <div>
          <div className="text-xl font-semibold">Редактор страницы клиента</div>
          <div className="text-sm text-muted-foreground">
            {settings?.brand_name?.trim() || clientName || `Клиент #${pageClientId}`} · `/c/${pageClientId}`
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" asChild>
            <Link href={`/c/${pageClientId}`} target="_blank" rel="noopener noreferrer">
              Открыть страницу
              <ExternalLink className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button type="button" variant="outline" onClick={() => void handleCopyPublicUrl()}>
            <Copy className="mr-2 h-4 w-4" />
            Копировать ссылку
          </Button>
          <Button type="button" onClick={() => void saveTemplate()} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>

      {saveMessage && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          {saveMessage}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <div className="space-y-6">
          <section className="rounded-2xl border p-5 space-y-4">
            <div className="text-sm font-semibold">Блоки страницы</div>
            <div className="space-y-3">
              {BLOCK_LABELS.map((item) => (
                <label key={item.key} className="flex items-start gap-3 rounded-lg border p-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4"
                    checked={Boolean(config.blocks[item.key])}
                    onChange={(event) => updateBlock(item.key, event.target.checked)}
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="block text-xs text-muted-foreground">{item.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border p-5 space-y-4">
            <div className="text-sm font-semibold">Продукт для отображения</div>
            <Select
              value={config.selected_product_id ? String(config.selected_product_id) : 'auto'}
              onValueChange={(value) => {
                setConfig((prev) => ({
                  ...prev,
                  selected_product_id: value === 'auto' ? null : Number(value),
                }));
                setSaveMessage(null);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Выберите продукт" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Авто (первый активный)</SelectItem>
                {activeProducts.map((product) => (
                  <SelectItem key={product.id} value={String(product.id)}>
                    {product.name || `Продукт #${product.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
              <div>
                Текущий выбор: <span className="font-medium text-foreground">{selectedProduct?.name || '—'}</span>
              </div>
              <div>
                Цена: <span className="font-medium text-foreground">{selectedProductPriceLabel}</span>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border p-5 space-y-4">
            <div className="text-sm font-semibold">Шаблонные поля для Tiptap</div>
            <div className="grid gap-2">
              {TEMPLATE_FIELDS.map((field) => (
                <div key={field.token} className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-xs font-medium">{field.label}</div>
                    <div className="truncate text-xs text-muted-foreground">{field.token}</div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button type="button" variant="ghost" size="sm" onClick={() => insertTemplateField(field.token)}>
                      Вставить
                    </Button>
                    <Button type="button" variant="ghost" size="sm" onClick={() => void copyTextToClipboard(field.token)}>
                      Копия
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="rounded-2xl border p-4">
          <div className="mb-3">
            <div className="text-sm font-semibold">Текстовый блок страницы</div>
            <div className="text-xs text-muted-foreground">
              Используется тот же Tiptap, что и в базе знаний. Текст покажется на странице клиента, если включен блок.
            </div>
          </div>
          <div className="rounded-xl border">
            <TipTapEditor
              initialContent={content}
              onChange={(next) => {
                setContent(next);
                setSaveMessage(null);
              }}
              onEditorReady={(editor) => {
                editorRef.current = editor;
              }}
              autoSave={false}
              showToolbar
              placeholder="Напишите описание, оффер, FAQ, условия записи и используйте шаблонные поля..."
            />
          </div>
        </section>
      </div>
    </div>
  );
}
