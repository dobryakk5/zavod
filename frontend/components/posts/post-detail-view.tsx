'use client';

import { useState, useEffect } from 'react';
import { postsApi } from '@/lib/api/posts';
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import type { GenerateVideoRequest, PostDetail } from '@/lib/types';
import { toast } from 'sonner';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  ready: 'Готово',
  approved: 'Утверждено',
  scheduled: 'Запланировано',
  published: 'Опубликовано',
};

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api').replace(/\/api\/?$/, '/');

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

  useEffect(() => {
    const loadPost = async () => {
      try {
        const data = await postsApi.get(postId);
        setPost(data);
      } catch (err) {
        setError('Не удалось загрузить пост');
        toast.error('Ошибка загрузки поста');
      }
    };

    loadPost();
  }, [postId]);

  const handleGenerateImage = async (model: 'pollinations' | 'nanobanana' | 'huggingface' | 'flux2' | 'sora_images') => {
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
        <div className="flex flex-wrap gap-3">
          {/* Image generation dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button disabled={!canEdit || loading} variant="default">
                Сгенерировать изображение
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => handleGenerateImage('pollinations')}>
                Pollinations AI
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleGenerateImage('nanobanana')}>
                Google Gemini (NanoBanana)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleGenerateImage('huggingface')}>
                HuggingFace FLUX.1
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleGenerateImage('flux2')}>
                FLUX.2
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleGenerateImage('sora_images')}>
                SORA Images
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Video generation button */}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={!canEdit || !canGenerateVideo || loading}
              variant={canGenerateVideo ? 'default' : 'secondary'}
              onClick={() => handleGenerateVideo()}
            >
              {canGenerateVideo ? 'Видео по изображению' : 'Сгенерировать видео (только dev)'}
            </Button>
            <Button
              disabled={!canEdit || !canGenerateVideo || loading || !post.text}
              variant={canGenerateVideo ? 'outline' : 'secondary'}
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
