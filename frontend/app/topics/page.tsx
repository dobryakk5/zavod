'use client';

import { TopicsList } from '@/components/topics/topics-list';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';
import Link from 'next/link';
import { useRole } from '@/lib/hooks';

export default function TopicsPage() {
  const { canEdit } = useRole();

  return (
    <div className="container mx-auto py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Темы</h1>
          <p className="text-gray-500 mt-2">
            Управляйте темами для генерации контента
          </p>
        </div>
        {canEdit && (
          <Link href="/topics/new">
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Создать тему
            </Button>
          </Link>
        )}
      </div>

      <TopicsList />
    </div>
  );
}
