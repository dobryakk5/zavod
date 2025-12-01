'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { postsApi } from '@/lib/api/posts';
import { PostDetailView } from '@/components/posts/post-detail-view';
import { PostForm } from '@/components/posts/post-form';
import { QuickPublishDialog } from '@/components/posts/quick-publish-dialog';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Edit, Eye, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';
import { useRole } from '@/lib/hooks';
import type { PostDetail } from '@/lib/types';

interface PostPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function PostPage({ params }: PostPageProps) {
  const router = useRouter();
  const { canEdit } = useRole();
  const [isEditing, setIsEditing] = useState(false);
  const [post, setPost] = useState<PostDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [postId, setPostId] = useState<number | null>(null);

  useEffect(() => {
    params.then((p) => setPostId(parseInt(p.id)));
  }, [params]);

  useEffect(() => {
    if (postId !== null) {
      loadPost();
    }
  }, [postId]);

  const loadPost = async () => {
    if (postId === null) return;
    try {
      const data = await postsApi.get(postId);
      setPost(data);
    } catch (error) {
      toast.error('Не удалось загрузить пост');
    }
  };

  const handleSubmit = async (data: any) => {
    if (postId === null) return;
    setLoading(true);
    try {
      await postsApi.update(postId, data);
      toast.success('Пост успешно обновлен');
      setIsEditing(false);
      await loadPost();
    } catch (error) {
      toast.error('Ошибка при обновлении поста');
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (postId === null) return;
    if (!confirm('Вы уверены, что хотите удалить этот пост?')) {
      return;
    }

    try {
      await postsApi.delete(postId);
      toast.success('Пост успешно удален');
      router.push('/posts');
    } catch (error) {
      toast.error('Ошибка при удалении поста');
    }
  };

  return (
    <div className="container max-w-4xl mx-auto py-8">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/posts">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к постам
          </Button>
        </Link>

        {post && canEdit && postId !== null && (
          <div className="flex gap-2">
            {!isEditing && (
              <>
                <QuickPublishDialog postId={postId} />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(true)}
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Редактировать
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDelete}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Удалить
                </Button>
              </>
            )}
            {isEditing && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(false)}
              >
                <Eye className="h-4 w-4 mr-2" />
                Просмотр
              </Button>
            )}
          </div>
        )}
      </div>

      {isEditing && post ? (
        <div>
          <div className="mb-8">
            <h1 className="text-3xl font-bold">Редактировать пост</h1>
            <p className="text-gray-500 mt-2">
              Обновите информацию о посте
            </p>
          </div>
          <PostForm post={post} onSubmit={handleSubmit} loading={loading} />
        </div>
      ) : (
        postId !== null && <PostDetailView postId={postId} />
      )}
    </div>
  );
}
