'use client';

import { useRouter } from 'next/navigation';
import { postsApi } from '@/lib/api/posts';
import { PostForm } from '@/components/posts/post-form';
import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import Link from 'next/link';

export default function NewPostPage() {
  const router = useRouter();

  const handleSubmit = async (data: any) => {
    try {
      const post = await postsApi.create(data);
      toast.success('Пост успешно создан');
      router.push(`/posts/${post.id}`);
    } catch (error) {
      toast.error('Ошибка при создании поста');
      throw error;
    }
  };

  return (
    <div className="container max-w-4xl mx-auto py-8">
      <div className="mb-6">
        <Link href="/posts">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к постам
          </Button>
        </Link>
      </div>

      <div className="mb-8">
        <h1 className="text-3xl font-bold">Создать новый пост</h1>
        <p className="text-gray-500 mt-2">
          Заполните форму для создания нового поста
        </p>
      </div>

      <PostForm onSubmit={handleSubmit} />
    </div>
  );
}
