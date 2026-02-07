import type { PropertyDraft } from '../types';
import type { MindNodeProperty } from '@/lib/types';

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES - Shared utilities
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Конвертирует свойства в черновики для редактирования
 */
export const toDrafts = (props: MindNodeProperty[]): PropertyDraft[] =>
  [...props]
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .map((p) => ({
      key: String(p.id),
      id: p.id,
      title: p.title ?? '',
      value: p.value ?? '',
      delta: p.delta ?? '',
      order_index: p.order_index ?? 0
    }));

/**
 * Извлекает ID продукта из мета данных узла
 */
export const extractProductId = (meta: Record<string, unknown> | null): number | null => {
  if (!meta || meta.entity !== 'product') return null;
  
  const raw = meta.product_id;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string') {
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
};

/**
 * Проверяет является ли узел сайтом
 */
export const isWebsiteNode = (meta: Record<string, unknown> | null): boolean => {
  return meta?.entity === 'website';
};

/**
 * Извлекает заголовок для website узла
 */
export const extractWebsiteTitle = (
  meta: Record<string, unknown>, 
  fallback: string
): string => {
  const websiteTitleRaw =
    (typeof meta.page_title === 'string' && meta.page_title.trim()) ||
    (typeof meta.title === 'string' && meta.title.trim()) ||
    '';
  return websiteTitleRaw || fallback;
};

/**
 * Извлекает URL для website узла
 */
export const extractWebsiteUrl = (meta: Record<string, unknown>): string => {
  return (
    (typeof meta.metric_type === 'string' && 
     meta.metric_type.trim() && 
     meta.metric_type !== 'url' ? meta.metric_type.trim() : '') ||
    (typeof meta.page_url === 'string' && meta.page_url.trim() ? meta.page_url.trim() : '') ||
    (typeof meta.url === 'string' && meta.url.trim() ? meta.url.trim() : '')
  );
};

/**
 * Валидирует свойства перед сохранением
 */
export const validateProperties = (properties: PropertyDraft[]): string | null => {
  const hasInvalidNew = properties.some(
    (p) => !p.deleted && !p.id && !p.title.trim()
  );
  
  if (hasInvalidNew) {
    return 'У новых свойств нужно заполнить название';
  }
  
  return null;
};

/**
 * Фильтрует удалённые свойства
 */
export const filterDeleted = <T extends { deleted?: boolean }>(items: T[]): T[] => {
  return items.filter((item) => !item.deleted);
};
