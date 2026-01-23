import { Suspense } from 'react';
import { PostsTable } from '@/components/posts/posts-table';
import { WeeklyPlanTable } from '@/components/posts/weekly-plan-table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ContentStrategyTab } from './content-strategy-tab';

export default function PostsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Посты</h1>
      <Tabs defaultValue="posts" className="space-y-6">
        <TabsList>
          <TabsTrigger value="posts">Посты</TabsTrigger>
          <TabsTrigger value="strategy">Контент стратегия</TabsTrigger>
        </TabsList>
        <TabsContent value="posts" className="space-y-4">
          <WeeklyPlanTable />
          <Suspense fallback={<div>Загрузка...</div>}>
            <PostsTable />
          </Suspense>
        </TabsContent>
        <TabsContent value="strategy">
          <ContentStrategyTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
