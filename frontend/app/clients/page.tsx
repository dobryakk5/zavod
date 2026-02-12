'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar } from 'lucide-react';
import { crmContactsApi, crmEventsApi } from '@/lib/api/crm';
import { clientApi } from '@/lib/api/client';
import { chainsApi, type ChainCatalogItem } from '@/lib/api/chains';
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
  const [chatbotChains, setChatbotChains] = useState<ChainCatalogItem[]>([]);
  const [chatbotChainsLoading, setChatbotChainsLoading] = useState(true);
  const [chatbotChainsError, setChatbotChainsError] = useState<string | null>(null);

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
        const nextEvents = upcomingEventsSorted.slice(0, 1).map((event) => ({
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

  useEffect(() => {
    let isActive = true;

    const loadChatbotChains = async () => {
      setChatbotChainsLoading(true);
      setChatbotChainsError(null);
      try {
        const items = await chainsApi.list();
        if (!isActive) return;
        setChatbotChains(items);
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load chatbot chains', err);
        setChatbotChainsError('Не удалось загрузить список цепочек.');
      } finally {
        if (isActive) {
          setChatbotChainsLoading(false);
        }
      }
    };

    void loadChatbotChains();

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
        <div className="rounded-lg bg-transparent">
          <div className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {displayStats.nextEvents.length > 0 && (
              <div>
                Ближайшая встреча:{' '}
                {formatEventTime(displayStats.nextEvents[0].start_time, tenantTimezone)} ·{' '}
                {displayStats.nextEvents[0].title} ·{' '}
                <Link
                  href={`/contact/${displayStats.nextEvents[0].contactId}`}
                  className="text-blue-600 hover:underline"
                >
                  {displayStats.nextEvents[0].contactName}
                </Link>
              </div>
            )}
            {displayStats.nextEvents.length === 0 && (
              <div>Ближайшая встреча: Нет запланированных встреч</div>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="schedule">Расписание</TabsTrigger>
          <TabsTrigger value="service-level">Уровень сервиса</TabsTrigger>
          <TabsTrigger value="categories">Теги</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
          <TabsTrigger value="welcome-chain">ChatBot</TabsTrigger>
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

        <TabsContent value="welcome-chain" className="space-y-6">
          <div className="bg-white rounded-lg p-6 space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Цепочки ChatBot</h2>
              <p className="text-sm text-muted-foreground mt-1">
                Выберите цепочку и откройте отдельную страницу редактора.
              </p>
            </div>

            {chatbotChainsLoading && (
              <p className="text-sm text-muted-foreground">Загрузка цепочек...</p>
            )}

            {chatbotChainsError && (
              <p className="text-sm text-red-500">{chatbotChainsError}</p>
            )}

            {!chatbotChainsLoading && !chatbotChainsError && (
              <div className="space-y-3">
                {chatbotChains.map((chain) => (
                  <Link
                    key={chain.id}
                    href={`/clients/chatbot/${chain.id}`}
                    className="block rounded-lg border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div>
                      <div className="font-medium text-slate-900">{chain.title}</div>
                      <div className="text-xs text-slate-500 mt-1">
                        ID: {chain.id} · Статус: {chain.status}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
