import type { ProductCourseLesson } from './types';

export type CourseVideoProvider = 'youtube' | 'rutube' | 'vk';

export type CourseLessonVideoFields = {
  youtube_video_id: string | null;
  rutube_video_id: string | null;
  vk_owner_id: string | null;
  vk_video_id: string | null;
  vk_hash: string | null;
};

export type CourseLessonVideoBlock = CourseLessonVideoFields & {
  id: string;
  type: 'video';
  video_url: string;
};

export type CourseLessonTiptapBlock = {
  id: string;
  type: 'tiptap';
  content: Record<string, unknown>;
};

export type CourseLessonImageBlock = {
  id: string;
  type: 'image';
  image_url: string;
  caption: string;
};

export type CourseLessonBlock = CourseLessonVideoBlock | CourseLessonTiptapBlock | CourseLessonImageBlock;

export type CourseLessonContent = {
  blocks: CourseLessonBlock[];
};

export type ParsedCourseVideo = CourseLessonVideoFields & {
  provider: CourseVideoProvider;
  video_url: string;
};

const DEFAULT_TIPTAP_DOC: Record<string, unknown> = {
  type: 'doc',
  content: [{ type: 'paragraph', content: [] }],
};

const EMPTY_VIDEO_FIELDS: CourseLessonVideoFields = {
  youtube_video_id: null,
  rutube_video_id: null,
  vk_owner_id: null,
  vk_video_id: null,
  vk_hash: null,
};

const isObjectRecord = (value: unknown): value is Record<string, unknown> => (
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)
);

const asString = (value: unknown): string => (typeof value === 'string' ? value : '');

const createBlockId = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `block_${Math.random().toString(36).slice(2, 10)}`;
};

export const normalizeTiptapDoc = (value: unknown): Record<string, unknown> => {
  if (isObjectRecord(value) && value.type === 'doc' && Array.isArray(value.content)) {
    return value;
  }

  if (typeof value === 'string' && value.trim()) {
    return {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [{ type: 'text', text: value.trim() }],
        },
      ],
    };
  }

  return DEFAULT_TIPTAP_DOC;
};

export const createCourseLessonVideoBlock = (): CourseLessonVideoBlock => ({
  id: createBlockId(),
  type: 'video',
  video_url: '',
  ...EMPTY_VIDEO_FIELDS,
});

export const createCourseLessonTiptapBlock = (): CourseLessonTiptapBlock => ({
  id: createBlockId(),
  type: 'tiptap',
  content: DEFAULT_TIPTAP_DOC,
});

export const createCourseLessonImageBlock = (): CourseLessonImageBlock => ({
  id: createBlockId(),
  type: 'image',
  image_url: '',
  caption: '',
});

export const createDefaultCourseLessonContent = (): CourseLessonContent => ({
  blocks: [createCourseLessonVideoBlock(), createCourseLessonTiptapBlock()],
});

const normalizeVideoBlock = (raw: unknown): CourseLessonVideoBlock | null => {
  if (!isObjectRecord(raw) || raw.type !== 'video') return null;
  return {
    id: asString(raw.id) || createBlockId(),
    type: 'video',
    video_url: asString(raw.video_url),
    youtube_video_id: asString(raw.youtube_video_id) || null,
    rutube_video_id: asString(raw.rutube_video_id) || null,
    vk_owner_id: asString(raw.vk_owner_id) || null,
    vk_video_id: asString(raw.vk_video_id) || null,
    vk_hash: asString(raw.vk_hash) || null,
  };
};

const normalizeTiptapBlock = (raw: unknown): CourseLessonTiptapBlock | null => {
  if (!isObjectRecord(raw) || raw.type !== 'tiptap') return null;
  return {
    id: asString(raw.id) || createBlockId(),
    type: 'tiptap',
    content: normalizeTiptapDoc(raw.content),
  };
};

const normalizeImageBlock = (raw: unknown): CourseLessonImageBlock | null => {
  if (!isObjectRecord(raw) || raw.type !== 'image') return null;
  return {
    id: asString(raw.id) || createBlockId(),
    type: 'image',
    image_url: asString(raw.image_url),
    caption: asString(raw.caption),
  };
};

