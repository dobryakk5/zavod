// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES FOR MINDMAP
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Конвертирует свойства узла в PropertyDraft[]
 */
export function toDrafts(props) {
  return [...props]
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .map((p) => ({
      key: String(p.id),
      id: p.id,
      title: p.title ?? '',
      value: p.value ?? '',
      delta: p.delta ?? '',
      order_index: p.order_index ?? 0
    }));
}

/**
 * Извлекает product_id из meta
 */
export function extractProductId(meta) {
  if (!meta || meta.entity !== 'product') return null;
  
  const raw = meta.product_id;
  
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string') {
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  
  return null;
}

/**
 * Проверяет, является ли узел website
 */
export function isWebsiteNode(meta) {
  return meta && typeof meta === 'object' && meta.entity === 'website';
}

/**
 * Извлекает title для website узла
 */
export function getWebsiteTitle(meta, defaultText) {
  if (!isWebsiteNode(meta)) return defaultText;
  
  const titleFromMeta =
    (typeof meta.page_title === 'string' && meta.page_title.trim()) ||
    (typeof meta.title === 'string' && meta.title.trim()) ||
    '';
  
  return titleFromMeta || defaultText;
}

/**
 * Извлекает URL для website узла
 */
export function getWebsiteUrl(meta) {
  if (!isWebsiteNode(meta)) return '';
  
  return (
    (typeof meta.metric_type === 'string' && 
     meta.metric_type.trim() && 
     meta.metric_type !== 'url' 
       ? meta.metric_type.trim() 
       : '') ||
    (typeof meta.page_url === 'string' && meta.page_url.trim()) ||
    (typeof meta.url === 'string' && meta.url.trim()) ||
    ''
  );
}

/**
 * Подготавливает данные свойств для сохранения
 */
export function preparePropertiesForSave(properties, nodeId) {
  const toCreate = [];
  const toUpdate = [];
  const toDelete = [];

  properties.forEach((p, idx) => {
    if (p.deleted && p.id) {
      toDelete.push(p.id);
    } else if (!p.deleted && p.id) {
      toUpdate.push({
        id: p.id,
        node_id: nodeId,
        title: p.title,
        value: p.value,
        delta: p.delta,
        order_index: idx
      });
    } else if (!p.deleted && !p.id && p.title.trim()) {
      toCreate.push({
        node_id: nodeId,
        title: p.title,
        value: p.value,
        delta: p.delta,
        order_index: idx
      });
    }
  });

  return { toCreate, toUpdate, toDelete };
}

/**
 * Валидация перед сохранением
 */
export function validateProperties(properties) {
  const hasInvalidNew = properties.some(
    (p) => !p.deleted && !p.id && !p.title.trim()
  );
  
  return {
    valid: !hasInvalidNew,
    error: hasInvalidNew ? 'У новых свойств нужно заполнить название' : null
  };
}
