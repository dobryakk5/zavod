export const CLIENT_PAGE_BLOCK_KEYS = [
  'hero',
  'image',
  'video',
  'header',
  'product',
  'purchases',
  'custom_content',
  'booking',
  'planned_meetings',
  'referrals',
] as const;

export type ClientPageBlockKey = (typeof CLIENT_PAGE_BLOCK_KEYS)[number];

export type ClientPageBlocksConfig = Record<ClientPageBlockKey, boolean>;

export type ClientPageHeroConfig = {
  title: string;
  subtitle: string;
  button_text: string;
  button_url: string;
  show_subtitle: boolean;
  show_button: boolean;
  align: 'left' | 'center' | 'right';
  background: string;
  text_color: string;
  image_url: string;
  overlay_opacity: number;
};

export type ClientPageImageBlockConfig = {
  url: string;
  alt: string;
  caption: string;
  fit: 'cover' | 'contain';
  max_height: number;
};

export type ClientPageVideoBlockConfig = {
  url: string;
  caption: string;
};

export type ClientPageExtraBlocksConfig = {
  image: ClientPageImageBlockConfig;
  video: ClientPageVideoBlockConfig;
};

export type ClientPageTemplateConfig = {
  blocks: ClientPageBlocksConfig;
  block_order: ClientPageBlockKey[];
  selected_product_id: number | null;
  hero: ClientPageHeroConfig;
  extra_blocks: ClientPageExtraBlocksConfig;
};

export const CLIENT_PAGE_BLOCK_LIBRARY: Array<{
  key: ClientPageBlockKey;
  label: string;
  description: string;
}> = [
  {
    key: 'hero',
    label: 'Hero',
    description: 'Первый экран с заголовком, оффером и CTA-кнопкой',
  },
  {
    key: 'image',
    label: 'Изображение',
    description: 'Картинка по ссылке',
  },
  {
    key: 'video',
    label: 'Видео',
    description: 'YouTube, Vimeo или mp4',
  },
  {
    key: 'header',
    label: 'Шапка',
    description: 'Имя клиента, ниша и служебная информация',
  },
  {
    key: 'product',
    label: 'Продукт',
    description: 'Выбранный продукт, описание и кнопка покупки',
  },
  {
    key: 'purchases',
    label: 'Список покупок',
    description: 'Купленные цифровые продукты контакта',
  },
  {
    key: 'custom_content',
    label: 'Текстовый блок',
    description: 'Rich-text контент из редактора TipTap',
  },
  {
    key: 'booking',
    label: 'Запись',
    description: 'Календарь свободных слотов и запись',
  },
  {
    key: 'planned_meetings',
    label: 'Запланированные встречи',
    description: 'Список текущих встреч контакта',
  },
  {
    key: 'referrals',
    label: 'Рефералы',
    description: 'Код приглашения и список приглашений',
  },
];

export const CLIENT_PAGE_BLOCK_DEFAULT_ORDER: ClientPageBlockKey[] = [
  'hero',
  'image',
  'video',
  'header',
  'product',
  'purchases',
  'custom_content',
  'booking',
  'planned_meetings',
  'referrals',
];

export const DEFAULT_CLIENT_PAGE_BLOCKS: ClientPageBlocksConfig = {
  hero: false,
  image: false,
  video: false,
  header: true,
  product: true,
  purchases: true,
  custom_content: true,
  booking: true,
  planned_meetings: true,
  referrals: true,
};

export const DEFAULT_CLIENT_PAGE_HERO_CONFIG: ClientPageHeroConfig = {
  title: '{{brand_name}}',
  subtitle: 'Добро пожаловать в личный мини-портал клиента.',
  button_text: 'Оставить заявку',
  button_url: '#booking',
  show_subtitle: true,
  show_button: true,
  align: 'left',
  background: 'linear-gradient(135deg,#0f172a,#1d4ed8)',
  text_color: '#ffffff',
  image_url: '',
  overlay_opacity: 35,
};

export const DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG: ClientPageImageBlockConfig = {
  url: '',
  alt: '',
  caption: '',
  fit: 'cover',
  max_height: 420,
};

export const DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG: ClientPageVideoBlockConfig = {
  url: '',
  caption: '',
};

export const DEFAULT_CLIENT_PAGE_EXTRA_BLOCKS_CONFIG: ClientPageExtraBlocksConfig = {
  image: { ...DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG },
  video: { ...DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG },
};

const createDefaultBlockOrder = (blocks: ClientPageBlocksConfig): ClientPageBlockKey[] => {
  return CLIENT_PAGE_BLOCK_DEFAULT_ORDER.filter((key) => blocks[key]);
};