const parseJsonString = (raw: string): unknown => {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
};

const inferVideoUrlFromLessonFields = (lesson: Pick<ProductCourseLesson, keyof CourseLessonVideoFields>): string => {
  if (lesson.youtube_video_id) {
    return `https://youtu.be/${lesson.youtube_video_id}`;
  }
  if (lesson.rutube_video_id) {
    return `https://rutube.ru/video/${lesson.rutube_video_id}/`;
  }
  if (lesson.vk_owner_id && lesson.vk_video_id) {
    if (lesson.vk_hash) {
      return `https://vk.com/video_ext.php?oid=${lesson.vk_owner_id}&id=${lesson.vk_video_id}&hash=${lesson.vk_hash}`;
    }
    return `https://vk.com/video${lesson.vk_owner_id}_${lesson.vk_video_id}`;
  }
  return '';
};

export const normalizeCourseLessonContent = (rawContent: unknown): CourseLessonContent => {
  const source = typeof rawContent === 'string' ? parseJsonString(rawContent) : rawContent;
  const blocks: CourseLessonBlock[] = [];

  if (isObjectRecord(source) && Array.isArray(source.blocks)) {
    for (const rawBlock of source.blocks) {
      const video = normalizeVideoBlock(rawBlock);
      if (video) {
        blocks.push(video);
        continue;
      }

      const tiptap = normalizeTiptapBlock(rawBlock);
      if (tiptap) {
        blocks.push(tiptap);
        continue;
      }

      const image = normalizeImageBlock(rawBlock);
      if (image) {
        blocks.push(image);
      }
    }
  } else if (isObjectRecord(source) && source.type === 'doc' && Array.isArray(source.content)) {
    blocks.push(createCourseLessonVideoBlock());
    blocks.push({
      id: createBlockId(),
      type: 'tiptap',
      content: normalizeTiptapDoc(source),
    });
  } else if (typeof source === 'string' && source.trim()) {
    blocks.push(createCourseLessonVideoBlock());
    blocks.push({
      id: createBlockId(),
      type: 'tiptap',
      content: normalizeTiptapDoc(source),
    });
  }

  if (!blocks.length) {
    return createDefaultCourseLessonContent();
  }

  return { blocks };
};

export const mergeTopLevelVideoFields = (
  content: CourseLessonContent,
  lesson: Pick<ProductCourseLesson, keyof CourseLessonVideoFields>,
): CourseLessonContent => {
  const blocks = [...content.blocks];
  const firstVideoIndex = blocks.findIndex((item) => item.type === 'video');

  if (firstVideoIndex < 0) {
    return {
      blocks: [
        {
          ...createCourseLessonVideoBlock(),
          video_url: inferVideoUrlFromLessonFields(lesson),
          youtube_video_id: lesson.youtube_video_id ?? null,
          rutube_video_id: lesson.rutube_video_id ?? null,
          vk_owner_id: lesson.vk_owner_id ?? null,
          vk_video_id: lesson.vk_video_id ?? null,
          vk_hash: lesson.vk_hash ?? null,
        },
        ...blocks,
      ],
    };
  }

  const video = blocks[firstVideoIndex] as CourseLessonVideoBlock;
  const hasVideoData = Boolean(
    video.youtube_video_id
    || video.rutube_video_id
    || video.vk_owner_id
    || video.vk_video_id
    || video.vk_hash
  );

  if (hasVideoData) return content;

  blocks[firstVideoIndex] = {
    ...video,
    video_url: video.video_url || inferVideoUrlFromLessonFields(lesson),
    youtube_video_id: lesson.youtube_video_id ?? null,
    rutube_video_id: lesson.rutube_video_id ?? null,
    vk_owner_id: lesson.vk_owner_id ?? null,
    vk_video_id: lesson.vk_video_id ?? null,
    vk_hash: lesson.vk_hash ?? null,
  };

  return { blocks };
};

export const updateCourseLessonTiptapBlock = (
  content: CourseLessonContent,
  blockId: string,
  nextDoc: Record<string, unknown>,
): CourseLessonContent => ({
  blocks: content.blocks.map((block) => {
    if (block.type !== 'tiptap' || block.id !== blockId) return block;
    return {
      ...block,
      content: normalizeTiptapDoc(nextDoc),
    };
  }),
});

