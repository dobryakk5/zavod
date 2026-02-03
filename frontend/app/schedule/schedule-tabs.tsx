'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ContentCalendarPage from './calendar';
import ScheduleListView from './list-view';

type ScheduleTabsProps = {
  showTitle?: boolean;
};

export default function ScheduleTabs({ showTitle = true }: ScheduleTabsProps) {
  const [activeTab, setActiveTab] = useState('calendar');

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex items-center justify-between mb-4">
          {showTitle ? (
            <h1 className="text-2xl font-semibold">Расписание публикаций</h1>
          ) : (
            <span />
          )}
          <TabsList>
            <TabsTrigger value="calendar">Календарь</TabsTrigger>
            <TabsTrigger value="list">Список</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="calendar" className="mt-0">
          <ContentCalendarPage />
        </TabsContent>

        <TabsContent value="list" className="mt-0">
          <ScheduleListView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
