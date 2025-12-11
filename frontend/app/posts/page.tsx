import { Suspense } from 'react';
import { PostsTable } from '@/components/posts/posts-table';
import { WeeklyPlanTable } from '@/components/posts/weekly-plan-table';

export default function PostsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Посты</h1>
      <WeeklyPlanTable />
      <Suspense fallback={<div>Загрузка...</div>}>
        <PostsTable />
      </Suspense>
    </div>
  );
}