export const applyVideoToCourseLessonContent = (
  content: CourseLessonContent,
  blockId: string,
  parsedVideo: ParsedCourseVideo | null,
  rawVideoUrl: string,
): CourseLessonContent => ({
  blocks: content.blocks.map((block) => {
    if (block.type !== 'video' || block.id !== blockId) return block;
    if (!parsedVideo) {
      return {
        ...block,
        video_url: rawVideoUrl,
        ...EMPTY_VIDEO_FIELDS,
      };
    }
    return {
      ...block,
      youtube_video_id: parsedVideo.youtube_video_id,
      rutube_video_id: parsedVideo.rutube_video_id,
      vk_owner_id: parsedVideo.vk_owner_id,
      vk_video_id: parsedVideo.vk_video_id,
      vk_hash: parsedVideo.vk_hash,
      video_url: rawVideoUrl,
    };
  }),
});

const normalizeExternalUrl = (rawUrl: string): string | null => {
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (/^[A-Za-z0-9_-]{11}$/.test(trimmed)) {
    return `https://youtu.be/${trimmed}`;
  }
  return `https://${trimmed}`;
};

const extractYoutubeId = (url: URL): string | null => {
  const host = url.hostname.toLowerCase();
  if (host === 'youtu.be') {
    return url.pathname.replace(/^\/+/, '').split('/')[0] || null;
  }

  if (!host.includes('youtube.com')) return null;

  const fromQuery = (url.searchParams.get('v') || '').trim();
  if (fromQuery) return fromQuery;

  const pathParts = url.pathname.split('/').filter(Boolean);
  const markerIndex = pathParts.findIndex((part) => part === 'embed' || part === 'shorts' || part === 'live');
  if (markerIndex >= 0 && pathParts[markerIndex + 1]) {
    return pathParts[markerIndex + 1];
  }
  return null;
};

const extractRutubeId = (url: URL): string | null => {
  const host = url.hostname.toLowerCase();
  if (!host.includes('rutube.ru')) return null;

  const path = url.pathname;
  const match =
    path.match(/\/play\/embed\/([A-Za-z0-9_-]+)/i)
    || path.match(/\/video\/([A-Za-z0-9_-]+)/i)
    || path.match(/\/embed\/([A-Za-z0-9_-]+)/i);
  if (match?.[1]) return match[1];

  const queryId = (url.searchParams.get('id') || '').trim();
  return queryId || null;
};

const extractVkVideoParts = (url: URL): { ownerId: string; videoId: string; hash: string | null } | null => {
  const host = url.hostname.toLowerCase();
  if (!host.includes('vk.com') && !host.includes('vkvideo.ru')) return null;

  if (url.pathname.toLowerCase().includes('video_ext.php')) {
    const ownerId = (url.searchParams.get('oid') || '').trim();
    const videoId = (url.searchParams.get('id') || '').trim();
    const hash = (url.searchParams.get('hash') || '').trim() || null;
    if (ownerId && videoId) return { ownerId, videoId, hash };
  }

  const directMatch = decodeURIComponent(url.pathname).match(/video(-?\d+)_([0-9]+)/i);
  if (directMatch?.[1] && directMatch?.[2]) {
    const hash = (url.searchParams.get('hash') || '').trim() || null;
    return { ownerId: directMatch[1], videoId: directMatch[2], hash };
  }

  const zParam = decodeURIComponent(url.searchParams.get('z') || '');
  const zMatch = zParam.match(/video(-?\d+)_([0-9]+)/i);
  if (zMatch?.[1] && zMatch?.[2]) {
    const hash = (url.searchParams.get('hash') || '').trim() || null;
    return { ownerId: zMatch[1], videoId: zMatch[2], hash };
  }

  return null;
};

