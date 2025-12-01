import { Suspense } from 'react';
import { PostsTable } from '@/components/posts/posts-table';

export default function PostsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Посты</h1>
      <Suspense fallback={<div>Загрузка...</div>}>
        <PostsTable />
      </Suspense>
    </div>
  );
}
