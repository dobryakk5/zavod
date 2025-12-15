'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { postsApi } from '@/lib/api/posts';
import { schedulesApi } from '@/lib/api/schedules';
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { VisuallyHidden } from '@/components/ui/visually-hidden';
import type { GenerateVideoRequest, PostDetail, Schedule } from '@/lib/types';
import { toast } from 'sonner';
import { SchedulePostDialog } from './schedule-post-dialog';
import { Trash2, Loader2 } from 'lucide-react';

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
  const [imageGenerationLoading, setImageGenerationLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imageGenerationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [selectedImage, setSelectedImage] = useState<{ src: string; alt: string } | null>(null);
  const [imageToDelete, setImageToDelete] = useState<number | null>(null);
  const [videoToDelete, setVideoToDelete] = useState<number | null>(null);

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
      toast.error('Ошибка при генерации изображения');
      stopImageGenerationPolling();
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

  const handleImageClick = (image: { image: string; alt_text?: string; id: number }) => {
    setSelectedImage({
      src: resolveMediaUrl(image.image),
      alt: image.alt_text || post.title || `Изображение ${image.id}`
    });
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
  const imageGenerationDisabled = !canEdit || imageGenerationLoading || !MEDIA_FEATURES_AVAILABLE;
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
              <Button
                disabled={imageGenerationDisabled}
                variant="default"
                onClick={handleGenerateImage}
                className={imageGenerationLoading ? 'animate-pulse' : ''}
              >
                {imageGenerationLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Изображение
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
                <div key={image.id} className="rounded-lg border bg-background p-2 shadow-sm relative group">
                  <img
                    src={resolveMediaUrl(image.image)}
                    alt={image.alt_text || post.title || `Изображение ${image.id}`}
                    className="h-40 w-full rounded-md object-cover cursor-pointer"
                    onClick={() => handleImageClick(image)}
                  />
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
              ))}
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
        {videos.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Видео</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {videos.map((video) => (
                <div key={video.id} className="rounded-lg border bg-background p-2 shadow-sm relative group">
                  <video
                    src={resolveMediaUrl(video.video)}
                    controls
                    className="w-full rounded-md object-contain max-h-[60vh] bg-black"
                  />
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