export const parseCourseVideoUrl = (rawUrl: string): ParsedCourseVideo | null => {
  const normalizedUrl = normalizeExternalUrl(rawUrl);
  if (!normalizedUrl) return null;

  let parsed: URL;
  try {
    parsed = new URL(normalizedUrl);
  } catch {
    return null;
  }

  const youtubeId = extractYoutubeId(parsed);
  if (youtubeId) {
    return {
      provider: 'youtube',
      video_url: normalizedUrl,
      youtube_video_id: youtubeId,
      rutube_video_id: null,
      vk_owner_id: null,
      vk_video_id: null,
      vk_hash: null,
    };
  }

  const rutubeId = extractRutubeId(parsed);
  if (rutubeId) {
    return {
      provider: 'rutube',
      video_url: normalizedUrl,
      youtube_video_id: null,
      rutube_video_id: rutubeId,
      vk_owner_id: null,
      vk_video_id: null,
      vk_hash: null,
    };
  }

  const vkParts = extractVkVideoParts(parsed);
  if (vkParts) {
    return {
      provider: 'vk',
      video_url: normalizedUrl,
      youtube_video_id: null,
      rutube_video_id: null,
      vk_owner_id: vkParts.ownerId,
      vk_video_id: vkParts.videoId,
      vk_hash: vkParts.hash,
    };
  }

  return null;
};

const inferVideoProvider = (video: Partial<CourseLessonVideoFields>): CourseVideoProvider | null => {
  if (video.youtube_video_id) return 'youtube';
  if (video.rutube_video_id) return 'rutube';
  if (video.vk_owner_id && video.vk_video_id) return 'vk';
  return null;
};

export const buildCourseLessonEmbedUrl = (
  video: Partial<CourseLessonVideoFields> & { video_url?: string | null },
): string | null => {
  const provider = inferVideoProvider(video);
  const youtubeId = video.youtube_video_id;
  const rutubeId = video.rutube_video_id;
  const vkOwnerId = video.vk_owner_id;
  const vkVideoId = video.vk_video_id;
  const vkHash = video.vk_hash;

  if (provider === 'youtube' && youtubeId) {
    return `https://www.youtube.com/embed/${youtubeId}?rel=0&modestbranding=1`;
  }
  if (provider === 'rutube' && rutubeId) {
    return `https://rutube.ru/play/embed/${rutubeId}`;
  }
  if (provider === 'vk' && vkOwnerId && vkVideoId && vkHash) {
    return `https://vk.com/video_ext.php?oid=${vkOwnerId}&id=${vkVideoId}&hash=${vkHash}&hd=2`;
  }

  if (video.video_url) {
    const parsed = parseCourseVideoUrl(video.video_url);
    if (parsed) {
      return buildCourseLessonEmbedUrl({
        youtube_video_id: parsed.youtube_video_id,
        rutube_video_id: parsed.rutube_video_id,
        vk_owner_id: parsed.vk_owner_id,
        vk_video_id: parsed.vk_video_id,
        vk_hash: parsed.vk_hash,
      });
    }
  }

  return null;
};

export const extractPrimaryCourseVideoFields = (
  content: CourseLessonContent,
): CourseLessonVideoFields => {
  const firstVideo = content.blocks.find((block) => block.type === 'video') as CourseLessonVideoBlock | undefined;
  if (!firstVideo) return { ...EMPTY_VIDEO_FIELDS };

  if (firstVideo.youtube_video_id || firstVideo.rutube_video_id || (firstVideo.vk_owner_id && firstVideo.vk_video_id)) {
    return {
      youtube_video_id: firstVideo.youtube_video_id || null,
      rutube_video_id: firstVideo.rutube_video_id || null,
      vk_owner_id: firstVideo.vk_owner_id || null,
      vk_video_id: firstVideo.vk_video_id || null,
      vk_hash: firstVideo.vk_hash || null,
    };
  }

  if (firstVideo.video_url) {
    const parsed = parseCourseVideoUrl(firstVideo.video_url);
    if (parsed) {
      return {
        youtube_video_id: parsed.youtube_video_id,
        rutube_video_id: parsed.rutube_video_id,
        vk_owner_id: parsed.vk_owner_id,
        vk_video_id: parsed.vk_video_id,
        vk_hash: parsed.vk_hash,
      };
    }
  }

  return { ...EMPTY_VIDEO_FIELDS };
};