export const createDefaultClientPageTemplateConfig = (): ClientPageTemplateConfig => {
  const blocks = { ...DEFAULT_CLIENT_PAGE_BLOCKS };
  return {
    blocks,
    block_order: createDefaultBlockOrder(blocks),
    selected_product_id: null,
    hero: { ...DEFAULT_CLIENT_PAGE_HERO_CONFIG },
    extra_blocks: {
      image: { ...DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG },
      video: { ...DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG },
    },
  };
};

export const DEFAULT_CLIENT_PAGE_TEMPLATE_CONFIG = createDefaultClientPageTemplateConfig();

export const isClientPageBlockKey = (value: unknown): value is ClientPageBlockKey => {
  return (
    typeof value === 'string'
    && (CLIENT_PAGE_BLOCK_KEYS as readonly string[]).includes(value)
  );
};

const normalizeHeroConfig = (value: unknown): ClientPageHeroConfig => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ...DEFAULT_CLIENT_PAGE_HERO_CONFIG };
  }

  const raw = value as Record<string, unknown>;
  const alignRaw = raw.align;
  const align: ClientPageHeroConfig['align'] = alignRaw === 'center' || alignRaw === 'right' ? alignRaw : 'left';

  const overlayRaw = typeof raw.overlay_opacity === 'number' ? raw.overlay_opacity : DEFAULT_CLIENT_PAGE_HERO_CONFIG.overlay_opacity;
  const overlay = Number.isFinite(overlayRaw) ? Math.max(0, Math.min(100, Math.round(overlayRaw))) : DEFAULT_CLIENT_PAGE_HERO_CONFIG.overlay_opacity;

  return {
    title: typeof raw.title === 'string' ? raw.title : DEFAULT_CLIENT_PAGE_HERO_CONFIG.title,
    subtitle: typeof raw.subtitle === 'string' ? raw.subtitle : DEFAULT_CLIENT_PAGE_HERO_CONFIG.subtitle,
    button_text: typeof raw.button_text === 'string' ? raw.button_text : DEFAULT_CLIENT_PAGE_HERO_CONFIG.button_text,
    button_url: typeof raw.button_url === 'string' ? raw.button_url : DEFAULT_CLIENT_PAGE_HERO_CONFIG.button_url,
    show_subtitle: typeof raw.show_subtitle === 'boolean' ? raw.show_subtitle : DEFAULT_CLIENT_PAGE_HERO_CONFIG.show_subtitle,
    show_button: typeof raw.show_button === 'boolean' ? raw.show_button : DEFAULT_CLIENT_PAGE_HERO_CONFIG.show_button,
    align,
    background: typeof raw.background === 'string' ? raw.background : DEFAULT_CLIENT_PAGE_HERO_CONFIG.background,
    text_color: typeof raw.text_color === 'string' ? raw.text_color : DEFAULT_CLIENT_PAGE_HERO_CONFIG.text_color,
    image_url: typeof raw.image_url === 'string' ? raw.image_url : DEFAULT_CLIENT_PAGE_HERO_CONFIG.image_url,
    overlay_opacity: overlay,
  };
};

const normalizeImageBlockConfig = (value: unknown): ClientPageImageBlockConfig => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ...DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG };
  }

  const raw = value as Record<string, unknown>;
  const fitRaw = raw.fit;
  const fit: ClientPageImageBlockConfig['fit'] = fitRaw === 'contain' ? 'contain' : 'cover';
  const rawMaxHeight = typeof raw.max_height === 'number'
    ? raw.max_height
    : DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG.max_height;
  const maxHeight = Number.isFinite(rawMaxHeight)
    ? Math.max(120, Math.min(1200, Math.round(rawMaxHeight)))
    : DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG.max_height;

  return {
    url: typeof raw.url === 'string' ? raw.url : DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG.url,
    alt: typeof raw.alt === 'string' ? raw.alt : DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG.alt,
    caption: typeof raw.caption === 'string' ? raw.caption : DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG.caption,
    fit,
    max_height: maxHeight,
  };
};

const normalizeVideoBlockConfig = (value: unknown): ClientPageVideoBlockConfig => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ...DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG };
  }

  const raw = value as Record<string, unknown>;
  return {
    url: typeof raw.url === 'string' ? raw.url : DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG.url,
    caption: typeof raw.caption === 'string' ? raw.caption : DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG.caption,
  };
};

