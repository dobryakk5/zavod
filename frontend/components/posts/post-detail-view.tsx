'use client';

import { useState, useEffect, useCallback } from 'react';
import { postsApi } from '@/lib/api/posts';
import { schedulesApi } from '@/lib/api/schedules';
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { GenerateVideoRequest, PostDetail, Schedule } from '@/lib/types';
import { toast } from 'sonner';
import { SchedulePostDialog } from './schedule-post-dialog';

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
const MEDIA_FEATURES_AVAILABLE = false;

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

interface PostDetailViewProps {
  postId: number;
}

export function PostDetailView({ postId }: PostDetailViewProps) {
  const { canEdit } = useRole();
  const { canGenerateVideo } = useCanGenerateVideo();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);

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

  const refreshSchedulesAndPost = useCallback(async () => {
    await loadSchedules();
    try {
      const updatedPost = await postsApi.get(postId);
      setPost(updatedPost);
    } catch {
      // swallowing error to avoid duplicate toasts for background refresh
    }
  }, [loadSchedules, postId]);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  const handleGenerateImage = async (model: 'openrouter' | 'veo_photo') => {
    setLoading(true);
    try {
      await postsApi.generateImage(postId, model);
      toast.success('Генерация изображения запущена');
      // Reload post after a delay to show the new image
      setTimeout(async () => {
        const updatedPost = await postsApi.get(postId);
        setPost(updatedPost);
      }, 3000);
    } catch (err) {
      toast.error('Ошибка при генерации изображения');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateVideo = async (options?: GenerateVideoRequest) => {
    setLoading(true);
    try {
      await postsApi.generateVideo(postId, options);
      const isTextVideo = options?.source === 'text';
      toast.success(isTextVideo ? 'Генерация видео по тексту запущена' : 'Генерация видео запущена');
      // Reload post after a delay to show the new video
      setTimeout(async () => {
        const updatedPost = await postsApi.get(postId);
        setPost(updatedPost);
      }, options?.source === 'text' ? 6000 : 5000);
    } catch (err) {
      toast.error(options?.source === 'text' ? 'Ошибка при генерации видео по тексту' : 'Ошибка при генерации видео');
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
      await schedulesApi.publishNow(scheduleId);
      toast.success('Публикация запущена');
      await refreshSchedulesAndPost();
    } catch (err) {
      toast.error('Не удалось запустить публикацию');
    }
  };

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  if (!post) {
    return <div>Загрузка...</div>;
  }

  const statusLabel = STATUS_LABELS[post.status] ?? post.status;
  const postTypeLabel = formatPostTypeLabel(post.template_type);
  const images = post.images ?? [];
  const videos = post.videos ?? [];
  const imageGenerationDisabled = !canEdit || loading || !MEDIA_FEATURES_AVAILABLE;
  const videoGenerationDisabled = !canEdit || loading || !MEDIA_FEATURES_AVAILABLE || !canGenerateVideo;
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
        </div>
      </div>

      {/* Content */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold mb-2">Текст</h2>
          <p className="whitespace-pre-wrap">{post.text || 'Текст не добавлен'}</p>
        </div>

        {/* Action Buttons */}
        <div>
          <div className="flex flex-wrap gap-3">
            {/* Image generation */}
            <div className="flex flex-wrap gap-2">
              <Button disabled={imageGenerationDisabled} variant="default" onClick={() => handleGenerateImage('openrouter')}>
                Изображение
              </Button>
              <Button disabled={imageGenerationDisabled} variant="outline" onClick={() => handleGenerateImage('veo_photo')}>
                VEO фото
              </Button>
            </div>

            {/* Video generation button */}
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={videoGenerationDisabled}
                variant={MEDIA_FEATURES_AVAILABLE && canGenerateVideo ? 'default' : 'secondary'}
                onClick={() => handleGenerateVideo()}
              >
                {canGenerateVideo ? 'Видео по изображению' : 'Сгенерировать видео (только dev)'}
              </Button>
              <Button
                disabled={videoFromTextDisabled}
                variant={MEDIA_FEATURES_AVAILABLE && canGenerateVideo ? 'outline' : 'secondary'}
                onClick={() => handleGenerateVideo({ source: 'text', method: 'veo' })}
                title={!post.text ? 'Добавьте текст в пост, чтобы сгенерировать видео по тексту' : undefined}
              >
                Видео по тексту (VEO)
              </Button>
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
        {images.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Изображения</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              {images.map((image) => (
                <div key={image.id} className="rounded-lg border bg-background p-2 shadow-sm">
                  <img
                    src={resolveMediaUrl(image.image)}
                    alt={image.alt_text || post.title || `Изображение ${image.id}`}
                    className="h-40 w-full rounded-md object-cover"
                  />
                  {image.alt_text && (
                    <p className="mt-2 text-sm text-muted-foreground">{image.alt_text}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Video gallery */}
        {videos.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Видео</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {videos.map((video) => (
                <div key={video.id} className="rounded-lg border bg-background p-2 shadow-sm">
                  <video
                    src={resolveMediaUrl(video.video)}
                    controls
                    className="w-full rounded-md object-contain max-h-[60vh] bg-black"
                  />
                  {video.caption && (
                    <p className="mt-2 text-sm text-muted-foreground">{video.caption}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
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
