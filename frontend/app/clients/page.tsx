'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar } from 'lucide-react';
import { crmContactsApi, crmEventsApi } from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { DEFAULT_TENANT_TIMEZONE, formatInTenantTimezone, normalizeTenantTimezone } from '@/lib/timezone';
import { ClientsTab } from '../products/clients-tab';
import { CategoriesTab } from '../products/categories-tab';
import ScheduleTasksView from '../schedule/tasks-view';
import NewClientsEditor from './new/new-clients-editor';
import ClientsSchedule from './clients-schedule';

type ClientsStats = {
  upcomingEvents: number;
  nextEvents: Array<{
    id: number;
    title: string;
    start_time: string;
    contactName: string;
    contactId: number;
  }>;
};

const emptyStats: ClientsStats = {
  upcomingEvents: 0,
  nextEvents: [],
};

function formatEventTime(value: string, timeZone: string) {
  return formatInTenantTimezone(value, timeZone, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ClientsPage() {
  const [stats, setStats] = useState<ClientsStats>(emptyStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [tenantTimezone, setTenantTimezone] = useState(DEFAULT_TENANT_TIMEZONE);

  useEffect(() => {
    let isActive = true;

    const loadStats = async () => {
      setStatsLoading(true);
      setStatsError(null);

      try {
        const [contacts, events, settings] = await Promise.all([
          crmContactsApi.list(),
          crmEventsApi.list(),
          clientApi.getSettings(),
        ]);

        if (!isActive) return;

        setTenantTimezone(normalizeTenantTimezone(settings.timezone));
        const now = new Date();

        const contactsById = new Map(contacts.map((contact) => [contact.id, contact.name]));
        const upcomingEventsSorted = events
          .filter((event) => {
            if (event.status !== 'scheduled') return false;
            const startDate = new Date(event.start_time);
            return !Number.isNaN(startDate.getTime()) && startDate >= now;
          })
          .sort((a, b) => {
            const aTime = new Date(a.start_time).getTime();
            const bTime = new Date(b.start_time).getTime();
            return aTime - bTime;
          });
        const nextEvents = upcomingEventsSorted.slice(0, 2).map((event) => ({
          id: event.id,
          title: event.title || 'Встреча',
          start_time: event.start_time,
          contactName: contactsById.get(event.contact_id) || `Клиент #${event.contact_id}`,
          contactId: event.contact_id,
        }));

        setStats({
          upcomingEvents: nextEvents.length,
          nextEvents,
        });
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load CRM stats', err);
        setStatsError('Не удалось загрузить статистику CRM.');
      } finally {
        if (isActive) {
          setStatsLoading(false);
        }
      }
    };

    void loadStats();

    return () => {
      isActive = false;
    };
  }, []);

  const displayStats = useMemo(() => {
    if (statsLoading || statsError) {
      return {
        totalClients: null,
        upcomingEvents: null,
        nextEvents: [],
      };
    }

    return {
      upcomingEvents: stats.upcomingEvents,
      nextEvents: stats.nextEvents,
    };
  }, [stats, statsError, statsLoading]);

  return (
    <div className="container mx-auto py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Управление клиентами</h1>
        <p className="text-muted-foreground mt-2">
          Управление клиентами, расписанием и платежами
        </p>
        {statsError && (
          <p className="text-sm text-red-500 mt-2">{statsError}</p>
        )}
      </div>

      <div className="mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Ближайшие встречи</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {displayStats.nextEvents.length > 0 && (
              <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                {displayStats.nextEvents.map((event) => (
                  <div key={event.id}>
                    {formatEventTime(event.start_time, tenantTimezone)} · {event.title} ·{' '}
                    <Link
                      href={`/contact/${event.contactId}`}
                      className="text-blue-600 hover:underline"
                    >
                      {event.contactName}
                    </Link>
                  </div>
                ))}
              </div>
            )}
            {displayStats.nextEvents.length === 0 && (
              <p className="text-xs text-muted-foreground">Нет запланированных встреч</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="schedule">Расписание</TabsTrigger>
          <TabsTrigger value="service-level">Уровень сервиса</TabsTrigger>
          <TabsTrigger value="categories">Теги</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
        </TabsList>

        <TabsContent value="clients" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <ClientsTab />
          </div>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-6">
          <div className="bg-white rounded-lg">
            <ClientsSchedule />
          </div>
        </TabsContent>

        <TabsContent value="service-level" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <ScheduleTasksView />
          </div>
        </TabsContent>

        <TabsContent value="categories" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <CategoriesTab />
          </div>
        </TabsContent>

        <TabsContent value="payments" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <NewClientsEditor activeTab="payments" />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