const normalizeExtraBlocksConfig = (value: unknown): ClientPageExtraBlocksConfig => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {
      image: { ...DEFAULT_CLIENT_PAGE_IMAGE_BLOCK_CONFIG },
      video: { ...DEFAULT_CLIENT_PAGE_VIDEO_BLOCK_CONFIG },
    };
  }

  const raw = value as Record<string, unknown>;
  return {
    image: normalizeImageBlockConfig(raw.image),
    video: normalizeVideoBlockConfig(raw.video),
  };
};

const normalizeBlockOrder = (
  value: unknown,
  blocks: ClientPageBlocksConfig,
): ClientPageBlockKey[] => {
  const parsed = Array.isArray(value)
    ? value.filter(isClientPageBlockKey)
    : [];

  const unique: ClientPageBlockKey[] = [];
  parsed.forEach((key) => {
    if (blocks[key] && !unique.includes(key)) {
      unique.push(key);
    }
  });

  CLIENT_PAGE_BLOCK_DEFAULT_ORDER.forEach((key) => {
    if (blocks[key] && !unique.includes(key)) {
      unique.push(key);
    }
  });

  return unique;
};

export const normalizeClientPageTemplateConfig = (value: unknown): ClientPageTemplateConfig => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return createDefaultClientPageTemplateConfig();
  }

  const raw = value as Record<string, unknown>;
  const rawBlocks = (raw.blocks && typeof raw.blocks === 'object' && !Array.isArray(raw.blocks))
    ? (raw.blocks as Record<string, unknown>)
    : {};

  const blocks: ClientPageBlocksConfig = { ...DEFAULT_CLIENT_PAGE_BLOCKS };
  CLIENT_PAGE_BLOCK_KEYS.forEach((key) => {
    if (typeof rawBlocks[key] === 'boolean') {
      blocks[key] = rawBlocks[key] as boolean;
    }
  });

  const selectedProduct = raw.selected_product_id;
  const selectedProductId = typeof selectedProduct === 'number' && Number.isFinite(selectedProduct)
    ? selectedProduct
    : null;

  return {
    blocks,
    block_order: normalizeBlockOrder(raw.block_order, blocks),
    selected_product_id: selectedProductId,
    hero: normalizeHeroConfig(raw.hero),
    extra_blocks: normalizeExtraBlocksConfig(raw.extra_blocks),
  };
};

export type ClientPageVideoSourceType = 'youtube' | 'vimeo' | 'direct' | 'unknown';

export type ClientPageVideoSource = {
  type: ClientPageVideoSourceType;
  embed_url: string;
};

const extractYoutubeId = (url: URL): string => {
  const host = url.hostname.toLowerCase();
  if (host === 'youtu.be') {
    return url.pathname.replace(/^\/+/, '').split('/')[0] || '';
  }
  if (host.includes('youtube.com')) {
    const watchId = (url.searchParams.get('v') || '').trim();
    if (watchId) {
      return watchId;
    }
    const pathParts = url.pathname.split('/').filter(Boolean);
    const embedIndex = pathParts.findIndex((part) => part === 'embed' || part === 'shorts' || part === 'live');
    if (embedIndex >= 0 && pathParts[embedIndex + 1]) {
      return pathParts[embedIndex + 1];
    }
  }
  return '';
};

const extractVimeoId = (url: URL): string => {
  const host = url.hostname.toLowerCase();
  if (!host.includes('vimeo.com')) {
    return '';
  }
  const pathParts = url.pathname.split('/').filter(Boolean);
  const numericPart = pathParts.find((part) => /^[0-9]+$/.test(part));
  return numericPart || '';
};

export const resolveClientPageVideoSource = (rawUrl: string): ClientPageVideoSource => {
  const trimmed = rawUrl.trim();
  if (!trimmed) {
    return { type: 'unknown', embed_url: '' };
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { type: 'unknown', embed_url: '' };
  }

  const youtubeId = extractYoutubeId(parsed);
  if (youtubeId) {
    return {
      type: 'youtube',
      embed_url: `https://www.youtube.com/embed/${youtubeId}`,
    };
  }

  const vimeoId = extractVimeoId(parsed);
  if (vimeoId) {
    return {
      type: 'vimeo',
      embed_url: `https://player.vimeo.com/video/${vimeoId}`,
    };
  }

  const path = parsed.pathname.toLowerCase();
  if (path.endsWith('.mp4') || path.endsWith('.webm') || path.endsWith('.ogg')) {
    return {
      type: 'direct',
      embed_url: parsed.toString(),
    };
  }

  return { type: 'unknown', embed_url: '' };
};
