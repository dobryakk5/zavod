'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { SyntheticEvent } from 'react';
import { postsApi } from '@/lib/api/posts';
import { schedulesApi } from '@/lib/api/schedules';
import { ApiError } from '@/lib/api';
import { useClient } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { VisuallyHidden } from '@/components/ui/visually-hidden';
import type { GenerateVideoRequest, PostDetail, Schedule } from '@/lib/types';
import { toast } from 'sonner';
import { SchedulePostDialog } from './schedule-post-dialog';
import { ChevronLeft, ChevronRight, Trash2, Loader2 } from 'lucide-react';
import { sanitizeRichText } from '@/lib/sanitize-html';
import { highlightPhrasesInHtml } from '@/lib/highlight-html';
import Link from 'next/link';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  ready: 'Готово',
  approved: 'Утверждено',
  scheduled: 'Запланировано',
  published: 'Опубликовано',
};

const SCHEDULE_STATUS_LABELS: Record<string, string> = {
  pending: 'В очереди',
  in_progress: 'Публикуется',
  published: 'Опубликован',
  failed: 'Ошибка',
};

const SCHEDULE_STATUS_STYLES: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  in_progress: 'bg-blue-100 text-blue-800',
  published: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api').replace(/\/api\/?$/, '/');
const MEDIA_FEATURES_AVAILABLE = true;
const ONE_HOUR_MS = 60 * 60 * 1000;

const resolveMediaUrl = (url?: string | null) => {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  return `${API_ORIGIN}${url.startsWith('/') ? url.slice(1) : url}`;
};

