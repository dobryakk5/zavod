'use client';

import { useState, useEffect } from 'react';
import { postsApi } from '@/lib/api/posts';
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import type { PostDetail } from '@/lib/types';
import { toast } from 'sonner';

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

  const handleGenerateImage = async (model: 'pollinations' | 'nanobanana' | 'huggingface' | 'flux2') => {
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

  const handleGenerateVideo = async () => {
    setLoading(true);
    try {
      await postsApi.generateVideo(postId);
      toast.success('Генерация видео запущена');
      // Reload post after a delay to show the new video
      setTimeout(async () => {
        const updatedPost = await postsApi.get(postId);
        setPost(updatedPost);
      }, 5000);
    } catch (err) {
      toast.error('Ошибка при генерации видео');
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{post.title || `Пост #${post.id}`}</h1>
          <div className="flex gap-2 mt-2">
            <Badge>{post.status}</Badge>
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
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Video generation button */}
          <Button
            disabled={!canEdit || !canGenerateVideo || loading}
            variant={canGenerateVideo ? 'default' : 'secondary'}
            onClick={handleGenerateVideo}
          >
            {canGenerateVideo ? 'Сгенерировать видео' : 'Сгенерировать видео (только dev)'}
          </Button>

          {/* Regenerate text */}
          <Button disabled={!canEdit || loading} variant="outline" onClick={handleRegenerateText}>
            Перегенерировать текст
          </Button>
        </div>

        {/* Image preview */}
        {post.image && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Изображение</h2>
            <img src={post.image} alt={post.title || 'Post image'} className="max-w-2xl rounded-lg shadow-md" />
          </div>
        )}

        {/* Video preview */}
        {post.video && (
          <div>
            <h2 className="text-lg font-semibold mb-2">Видео</h2>
            <video src={post.video} controls className="max-w-2xl rounded-lg shadow-md" />
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