const formatPostTypeLabel = (value?: string | null) => {
  if (!value) {
    return '';
  }
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatCooldownDuration = (ms: number) => {
  if (ms <= 0) {
    return 'несколько секунд';
  }
  const totalSeconds = Math.ceil(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes > 0 && seconds > 0) {
    return `${minutes} мин ${seconds.toString().padStart(2, '0')} сек`;
  }
  if (minutes > 0) {
    return `${minutes} мин`;
  }
  return `${seconds} сек`;
};

const computeCooldownUntil = (isoDate?: string | null): Date | null => {
  if (!isoDate) {
    return null;
  }
  const timestamp = Date.parse(isoDate);
  if (Number.isNaN(timestamp)) {
    return null;
  }
  return new Date(timestamp + ONE_HOUR_MS);
};

const parseApiErrorPayload = (error: unknown): { message?: string; cooldownEndsAt?: Date | null } => {
  if (error instanceof ApiError) {
    if (error.body) {
      try {
        const payload = JSON.parse(error.body) as {
          error?: string;
          cooldown_ends_at?: string;
        };
        const cooldownEndsAt = payload.cooldown_ends_at ? new Date(payload.cooldown_ends_at) : null;
        return {
          message: typeof payload.error === 'string' ? payload.error : undefined,
          cooldownEndsAt: cooldownEndsAt && !Number.isNaN(cooldownEndsAt.getTime()) ? cooldownEndsAt : null,
        };
      } catch {
        return { message: error.message };
      }
    }
    return { message: error.message };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return {};
};

interface PostDetailViewProps {
  postId: number;
}

export function PostDetailView({ postId }: PostDetailViewProps) {
  const { data: clientInfo } = useClient();
  const role = clientInfo?.role ?? null;
  const canEdit = role === 'owner' || role === 'editor';
  const clientSlug = clientInfo?.client?.slug;
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';
  const canGenerateVideo = isDevMode || clientSlug === 'zavod';
  const isMediaFeatureLocked = !MEDIA_FEATURES_AVAILABLE || !canGenerateVideo;
  const paidFeatureHoverLabel = 'Платная функция';
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [imageGenerationLoading, setImageGenerationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imageGenerationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState<{ src: string; alt: string } | null>(null);
  const [imageToDelete, setImageToDelete] = useState<number | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<number | null>(null);
  const [videoAspectRatios, setVideoAspectRatios] = useState<Record<number, number>>({});
  const [imageCooldownUntil, setImageCooldownUntil] = useState<Date | null>(null);
  const [videoCooldownUntil, setVideoCooldownUntil] = useState<Date | null>(null);
  const [showImageCooldownMessage, setShowImageCooldownMessage] = useState(false);
  const [showVideoCooldownMessage, setShowVideoCooldownMessage] = useState(false);
  const [cooldownClock, setCooldownClock] = useState(() => Date.now());
  const [hookTitleDraft, setHookTitleDraft] = useState('');
  const [hookTitleSaving, setHookTitleSaving] = useState(false);
  const [adjacentPostIds, setAdjacentPostIds] = useState<{ prev: number | null; next: number | null }>({
    prev: null,
    next: null,
  });
  const sanitizedText = useMemo(() => sanitizeRichText(post?.text || ''), [post?.text]);
  const highlightedText = useMemo(
    () => highlightPhrasesInHtml(sanitizedText, post?.wordstat_phrases_used),
    [post?.wordstat_phrases_used, sanitizedText]
  );

  const loadPost = useCallback(async () => {
    try {
      const data = await postsApi.get(postId);
      setPost(data);
    } catch (err) {
      setError('Не удалось загрузить пост');
      toast.error('Ошибка загрузки поста');
    }
  }, [postId]);

  const loadSchedules = useCallback(async () => {
    setSchedulesLoading(true);
    try {
      const data = await schedulesApi.list({ post: postId });
      setSchedules(data);
    } catch (err) {
      toast.error('Не удалось загрузить расписание поста');
    } finally {
      setSchedulesLoading(false);
    }
  }, [postId]);

  const loadAdjacentPosts = useCallback(async () => {
    try {
      const posts = await postsApi.list();
      if (!Array.isArray(posts)) {
        return;
      }
      const sorted = [...posts].sort((a, b) => a.id - b.id);
      const index = sorted.findIndex((item) => item.id === postId);
      if (index === -1) {
        setAdjacentPostIds({ prev: null, next: null });
        return;
      }
      setAdjacentPostIds({
        prev: sorted[index - 1]?.id ?? null,
        next: sorted[index + 1]?.id ?? null,
      });
    } catch {
      setAdjacentPostIds({ prev: null, next: null });
    }
  }, [postId]);

  const refreshSchedulesAndPost = useCallback(async () => {
    await loadSchedules();
    try {
      const updatedPost = await postsApi.get(postId);
      setPost(updatedPost);
    } catch {
      // swallowing error to avoid duplicate toasts for background refresh
    }
  }, [loadSchedules, postId]);

  const stopImageGenerationPolling = useCallback(() => {
    if (imageGenerationIntervalRef.current) {
      clearInterval(imageGenerationIntervalRef.current);
      imageGenerationIntervalRef.current = null;
    }
    setImageGenerationLoading(false);
  }, []);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  useEffect(() => {
    loadAdjacentPosts();
  }, [loadAdjacentPosts]);

  useEffect(() => {
    setImageCooldownUntil(computeCooldownUntil(clientInfo?.client?.last_image_generation_at));
    setVideoCooldownUntil(computeCooldownUntil(clientInfo?.client?.last_video_generation_at));
  }, [clientInfo?.client?.last_image_generation_at, clientInfo?.client?.last_video_generation_at]);

  useEffect(() => {
    const interval = setInterval(() => setCooldownClock(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setHookTitleDraft(post?.hook_title || '');
  }, [post?.hook_title]);

  const handleHookTitleSave = async () => {
    if (!post || !canEdit) {
      return;
    }
    const originalValue = post.hook_title ?? '';
    if (hookTitleDraft === originalValue) {
      return;
    }
    setHookTitleSaving(true);
    try {
      const updatedPost = await postsApi.update(post.id, { hook_title: hookTitleDraft || '' });
      setPost(updatedPost);
      toast.success('Цепляющий заголовок (для фото) обновлен');
    } catch (err) {
      toast.error('Не удалось обновить цепляющий заголовок');
    } finally {
      setHookTitleSaving(false);
    }
  };

  useEffect(() => {
    if (!imageCooldownUntil) {
      setShowImageCooldownMessage(false);
      return undefined;
    }
    if (imageCooldownUntil.getTime() <= Date.now()) {
      setShowImageCooldownMessage(false);
      return undefined;
    }
    setShowImageCooldownMessage(true);
    const timeout = setTimeout(() => setShowImageCooldownMessage(false), 5000);
    return () => clearTimeout(timeout);
  }, [imageCooldownUntil]);

  useEffect(() => {
    if (!videoCooldownUntil) {
      setShowVideoCooldownMessage(false);
      return undefined;
    }
    if (videoCooldownUntil.getTime() <= Date.now()) {
      setShowVideoCooldownMessage(false);
      return undefined;
    }
    setShowVideoCooldownMessage(true);
    const timeout = setTimeout(() => setShowVideoCooldownMessage(false), 5000);
    return () => clearTimeout(timeout);
  }, [videoCooldownUntil]);

  // Cleanup polling interval on unmount
  useEffect(() => {
    return () => {
      if (imageGenerationIntervalRef.current) {
        clearInterval(imageGenerationIntervalRef.current);
      }
    };
  }, []);

  const handleGenerateImage = async () => {
    // Stop any existing polling
    stopImageGenerationPolling();

    setImageGenerationLoading(true);
    try {
      await postsApi.generateImage(postId);
      setImageCooldownUntil(new Date(Date.now() + ONE_HOUR_MS));
      toast.success('Генерация изображения запущена');

      // Start polling every 5 seconds to check if image is ready
      imageGenerationIntervalRef.current = setInterval(async () => {
        try {
          const updatedPost = await postsApi.get(postId);
          const currentImageCount = post?.images?.length || 0;
          const newImageCount = updatedPost.images?.length || 0;

          // If we have a new image, stop polling
          if (newImageCount > currentImageCount) {
            setPost(updatedPost);
            stopImageGenerationPolling();
            toast.success('Изображение сгенерировано!');
            return;
          }

          setPost(updatedPost); // Update post data even if no new image yet
        } catch (err) {
          console.warn('Error checking image generation status:', err);
          // Don't stop polling on network errors, just continue
        }
      }, 5000);

      // Safety timeout - stop polling after 5 minutes (300 seconds)
      setTimeout(() => {
        if (imageGenerationIntervalRef.current) {
          stopImageGenerationPolling();
          toast.warning('Генерация изображения занимает слишком много времени. Попробуйте позже.');
        }
      }, 300000);

    } catch (err) {
      const { message, cooldownEndsAt } = parseApiErrorPayload(err);
      if (cooldownEndsAt) {
        setImageCooldownUntil(cooldownEndsAt);
      }
      toast.error(message || 'Ошибка при генерации изображения');
      stopImageGenerationPolling();
    }
  };

  const handleGenerateVideo = async (options?: GenerateVideoRequest) => {
    setLoading(true);
    const isTextVideo = options?.source === 'text';
    try {
      await postsApi.generateVideo(postId, options);
      setVideoCooldownUntil(new Date(Date.now() + ONE_HOUR_MS));
      toast.success(isTextVideo ? 'Генерация видео по тексту запущена' : 'Генерация видео запущена');
      // Reload post after a delay to show the new video
      setTimeout(async () => {
        const updatedPost = await postsApi.get(postId);
        setPost(updatedPost);
      }, isTextVideo ? 6000 : 5000);
    } catch (err) {
      const { message, cooldownEndsAt } = parseApiErrorPayload(err);
      if (cooldownEndsAt) {
        setVideoCooldownUntil(cooldownEndsAt);
      }
      toast.error(message || (isTextVideo ? 'Ошибка при генерации видео по тексту' : 'Ошибка при генерации видео'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateText = async () => {
    setLoading(true);
    try {
      await postsApi.regenerateText(postId);
      toast.success('Перегенерация текста запущена');
      // Reload post after a delay to show the new text
      setTimeout(async () => {
        const updatedPost = await postsApi.get(postId);
        setPost(updatedPost);
      }, 3000);
    } catch (err) {
      toast.error('Ошибка при перегенерации текста');
    } finally {
      setLoading(false);
    }
  };

  const handlePublishScheduleNow = async (scheduleId: number) => {
    try {
      const response = await schedulesApi.publishNow(scheduleId);
      const isPublished = response.status === 'published';
      toast.success(isPublished ? 'Опубликовано' : response.message || 'Публикация запущена');
      await refreshSchedulesAndPost();
    } catch (err) {
      toast.error('Не удалось запустить публикацию');
    }
  };

  const handleShowDeleteMenu = (imageId: number) => {
    setImageToDelete(imageId);
  };

  const handleConfirmDelete = async () => {
    if (!imageToDelete) return;

    try {
      await postsApi.deleteImage(postId, imageToDelete);
      toast.success('Изображение удалено');
      // Reload post to update the images list
      const updatedPost = await postsApi.get(postId);
      setPost(updatedPost);
    } catch (err) {
      toast.error('Ошибка при удалении изображения');
    } finally {
      setImageToDelete(null);
    }
  };

  const handleCancelDelete = () => {
    setImageToDelete(null);
  };

  const handleShowVideoDeleteMenu = (videoId: number) => {
    setVideoToDelete(videoId);
  };

  const handleConfirmVideoDelete = async () => {
    if (!videoToDelete) return;

    try {
      await postsApi.deleteVideo(postId, videoToDelete);
      toast.success('Видео удалено');
      // Reload post to update the videos list
      const updatedPost = await postsApi.get(postId);
      setPost(updatedPost);
    } catch (err) {
      toast.error('Ошибка при удалении видео');
    } finally {
      setVideoToDelete(null);
    }
  };

  const handleCancelVideoDelete = () => {
    setVideoToDelete(null);
  };

  const handleVideoMetadataLoaded = useCallback(
    (videoId: number, event: SyntheticEvent<HTMLVideoElement>) => {
      const { videoWidth, videoHeight } = event.currentTarget;
      if (!videoWidth || !videoHeight) {
        return;
      }
      const ratio = Math.max(0.5, Math.min(2.0, videoWidth / videoHeight));
      setVideoAspectRatios((prev) => {
        if (prev[videoId] === ratio) {
          return prev;
        }
        return { ...prev, [videoId]: ratio };
      });
    },
    [],
  );

  const handleImageClick = (image: { image: string; alt_text?: string; id: number }) => {
    setSelectedImage({
      src: resolveMediaUrl(image.image),
      alt: image.alt_text || post?.title || `Изображение ${image.id}`
    });
  };

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  if (!post) {
    return <div>Загрузка...</div>;
  }

  const nowMs = cooldownClock;
  const statusLabel = STATUS_LABELS[post.status] ?? post.status;
  const postTypeLabel = formatPostTypeLabel(post.template_type);
  const images = post.images ?? [];
  const videos = post.videos ?? [];
  const hookTitleOriginal = post.hook_title ?? '';
  const hookTitle = hookTitleOriginal.trim();
  const hookTitleHasChanges = hookTitleDraft !== hookTitleOriginal;
  const isImageOnCooldown = Boolean(imageCooldownUntil && imageCooldownUntil.getTime() > nowMs);
  const isVideoOnCooldown = Boolean(videoCooldownUntil && videoCooldownUntil.getTime() > nowMs);
  const imageCooldownRemainingMs = isImageOnCooldown && imageCooldownUntil ? imageCooldownUntil.getTime() - nowMs : 0;
  const videoCooldownRemainingMs = isVideoOnCooldown && videoCooldownUntil ? videoCooldownUntil.getTime() - nowMs : 0;
  const imageCooldownLabel = isImageOnCooldown ? formatCooldownDuration(imageCooldownRemainingMs) : '';
  const videoCooldownLabel = isVideoOnCooldown ? formatCooldownDuration(videoCooldownRemainingMs) : '';
  const imageGenerationDisabled = !canEdit || imageGenerationLoading || !MEDIA_FEATURES_AVAILABLE || isImageOnCooldown;
  const videoGenerationDisabled = !canEdit || loading || isMediaFeatureLocked || isVideoOnCooldown;
  const videoFromTextDisabled = videoGenerationDisabled || !post.text;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{post.title || `Пост #${post.id}`}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <Badge>{statusLabel}</Badge>
            {postTypeLabel && (
              <Badge variant="outline">Тип: {postTypeLabel}</Badge>
            )}
            {post.platforms?.map((platform) => (
              <Badge key={platform} variant="outline">
                {platform}
              </Badge>
            ))}
          </div>
          <div className="mt-3 text-base text-muted-foreground">
            <span className="font-semibold block">Цепляющий заголовок (для фото):</span>
            {canEdit ? (
              <div className="mt-2 flex w-full flex-wrap items-center gap-2">
                <Input
                  value={hookTitleDraft}
                  onChange={(event) => setHookTitleDraft(event.target.value)}
                  placeholder="Например: Это работает!"
                  maxLength={100}
                  disabled={hookTitleSaving}
                  className="w-full max-w-md bg-white text-black placeholder:text-gray-500 dark:bg-white dark:text-black"
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={handleHookTitleSave}
                  disabled={!hookTitleHasChanges || hookTitleSaving}
                  variant="secondary"
                >
                  {hookTitleSaving ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Сохранение...
                    </>
                  ) : (
                    'Сохранить'
                  )}
                </Button>
              </div>
            ) : (
              <span>{hookTitle || 'не сгенерирован'}</span>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold mb-2">Текст</h2>
          {highlightedText ? (
            <div
              className="prose max-w-none whitespace-pre-wrap break-words text-gray-900"
              dangerouslySetInnerHTML={{ __html: highlightedText }}
            />
          ) : (
            <p className="text-gray-500">Текст не добавлен</p>
          )}
        </div>

        {post.wordstat_phrases_used && post.wordstat_phrases_used.length > 0 && (
          <div className="rounded-lg border bg-white/60 p-4">
            <p className="text-sm font-semibold">Фразы Wordstat, использованные в тексте</p>
            <p className="text-sm text-muted-foreground mt-1">
              {post.wordstat_phrases_used.join(' • ')}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div>
          <div className="flex flex-wrap gap-3">
            {/* Image generation */}
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={imageGenerationDisabled}
                  variant="secondary"
                  onClick={handleGenerateImage}
                  title={paidFeatureHoverLabel}
                  className={[
                    imageGenerationLoading ? 'animate-pulse' : '',
                    'group disabled:pointer-events-auto',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {imageGenerationLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  <span className="group-hover:hidden">Изображение</span>
                  <span className="hidden group-hover:inline">{paidFeatureHoverLabel}</span>
                </Button>
              </div>
              {isImageOnCooldown && showImageCooldownMessage && (
                <p className="text-xs text-muted-foreground">
                  Повторная генерация изображения будет доступна через {imageCooldownLabel}.
                </p>
              )}
            </div>

            {/* Video generation button */}
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={videoGenerationDisabled}
                  variant={isMediaFeatureLocked ? 'secondary' : 'default'}
                  onClick={() => handleGenerateVideo()}
                  title={paidFeatureHoverLabel}
                  className="group disabled:pointer-events-auto"
                >
                  <span className="group-hover:hidden">Видео по фото</span>
                  <span className="hidden group-hover:inline">{paidFeatureHoverLabel}</span>
                </Button>
                <Button
                  disabled={videoFromTextDisabled}
                  variant={isMediaFeatureLocked ? 'secondary' : 'default'}
                  onClick={() => handleGenerateVideo({ source: 'text', method: 'veo' })}
                  title={paidFeatureHoverLabel}
                  className="group disabled:pointer-events-auto"
                >
                  <span className="group-hover:hidden">Видео по тексту</span>
                  <span className="hidden group-hover:inline">{paidFeatureHoverLabel}</span>
                </Button>
              </div>
              {isVideoOnCooldown && showVideoCooldownMessage && (
                <p className="text-xs text-muted-foreground">
                  Повторная генерация видео будет доступна через {videoCooldownLabel}.
                </p>
              )}
            </div>

            {/* Regenerate text */}
            <Button disabled={!canEdit || loading} variant="outline" onClick={handleRegenerateText}>
              Перегенерировать текст
            </Button>
          </div>
          {!MEDIA_FEATURES_AVAILABLE && (
            <p className="mt-2 text-sm text-muted-foreground">
              Изображения и видео не доступны в пробном доступе
            </p>
          )}
        </div>

        {/* Schedules */}
        <div className="rounded-lg border bg-background p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Запланированные публикации</h2>
              <p className="text-sm text-muted-foreground">
                Управляйте расписанием и отправляйте посты в соцсети по графику
              </p>
            </div>
            {canEdit && (
              <SchedulePostDialog
                postId={postId}
                disabled={loading}
                onScheduled={refreshSchedulesAndPost}
              />
            )}
          </div>
          <div className="mt-4 space-y-3">
            {schedulesLoading && (
              <p className="text-sm text-muted-foreground">Загрузка расписания...</p>
            )}
            {!schedulesLoading && schedules.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Запланированных публикаций для этого поста нет.
              </p>
            )}
            {!schedulesLoading && schedules.length > 0 && (
              <div className="space-y-3">
                {schedules.map((schedule) => (
                  <div
                    key={schedule.id}
                    className="flex flex-col gap-3 rounded-lg border bg-white/50 p-3 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <p className="font-medium">
                        {new Date(schedule.scheduled_at).toLocaleString('ru-RU', {
                          day: 'numeric',
                          month: 'long',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {schedule.social_account_name || 'Аккаунт'} • {schedule.platform}
                      </p>
                    </div>
                    <div className="flex flex-col gap-2 md:flex-row md:items-center">
                      <Badge className={SCHEDULE_STATUS_STYLES[schedule.status] || ''}>
                        {SCHEDULE_STATUS_LABELS[schedule.status] || schedule.status}
                      </Badge>
                      {schedule.status === 'pending' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handlePublishScheduleNow(schedule.id)}
                        >
                          Опубликовать сейчас
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Image gallery */}
        {(images.length > 0 || imageGenerationLoading) && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Изображения</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {imageGenerationLoading && (
                <div className="rounded-lg border bg-background p-2 shadow-sm">
                  <div className="aspect-square bg-gray-100 rounded-md flex items-center justify-center">
                    <div className="text-center">
                      <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-gray-400" />
                      <p className="text-sm text-gray-500">Генерация изображения...</p>
                    </div>
                  </div>
                </div>
              )}
              {images.map((image) => {
                const aspectRatio = image.width && image.height ? image.width / image.height : 4 / 3;
                const clampedRatio = Math.max(0.5, Math.min(2.0, aspectRatio));

                return (
                  <div key={image.id} className="rounded-lg border bg-background p-2 shadow-sm relative group">
                    <div
                      className="w-full overflow-hidden rounded-md"
                      style={{ aspectRatio: `${clampedRatio}` }}
                    >
                      <img
                        src={resolveMediaUrl(image.image)}
                        alt={image.alt_text || post.title || `Изображение ${image.id}`}
                        className="w-full h-full object-contain cursor-pointer"
                        onClick={() => handleImageClick(image)}
                      />
                    </div>
                  {canEdit && (
                    <div className="absolute top-2 right-2">
                      {/* Delete confirmation menu */}
                      {imageToDelete === image.id && (
                        <div className="absolute top-full right-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-10 p-2 min-w-[120px]">
                          <p className="text-sm font-medium mb-2 text-gray-700">Удалить?</p>
                          <div className="flex gap-1">
                            <Button
                              variant="destructive"
                              size="sm"
                              className="flex-1 text-xs"
                              onClick={handleConfirmDelete}
                            >
                              Да
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="flex-1 text-xs"
                              onClick={handleCancelDelete}
                            >
                              Нет
                            </Button>
                          </div>
                        </div>
                      )}

                      {/* Trash button */}
                      <Button
                        variant="destructive"
                        size="sm"
                        className={`opacity-0 group-hover:opacity-100 transition-opacity ${
                          imageToDelete === image.id ? 'opacity-100' : ''
                        }`}
                        onClick={() => handleShowDeleteMenu(image.id)}
                        title="Удалить изображение"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                  {image.alt_text && (
                    <p className="mt-2 text-sm text-muted-foreground">{image.alt_text}</p>
                  )}
                </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Image modal */}
        <Dialog open={!!selectedImage} onOpenChange={() => setSelectedImage(null)}>
          <DialogContent className="max-w-[95vw] w-[95vw] p-0">
            <VisuallyHidden>
              <DialogTitle>Просмотр изображения</DialogTitle>
              <DialogDescription>
                {selectedImage?.alt || 'Предпросмотр выбранного изображения поста'}
              </DialogDescription>
            </VisuallyHidden>
            {selectedImage && (
              <div className="relative">
                <img
                  src={selectedImage.src}
                  alt={selectedImage.alt}
                  className="w-full h-auto max-h-[90vh] object-contain"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  className="absolute top-2 right-2"
                  onClick={() => setSelectedImage(null)}
                >
                  ✕
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Video gallery */}
        {(videos.length > 0 || loading) && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Видео</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {loading && (
                <div className="rounded-lg border bg-background p-2 shadow-sm">
                  <div className="aspect-video bg-gray-900 rounded-md flex items-center justify-center">
                    <div className="text-center">
                      <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2 text-gray-400" />
                      <p className="text-sm text-gray-400">Генерация видео...</p>
                    </div>
                  </div>
                </div>
              )}
              {videos.map((video) => {
                const aspectRatio = videoAspectRatios[video.id] ?? 16 / 9;

                return (
                  <div key={video.id} className="rounded-lg border bg-background p-2 shadow-sm relative group">
                    <div
                      className="w-full overflow-hidden rounded-md bg-black"
                      style={{ aspectRatio: `${aspectRatio}` }}
                    >
                      <video
                        src={resolveMediaUrl(video.video)}
                        controls
                        className="w-full h-full object-contain"
                        onLoadedMetadata={(event) => handleVideoMetadataLoaded(video.id, event)}
                      />
                    </div>
                    {canEdit && (
                      <div className="absolute top-2 right-2">
                        {/* Delete confirmation menu */}
                        {videoToDelete === video.id && (
                          <div className="absolute top-full right-0 mt-1 bg-white border border-gray-200 rounded-md shadow-lg z-10 p-2 min-w-[120px]">
                            <p className="text-sm font-medium mb-2 text-gray-700">Удалить?</p>
                            <div className="flex gap-1">
                              <Button
                                variant="destructive"
                                size="sm"
                                className="flex-1 text-xs"
                                onClick={handleConfirmVideoDelete}
                              >
                                Да
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                className="flex-1 text-xs"
                                onClick={handleCancelVideoDelete}
                              >
                                Нет
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* Trash button */}
                        <Button
                          variant="destructive"
                          size="sm"
                          className={`opacity-0 group-hover:opacity-100 transition-opacity ${
                            videoToDelete === video.id ? 'opacity-100' : ''
                          }`}
                          onClick={() => handleShowVideoDeleteMenu(video.id)}
                          title="Удалить видео"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="mt-6 flex flex-col gap-3 rounded-lg border bg-background p-4 sm:flex-row sm:items-center sm:justify-between">
          {adjacentPostIds.prev ? (
            <Button variant="outline" className="w-full sm:w-auto" asChild>
              <Link href={`/posts/${adjacentPostIds.prev}`} className="flex items-center gap-2">
                <ChevronLeft className="h-4 w-4" />
                Предыдущий пост
              </Link>
            </Button>
          ) : (
            <Button variant="outline" className="w-full sm:w-auto" disabled>
              <ChevronLeft className="h-4 w-4" />
              Предыдущий пост
            </Button>
          )}

          {adjacentPostIds.next ? (
            <Button variant="outline" className="w-full sm:w-auto justify-end" asChild>
              <Link href={`/posts/${adjacentPostIds.next}`} className="flex items-center gap-2">
                Следующий пост
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          ) : (
            <Button variant="outline" className="w-full sm:w-auto justify-end" disabled>
              Следующий пост
              <ChevronRight className="h-4 w-4" />
            </Button>
          )}
        </div>

        <div className="text-sm text-gray-500 space-y-1">
          {post.created_at && (
            <p>Создан: {new Date(post.created_at).toLocaleString('ru-RU')}</p>
          )}
          {post.scheduled_time && (
            <p>Запланировано на: {new Date(post.scheduled_time).toLocaleString('ru-RU')}</p>
          )}
        </div>
      </div>
    </div>
  );
}
